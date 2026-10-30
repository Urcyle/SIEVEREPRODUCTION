# Protocol: Twitter clusters from the authors' sample100 mirror (frozen 2026-10-20, before any download)

**Purpose.** Figure 3c/3f's paper distribution covers 54 Twitter clusters; the union of our runs and the SIEVEREPRODUCTION snapshot covers 27 (10% cache) to 29 (0.1% cache). This extension adds clusters that neither of us has run, to see whether the Twitter means move toward the paper's. It tests nothing new about SIEVE; it widens coverage.

**Inputs (fixed now).** The files `twitter/sample100/cluster{N}.oracleGeneral.sample100.zst` on the CMU PDL mirror used by the artifact (`https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets`), for **N in {32, 37, 40, 43, 46, 52, 54}**. Selection rule, applied before downloading: sample100 files under 1 GiB (so the pinned simulator's working-set estimate is exact and no sampled-WSS exception is needed) for clusters that no earlier run, ours or SIEVEREPRODUCTION's, covers; cluster 27 (1.37 GB) is excluded by the size rule. Total download about 3.4 GB, inside the remaining aggregate budget (`resources_current.json`: 13.4 GB). A sample100 file is the mirror's 1% spatial sample of the cluster, not the cluster itself; results are labelled `sample100`, never "cluster N full".

**Policies and capacities.** FIFO, LRU, CLOCK, SIEVE, ARC, TwoQ, LIRS, LHD, CACHEUS, Hyperbolic, TinyLFU (pinned snapshot), B-LRU: the paper's 11 algorithms plus the FIFO baseline. Capacity = floor(exact unique objects x fraction) with fractions 0.001 and 0.1, sizes ignored, cold start, one thread. Stochastic policies use the controlled seed 42 of the seeded-baselines build; no seed study.

**Identity and exact working set.** SHA-256, `zstd -t`, packed-record schema and exact unique-object count of each file via `sieve_repro.trace.validate_oracle_file(count_unique=True)`; the HEAD content length must equal the stored size.

**Resource rules (unchanged from the other studies).** One simulator per worker root, estimated peak = 4 GiB + 300 bytes per unique object (checked against the 12 GiB soft cap and a 4 GiB available-memory headroom); a run that cannot meet the gate is recorded as omitted with its reason, not retried with a different configuration. Three workers at most.

**Reporting rule.** All results enter the comparison tables only as `sample100` entries, keep their exact counters, and are never mixed silently with full-trace clusters: the union in Figure 3c/3f lists each source. Exact miss counts, not four-decimal ratios, are used for reductions. No hypothesis is attached; any outcome is reported.

**Not done here.** Cluster 27 and the sample10 files (1-3 GB each, 24 clusters) exceed the size rule or the budget; full-size files of any cluster; Tencent Photo; Wiki 2016u/2019u; per-trace Meta KV.

## Amendment 1 (2026-10-20, after the first run attempt, before any result was used)

The first attempt used the peak estimate above (4 GiB + 300 bytes per object). With 8.3 GiB available and the 4 GiB headroom rule, that estimate blocked nearly every run of clusters 52, 46, 37 and 32 as `MemoryError` omissions (listed in `worker1/omitted_attempt1_estimate_too_conservative.csv`), although the first measured runs of cluster 54 peaked at 0.3 GB. The estimate is changed to **1 GiB + 250 bytes per unique object** (about 4 GiB for the largest feasible file, 12M objects), all omitted entries are retried, and nothing else changes: same files, policies, capacities, seed, gates and reporting rule. Cluster 32 (35.6M objects, estimated 9.3 GiB) is still expected to be blocked by the available-memory gate and will be reported as omitted if so. The edited config is `config/twitter_sampled_extension.json` (its hash is part of every baseline run's identity, so the first attempt's completed runs of the seven extra policies, if any, were recomputed).

## Amendment 2 (2026-10-20): four workers instead of two

Throughput was about one run per 1.7 minutes per worker, so the 168-run plan would have taken about 2.4 hours. The worker partition in the config is changed to four workers (`[[54], [52], [43, 40], [46, 37, 32]]`; the memory use per run is 0.3-0.4 GB). Nothing about the inputs, policies, capacities, seed, gates or reporting rule changes. Only the config hash differs, so the few extra-policy runs completed before the change were recomputed.
