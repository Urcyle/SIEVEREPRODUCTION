# SIEVE variant experiment: frozen protocol

Status: **frozen before any variant is implemented or run on any trace.** The commit that adds this file is the freeze point; later edits must be additions in a clearly dated "Amendments" section at the end, never silent changes.

The goal is a small, honest test of whether simple modifications improve on SIEVE in miss ratio, and what they cost in extra state. The result may well be "no robust improvement". That is a valid outcome and will be reported as such. The paper's claim being tested is a different one (SIEVE is simple *and* competitive); a variant that wins by adding state does not refute it, but it does show where the simplicity has a price.

## 1. Evidence that motivates the hypotheses (already in the repository)

* Baseline SIEVE recovers slowly after a hot-set change: `local_results/phase_change_recovery.csv` (seed 42) shows miss recovery after about 1.7M requests for SIEVE versus 0.6M for LRU and 0.7M for ARC. A visited bit that stays set until the hand reaches it keeps stale objects alive. This motivates **aging**.
* SIEVE ignores access counts beyond one bit. On frequency-skewed workloads LFU/ARC beat it at some sizes (Figure 8a reproduction). This motivates a **multi-bit counter**.
* The paper itself states SIEVE is not scan resistant (section 7.2) and that TwoQ/LHD beat it at the small cache on some traces. Admission and ghost history are the standard remedies. This motivates **ghost-informed insertion** and a **second-request admission** baseline.
* The earlier 16-trace diagnostic found no association between singleton share and SIEVE's outcome ([report](trace_frequency_all16_report.md)). It is not used to select any rule here.

Because all real traces already had baseline SIEVE results inspected, no real trace is an untouched blind set. The protocol therefore never uses a real trace to choose parameters (section 5).

## 2. Variants (all object-count mode, sizes ignored, as in the paper's section 4.2)

Baseline SIEVE is Algorithm 1: queue with newest at the head, a hand that starts at the tail, a visited bit set on hit, no reordering on hit; on eviction the hand moves toward the head clearing visited bits, wraps to the tail, evicts the first unvisited object and keeps the hand at that object's predecessor. New objects enter at the head unvisited.

Notation: `C` is the capacity in objects, `n` the 0-based index of the current request.

**ctr(K)** — saturating counter. A hit sets `freq = min(freq + 1, K)`. The eviction sweep decrements `freq` by one instead of clearing it. `K = 1` is exactly baseline SIEVE. Grid: `K in {1, 3, 7}`. Extra state: 2 or 3 bits per object instead of 1.

**ghost(g)** — ghost-informed insertion. Keep a FIFO of the IDs of the most recent `floor(g*C)` evicted objects (at least one). On a miss for an ID found in the ghost, remove it from the ghost and insert it with `freq = 1`; otherwise insert with `freq = 0`. Evicted IDs are pushed to the ghost tail; the oldest ID is dropped when the ghost exceeds its size. Grid: `g in {0.5, 1.0}`. Extra state: one 8-byte ID plus index overhead per ghost entry; this is *not* free and is reported as such.

**age(P)** — epoch aging. `epoch(n) = floor(n / P)` with `P = m*C`. A hit sets `freq = 1` and records `stamp = epoch(n)`. During the sweep a visited bit counts only if `freq > 0` and `stamp == epoch(current n)`; a stale bit is treated as unvisited. The stamp is a 32-bit value and the run aborts if an epoch above 2^32 - 1 would be recorded. Grid: `m in {1, 2, 4, 8}`. Extra state: one stamp per object. There is no queue walk when the epoch advances.

**bloom** — second-request admission. The simulator's existing `-a bloom-filter` admission is applied to SIEVE: an object is admitted only if it has been requested before (the implementation is an exact, unbounded set of seen IDs, not a real Bloom filter; this is the same mechanism the authors used for B-LRU). It is the only variant needing memory proportional to the whole footprint; it is run only on traces with at most 70 million distinct IDs and is labeled "exact-history admission".

No combination of variants is evaluated. Each family changes one thing. Defaults reproduce baseline SIEVE bit-for-bit (section 4).

