# Cross-check results: an independent re-run of Figures 8-11 and a comparison of Figures 3-5

Results of an independent re-run and comparison, added **as a branch for review**; nothing in the existing figures was changed. This folder holds only result tables and figures: no code, no traces; the scripts that produced them can be provided on request.

**What was done.** Your repository (commit `43fc450`) was cloned and its result tables imported; none of its code was run. We then re-ran Figures 8, 9, 10 and 11 with our own generator (NumPy PCG64, seeds 42-44) and our own build of the same pinned simulator (artifact `0861f82`), and compared everything else from your saved tables. The two pipelines share the simulator source and the GitHub account, so agreement shows reproducibility of the pipeline, not independence of the simulator; the paper's plotted values are the independent anchor.

## What it says about your figures

* **Figure 8a is confirmed.** At 10,000 objects and 10 M requests our runs are within 0.0008 of the paper at all 24 ARC/LRU/SIEVE points (`results/figure8a_10k_objects_vs_paper.csv`). Our earlier 1 M-object runs were 0.1-0.27 too low (`figures/fig08c_zipf_support_1M_vs_10k.png`), so the workload size you found was the missing piece.
* **Figure 9a is confirmed** within 0.002 (`figure9a_10k_objects_miss_ratio.csv`); SIEVE is lowest at every skew. **9b** matches the ordering with an average gap of 0.011. **9c** reproduces with your setup (1 M objects, 1,000-object cache, cut at the 262,144th eviction): wraps 0 / 1-2 / 5-7 over three seeds (`hand_summary.csv`). Sampling the hand every 250 requests missed wraps at alpha 1.2; every 10 requests worked. That setup was found by searching against the paper, so it shows reproducibility, not prediction.
* **Figure 8b** with the other averaging choices (second half, end value) and a generating-rank popular set: all differ from the paper by 0.018-0.022 on average, so none explains the residual (`popular_ratio_averaging_variants.csv`).
* **Figure 10** at the 10,000-object support (`steady_state.csv`, `paper_comparison.csv`, `figures/fig10c_workload_change_10k_objects.png`): policy order, LFU never recovering and SIEVE's post-switch dip match the paper; SIEVE's miss-ratio bump is larger (0.24 vs about 0.18). The 3,000-object cache is the one fitted parameter.
* **Figure 11 does not use 10,000 objects**: all 18 miss ratios printed over the paper's bars equal 1 M-object / 100 M-request runs at two decimals (`figure11_printed_miss_ratio_check.csv`).
* **Figure 4:** on the 96 cells both of us ran (Meta CDN, Meta KV trace 1, Wiki 2019t) deterministic policies agree to 0.0001; LHD and CACHEUS (random) to 0.0045 and 0.0164 (`fig4_ours_vs_theirs.csv`). Mapping-free check against the paper's dots: all 26 of your SIEVE points are within 0.0001 (`fig4_theirs_vs_paper_dots.csv`). The pinned TinyLFU differs from the paper's in both pipelines (23 cells, up to 0.05).
* **Figure 5:** 7 of 8 public-dataset bars equal the paper's; Tencent large differs through one CACHEUS cell (0.1150 vs SIEVE 0.1146) on the 10% sample (`fig5_theirs_vs_paper.csv`).
* **Figure 3:** overlap on clusters 3, 7, 8, 10, 13, 21 agrees to 0.0014 except SIEVE on the 1%-sampled cluster 13 at the small cache (0.0052) (`fig3_twitter_overlap.csv`).

## Things worth checking in your pipeline

* Reductions computed from four-decimal miss ratios are noisy on low-miss-ratio traces (cluster 3 at 10%: ARC 0.1893 from rounded ratios vs 0.1909 from exact counters), and Twitter ties in Figure 5 are partly rounding artifacts. Exact counters (`SIEVE_COUNTERS` lines) avoid this.
* For files of 1 GiB or more the simulator's working-set estimate is sampled and ran 0.1-0.2% above the exact count (cluster 33: 1,910,084 vs 1,907,377 objects); capacities derived from it differ slightly from floor(exact x fraction). The effect on your Meta KV and Wiki cache sizes was below 0.0001 in miss ratio on the cells compared.
* Wiki request totals (5,667 M) do not match the paper's Table 1 (2,863 M); unresolved on both sides.

## Additional Twitter clusters (our own runs on the authors' sample files)

17 clusters that neither pipeline had covered: sample100 for 37, 40, 43, 46, 52, 54 and 27; sample10 for 25, 28, 30, 33, 34, 36, 42, 44, 47, 51; 12 policies x 2 cache sizes, 407 of 408 runs (`sample100_extension.csv`, `sample10_extension.csv`, `omitted.csv`). Clusters 29, 41 and 32 were excluded by a memory gate. Together with your 24 clusters and our full-size ones the union is 44 clusters (10% cache) and 45 (0.1%): rank correlation of the 11 algorithms' means with the paper **0.99 / 0.98**, SIEVE mean 0.167 / 0.097 (paper 0.153 / 0.083), TinyLFU and Hyperbolic now close to the paper's means (`fig3_twitter_means.csv`, `figures/fig03c_twitter_means_three_sets.png`). These are spatial samples and are labelled so.

`ghost_heldout*_verdict.csv` belong to a separate study of a SIEVE variant (ghost-informed insertion) and are included only for completeness.
