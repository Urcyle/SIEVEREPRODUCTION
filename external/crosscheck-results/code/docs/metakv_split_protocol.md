# Protocol: the five Meta KV traces from the merged file, and their Figure 4/5 points (frozen 2026-10-23, before any run on them)

**Why.** The paper's Meta KV panel has five traces (Meta's `202206` CacheLib KV traces, `kvcache_traces_1..5`). We held only the merged mirror file and trace 1. SIEVEREPRODUCTION showed the merged file is the five concatenated. Splitting it needs no download.

**Data step (not a hypothesis).** `scripts/split_metakv_202206.py` streams the merged file, drops zero-size records (GET misses and DELETEs, which every reader skips) and cuts after the per-trace valid-request counts that SIEVEREPRODUCTION measured from Meta's per-trace CSV files (335,173,084; 328,002,954; 318,815,605; 329,914,873; 332,855,870, summing exactly to the merged file's 1,644,762,386 valid requests). **Pass conditions:** each part's exact distinct-object count is within 0.1% of SIEVEREPRODUCTION's working-set figure (16,982,130; 16,542,009; 16,168,504; 16,236,011; 16,661,458). part 1 equals our separately downloaded trace-1 file record for record in (object id, size) (hash of the valid-record stream). The files are `data/metakv_split/kvcache_traces_N.valid.oracleGeneral.zst`; the receipt is `local_results/metakv_split_receipt.json`. A split point may fall among zero-size records, which cannot change what a reader sees.

**Runs.** The 12 policies of Figure 4 plus the FIFO baseline (FIFO, LRU, CLOCK, SIEVE, ARC, TwoQ, LIRS, LHD, CACHEUS, Hyperbolic, TinyLFU snapshot, B-LRU) on all five parts at 0.1% and 10% of the exact distinct objects (capacity passed explicitly, sizes ignored, cold start), the stochastic ones with controlled seed 42; 120 runs, four workers, the memory estimate and retry rules of the sample10 batch (`docs/twitter_sample10_extension_protocol.md`, amendments). The pre-fix TinyLFU build is then run on the same ten cells (`scripts/tinylfu_dot_check.py` extended to the five traces).

**Pre-declared checks (reported whatever they give).**
1. Our deterministic policies (all but LHD and CACHEUS) agree with SIEVEREPRODUCTION's `fig4.csv` miss ratios to within 0.0005 on every cell (their capacity comes from the simulator's sampled working-set estimate, ours from the exact count, so a difference of that size is the expected limit).
2. Our SIEVE reduction equals the paper's dot of the same trace (the dot of each trace as matched by SIEVEREPRODUCTION from SIEVE's value, taken from its `summary.md`: trace 5 is dot 1, trace 1 dot 2, trace 3 dot 3, trace 4 dot 4, trace 2 dot 5) to within 0.0005 on all ten cells.
3. TinyLFU: for each of the ten cells, which of the pinned and pre-fix builds is nearer the paper's dot of that trace (descriptive; on trace 1 it split: pinned nearer at 0.1%, pre-fix at 10%).

**Correction before the split was accepted (2026-10-23).** The first version of this protocol compared the exact counts with the `objects` column of SIEVEREPRODUCTION's per-trace statistics (16,841,368 for trace 1 and so on). Our exact count for trace 1 (16,984,531, the same figure our trace-1 runs have always used) differs from that column by 0.8% but from its `wss_obj` column (the simulator's sampled working-set estimate) by 0.014%, so the check was pointed at the wrong column; the pass condition above is the corrected one. The split was re-run unchanged.

**Second correction (2026-10-23).** The first comparison hashed whole records and failed for the right reason: the two sources agree on object id and size in every one of the first 5 M valid records but differ in the `time` field (the merged file carries 0 or its own values) and in `next` (next-access positions computed over the whole merged stream), which none of the policies run here use. The split therefore writes `time = 0` and `next = -2`, and the trace-1 check hashes (id, size) pairs. The split was re-run once more, unchanged otherwise.

## Amendment 1 (2026-10-23, after the first pass, before any result was used)