## 3. Implementation constraints

* A single patch against the pinned artifact (`0861f82…`) adds the parameters `max-freq`, `ghost-ratio`, `age-period-x` to the SIEVE policy's `--eviction-params`. The artifact checkout stays clean. Source and binaries live in a new directory `build/sieve-variants*` and a new results namespace `local_results/variants/`.
* With no parameters, behavior must equal baseline SIEVE. Verified by (a) exact counter equality against the three saved `meta_reag` baseline runs (small cache, large cache, both builds) and (b) randomized differential tests.
* An independent Python reference model implements the definitions in section 2. Tests compare it per request (hit/miss, queue contents with counters/stamps, hand, ghost) against a state-instrumented build on hand-worked sequences, scan/loop sequences, and seeded random sequences over several capacities, plus counter equality of the production build.
* Evaluation uses the exact-counter build and absolute object capacities taken from the saved baseline runs (same trace SHA-256, same exact working-set footprint, floors of 0.1% and 10%). Baseline SIEVE and FIFO counters are reused from the saved runs of the same trace and capacity; the variant build's default mode is re-run once per family of traces to confirm equality.
* One simulator job at a time per experiment, at most two concurrently overall, only when available RAM stays at least 4 GiB above the estimated peak. The 10% capacity on Twitter clusters 31, 38 and 39 (baseline SIEVE peak RSS about 10.7 GiB) and cluster 21 (no baseline 10% run) is excluded; cluster 13 at 10% (baseline peak about 4.6 GiB) runs only if the memory gate passes at launch time. Excluded or gated configurations are listed in the report.

## 4. Data split

**Development (used for choosing a configuration)**

* Zipf finite-support, `M = 100,000`, `N = 10,000,000`, `alpha in {0.8, 1.0, 1.2}`, seeds 42, 43, 44 (existing files `zipf9a_scaled_*`), object capacities 100, 1,000 and 10,000 (0.1%, 1%, 10% of `M`).
* Phase-change workload: existing `phase_change_scaled_seed{42,43,44}` (two disjoint alpha=1 phases of 100,000 objects, 10M requests each, capacity 10,000).
* Tiny scan and loop stress inputs from `scripts/scan_loop_stress.py` (limitation checks; reported but not scored).

**Held-out synthetic (never run before the configuration is frozen)**

* The same recipes with seeds 45, 46, 47 (phase-change seeds 45/1045, 46/1046, 47/1047). Before generation, verify that no file or result for these seeds exists.

**Held-out real traces (run exactly once per frozen configuration; no parameter tuning on them)**

* Every complete local trace with a saved baseline: Meta CDN `meta_reag`, `meta_rprn`, `meta_rnha`; Wiki `wiki_2019t`; Meta KV `metakv_202206`, `metakv_202210`, `metakv_trace1_candidate`; Twitter clusters 3, 7, 8, 10, 13, 21, 26, 31, 35, 38, 39, 45, 48, 49, 50, 53. Capacities: 0.1% everywhere; 10% wherever the baseline 10% run exists. All of them were inspected at baseline before this protocol, which is why they are not used to select anything.

## 5. Selection rule (written before running anything)

For every family and every grid member compute, on the development set only, the score

`score = mean over (workload, seed, capacity) of (m_SIEVE - m_variant) / m_SIEVE`

where `m` is the exact miss count. The configuration with the highest score is the family's **primary** configuration; ties go to the smaller parameter. A family whose best score is not above zero has no primary configuration and is reported as "no gain on development data", but its grid is still run on the held-out synthetic seeds and the cheap real traces for completeness.

Only primary configurations are run on all held-out real traces. The full grids are additionally run on the cheap real traces (fewer than 400M requests: the three Meta CDN traces, Wiki `wiki_2019t`, `metakv_trace1_candidate` and Twitter clusters 10, 26, 45, 50 and 53) as sensitivity analysis and are labeled "sensitivity, not primary".

## 6. Metrics, reporting and decision rules

