# Comparison with the SIEVEREPRODUCTION repository (2026-10-20)

**What this is.** [Urcyle/SIEVEREPRODUCTION](https://github.com/Urcyle/SIEVEREPRODUCTION) (commit `43fc450`) reproduces Figures 3c/3f, 4, 5, 8 and 9 with its own code, its own run set and its own reading of the paper's PDF. This page compares it with this repository, says what we adopt, and lists what is still missing. Everything below is regenerated from saved files by `python3 -B scripts/compare_independent_replication.py compare` (no simulation); the numbers are in `local_results/independent_replication/`.

**How independent it is.** Different code base, different run set, different trace-preparation path (it uses sampled and truncated Twitter/Tencent copies, we use full files), and its own extraction of the paper's plotted values. Not independent in authorship (same GitHub account) and not in simulator source (both use the authors' artifact `0861f82`; theirs plus a three-file build-fix patch). So agreement on deterministic policies shows that two pipelines produce the same numbers from that simulator; the independent anchor is the paper's own plotted values.

**What was imported.** A snapshot of 31 small files (result tables, paper-value extractions, side-by-side figures, READMEs, the build-fix patch; 1.3 MB) in `external_replication/sievereproduction_43fc450/`, with a SHA-256 manifest. No code from that repository was run, and no traces were copied. See `external_replication/README.md`.

## Scoreboard: paper, SIEVEREPRODUCTION and our work, with the reason for every disagreement (updated 2026-10-23)

"Theirs" is SIEVEREPRODUCTION. A figure counts as aligned when the three agree within the paper's own readability (about 0.001-0.003 for read-off values).

