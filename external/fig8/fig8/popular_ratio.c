/*
 * Miss ratio and "popular object ratio" (paper §5.3, Figure 8b) of one eviction algorithm at
 * one cache size, using libCacheSim's own algorithms.
 *
 * Popular object ratio: with cache size C (objects), the popular objects H are the C most
 * frequent objects of the whole trace (ties broken by smaller object id, which in the authors'
 * Zipf generator is the more popular rank). At time t, I_t = |H ∩ A_t| / C, A_t = cache contents.
 * The paper plots one value per cache size and does not say at which t, so this prints
 *   at_end     I_t after the last request
 *   mean_all   the mean of I_t over samples every <interval> requests, whole trace
 *   mean_half  the same over the second half of the trace (after warm-up)
 *
 * The cache is created with cachesim's own create_cache() (bin/cachesim/cache_init.h), requests
 * are read with cachesim's reader settings (object size ignored, size-0 requests skipped), and
 * each request goes through cache->get(), as in cachesim, so the miss ratio printed equals
 * cachesim's. Membership is checked read-only with hashtable_find() on the cache's hash table,
 * which is what cache_find_base() does without side effects; ARC's ghost entries are not cache
 * contents and are skipped. (cache->find(cache, req, false) is not used: ARC_find dereferences
 * a NULL object when update_cache is false.)
 *
 * usage: popular_ratio <trace.oracleGeneral> <algo: lru|lfu|arc|sieve> <cache size (objects)>
 *                      [interval, default 10000]
 * output: one line "algo cache_size n_req miss_ratio at_end mean_all mean_half
 *                   n_popular_same_as_true_top"
 * (the last field: how many of H are also among object ids 0..C-1, the generator's true top C)
 */
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "libCacheSim/cache.h"
#include "libCacheSim/evictionAlgo.h"
#include "libCacheSim/reader.h"
#include "libCacheSim/request.h"
#include "../external/NSDI24-SIEVE/libCacheSim/libCacheSim/bin/cachesim/cache_init.h"
#include "../external/NSDI24-SIEVE/libCacheSim/libCacheSim/dataStructure/hashtable/hashtable.h"

typedef struct {
  uint64_t id, cnt;
} oc_t;

static int by_cnt_desc(const void *a, const void *b) {
  const oc_t *x = a, *y = b;
  if (x->cnt != y->cnt) return x->cnt > y->cnt ? -1 : 1;
  return x->id < y->id ? -1 : (x->id > y->id);
}

static reader_t *open_reader(const char *path) {
  reader_init_param_t p;
  memset(&p, 0, sizeof(p));
  p.ignore_obj_size = true;
  p.ignore_size_zero_req = true;
  p.obj_id_is_num = true;
  p.cap_at_n_req = -1;
  return open_trace(path, ORACLE_GENERAL_TRACE, &p);
}

int main(int argc, char **argv) {
  if (argc < 4) {
    fprintf(stderr, "usage: %s trace algo cache_size [interval]\n", argv[0]);
    return 2;
  }
  const char *path = argv[1], *algo = argv[2];
  uint64_t C = strtoull(argv[3], NULL, 10);
  uint64_t interval = argc > 4 ? strtoull(argv[4], NULL, 10) : 10000;

  /* pass 1: request count per object (object ids of the Zipf traces are 0..m-1) */
  reader_t *r = open_reader(path);
  request_t *req = new_request();
  uint64_t max_id = 0, n_req = 0, cap = 1 << 20;
  uint64_t *cnt = calloc(cap, sizeof(uint64_t));
  while (read_one_req(r, req) == 0) {
    if (req->obj_id >= cap) {
      uint64_t nc = cap;
      while (req->obj_id >= nc) nc *= 2;
      cnt = realloc(cnt, nc * sizeof(uint64_t));
      memset(cnt + cap, 0, (nc - cap) * sizeof(uint64_t));
      cap = nc;
    }
    cnt[req->obj_id]++;
    if (req->obj_id > max_id) max_id = req->obj_id;
    n_req++;
  }
  close_reader(r);

  /* H = the C most frequent objects */
  uint64_t n_obj = 0;
  oc_t *oc = malloc((max_id + 1) * sizeof(oc_t));
  for (uint64_t i = 0; i <= max_id; i++)
    if (cnt[i]) oc[n_obj++] = (oc_t){i, cnt[i]};
  qsort(oc, n_obj, sizeof(oc_t), by_cnt_desc);
  uint64_t nH = C < n_obj ? C : n_obj, same_as_true = 0;
  request_t **H = malloc(nH * sizeof(request_t *));
  for (uint64_t i = 0; i < nH; i++) {
    H[i] = new_request();
    H[i]->obj_id = oc[i].id;
    H[i]->obj_size = 1;
    if (oc[i].id < C) same_as_true++;
  }

  /* pass 2: simulate, sampling I_t */
  cache_t *cache = create_cache(path, algo, C, NULL, false);
  if (cache == NULL) {
    fprintf(stderr, "unknown algorithm %s\n", algo);
    return 2;
  }
  int is_arc = strcasecmp(algo, "arc") == 0;
  r = open_reader(path);
  uint64_t i = 0, n_miss = 0, n_samp = 0, n_samp2 = 0;
  double sum = 0, sum2 = 0, last = 0;
  while (read_one_req(r, req) == 0) {
    if (!cache->get(cache, req)) n_miss++;
    i++;
    if (i % interval == 0 || i == n_req) {
      uint64_t in = 0;
      for (uint64_t k = 0; k < nH; k++) {
        cache_obj_t *o = hashtable_find(cache->hashtable, H[k]);
        if (o != NULL && !(is_arc && o->ARC.ghost)) in++;
      }
      last = (double)in / C;
      sum += last;
      n_samp++;
      if (i > n_req / 2) {
        sum2 += last;
        n_samp2++;
      }
    }
  }
  close_reader(r);
  printf("%s %" PRIu64 " %" PRIu64 " %.6f %.6f %.6f %.6f %" PRIu64 "\n", algo, C, i,
         (double)n_miss / i, last, sum / n_samp, sum2 / n_samp2, same_as_true);
  return 0;
}