* Per trace and capacity: `rel = (m_SIEVE - m_variant) / m_SIEVE` (positive is better) and the paper's FIFO-normalized reduction for both algorithms, using the saved FIFO counters.
* Win/tie/loss counts per capacity with ties defined as exactly equal integer miss counts. Mean and median of `rel` over traces, plus every individual value. Negative values are shown, not clipped.
* Context only (not part of any decision rule): where saved 12-policy results exist, whether the variant moves SIEVE past TwoQ, ARC or LRU at the same trace and capacity.
* Cost: extra bits/bytes per object (analytical), and the simulator wall time from the run records relative to the baseline run on the same trace (indicative, single measurement, shared laptop).
* **Decision rule for the statement "variant improves SIEVE":** at the 0.1% capacity and at the 10% capacity separately, on the held-out real traces, the mean `rel` must be positive and the median `rel` must be non-negative, and the variant must lose on at most one quarter of traces; and on the held-out synthetic seeds the sign of the mean `rel` must agree across all three seeds. If any condition fails, the statement made is "no robust improvement over SIEVE in this test", with the numbers.
* Trace-level paired sign-test p-values are reported descriptively. Traces are not an independent random sample of any population and three public families dominate, so no population claim is made.
* Failed, aborted or resource-gated runs are preserved and listed; missing is never zero.

## 7. Outputs

`local_results/variants/` run records (same `complete.json` conventions, `eviction_params` in the spec, a new `workload_label` suffix), tidy CSVs, plots generated only from saved counters, a regeneration receipt, `docs/sieve_variants_report.md` written in plain language, and a PROGRESS.md entry. Plot and summary scripts must not rerun simulations. The baseline plot commands must keep working (their selection filter excludes any run with `eviction_params`).

## Amendments

### Amendment 1 (2026-10-19, after the variant build and tests, before any dev/held-out run)

Operational only; no definition, grid, split, selection rule or decision rule changes.

* Run records go to `local_results/variants/runs/<run_id>/` with their own schema (trace SHA-256, baseline run ID, binary SHA-256, parameters, exact counters, peak RSS, attempts), not to the shared `local_results/runs/`. The existing exact-WSS validator reads files under its own result root, so this keeps baseline and variant evidence separate and leaves the baseline plot/audit commands unaffected.
* Capacities, request counts and footprints for real traces are copied from the saved baseline SIEVE run of the same trace and capacity; the runner refuses a run whose reported capacity or request count differs. Baseline SIEVE and FIFO counters are those saved records (counter-sim build). For synthetic inputs, baseline SIEVE and FIFO are run with the variant build without parameters, since no single saved baseline covers every capacity.
* Held-out synthetic traces (seeds 45-47) are generated into scratch space, run, and deleted; the seed, recipe and SHA-256 are kept so each is regenerable bit-for-bit. Development traces are the existing compressed files.
* Meta KV `metakv_202206` and `metakv_202210` are read from their existing location on `/mnt/media_internal`; nothing is written there.
* The simulator is run with its working directory in scratch space so that its per-run output file does not land in the repository.

### Amendment 2 (2026-10-19): Round 2 of development, adding one bounded-memory family

Written after the Round 1 development grid and selection (`config/variant_selection.json`, commit `fa24386`) and **before any held-out run**: no held-out synthetic seed (45-47) and no variant run on any real trace exists yet. What round 1 showed on development data only: `ctr3` +0.04%, `bloom` +0.97%, and every `ghost` and `age` configuration negative. Round 1 files stay as recorded.

