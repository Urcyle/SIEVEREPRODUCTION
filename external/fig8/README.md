# SIEVE (NSDI'24) Figure 8: a replication

This repository reproduces **Figure 8** of
*SIEVE is Simpler than LRU: an Efficient Turn-Key Eviction Algorithm for Web Caches*
(Zhang et al., NSDI'24): the miss ratio (a) and popular object ratio (b) of LRU, LFU, ARC and
SIEVE over cache size, on a synthetic Zipfian workload (α = 1.0).

![Paper vs replication](fig8/fig8_side_by_side.png)

* **(a) Miss ratio: the paper's curves.** With the workload the paper's values point to (the
  artifact's own Zipf generator, 10,000 objects, 10 M requests), LRU, ARC and SIEVE agree with
  the paper to 0.0014 or better at all 8 cache sizes.
* **(b) Popular object ratio: the paper's ordering** at 7 of 8 sizes (SIEVE highest from 1% up),
  values within 0.02 on average; the paper does not say how it averaged this metric over time.

Method, reproduction and all numbers: [fig8/README.md](fig8/README.md).

| path | what |
|---|---|
| `fig8/` | scripts (`gen_trace.py`, `popular_ratio.c`, `run.sh`, `extract_paper_fig8.py`, `plot_fig8.py`, `build.sh`), figures, README |
| `results/fig8_raw.tsv` | every run: seed, algorithm, cache size, miss ratio, popular object ratio |
| `results/fig8_comparison.csv` | every point: paper vs replication |
| `paper/` | the paper and the values extracted from its Figure 8 |
| `external/NSDI24-SIEVE` | the authors' artifact (simulator), pinned at `0346336` |
