# SIEVE-G correctness gates (Phase 2)

Run with `tests/gates.sh g1|g2|g4` (G3 below). Traces are generated into `tests/data/` (not in
git). Simulator: the artifact `0861f82` + `patches/NSDI24-SIEVE-build-fix.patch` +
`patches/SIEVE-G.patch` (438 lines: `SieveG.c` 403 lines, and 3 / 6 / 1 lines added to
`evictionAlgo.h`, `cache_init.h`, `CMakeLists.txt`; no other algorithm is changed).

| gate | what | result |
|---|---|---|
| G1 | no ghost equals SIEVE: Zipf α 0.8/1.0/1.2, 10,000 objects, 10 M requests, `sieve,sieveg-0` at 0.1%/1%/10% | **pass**: 9 of 9 miss ratios identical ([g1/g1.log](g1/g1.log)) |
| G2 | every object requested twice, `gap` requests apart, cache 1,000 objects | **expectation not met** (below); kept as specified, not tuned ([g2/g2.log](g2/g2.log)) |
| G3 | 6-request trace A B C A B C, cache 2 objects | **pass**: A, B, C are re-inserted with `freq 1` after being evicted ([g3/g3.log](g3/g3.log)) |
| G4 | baseline unchanged: cluster 13, `fifo,sieve` | **pass**: identical to Phase 0 and to the Figure 3 logs ([g4/g4.log](g4/g4.log)) |

## G2

| gap | FIFO | CLOCK | SIEVE | SIEVE-G 0.5 |
|---|---|---|---|---|
| 10 | 0.5000 | 0.5000 | 0.5000 | 0.5000 |
| 50 | 0.5000 | 0.5000 | 0.5000 | 0.5000 |
| 200 | 0.5000 | 0.5000 | 0.5000 | 0.5000 |
| 800 | 0.5000 | 0.6248 | 0.9992 | 0.9992 |

The plan expected SIEVE near 1.0 for every gap below the cache size, and SIEVE-G clearly below
SIEVE. Neither holds:

1. **SIEVE equals FIFO (0.5) for gaps 10–200.** The hand does not reach a new object before its
   second request when the gap is small, so SIEVE keeps it. SIEVE only fails close to the cache
   size (0.9992 at gap 800, where CLOCK is 0.6248 and FIFO 0.5).
2. **SIEVE-G equals SIEVE, by construction of this trace.** A ghost hit happens on an object's
   second request, which is a miss whatever the ghost does; marking the object visited can only
   help a third request, and this trace has none. In addition there were **no ghost hits at
   all** (`SIEVEG_STATS=1`: 0 of 999,200 insertions at gap 800): SIEVE evicts a new object
   within about 300 requests of inserting it, while a 500-entry ghost (ratio 0.5) only remembers
   the last 500 evictions, so the id has left the ghost by the time the object returns 800
   requests after its first request.

So G2 tests a pattern SIEVE-G cannot improve, and the implementation behaves as designed (G1, G3
show the ghost is neutral when empty and re-inserts evicted ids as visited). The gate was kept as
specified rather than changed to make SIEVE-G look better; the ghost ratio is chosen on the
development clusters (Phase 3), where 0.25, 0.5 and 1.0 are compared.

## G3

`SieveG.c` got a temporary print in `SieveG_insert` and `SieveG_evict` (behind `SIEVEG_DEBUG`),
run on A B C A B C (A = 1, B = 2, C = 3) with a 2-object cache and `sieveg-1.0` (a 2-entry ghost;
with the default 0.5 the ghost holds 1 id and A would have left it before A returns). Output:

```
insert 1 freq 0;  insert 2 freq 0;  evict 1 -> ghost;  insert 3 freq 0;
evict 2 -> ghost;  insert 1 freq 1  (A back, from the ghost);  evict 3 -> ghost;
insert 2 freq 1;  evict 1 -> ghost;  insert 3 freq 1
```

The print was then removed; the source was checked to equal `patches/SIEVE-G.patch` again, and
cachesim rebuilt before G4.