| Figure | Paper vs theirs | Paper vs ours | Ours vs theirs | Why they differ, and how we know |
|---|---|---|---|---|
| 3c/3f Twitter | their 24 scaled clusters: rank correlation of means 0.96 / 0.98 | our own 5-7 full-size clusters alone: SIEVE mean 0.10 / 0.00 (paper 0.153 / 0.083); with their 24 plus 23 more sampled clusters we ran: 0.99 / 0.98 over 47-48 | overlap (clusters 3, 7, 8, 10, 13, 21) within 0.0014 except SIEVE on a 1%-sampled cluster (0.0052) | trace set size and sampling; tested by adding clusters (sample extensions) and the union converges on the paper |
| 4 per-trace, deterministic policies | 26 of 26 SIEVE points within 0.0001 | same on the 5 traces we hold | within 0.0001 on 96 shared cells | aligned |
| 4 TinyLFU | off by up to 0.05 | off by the same amount | identical | **explained**: the pinned artifact has upstream fix 759f4ca; a build without it matches the paper on all 8 Meta CDN/Wiki cells (<=0.0005), on all five Meta KV large-cache cells (<=0.0018) and on Meta KV small traces 2 and 4. Meta KV trace 1 at 0.1% was split only because our exact capacity (16,984) sits across a sketch-size jump from the simulator's (16,982): at the simulator's capacities pre-fix equals the dots (0.1397, 0.0896). Small-cache traces 3 and 5, re-run on 2026-11-06 at those capacities, are within 0.0002 of the dots (one large cell, trace 3, 0.0007 on the primary reading and 0.0004 on the second) |
| 4 CACHEUS / LHD | default (clock-seeded) draw matches the paper exactly in 37 of 48 cells, off in a few (e.g. CACHEUS `wiki_2019u` large 0.128) | our fixed seeds are other draws, hence more differences | up to 0.016 | the artifact seeds its generator from the clock (`srand(time(NULL))`); CACHEUS on `meta_rnha` is bimodal across 8 seeds with the paper's value the common outcome (0.0148 at 0.1%, 0.0482 at 10%); declared range rule narrowly failed at the small cache; other disagreeing cells' traces not held |
| 5 | 7 of 8 public bars equal the paper's; Tencent large flips (CACHEUS 0.1150 vs paper 0.0825 on `tencent_photo2`) | our own Fig 5 uses 5 or 11 candidates on 7-23 traces | not comparable | our own tests (`docs/tencent_full_protocol.md`, outcome): the flip is **not** a seed draw. On `tencent_photo2` at the large cache CACHEUS gives 0.1150 on all nine seeds (SIEVE 0.1148), and full-size runs agree with the 10% sample (median gap about 0.0002). Why the paper's CACHEUS dot is 0.0825 remains open |
| 8a, 9a | match to 0.0014 / 0.003 | **match to 0.0008 / 0.002 at 10,000 objects** (our first 1 M-object design was 0.1-0.27 low) | agree | workload size was the whole gap (their finding, re-verified) |
| 8b, 9b | residual about 0.02 | residual about 0.02 (0.011) | agree to 0.005 | not the averaging, not the popularity definition, not the seed (all tested); left open |
| 9c | wraps 0 / 1-2 / 5-7 | same with their setup | agree | setup found by search; sampling every 250 requests misses wraps |
| 10 | not run | order, LFU failure and SIEVE dip match; SIEVE bump larger | n/a | the bump is the plotting interval (500,000-request averages give the paper's bump heights) |
| 11 | not run | 18 of 18 printed miss ratios equal at 1 M objects | n/a | Fig 11 uses 1 M objects, Fig 8 uses 10,000 |
| 12 | not run | ARC-SIEVE loses on our 7-file mean; TwoQ-SIEVE is level; LeCaR-SIEVE gains at 10% once our wrap bug is fixed | n/a | trace mix plus a promotion mechanism (ARC), and a bug of ours found by a failed control (LeCaR); on CDN/Wiki traces all three beat their LRU originals as in the paper |
| 1, 2, 6, 7, 13, 14, Tables | not run | partial / adaptation / not replicated | n/a | proprietary traces or CacheLib; see the coverage matrix |

## Result in one table

| Paper item | Before | After comparison | Evidence |
|---|---|---|---|
| Fig 8a miss ratio vs size | not replicated: our curves 0.1-0.27 lower than the paper's | **replicated**: all 24 ARC/LRU/SIEVE points within 0.0008 of the paper, SIEVE lowest from 0.3% up, the paper's order at 8 of 8 sizes | cause was the workload size: 10,000 objects, not 100,000-1,000,000 |
| Fig 8b popular object ratio | partial (ordering only) | partial: values within 0.02 on average (largest 0.09 at the smallest cache), the paper's full order at 4 of 8 sizes (theirs 6 of 8); SIEVE highest from 1% up | the averaging over time is unstated in the paper |
| Fig 9a miss ratio vs skew | scaled study; SIEVE tied LFU at 1.4 and trailed ARC at 1.6 | **replicated**: within 0.002 of the paper at all 32 points; SIEVE lowest at every skew | the earlier "SIEVE trails ARC at 1.6" was a scale artifact |
| Fig 9b popular ratio vs skew | scaled, partial | partial: SIEVE highest at every skew, full order at 6 of 8, values within 0.03 | as 8b |
| Fig 9c hand position | sampled series at another scale | **replicated with a transplanted setup**: wraps 0 / 1-2 / 5-7 (paper 0 / 2 / 7); curve ends at 317.6-317.9 k and 518-520 k requests (paper 317.5 k, 519.3 k) | the setup was found by search against the paper, so this shows reproducibility, not prediction |
| Fig 4 per-trace scatter | 7 traces, 4 policies on Meta KV, no Tencent | **all 13 public traces x 11 algorithms exist** (their data); deterministic policies agree with ours to 0.0001 on 96 shared cells | 26 of 26 SIEVE points within 0.0001 of a paper dot |
| Fig 5 best algorithm per dataset | 7 traces, 5 or 11 candidates | 7 of 8 public-dataset bars equal the paper's (their data); Twitter close | Tencent large differs (SIEVE 1/2 vs 1) |
| Fig 3c/3f Twitter box plots | 5-7 clusters with all 11 algorithms | their 24 clusters (scaled) plus our full-size clusters plus 17 new sampled clusters give 44 (10%) / 45 (0.1%); rank correlation of means with the paper 0.96 / 0.98 (theirs), 0.99 / 0.98 (union) | trace set matters: our 5-7 full-size clusters alone give SIEVE means 0.10 / 0.00 against the paper's 0.153 / 0.083 |
| Fig 3 a, b, d, e (CDN1, CDN2) | proprietary | still proprietary | not obtainable |

Net change in status: Figures 8a and 9a become replicated; 9c is replicated only with a setup found by search; 8b and 9b stay partial; the Fig 4 / 5 / 3 items stay partial in our own runs but gain full-coverage evidence from the imported snapshot (not our runs).

## Figure 8 and 9: the workload size was the missing piece

The paper does not state its Zipf workload size. The other repository found that **10,000 objects and 10,000,000 requests** reproduce Figure 8a, by testing three candidates from the authors' artifact. We did not take that on trust:

* We generated our own 10,000-object streams (NumPy PCG64, seeds 42-44, `sieve_repro.zipf.generate_zipf`) and ran our own counter build of the pinned simulator: `python3 -B scripts/zipf_support_check.py run` (180 runs, exact integer counters in `local_results/zipf_support_check/runs.csv`).
* **Figure 8a**, mean of three seeds against the paper's plotted values (`figure8a_10k_objects_vs_paper.csv`): LRU 0.8691 vs 0.8691 at 0.1%, SIEVE 0.7381 vs 0.7381 at 0.1%, 0.4881 vs 0.4886 at 1%, 0.0273 vs 0.0273 at 80%. All 24 ARC, LRU and SIEVE points are within 0.0008; LFU is within 0.0020 except at 0.1% (+0.013) and 1% (+0.007), where seeds spread by 0.02 and 0.006.
* Our earlier 1,000,000-object, 100,000,000-request study gave LRU 0.597 at 0.1% against the paper's 0.869. The sampler, the seed and the RNG did not matter (we had tested all three); the support size did. Cache sizes are fractions of the working set, so a bigger support at the same fractions changes the miss ratio a lot. Companion figure: `local_results/paper_figures/fig08c_zipf_support_1M_vs_10k.png`.
* **Figure 9a** at 10,000 objects and a 1,000-object cache: within 0.0018 of the paper at all 32 points. SIEVE is lowest at every skew from 0.2 to 1.6; our earlier scaled study had SIEVE tied with LFU at 1.4 and behind ARC at 1.6. That earlier result was a property of its scale (100,000 objects against a fixed 10,000-object cache), not evidence about the paper's claim.
* **Figure 8b / 9b** with our observer build (`zipf_support_check.py popular`; miss counts equal the counter build on all 180 runs): Figure 8b differs from the paper by 0.020 on average (median 0.013, 23 of 32 points within 0.02; largest 0.09 at the 0.1% cache, where one object is 10% of a 10-object cache); Figure 9b by 0.011 on average (largest 0.028). Our values and the other repository's differ by 0.005 on average (largest 0.06, LFU at a small cache), and both differ from the paper in the same places, so the residual is the unstated averaging, not the code.
* **Figure 9c**: the setup (1,000,000 objects, a 1,000-object cache, curves cut at the 262,144th eviction) was found by the other repository by searching until the paper's behaviour appeared; with the first setups tried, the hand moved the opposite way. We transplanted it and re-ran with our generator, seeds and the observer build sampling every 10 requests (`zipf_support_check.py hand`). It reproduces the paper's pattern (table below), but a setup chosen after the fact cannot count as a prediction.

| Figure 9c | alpha 0.8 | alpha 1.0 | alpha 1.2 |
|---|---|---|---|
| wraps, paper | 0 | 2 | 7 |
| wraps, ours (seeds 42-44) | 0, 0, 0 | 2, 1, 1 | 7, 5, 5 |
| hand first above 0.9, paper | ~204 k requests | ~95 k | ~92 k |
| hand first above 0.9, ours | 201-206 k | 96-100 k | 92-106 k |
| curve ends, paper | ~317.5 k | ~519.3 k | no ticks |
| curve ends, ours | 317.6-317.9 k | 517.8-520.0 k | 1.387-1.391 M |

A first attempt sampled the hand every 250 requests and found 0-1 wraps at alpha 1.2; the hand re-climbs within a sample at that skew, so a wrap is invisible at a coarse cadence. We kept the 10-request cadence and recorded the failed cadence here and in `scripts/zipf_support_check.py`.

What this does **not** show: that the paper really used 10,000 objects. The match is strong (24 of 24 non-LFU points to 0.0008, and the paper's own alpha = 1.0 points in Figure 9 equal its Figure 8 values at 10%), but the paper never states the size.

## Figure 4: every public trace now has numbers

On the 96 (trace, size, algorithm) cells that both repositories ran (`fig4_ours_vs_theirs.csv`: Meta CDN 3 traces, Meta KV trace 1, Wiki 2019t; 11 algorithms; 2 sizes; stochastic and deterministic):

| algorithm | largest absolute difference in miss ratio |
|---|---|
| SIEVE, ARC, LRU, CLOCK, TwoQ, LIRS, Hyperbolic, TinyLFU, B-LRU | 0.0001 (rounding of their 4-decimal output) |
| LHD | 0.0045 |
| CACHEUS | 0.0164 |

LHD and CACHEUS draw random numbers and the artifact seeds its generator from the clock, so every run is a different draw; most cells do not depend on it, a few do. The cache sizes differ by 240 objects of 1.7 M on Meta KV trace 1 and by 1,737 of 1.84 M on Wiki 2019t (30 of the 96 cells), because their simulator estimates the working set and we count it exactly; the effect on miss ratio is within the 0.0001 above.

Against the paper (`fig4_theirs_vs_paper_dots.csv`, mapping-free: each reduction is compared with the nearest paper dot in the same panel, so it does not rely on their trace-to-dot matching): all **26 of 26 SIEVE points are within 0.0001** of a paper dot; **207 of 208** reductions of the deterministic policies other than TinyLFU (that is, excluding CACHEUS and LHD as well) are within 0.0005. The cells that are off by more are 23 TinyLFU (up to 0.05), 9 CACHEUS, 2 LHD and 1 B-LRU. The TinyLFU gap is shared by both repositories and is **explained**: the pinned artifact contains upstream fix 759f4ca (frequency-sketch increment on window insertion); a build without it reproduces the paper's TinyLFU points to within 0.0005 on all eight Meta CDN and Wiki cells; and for Meta KV trace 1 too once the capacities are the paper simulator's: at 16,982 and 1,698,213 objects it gives 0.1397 and 0.0896, equal to the paper's dots, while at our exact capacity of 16,984 the small-cache result jumps by 0.007 (TinyLFU's sketch is sized from the capacity) (`docs/tinylfu_dot_check_protocol.md`, 2026-10-23). Their own trace-to-dot matching is by SIEVE's value; this check does not use it. Our own five overlapping traces give the same picture against the paper (`fig4_ours_vs_paper_dots.csv`: 77 of 96 cells within 0.0005; the rest are TinyLFU, LHD, CACHEUS and three Meta KV trace 1 cells at 0.0006-0.0007, where the cache sizes differ).

Their request totals agree with the paper's Table 1 for Meta KV (1,645 M vs 1,644 M), Meta CDN (231 M) and Tencent Photo (5,649 M vs 5,650 M) and disagree for Wiki (5,667 M vs 2,863 M); they say so and we cannot resolve it. They ran Tencent Photo on a 10% spatial sample (`cachesim -s 0.1`) because the files are 35-37 GB; that is the weakest point of their Fig 4 and Fig 5: on Tencent photo2 at the large cache their CACHEUS beats SIEVE by 0.0004 (0.1150 vs 0.1146) where the paper has SIEVE first, and that one stochastic cell turns Tencent's large-cache bar from 1 to 1/2.

Meta KV mapping, resolved by their repository: the paper's five Meta KV traces are the five `202206` Meta S3 traces (`kvcache_traces_1..5`). Our `metakv_202206` file is those five concatenated and our `metakv_trace1_candidate` is `kvcache_traces_1`; our earlier Fig 4 Meta KV points used non-equivalent traces except trace 1. Their five per-trace results supersede those points; ours remain valid for trace 1 (`fig4_ours_vs_theirs.csv`).

## Figure 5

Their bars come from their per-trace results (`fig5_theirs_vs_paper.csv`). Seven of the eight public-dataset bars are the paper's exactly (Meta KV, Meta CDN, Wiki, and Tencent small). Tencent large differs (SIEVE 1/2 against 1, from the CACHEUS cell above). Twitter (24 sampled clusters against the paper's 53) is within 0.05 at the large cache and 0.09 at the small, each cluster being 4% of a bar.