* **Motivation.** `bloom` (exact-history admission) was the only family with a clearly positive development score, concentrated at the 10% capacity (about +2%), but it needs memory proportional to the whole footprint and is therefore not a deployable change. A bounded version is the natural, honest follow-up.
* **New family `door(w)`: doorkeeper admission.** Keep a FIFO of the most recent `floor(w*C)` (at least one) IDs that missed and were *not* admitted. On a miss for an ID found there, remove it from the doorkeeper and admit it normally; otherwise push the ID to the doorkeeper (dropping the oldest when full) and do not cache the object (the request still counts as a miss, and no eviction happens). Grid `w in {1, 2, 4}`; extra state about one 8-byte ID plus index overhead per doorkeeper entry. Implemented as a second patch on top of the first (`patches/sieve-variants-round2.patch`), built into new directories `build/sieve-variants-r2*`. Parameter name `door-ratio`.
* **Everything else is unchanged:** the same development cells, the same score, the same selection rule (highest score per family, ties to the smaller parameter, none if not above zero). Round 2 reruns baseline SIEVE and FIFO plus the three `door` configurations on all 30 development cells with the new binary, and re-runs a subset of the round-1 configurations to confirm the new binary reproduces the round-1 counters exactly. The round-2 selection is written to `config/variant_selection_round2.json` and covers all ten configurations; the round-1 file is preserved. All later runs use the round-2 binary and the round-2 selection.
* **Cost of this look.** The development set has now been used to choose among 12 configurations in two rounds, so the development scores are optimistic for the winners. The held-out synthetic seeds and the real traces remain unseen and decide everything the decision rule decides.

### Amendment 3 (2026-10-19, night): a post-hoc hypothesis about `ghost`, with a confirmation set fixed before it is run

What was seen first. The primary configurations chosen on synthetic development data (`ctr3`, `bloom`, `door1`) were run on real traces while this amendment was being written, and the full grid was run on the cheap real traces as the protocol specifies. On those cheap traces (about 10-13 traces per capacity at that moment), `bloom` and `door1` lose heavily (they need two misses before an object can hit, which roughly doubles the misses on cache-friendly traces), `ctr3` and all `age` settings are mixed to negative, and the two `ghost` configurations (which had **no** primary configuration because they scored negative on synthetic data) are better than SIEVE on every one of those traces at both capacities. This is a post-hoc finding: the cheap real traces are exploratory for it and **do not count as confirmation**.

Hypothesis H (stated before the confirmation runs): *ghost-informed insertion (`ghost0.5` and `ghost1.0`) reduces misses relative to SIEVE on real request traces, but not on independent-reference Zipf workloads, where the synthetic development and held-out seeds already show it losing.*

Confirmation set (fixed now): every real trace with a saved baseline that is **not** in the cheap subset, that is Meta KV `metakv_202206` and `metakv_202210`, and Twitter clusters 3, 7, 8, 13, 21, 31, 35, 38, 39, 48 and 49, at 0.1% everywhere and at 10% wherever the memory gate and the 12 GiB cap allow (the same exclusions as the primaries). Configurations: `ghost0.5` and `ghost1.0`, both, run once each. No parameter is tuned.

Decision rule for H on the confirmation set only (the real-trace conditions of section 6, unchanged): at 0.1% and at 10% separately, mean `rel` > 0, median `rel` >= 0, and losses on at most a quarter of the traces. The synthetic condition of section 6 is **not** applied to H because it is already known to fail by construction; instead the report states plainly that `ghost` is not an improvement on IRM workloads and that H is limited to real traces. The decision rule of section 6 for the originally selected primaries (`ctr3`, `bloom`, `door1`) is unchanged and stays in force. If H is confirmed, the claim is "improves on 24-or-so public traces", not "improves SIEVE in general", and it carries an explicit cost: one 8-byte ID plus table overhead per ghost entry, 0.5 or 1.0 entries per cached object.

### Amendment 4 (2026-10-20, 00:36): the two Meta KV trace files were removed from `/mnt/media_internal`

The files `202206_kv_traces_all.csv.oracleGeneral.zst` (8,028,411,588 bytes) and `202210_kv_traces_all_sort.csv.oracleGeneral.zst` (6,970,491,369 bytes) existed when the real-trace runs started and were still present at 23:56 on 2026-10-19; their directories were gone by 00:07 on 2026-10-20 (not in the drive's trash; 14 GB became free). The study did not remove them (it only removed three empty directories at about 23:56 at the user's request to clear stale worktrees). Consequence: `metakv_202206` has no variant run of any kind and `metakv_202210` has only `ctr3` and `door1` at 0.1%. Their baseline counters, manifests and hashes remain in the repository, but these two traces can no longer be replayed or re-verified locally without a new download, which has not been authorized and was not attempted.

