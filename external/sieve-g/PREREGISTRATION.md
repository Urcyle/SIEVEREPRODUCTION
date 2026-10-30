# SIEVE-G pre-registration

Written and committed after the development runs (Phase 3) and **before any held-out run**
(Phase 4). Nothing below may change after this commit.

> **Frozen:** ghost ratio = **0.25** (`sieveg-0.25`: the ghost holds the ids of the last
> 0.25 × cache size evicted objects).
>
> **Pass rule (held-out clusters 25–54, each cache size separately):** mean reduction of SIEVE-G
> relative to SIEVE > 0, median ≥ 0, and SIEVE-G worse than SIEVE (by > 0.0001 in miss ratio)
> on ≤ 25% of clusters.
> Relative reduction = (mr_SIEVE − mr_SIEVEG) / mr_SIEVE, or / mr_SIEVEG when worse.
>
> **Fig 4 check:** report every trace; flag any loss > 0.005 in miss ratio.

## How the ratio was chosen

Development set: the six clusters where SIEVE lost to FIFO in the Figure 3 replication (8, 1,
12, 13, 23; 49 from the sampling validation), with their Figure 3 trace versions
(`manifests/dev.tsv`); FIFO and SIEVE equal the Figure 3 logs in all 24 values
(`scripts/dev_report.py`). Results: [results/dev_table.md](results/dev_table.md).

Rule (from the plan): among the ratios 0.25, 0.5, 1.0 that are **not worse than SIEVE on any dev
cluster at the 10% cache**, the one with the highest mean reduction from FIFO at the 0.1% cache;
ties to the smaller ratio.

| ratio | dev clusters worse than SIEVE at 10% (by > 0.0001) | higher than SIEVE at 10% at all | mean reduction from FIFO at 0.1% |
|---|---|---|---|
| 0.25 | none | cluster 1 (0.0052 vs 0.0051) | −0.069 |
| 0.50 | cluster 1 (0.0053 vs 0.0051) | cluster 1 | −0.063 |
| 1.00 | cluster 1 (0.0054 vs 0.0051) | cluster 1 | −0.059 |

(SIEVE: −0.140.)

**Deviation from the plan, stated plainly.** Read literally ("not worse" = not higher at all),
no ratio qualifies: all three have a miss ratio 0.0001–0.0003 above SIEVE on cluster 1 at the 10%
cache, and the plan gives no fallback. The plan's pass rule defines "worse than SIEVE" as "by
> 0.0001 in miss ratio" (also the resolution of cachesim's 4-decimal output); that same
definition is used here, which leaves only 0.25. The ratio with the best development numbers at
the small cache (1.0) is therefore **not** the one frozen.

## Analysis set and further definitions (fixed now)

* **Primary verdict: clusters 25–54 without cluster 49 (29 clusters).** Cluster 49 is in the
  development set (its `sample10` version) as well as in clusters 25–54 (its full trace), so it
  is not held out. The verdict over all 30 clusters is reported as well, as secondary.
* Trace versions: `manifests/heldout.tsv`, from the Figure 3 rule (`scripts/trace_stats.py` →
  `choose_twitter.py` → `make_manifests.py`; identical to Figure 3's choices for these clusters).
  All 30 files were already on disk; none had to be downloaded.
* Runs: `ALGOS=fifo,sieve,sieveg-0.25`, sizes 0.001 and 0.1 of the footprint as cachesim
  computes it, object size ignored (`scripts/run_sieveg.sh`), 6 miss ratios per log.
* "Better / equal / worse" counts: SIEVE-G's miss ratio below SIEVE's by > 0.0001 / within
  0.0001 / above by > 0.0001.
* Fig 4 check: the 13 traces of `manifests/fig4check.tsv`; before SIEVE-G's numbers are used,
  SIEVE must equal `external/sieve-fig4/results/fig4.csv` at the same cache size.