One weakness to keep in mind: they compute reductions from miss ratios printed to four decimals. On low-miss-ratio traces this makes the reduction noisy (cluster 3 at 10%: their ARC reduction 0.1893, ours 0.1909 from exact counters, with equal four-decimal miss ratios), and ties on Twitter, which they break by the paper's plotting order, are partly rounding artifacts (12 of 48 trace-size cases tie). Means are barely affected; exact winner counts on Twitter are.

## Figure 3c / 3f

Their 24 clusters are clusters 1-24 as sampled (`sample10`, `sample100`) or prefix-truncated copies (first 1 B requests); see their `twitter_choice.tsv` for each cluster. Where both repositories ran the same cluster (3, 7, 8, 10, 13, 21; 88 cells, `fig3_twitter_overlap.csv`):

| cluster | their trace | largest miss-ratio difference |
|---|---|---|
| 3, 7 | full | 0.0014 (CACHEUS, random); 0.0004 (LHD) at most for the rest |
| 8 | first 1 B of 1.30 B requests | 0.0006 |
| 10 | 10% sample | 0.0004 |
| 13 | 1% sample | 0.0003 at 10%; 0.0052 for SIEVE at 0.1% (0.6337 vs 0.6285) |
| 21 | 1% sample | 0.0025 at 0.1% (all policies shifted by +0.002) |

