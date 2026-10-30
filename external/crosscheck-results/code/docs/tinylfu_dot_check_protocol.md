# Protocol: does the pre-fix TinyLFU reproduce the paper's TinyLFU points in Figure 4? (frozen 2026-10-23, before the new runs)

**Background.** Our TinyLFU (W-TinyLFU in the pinned artifact, which contains upstream fix 759f4ca) differs from the paper's in every Figure 4 comparison, in both this repository and SIEVEREPRODUCTION (23 cells, up to 0.05; `docs/independent_replication_comparison.md`). `docs/tinylfu_provenance_comparison.md` built the artifact with that fix removed (`patches/tinylfu-before-759f4ca.patch`, binary `build/paper-tinylfu`) and found it worse than the pinned TinyLFU on `meta_reag`, but at that time the paper's plotted values were not available, so the comparison with the paper was left open.

**What was seen before this protocol.** The paper's TinyLFU dots for the Meta CDN panel were extracted from the PDF by SIEVEREPRODUCTION (`external_replication/sievereproduction_43fc450/fig4/fig4_paper_values.csv`). Computing the reduction from the two saved `meta_reag` counters with that file shows the pre-fix variant at -0.0385 (0.1% cache) and -0.0224 (10%) against paper dots of -0.0385 and -0.0226 (the pinned TinyLFU gives -0.0342 and -0.0105). So the two `meta_reag` cells are **not blind**.

**Prediction (declared now).** The pre-fix TinyLFU reproduces the paper's TinyLFU dots on the other overlapping public traces too.

**Test.** Pre-fix TinyLFU (`wtinylfu`, `main-cache=SLRU,window-size=0.01`, as in the saved receipts) on the four other traces whose results we hold: `meta_rprn`, `meta_rnha`, `wiki_2019t`, `metakv_trace1_candidate`, at 0.1% and 10%, with the saved capacities, cold start, sizes ignored; 8 new runs. For each of the 10 cells (including `meta_reag`) the reduction from FIFO is compared with the paper's TinyLFU dots of the same dataset and cache size, mapping-free (nearest dot), and with the pinned TinyLFU's reduction.

**Rule.** *Supported* if, on the 8 new cells, the pre-fix variant is within 0.0005 of the nearest paper dot in at least 7 and is closer to it than the pinned TinyLFU in all 8 where the pinned one is farther than 0.0005; otherwise *partly supported* (within 0.002 on at least 6) or *not supported*. Reported as it comes out. A pass shows that a build without that fix matches the paper's TinyLFU points, not that the paper used it.

## Outcome (2026-10-23)

Eight new runs (`local_results/tinylfu_dot_check/runs.csv`; comparison `comparison.csv`; `python3 -B scripts/tinylfu_dot_check.py summarize`). **By the rule declared above the result is "partly supported":** 6 of the 8 new cells are within 0.0005 of the nearest paper dot, 7 of 8 within 0.002, and the pre-fix variant is closer than the pinned TinyLFU in 6 of the 7 cells where the pinned one is off by more than 0.0005.

The declared test is mapping-free (nearest dot), which is weak for Meta KV, where the panel holds five dots of different traces. A **post-hoc refinement** uses the trace each dot belongs to, as SIEVEREPRODUCTION matched them from SIEVE's value (columns `posthoc_*`):

| trace, cache | paper dot of this trace | pre-fix TinyLFU (distance) | pinned TinyLFU (distance) |
|---|---|---|---|
| meta_reag 0.1% (not blind) | -0.0385 | -0.0385 (0.0000) | -0.0342 (0.0043) |
| meta_reag 10% (not blind) | -0.0226 | -0.0224 (0.0002) | -0.0105 (0.0121) |
| meta_rnha 0.1% | -0.0614 | -0.0615 (0.0001) | -0.0615 (0.0001) |
| meta_rnha 10% | 0.0138 | 0.0139 (0.0001) | 0.0241 (0.0103) |
| meta_rprn 0.1% | -0.0659 | -0.0659 (0.0000) | -0.0600 (0.0059) |
| meta_rprn 10% | 0.0082 | 0.0081 (0.0001) | 0.0183 (0.0101) |
| wiki_2019t 0.1% | 0.1276 | 0.1275 (0.0001) | 0.1252 (0.0024) |
| wiki_2019t 10% | 0.3095 | 0.3098 (0.0003) | 0.3141 (0.0046) |
| **metakv trace 1 0.1%** | 0.1397 | 0.1125 (**0.0272**) | 0.1388 (**0.0009**) |
| metakv trace 1 10% | 0.0896 | 0.0903 (0.0007) | 0.1217 (0.0321) |