* The confirmation set of Amendment 3 is therefore the **Twitter clusters 3, 7, 8, 13, 21, 31, 35, 38, 39, 48 and 49 only**. The decision rule is unchanged and is applied to whatever subset of them could be run under the memory gates; the report lists every omitted (trace, capacity) pair with its reason.
* Held-out evaluation of the primaries `ctr3`, `bloom` and `door1` loses the same two traces; the cited "n" in every table is the number of traces actually run.

### Amendment 5 (2026-10-20, 02:52): Meta KV traces re-downloaded to the main disk; Amendment 4's narrowing is reversed

At the user's instruction the two Meta KV files were fetched again from the same author-linked CMU URLs (`config/metakv_202206_manifest.json`, `config/metakv_202210_manifest.json`), this time to `data/metakv_2022/` on the main disk (not the external drive), with `scripts/redownload_metakv.py` and the project's resumable downloader. Both files match the recorded originals exactly: `202206_kv_traces_all.csv.oracleGeneral.zst` 8,028,411,588 bytes, SHA-256 `4bdcde2ed036da0bdf81d6bfd3fb721fab20cf90e015a8027db49a15449b2ac8`; `202210_kv_traces_all_sort.csv.oracleGeneral.zst` 6,970,491,369 bytes, SHA-256 `256828fd0a33e67987ca6f334be1df73a242803587db24e449546c6063a82e9e`. The study's trace table now points there. Consequences: the confirmation set of Amendment 3 again includes `metakv_202206` and `metakv_202210`; the primaries are run on them; the runs already made on `metakv_202210` before the removal stay valid (same identity hash). The statement in Amendment 4 that these traces cannot be replayed no longer applies. The data stays out of Git (`data/` is ignored).


### Amendment 6 (2026-10-20, 15:44): a second held-out check of ghost-informed insertion on new sample100 Twitter files, fixed before any ghost run on them

Why. The ghost result was confirmed on traces that did not generate it, but all of them are complete traces of clusters that were also part of the exploratory set's families, and the strongest gains came from three clusters (49, 50, 8). The Twitter sample100 extension (`docs/twitter_sampled_extension_protocol.md`) adds files for clusters that neither the exploration nor the confirmation set touched.

Fixed now, before any `ghost0.5` or `ghost1.0` run on them: the **held-out-2 set** is the sample100 files of Twitter clusters **37, 40, 43, 46, 52, 54** (cluster 32 is expected to be blocked by the memory gate and joins only if its baseline runs). Configurations: `ghost0.5` and `ghost1.0` only, both capacities (0.1% and 10% of the exact unique objects), the same patch and binary (`build/sieve-variants/bin/cachesim`). Comparison: misses against SIEVE on the same file, using the extension's saved SIEVE counters (base equality was verified on other traces; it is checked again here on one file per capacity by running `base`). Decision rule, per capacity and per configuration, as in Amendment 3 restricted to real-trace conditions: mean miss reduction > 0, median >= 0, and no more than a quarter of the traces lost. Outcomes are reported whatever they are; a pass supports the claim for sample100 Twitter files only. Caveat declared now: a 1% spatial sample changes the reuse structure (sampled objects keep their own reuse distances, but cache fractions are of the sampled footprint), so a pass or fail is evidence about sampled traces.

### Amendment 7 (2026-10-20, 19:27): held-out-3 for ghost-informed insertion, fixed before any ghost run on these files

The batch-2 Twitter sample files (`docs/twitter_sample10_extension_protocol.md`: clusters 25, 27, 28, 30, 33, 34, 36, 42, 44, 47, 51) have never been used for any variant. They form **held-out-3**. Configurations `ghost0.5` and `ghost1.0` only, both capacities, same binary, same comparison (against the saved SIEVE counters of the extension runs, base equality re-checked on one file per capacity), same decision rule as Amendments 3 and 6, applied (a) to held-out-3 alone and (b) pooled with held-out-2 (Amendment 6). A file whose runs the memory gate omits is dropped and listed. Caveat as in Amendment 6: these are spatial samples (10% or 1%).