Spatial sampling at 1% distorts clusters with tiny working sets at small caches, and SIEVE is the policy most sensitive to it. Their ranking of algorithms still correlates with the paper's at 0.96 (10%) and 0.98 (0.1%); adding our full-size clusters (26, 49, 50, plus 45 and 53 at 0.1%) and the 17 new sampled clusters (see below) gives 0.99 and 0.98 over 44 and 45 clusters. The position of SIEVE moves with the trace set: mean reduction 0.150 (24 clusters) / 0.167 (44) at 10% against the paper's 0.153, and 0.085 (24) / 0.097 (45) at 0.1% against 0.083.

Our own complete sets alone (5 clusters at 10%, 7 at 0.1%, full size) give SIEVE means of 0.103 and 0.002, far below the paper's, because they include clusters where SIEVE does badly at tiny caches (49, 50; the tiny-cache behaviour discussed in `docs/sieve_variants_report.md`). That is a statement about those clusters, not about the paper; the paper's average over 53 clusters is not reachable with our 5-7.

### Twitter sample extensions (new clusters, our own runs)

To widen Twitter coverage we ran the authors' spatial samples for 17 clusters that neither repository had covered, in two batches with protocols frozen before downloading ([sample100](twitter_sampled_extension_protocol.md): clusters 37, 40, 43, 46, 52, 54, 3.4 GB; [sample10](twitter_sample10_extension_protocol.md): clusters 25, 28, 30, 33, 34, 36, 42, 44, 47, 51 as 10% samples and 27 as a 1% sample, 27 GB). **407 of 408 exact-counter runs completed** (12 policies x 2 cache sizes x 17 clusters, minus the cases below); results are in `local_results/twitter_sampled_extension/` and `local_results/twitter_sample10_extension/`. Omitted by rule: clusters 29 and 41 (about 25 M objects) and 32 (35.6 M objects) by the memory gate, cluster 27's sample10 file by the size rule, and CACHEUS on cluster 25 at the 0.1% cache, which crossed the 12 GiB live-RSS guard on every attempt even with 12-14 GB free (a real blow-up, not a shortage). Cluster 25 therefore has 11 of 12 algorithms at 0.1% and is left out of that panel's union. Amendments (all before using a result): batch 1 memory estimate and worker count; batch 2 exact capacities (the simulator's working-set estimate is sampled on files of 1 GiB or more and ran 0.1-0.2% high), core policies run through the seeded-baselines runner, a lower memory estimate (1 GiB + 100 bytes per object), retries of runs the available-memory gate had omitted.