On the first pass all 120 runs were omitted by the available-memory gate (6.55 GiB needed, 5.9 available): the flat estimate (1 GiB + 100 bytes per object, 2.7 GiB for 17 M objects) over-states every policy but CACHEUS and under-states CACHEUS. The measured peak RSS of the 400+ completed runs of the sampled-Twitter batches (0.14-0.95 GiB at 5.8-7.1 M objects for every policy except CACHEUS; 1-3.2 GiB for CACHEUS, and one run above 9 GiB) gives a **policy-specific estimate**: CACHEUS 0.5 GiB + 600 bytes per object (about 10 GiB for 17 M objects), TwoQ, LIRS, TinyLFU and B-LRU 0.25 GiB + 150 bytes, all others 0.25 GiB + 80 bytes (config key `policy_specific_estimate`). The live guards are unchanged. Expected consequence, declared now: CACHEUS on these traces will be omitted by the gate (its estimate plus the 4 GiB headroom exceeds what this machine has free); the other policies should run. Omitted runs are retried unchanged in later passes; nothing else changes. The same estimate is used for the three gated Twitter files.

**Third correction (2026-10-23, before check 2 was evaluated).** The first draft of check 2 took the dot index to be the trace number; SIEVEREPRODUCTION's table shows it is not (the dots are numbered by plotting opacity), and a first look at trace 1 at the large cache against dot 1 (0.1795, which is trace 5's) made the error visible. The mapping above is used for checks 2 and 3 (and for the earlier TinyLFU check, where trace 1 was already dot 2).

## Outcome (2026-10-23; 110 of 120 runs, `python3 -B scripts/metakv_split_compare.py compare`)

The ten missing runs are CACHEUS on the five parts at both sizes: the memory gate omitted them (a 16 M-object CACHEUS needs more than the machine has free), so Figure 4/5 rows for Meta KV have 11 of 12 policies.

1. **Check 1: 87 of 90 deterministic cells agree with SIEVEREPRODUCTION within 0.0005.** The three exceptions are all TinyLFU at the 0.1% cache (trace 1 +0.0071, trace 3 +0.0055, trace 5 -0.0062): the capacity-sensitivity of TinyLFU's sketch (`docs/tinylfu_dot_check_protocol.md`, follow-up), since our exact capacity differs from the simulator's by a few objects. The split is therefore faithful: every other policy on every part reproduces the other replication's numbers.
2. **Check 2: our SIEVE reduction is within 0.0005 of the paper's dot on 8 of 10 cells; the largest distance is 0.0009.** The two outside 0.0005 are within 0.001 of it. Descriptive: SIEVE on the real Meta KV traces reproduces the paper's points to about a thousandth.
3. **Check 3 (TinyLFU, descriptive).** The pre-fix build is within 0.0018 of the paper's dot on **all five large-cache cells** and on the small cells of traces 2 and 4 (0.0001 and 0.0000); the pinned build is 0.031-0.033 away on four of the five large cells. On the small cells of traces 1, 3 and 5 neither build is near (0.022-0.027 away), at our exact capacities. Only trace 1 has been re-run at the paper simulator's capacity (16,982), where the pre-fix build equals the dot (0.1397); traces 3 and 5 have not been, so we do not claim the small-cell gap closes for them, only that it is the cell type where TinyLFU's capacity sensitivity (0.007 for a two-object change) was measured to act.

Files: `local_results/metakv_split_extension/comparison.csv`, `tinylfu_prefix_vs_pinned.csv`.

## Amendment 2 (2026-10-25, before any CACHEUS run on these parts): try the ten omitted CACHEUS cells under the live guard

**Why.** Ten of the 120 planned runs (CACHEUS, five traces, two sizes) were omitted by the pre-run estimate (0.5 GiB + 600 B x 16-17 M objects, above the 12 GiB budget). The estimate is conservative: completed CACHEUS runs on 5.8-7.1 M objects peaked at 1-3.2 GiB (150-590 B per object), with one earlier run above 9 GiB. A try costs hours but cannot harm the machine, because the runner stops any run whose process tree passes 12 GiB RSS or when system available RAM falls below 4 GiB, and records the omission.

