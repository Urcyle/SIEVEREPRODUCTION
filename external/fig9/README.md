# SIEVE (NSDI'24) Figure 9: a replication

This repository reproduces **Figure 9** of
*SIEVE is Simpler than LRU: an Efficient Turn-Key Eviction Algorithm for Web Caches*
(Zhang et al., NSDI'24): (a) miss ratio and (b) popular object ratio of LRU, LFU, ARC and SIEVE
over the Zipf skew α, and (c) the position of SIEVE's hand over time.

![Paper vs replication](fig9/fig9_side_by_side.png)

* **(a) the paper's curves** (0.0005 mean difference) and **(b) its ordering**: SIEVE has the
  lowest miss ratio and the highest popular object ratio at every α, as in the paper.
* **(c) the paper's hand behaviour**: no wrap for α = 0.8, 1–2 for α = 1.0 (paper: 2), 5–7 for
  α = 1.2 (paper: 7), over the same request ranges; the setup the paper does not state (1 M
  objects, a 1,000-object cache, 2^18 evictions) was recovered from its curves.

Method, reproduction and all numbers: [fig9/README.md](fig9/README.md).

| path | what |
|---|---|
| `fig9/` | scripts (`sieve_hand.c`, `run.sh`, `hand_summary.py`, `extract_paper_fig9.py`, `plot_fig9.py`, `build.sh`), figures, README |
| `results/fig9ab_raw.tsv` | (a), (b): every run (seed, α, algorithm, miss ratio, popular object ratio) |
| `results/fig9_comparison.csv` | (a), (b): every point, paper vs replication |
| `results/fig9c_summary.tsv`, `results/fig9c_hand_s1.tsv` | (c): per seed and α (wraps, timings); seed 1's curves |
| `paper/fig9_paper_values.csv` | the values extracted from the paper's Figure 9 |
| `external/fig8` | the Figure 8 replication (simulator, Zipf generator, popular-ratio tool), pinned |