These are **sampled** traces, labelled as such. In the union of 47 clusters (10% cache) and 48 (0.1% cache; 2026-10-25, after CACHEUS ran on clusters 29, 41 and 32 and let them join), the rank correlation of the 11 algorithms' means with the paper's is **0.991 / 0.982**, and two algorithms the smaller sets had wrong come into line with the paper: TinyLFU 0.057 (paper 0.069; their 24 clusters alone gave 0.118) and Hyperbolic 0.033 (paper 0.026; 0.071) at the large cache. CACHEUS 0.134 / 0.088 (paper 0.131 / 0.087). SIEVE's mean is 0.160 at 10% (paper 0.153) and 0.093 at 0.1% (paper 0.083), a little above the paper's: at 10% LHD (0.185) > SIEVE (0.160) > LIRS (0.159) > TwoQ (0.159) > ARC (0.150), at 0.1% LHD (0.160) > TwoQ (0.140) > ARC (0.105) > SIEVE (0.093). The paper also has LHD first and SIEVE ahead of ARC at 10%, and ARC ahead of SIEVE at 0.1% (0.099 vs 0.083). So the trace-set dependence of SIEVE's rank is real and our larger Twitter sample moves the picture toward, not away from, the paper's.

## Follow-up checks (same day): Figures 10 and 11, and the Figure 8b averaging

