#!/usr/bin/env python3
"""Choose, for each of the 54 Twitter clusters, which official version to simulate.

The CMU mirror has three versions of each cluster: full, sample10 (10% of objects) and
sample100 (1% of objects), both made with spatial sampling. Exact counts for sample100 come
from trace_stats.py. Counts for the other versions are estimated by scaling: x10 and x100.

Limits (see README.md for how they were measured):
    N_MAX = 1e9 requests per run   -> each run takes < 2 h (measured: 0.5-0.7 M req/s)
    F_MAX = 30e6 objects           -> peak memory fits in 11 GB
    F_MIN = 5e5 objects            -> the small cache (0.1%) holds >= 500 objects; below this,
                                      sampling changed reductions by up to 0.11 (results/validation)

Rule:
    1. Take the least-sampled version whose whole trace is within N_MAX and F_MAX.
    2. If its footprint is below F_MIN, the small cache would be degenerate (a few objects).
       Instead, take the least-sampled version within F_MAX and simulate only its first N_MAX
       requests.
    3. If even sample100 is over a limit, use sample100. Over F_MAX: sample it further inside
       cachesim (-s 1/k, the smallest integer k that brings the footprint under F_MAX).
       Over N_MAX: cap it at N_MAX requests.

usage: choose_twitter.py <sample100_stats.tsv>  -> TSV on stdout:
    cluster  version  extra_sample  max_req  est_req  est_obj  reason
"""
import math
import sys

N_MAX, F_MAX, F_MIN = 1_000_000_000, 30_000_000, 500_000
LEVELS = [("full", 100), ("sample10", 10), ("sample100", 1)]

print("cluster\tversion\textra_sample\tmax_req\test_req\test_obj\treason")
for line in open(sys.argv[1]):
    path, n_req, n_obj, _ = line.split("\t")
    cluster = path.rsplit("/", 1)[-1].split(".")[0]
    n_req, n_obj = int(n_req), int(n_obj)
    est = {v: (n_req * f, n_obj * f) for v, f in LEVELS}
    whole = [v for v, _ in LEVELS if est[v][0] <= N_MAX and est[v][1] <= F_MAX]
    extra = 1
    if whole and est[whole[0]][1] >= F_MIN:
        v, cap, why = whole[0], -1, "whole trace"
    elif whole:
        v = next(v for v, _ in LEVELS if est[v][1] <= F_MAX)
        cap = N_MAX if est[v][0] > N_MAX else -1
        why = (f"{whole[0]} footprint {est[whole[0]][1]} < {F_MIN}; "
               f"{v}" + (f" first {N_MAX} req" if cap > 0 else " whole trace"))
    else:
        v, why = "sample100", []
        r, o = est[v]
        if o > F_MAX:
            k = math.ceil(o / F_MAX)
            extra = round(1 / k, 6)
            r, o = r // k, o // k
            why.append(f"sample100 footprint > {F_MAX}: extra -s 1/{k}")
        cap = N_MAX if r > N_MAX else -1
        if cap > 0:
            why.append(f"first {N_MAX} req")
        print(f"{cluster}\t{v}\t{extra}\t{cap}\t{min(r, N_MAX)}\t{o}\t{'; '.join(why)}")
        continue
    r, o = est[v]
    print(f"{cluster}\t{v}\t{extra}\t{cap}\t{min(r, N_MAX) if cap > 0 else r}\t{o}\t{why}")
