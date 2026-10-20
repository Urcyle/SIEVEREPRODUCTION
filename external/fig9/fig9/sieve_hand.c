/*
 * Position of SIEVE's hand over time (paper Figure 9c), using libCacheSim's own SIEVE.
 *
 * SIEVE (cache/eviction/Sieve.c) keeps its objects in a queue from q_tail (oldest) to q_head
 * (newest) and its hand in `pointer`. An eviction starts at the hand (at q_tail when the hand is
 * NULL: before the first eviction, or after it passed the head), moves towards the head clearing
 * visited bits, evicts the first unvisited object and leaves the hand at the next object towards
 * the head (NULL if there is none).
 * Hand position from tail = (number of objects between q_tail and the hand) / (objects cached),
 * i.e. 0 at the tail and close to 1 at the head; a NULL hand is at the tail (0).
 *
 * The cache is created with cachesim's create_cache() and every request goes through
 * cache->get(), as in cachesim. Sieve_params_t is private to Sieve.c, so its layout is repeated
 * here (three pointers: q_head, q_tail, pointer).
 *
 * The hand only moves when SIEVE evicts. The paper's curves each end after the same number of
 * misses (about 263,000; at 318 k requests for alpha 0.8 and 520 k for alpha 1.0), so they were
 * recorded for a fixed number of evictions; this tool stops after <evictions> evictions.
 *
 * usage: sieve_hand <trace.oracleGeneral> <cache size (objects)> <evictions>
 *   prints "request position" for request 1 and after every request that caused an eviction,
 *   then "# misses <n> evictions <n> requests <n>"
 */
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "libCacheSim/cache.h"
#include "libCacheSim/evictionAlgo.h"
#include "libCacheSim/reader.h"
#include "libCacheSim/request.h"
#include "../external/fig8/external/NSDI24-SIEVE/libCacheSim/libCacheSim/bin/cachesim/cache_init.h"

typedef struct { /* = Sieve_params_t in cache/eviction/Sieve.c */
  cache_obj_t *q_head;
  cache_obj_t *q_tail;
  cache_obj_t *pointer;
} sieve_params_t;

int main(int argc, char **argv) {
  if (argc < 4) {
    fprintf(stderr, "usage: %s trace cache_size evictions\n", argv[0]);
    return 2;
  }
  uint64_t C = strtoull(argv[2], NULL, 10), e_max = strtoull(argv[3], NULL, 10);

  reader_init_param_t p;
  memset(&p, 0, sizeof(p));
  p.ignore_obj_size = true;
  p.ignore_size_zero_req = true;
  p.obj_id_is_num = true;
  p.cap_at_n_req = -1;
  reader_t *r = open_trace(argv[1], ORACLE_GENERAL_TRACE, &p);
  request_t *req = new_request();
  cache_t *cache = create_cache(argv[1], "sieve", C, NULL, false);
  sieve_params_t *sp = cache->eviction_params;

  uint64_t i = 0, n_miss = 0, n_evict = 0;
  while (n_evict < e_max && read_one_req(r, req) == 0) {
    int64_t n_before = cache->n_obj;
    int evicted = 0;
    if (!cache->get(cache, req)) {
      n_miss++;
      /* a miss in a full cache inserts after evicting one object: the count does not grow */
      evicted = cache->n_obj == n_before;
      n_evict += evicted;
    }
    if (i == 0 || evicted) {
      uint64_t pos = 0, n = 0;
      int found = sp->pointer == NULL;
      for (cache_obj_t *o = sp->q_tail; o != NULL; o = o->queue.prev, n++)
        if (!found && o == sp->pointer) {
          pos = n;
          found = 1;
        }
      printf("%" PRIu64 " %.6f\n", i + 1, n ? (double)pos / n : 0.0);
    }
    i++;
  }
  printf("# misses %" PRIu64 " evictions %" PRIu64 " requests %" PRIu64 "\n", n_miss, n_evict, i);
  close_reader(r);
  return 0;
}