**Figure 11 does not use the 10,000-object support.** The paper prints a miss ratio above each bar. Our saved 1,000,000-object, 100,000,000-request runs equal **all 18 printed values at two decimals** (`scripts/fig11_printed_miss_check.py`, `local_results/instructions/figure11_printed_miss_ratio_check.csv`; for example LRU/FIFO/SIEVE 0.22/0.25/0.18 at alpha 1.0 and the large cache). So Figure 11 was run at 1M objects and Figure 8 at 10,000: the paper's synthetic figures do not share one workload size, and nothing needed re-running for Figure 11. Instruction counts themselves still differ in level from the paper (different CPU and counting window; see `docs/instructions_report.md`).

**Figure 10 at the 10,000-object support** (`scripts/zipf10_support_check.py`, `local_results/zipf10_support_check/`, figure `fig10c`). Two disjoint 10,000-object alpha 1.0 phases of 5M requests, caches of 1,000-4,000 objects (declared before running), 100,000-request intervals, two seed pairs. The cache size is the one fitted choice: 3,000 objects is the grid point whose LRU plateau (0.175) is nearest the paper's (about 0.188 read by eye; interpolation puts it near 2,800). Not fitted, and matching the paper's picture:

| | paper (read by eye, +/-0.01) | ours at 3,000 objects |
|---|---|---|
| phase-1 miss ratio ARC / LRU / LFU / SIEVE | 0.165 / 0.188 / 0.155 / 0.150 | 0.162 / 0.175 / 0.146 / 0.132 |
| phase-1 popular ratio SIEVE / LFU / ARC / LRU | 0.75 / 0.71 / 0.65 / 0.54 | 0.83 / 0.73 / 0.64 / 0.59 |
| LFU after the switch | miss ratio off the plot, popularity 0 | 0.98, 0.0003 |
| SIEVE popularity one interval after the switch | dips to about 0.70 | 0.70 |
| ARC / LRU popularity after the switch | no visible dip | none |
| SIEVE miss-ratio bump after the switch | about 0.18 | 0.24 (larger than the paper's) |

The order of the policies and the unusual features (LFU never recovering, SIEVE alone dipping and then climbing past its earlier level) are reproduced; miss-ratio levels are within 0.02 (SIEVE 0.018, LRU 0.013 lower); popularity levels are within 0.05 except SIEVE's (0.08 higher), and SIEVE's post-switch bump is larger. This is better than our 1,000,000-object version (`fig10`), where ARC and SIEVE had equal plateaus (the paper has SIEVE 0.02 lower). We keep both figures; neither is more than a plausible scale for a paper that does not state it. Status of Figure 10 stays **partial-to-replicated with an inferred scale**.

**Why SIEVE's bump after the switch is larger here (0.24) than in the paper (about 0.18), post-hoc.** The bump is an average over one plotting interval, and the extra misses of refilling the cache are spread over it, so its height scales with 1 / interval. We used 100,000 requests; the paper's interval is unstated. Averaging our own samples over longer intervals (`local_results/zipf10_support_check/bump_vs_interval.csv`, no new runs): at 500,000 requests SIEVE's bump is +0.033, LRU's +0.003, ARC's +0.006, against about +0.035, +0.005 and +0.01 read by eye from the paper; at 100,000 requests they are +0.107, +0.011, +0.025. So an interval of roughly 4-5 times ours (equivalently, a cache about 4-5 times smaller relative to the interval) gives the paper's bump heights for all three policies at once, and the explanation is the plotting interval, not the algorithm. The SIEVE-to-LRU bump ratio (about 10 at 100,000, about 11 at 500,000, paper about 5-7) does not pin the interval exactly; the scale of the paper's workload remains unknown.

**Figure 8b averaging and popularity definition do not explain the residual.** `popular_ratio_averaging_variants.csv` compares the mean over the whole trace, the second half, and the value at the end (SIEVEREPRODUCTION's three variants and ours) and a generating-rank definition of the popular set against the paper's 32 points: mean absolute differences 0.018-0.022 in every variant, the end-of-trace value being slightly worse (0.022) and the generating-rank hot set no better (0.020 against 0.020). Seed spread is about 0.01 at most points, so the residual is not seed noise either. The largest single disagreements are at the smallest caches (one object is 10% of a 10-object cache) and the paper's own SIEVE curve is non-monotone (0.822 at 1%, 0.787 at 3%, which none of our variants reproduces; ours is 0.775 and 0.802). We leave Figures 8b and 9b at partial and do not chase the residual further.

## What we adopt, and what we do not

* Adopted as supporting evidence, clearly labelled: their Fig 4 and 5 per-trace tables (full coverage of the public traces), their 24 Twitter clusters (scaled), their Fig 8/9 paper-value extractions (hollow markers in `fig08`, `fig09`; our own digitization of Fig 8a is kept and agrees).
* Not adopted: any of their claims of exactness beyond what the files show; their Tencent 10%-sample result as a statement about full Tencent traces; their Fig 9c setup as an independent prediction.
* Ours stays authoritative for: everything beyond their scope (variants, throughput, byte miss ratio, Figure 12, Table 2/3 audit, Figure 7, Figure 10/11, full-size Twitter clusters 26, 45, 49, 50, 53).

## Findings about our own earlier results

1. **Figure 8a "not replicated" was our workload, not the paper.** The statement in `docs/accuracy_audit.md` that all local means sit below the paper's and that the sampler does not explain the gap is superseded: the workload size explains it.
2. **Figure 9a "SIEVE ties LFU at 1.4 and trails ARC at 1.6" is retracted** as a statement about the paper; it holds only at our earlier scale.
3. Figure 10 (workload change) was also run at 1,000,000 objects and a 100,000-object cache. Its paper scale is likewise unstated; if it shares Figure 8's 10,000-object support, our curves would change. Not rerun yet (see below).
4. Our Fig 4 cache sizes use exact working sets; the paper's simulator uses an estimate. Differences are 0.1% in size and below 0.0001 in miss ratio on the traces compared.

## Still missing, in priority order

1. ~~Figure 10 and 11 at the 10,000-object support~~ done above (Figure 11 needed no rerun).
2. **Twitter clusters 25-54**: 30 of the 30 now have a result from us (17 sampled files, 10 full-size, and clusters 29, 41, 32 run later without CACHEUS, so they are outside the 11-algorithm means); clusters 1-24 are covered only by SIEVEREPRODUCTION's scaled runs.
3. **Tencent Photo at full size** (two files of 35-37 GB): only their 10% spatial sample exists; one stochastic cell decides its Fig 5 bar.
4. ~~Wiki 2016u and 2019u~~ done 2026-10-25 (`docs/wiki_full_extension_protocol.md`): 22 of 24 runs per file (CACHEUS omitted by the memory gate), 32 of 32 deterministic cells within 0.0005 of theirs, SIEVE within 0.0003 of the paper's dots, pre-fix TinyLFU within 0.0004 at the simulator's capacities. The one differing winner (2019u small: TinyLFU vs the paper's LHD) is decided by TinyLFU's capacity sensitivity. The Table 1 request-count mismatch for Wiki stays unexplained: our three files total 5,666.8 M requests (2,803.5 + 2,655.6 + 207.6), equal to SIEVEREPRODUCTION's 5,667 M, while the paper's Table 1 gives 2,863 M.
5. ~~Meta KV per-trace runs of our own~~ done 2026-10-23 (`docs/metakv_split_protocol.md`).
6. ~~Figure 8b / 9b averaging~~ tested above: no variant explains the residual; left partial.
7. **CDN1 / CDN2 (Figures 1, 3a/b/d/e, 5, 12, 13)** remain proprietary. `docs/author_request_draft.md` is a ready-to-send request (not sent).
8. **Figure 6 on CacheLib** remains not replicated; our throughput study is an adaptation.
9. The SIEVE variant results (ghost-informed insertion) are on our traces; they have not been checked on their scaled Twitter set. A cheap robustness check, and a test of whether sampling changes the winner.

## Reproduce

```bash
python3 -B scripts/compare_independent_replication.py compare          # tables from the saved snapshot and our saved results
python3 -B scripts/zipf_support_check.py run && python3 -B scripts/zipf_support_check.py popular \
  && python3 -B scripts/zipf_support_check.py hand && python3 -B scripts/zipf_support_check.py summarize
python3 -B scripts/build_paper_figures.py fig03c fig04c fig05c fig08 fig08c fig09
```


## Figure 12: why ARC-SIEVE, TwoQ-SIEVE and LeCaR-SIEVE lose in our seven-file grid (code review and reproduction, 2026-10-23)

Protocol, controls and outcome: [figure12_promotion_protocol.md](figure12_promotion_protocol.md); results `local_results/figure12_promotion/`. Short version:

* **Code review.** Our ARC-SIEVE and TwoQ-SIEVE patches do what the paper's sentence says (only ARC's frequent-object queue, and TwoQ's main queue, become SIEVE) and match independent models; but an object enters that queue because it was just hit, and we insert it unvisited at the head, where SIEVE's hand reaches it first (the instant-demotion mechanism). Hypothesis H1: marking it visited removes the loss.
* **Reproduction.** A new opt-in `promote=visited` build reproduces all saved counters exactly with default parameters (8 of 8 controls) and was run on the 14 trace/capacity points (28 runs). By the rule declared before running, **H1 is not supported** (the visited variant wins on only 1-3 of 7 traces per cell).
* **What the data show instead (post-hoc split by trace family).** On the four Meta CDN and Wiki traces, ARC-SIEVE, TwoQ-SIEVE and LeCaR-SIEVE are already **at or above their LRU originals, as in the paper** (ARC 0.0495 to 0.0571 at 0.1% and 0.1133 to 0.1171 at 10%; LeCaR 0.0146 to 0.0508 and 0.0714 to 0.1111 after the correction below). On the three Twitter traces ARC-SIEVE collapses (-0.113 and -0.034 against +0.024 and +0.017 for ARC-LRU). The marked-visited variant repairs ARC's Twitter collapse (two traces carry it: cluster 26 at 0.1%, -0.340 to +0.071, and cluster 50 at 10%, -0.102 to +0.030) and loses the small CDN gain. **The LeCaR collapse (cluster 50: -0.27 and -0.51) was a bug in our own LeCaR-SIEVE patch**: after a wrap the SIEVE hand restarted at the newest object instead of the oldest (the artifact's `Sieve.c` restarts at the tail). A control (fixed expert weight 1.0 must equal plain SIEVE) failed, code review found the line, and the independent model had been written with the same rule so it could not catch it. Corrected, LeCaR-SIEVE gains over LeCaR-LRU as in the paper (CDN and Wiki, and the seven-file mean at 10%); see `docs/lecar_sieve_collapse_protocol.md`.
* **So** the disagreement with the paper is mostly the trace mix of our seven files (three Twitter traces against a CDN-dominated corpus) plus a real implementation-sensitive mechanism that the paper does not describe; it is not a coding error, and the paper's average gain (3.7% for ARC) is out of reach with these seven files.