**Rule.** The five parts are regenerated by `scripts/split_metakv_202206.py` and must match the recorded SHA-256 of each (`docs/data_removed_20261020.md`, fourth removal) before any run. CACHEUS only (`TWITTER_EXT_ONLY_POLICIES=cacheus`), seed 42, exact capacities as for the other policies, one worker at a time, estimate 0.5 GiB + 300 B x objects (`TWITTER_EXT_CACHEUS_PER_OBJECT=300`; this understates the worst measured case, 590 B, so the gate is the live guard, not the estimate). A run the guard stops is an omission with its reason; it is not retried with a larger allowance.

**Check (descriptive).** For each cell that completes, our CACHEUS reduction next to SIEVEREPRODUCTION's default-draw value and the paper's dot of that trace. CACHEUS draws random numbers, so a single seed is one draw (`docs/cacheus_seed_spread_protocol.md` found Meta CDN cells bimodal across seeds); a difference from their draw or from the paper's dot is therefore not by itself a discrepancy, and no pass/fail threshold is set.

**Amendment 2a (2026-10-25, before any CACHEUS result).** The first attempt at 300 B per object was omitted by the pre-run gate on all ten cells by about 0.1-0.3 GiB (needs 9.02-9.25 GiB available, the machine had 8.9 GiB). Nothing had run. The estimate is lowered to 0.5 GiB + 250 B x objects (`TWITTER_EXT_CACHEUS_PER_OBJECT=250`, still above the median of the measured 150-590 B); everything else in amendment 2 is unchanged, including the live guard that stops a run at 12 GiB RSS or below 4 GiB available RAM.

## Outcome of amendment 2 (2026-10-25): all ten CACHEUS cells completed; the Meta KV set is now 120 of 120

The five regenerated parts matched their recorded SHA-256 (`docs/data_removed_20261020.md`). All ten CACHEUS runs finished under the live guard with exact counters: peak RSS 0.77 GiB at the 0.1% cache and 1.86-2.45 GiB at 10% (about 150 B per object on 16-17 M objects), so the original estimate of 600 B per object was about four times too high for these traces (the Wiki and gated-Twitter estimates that rest on it are re-examined in their own protocols). No run was stopped by the guard. Each run took 250-290 s.

Descriptive comparison (`local_results/metakv_split_extension/comparison.csv`, CACHEUS rows; seed 42 is one draw of a random policy, so no threshold was set):

| trace | cache | ours miss ratio | SIEVEREPRODUCTION's | ours reduction | paper's dot | distance |
|---|---|---|---|---|---|---|
| 1 | 0.1% | 0.3117 | 0.3117 | 0.0753 | 0.0866 | 0.0113 |
| 1 | 10% | 0.0778 | 0.0778 | 0.1700 | 0.1697 | 0.0003 |
| 2 | 0.1% | 0.3098 | 0.3138 | 0.0871 | 0.0861 | 0.0010 |
| 2 | 10% | 0.0774 | 0.0798 | 0.1721 | 0.1465 | 0.0256 |
| 3 | 0.1% | 0.3138 | 0.3139 | 0.0744 | 0.0852 | 0.0108 |
| 3 | 10% | 0.0775 | 0.0799 | 0.1725 | 0.1473 | 0.0252 |
| 4 | 0.1% | 0.3072 | 0.3073 | 0.0745 | 0.0849 | 0.0104 |
| 4 | 10% | 0.0750 | 0.0750 | 0.1728 | 0.1731 | 0.0003 |
| 5 | 0.1% | 0.3083 | 0.3043 | 0.0747 | 0.0867 | 0.0120 |
| 5 | 10% | 0.0761 | 0.0762 | 0.1717 | 0.1708 | 0.0009 |

Our seed-42 draw equals SIEVEREPRODUCTION's default draw to within 0.0001 on 6 of 10 cells and differs by 0.002-0.004 on traces 2 and 3 at 10% and traces 2 and 5 at 0.1%. Against the paper's dots, 5 of 10 are within 0.001 (large cache of traces 1, 4, 5; small cache of trace 2) and the others are 0.010-0.026 away: at 10% on traces 2 and 3 our value (0.172) is about 0.025 above the paper's (0.147), at 0.1% on traces 1, 3, 4, 5 about 0.011 below. This is the same kind of seed-dependent spread as `docs/cacheus_seed_spread_protocol.md` found on Meta CDN (CACHEUS bimodal across seeds); we did not run a seed spread on Meta KV, so we do not claim that these gaps are seed draws, only that a single draw cannot tell them apart from a real difference.
