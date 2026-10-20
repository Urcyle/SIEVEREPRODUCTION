/*
 * B-LRU (LRU that admits an object only from its second request on) for traces too large for
 * cachesim's "lru -a bloom-filter".
 *
 * Why: libCacheSim's "bloom-filter" admissioner (cache/admission/bloomfilter.c) is an exact
 * GHashTable of every object ever seen, never cleared, so its memory grows with the number of
 * unique objects of the trace (Tencent Photo: 529 M objects, > 11 GB) whatever the cache size.
 *
 * What it computes is the same: admit(req) is called on every miss and returns true iff the
 * object was requested before (a hit implies an earlier admitted miss, so every earlier request
 * left the object in the table). This program gets "requested before" without a per-object
 * table, from the oracleGeneral next_access_vtime field (1-based index of the object's next
 * request): scanning forward, request i carries a bit seen[i]; the bit of its next request is
 * set to seen[i] OR (request i is read by the simulator). One bit per request: 2.9 G requests
 * = 365 MB.
 *
 * The cache is plain LRU with the same rules as libCacheSim's cache_get_base + LRU, object size
 * ignored (every object counts 1, cache size in objects):
 *   hit: move to the head;  miss: if admitted, evict from the tail until there is room, insert
 *   at the head;  not admitted: nothing.
 * Requests with object size 0 are skipped, like cachesim's reader (ignore_size_zero_req).
 * Several cache sizes are simulated in one pass.
 *
 * usage: zstd -dc trace.oracleGeneral.zst | blru_bitmap <trace name> <size>[,<size>...]
 * output: one line per size in cachesim's format (name "LRU"), plus a "#" line with exact
 * counts.  build: cc -O2 -o tools/blru_bitmap tools/blru_bitmap.c
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct __attribute__((packed)) {
  uint32_t t;
  uint64_t id;
  uint32_t sz;
  int64_t next;
} rec_t;

typedef struct {
  uint64_t cap, n;
  uint64_t *key;          /* node -> obj id */
  uint32_t *prev, *next;  /* LRU list over nodes; head = most recent */
  uint32_t head, tail, free_top;
  uint32_t *free_list;
  uint64_t mask;          /* hash table (linear probing): slot -> node + 1, 0 = empty */
  uint32_t *slot;
  uint64_t n_req, n_miss;
} lru_t;

#define NIL UINT32_MAX

static inline uint64_t hash64(uint64_t x) {
  x ^= x >> 33; x *= 0xff51afd7ed558ccdULL; x ^= x >> 33; x *= 0xc4ceb9fe1a85ec53ULL;
  return x ^ (x >> 33);
}

static void lru_init(lru_t *c, uint64_t cap) {
  memset(c, 0, sizeof(*c));
  c->cap = cap;
  c->key = malloc(cap * sizeof(uint64_t));
  c->prev = malloc(cap * sizeof(uint32_t));
  c->next = malloc(cap * sizeof(uint32_t));
  c->free_list = malloc(cap * sizeof(uint32_t));
  for (uint64_t i = 0; i < cap; i++) c->free_list[i] = (uint32_t)(cap - 1 - i);
  c->free_top = (uint32_t)cap;
  uint64_t ts = 1;
  while (ts < 2 * cap) ts <<= 1;
  c->mask = ts - 1;
  c->slot = calloc(ts, sizeof(uint32_t));
  c->head = c->tail = NIL;
  if (!c->key || !c->prev || !c->next || !c->free_list || !c->slot) { perror("malloc"); exit(1); }
}

static inline uint64_t find_slot(lru_t *c, uint64_t id) { /* slot holding id, or empty slot */
  uint64_t s = hash64(id) & c->mask;
  while (c->slot[s] && c->key[c->slot[s] - 1] != id) s = (s + 1) & c->mask;
  return s;
}

static void unlink_node(lru_t *c, uint32_t x) {
  if (c->prev[x] != NIL) c->next[c->prev[x]] = c->next[x]; else c->head = c->next[x];
  if (c->next[x] != NIL) c->prev[c->next[x]] = c->prev[x]; else c->tail = c->prev[x];
}

static void push_head(lru_t *c, uint32_t x) {
  c->prev[x] = NIL; c->next[x] = c->head;
  if (c->head != NIL) c->prev[c->head] = x; else c->tail = x;
  c->head = x;
}