**Reading.** On all eight Meta CDN and Wiki cells the pre-fix build lands within 0.0005 of the paper's point, where the pinned build is off by up to 0.012: the TinyLFU disagreement for those datasets is explained by the frequency-sketch increment on window insertion that upstream added in 759f4ca, to within the precision of the paper's extraction. **Meta KV trace 1 does not fit that story:** at the 10% cache the pre-fix build matches (0.0007) and the pinned build is 0.032 off, but at the 0.1% cache it is the other way round (pinned 0.0009 away, pre-fix 0.027 away). No single TinyLFU revision reproduces both Meta KV cells, so either the paper's Meta KV runs differ from the trace or build we use (the Meta KV trace mapping was itself uncertain, and the paper's Meta KV runs may use another file version), or the effect of the fix depends on cache size in a way our build does not capture. We cannot tell which. It shows what the code gives, not that the authors used that revision: no paper-era commit exists in the artifact.

## Follow-up (2026-10-23): is TinyLFU's Meta KV split a capacity artifact? (declared before the runs)

**Observation.** With the five Meta KV traces split out (`docs/metakv_split_protocol.md`), our pinned TinyLFU differs from SIEVEREPRODUCTION's pinned TinyLFU at the small cache on three traces (miss ratios +0.0071, +0.0055, -0.0062) while every other deterministic policy agrees to 0.0005. Both use the same simulator source. They differ in the capacity: SIEVEREPRODUCTION (like the paper's simulator) takes it from the simulator's sampled working-set estimate (16,982 objects for trace 1 at 0.1%), we from the exact distinct count (16,984). The sketch behind W-TinyLFU is sized from the capacity and hashes with fixed seeds (no randomness in `minimalIncrementCBF.c`), so a different capacity changes every collision.

**Hypothesis H-cap.** TinyLFU's result depends on the exact capacity through the sketch size by amounts of the observed order, and the earlier Meta KV trace-1 split (pinned matched the paper at 0.1%, pre-fix at 10%) is explained by that, not by the revision.

**Test (trace 1 only; 8 runs).** (a) The pinned and the pre-fix builds at SIEVEREPRODUCTION's capacities (16,982 and 1,698,213 objects). (b) The pinned build at the small cache with capacities 16,980, 16,984 (ours), 16,990 and 17,000. **Rule.** Supported if (a) the pinned build at 16,982 reproduces SIEVEREPRODUCTION's TinyLFU miss ratio at 0.1% to within 0.0005 and (b) the miss ratio varies by more than 0.002 across the four nearby capacities. In (a) we then also record which build is nearer the paper's dot of trace 1 (0.1397 small, 0.0896 large) at the paper-style capacities; that comparison is descriptive.

### Outcome of the follow-up (2026-10-23): H-cap supported, and the Meta KV split disappears

Runs: `local_results/tinylfu_capacity_sensitivity/runs.csv` (8 runs; `python3 -B scripts/tinylfu_capacity_sensitivity.py summarize`).

| build, capacity (objects) | TinyLFU miss ratio, Meta KV trace 1 |
|---|---|
| pinned, 16,980 | 0.2903 |
| pinned, 16,982 (SIEVEREPRODUCTION's) | 0.2903 (theirs 0.2903) |
| pinned, 16,984 (ours, exact) | 0.2974 |
| pinned, 16,990 | 0.2902 |
| pinned, 17,000 | 0.2962 |
| pre-fix, 16,982 | 0.2900 |
| pinned, 1,698,213 (SIEVEREPRODUCTION's) | 0.0823 (theirs 0.0823) |
| pre-fix, 1,698,213 | 0.0853 |

**Rule: both parts hold** - the pinned build at 16,982 reproduces SIEVEREPRODUCTION's value exactly, and the miss ratio moves by 0.0072 across capacities that differ by a few objects (a two-object change, 16,982 to 16,984, moves it from 0.2903 to 0.2974). TinyLFU's outcome at a tiny cache is chaotic in the capacity through the sketch size. **Consequence for the earlier question.** At SIEVEREPRODUCTION's (the paper simulator's) capacities the pre-fix build gives reductions of **0.1397 (0.1% cache) and 0.0896 (10%) on trace 1, equal to the paper's dots exactly**, while the pinned build gives 0.1388 and 0.1217. The earlier "split" (pinned nearer at 0.1%) came from our exact capacity of 16,984 landing on the other side of this sensitivity for the pre-fix build. So the Figure 4 TinyLFU gap is explained for Meta CDN, Wiki and Meta KV trace 1 alike: the paper's points were produced by a build without fix 759f4ca at the capacities its simulator derived from its sampled working-set estimate. A caution that goes with it: any result at a tiny cache for TinyLFU (including the paper's) is sensitive to a few objects of capacity, so agreement to four decimals is partly luck of the capacity.