static void slot_delete(lru_t *c, uint64_t s) { /* backward-shift deletion */
  uint64_t j = s;
  c->slot[s] = 0;
  for (;;) {
    j = (j + 1) & c->mask;
    if (!c->slot[j]) return;
    uint64_t home = hash64(c->key[c->slot[j] - 1]) & c->mask;
    /* move slot[j] back to s if its home is not in (s, j] cyclically */
    if ((s <= j) ? (home <= s || home > j) : (home <= s && home > j)) {
      c->slot[s] = c->slot[j]; c->slot[j] = 0; s = j;
    }
  }
}

static void lru_get(lru_t *c, uint64_t id, int admit) {
  c->n_req++;
  uint64_t s = find_slot(c, id);
  if (c->slot[s]) { /* hit */
    uint32_t x = c->slot[s] - 1;
    unlink_node(c, x); push_head(c, x);
    return;
  }
  c->n_miss++;
  if (!admit) return;
  if (c->n == c->cap) { /* evict the tail */
    uint32_t v = c->tail;
    unlink_node(c, v);
    slot_delete(c, find_slot(c, c->key[v]));
    c->free_list[c->free_top++] = v;
    c->n--;
    s = find_slot(c, id); /* the table changed */
  }
  uint32_t x = c->free_list[--c->free_top];
  c->key[x] = id;
  c->slot[s] = x + 1;
  push_head(c, x);
  c->n++;
}

int main(int argc, char **argv) {
  if (argc != 3) { fprintf(stderr, "usage: zstd -dc t.zst | %s <name> <size>[,<size>...]\n", argv[0]); return 2; }
  int n_size = 0;
  uint64_t sizes[16];
  for (char *tok = strtok(argv[2], ","); tok && n_size < 16; tok = strtok(NULL, ","))
    sizes[n_size++] = strtoull(tok, NULL, 10);
  lru_t *caches = malloc(n_size * sizeof(lru_t));
  for (int k = 0; k < n_size; k++) lru_init(&caches[k], sizes[k]);

  uint64_t bits_cap = 1ULL << 30; /* grown as needed */
  uint64_t *seen = calloc(bits_cap / 64, sizeof(uint64_t));
  enum { B = 1 << 16 };
  static rec_t buf[B];
  uint64_t i = 0, n_zero = 0;
  size_t got;
  while ((got = fread(buf, sizeof(rec_t), B, stdin)) > 0) {
    for (size_t r = 0; r < got; r++, i++) {
      int was_seen = (seen[i >> 6] >> (i & 63)) & 1;
      int counted = buf[r].sz != 0;
      if (counted) {
        for (int k = 0; k < n_size; k++) lru_get(&caches[k], buf[r].id, was_seen);
      } else {
        n_zero++;
      }
      int64_t nx = buf[r].next; /* 1-based index of the next request, -1 = none */
      if (nx > 0 && (was_seen || counted)) {
        uint64_t j = (uint64_t)nx - 1;
        while (j >= bits_cap) {
          seen = realloc(seen, bits_cap / 4);
          memset(seen + bits_cap / 64, 0, bits_cap / 8);
          bits_cap *= 2;
        }
        seen[j >> 6] |= 1ULL << (j & 63);
      }
    }
    if ((i & ((1ULL << 28) - 1)) < B) fprintf(stderr, "%s: %lu M requests\n", argv[1], (unsigned long)(i / 1000000));
  }
  for (int k = 0; k < n_size; k++) {
    lru_t *c = &caches[k];
    double mr = c->n_req ? (double)c->n_miss / c->n_req : 0;
    printf("result/%s %32s cache size %8lu, %lu req, miss ratio %.4lf, byte miss ratio %.4lf\n",
           argv[1], "LRU", (unsigned long)c->cap, (unsigned long)c->n_req, mr, mr);
    printf("# exact %s cache_size %lu n_req %lu n_miss %lu miss_ratio %.10f zero_size_skipped %lu\n",
           argv[1], (unsigned long)c->cap, (unsigned long)c->n_req, (unsigned long)c->n_miss, mr,
           (unsigned long)n_zero);
  }
  return 0;
}
