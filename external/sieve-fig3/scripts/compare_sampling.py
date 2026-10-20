#!/usr/bin/env python3
"""Compare miss ratio reductions of the same Twitter cluster at 10% and 1% spatial sampling.

usage: compare_sampling.py results/validation -o results/validation/sampling_check.csv

For each cluster, cache size and algorithm, prints the reduction at sample10 and at sample100
and their difference. It also prints, per cluster and size, the cache size in objects and
SIEVE's rank among the 11 non-FIFO algorithms at each sampling level.
"""
import argparse
import glob
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from parse_logs import parse  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    rows = []
    for p in glob.glob(os.path.join(a.dir, "*.s10.log")):
        q = p.replace(".s10.log", ".s100.log")
        if not os.path.exists(q):
            continue
        cl = os.path.basename(p).split(".")[0]
        for lvl, path in (("s10", p), ("s100", q)):
            for r in parse(path):
                rows.append(dict(cluster=cl, level=lvl, size=r["size"], algo=r["algo"],
                                 reduction=r["reduction"], cache_obj=r["cache_size_obj"]))
    df = pd.DataFrame(rows)
    wide = df.pivot_table(index=["cluster", "size", "algo"], columns="level",
                          values="reduction").reset_index()
    wide["diff"] = wide["s100"] - wide["s10"]
    wide.round(4).to_csv(a.out, index=False)

    cache = df.pivot_table(index=["cluster", "size"], columns="level", values="cache_obj",
                           aggfunc="first")
    others = df[df.algo != "FIFO"].copy()
    others["rank"] = others.groupby(["cluster", "size", "level"])["reduction"].rank(
        ascending=False, method="min")
    sieve = others[others.algo == "SIEVE"].pivot_table(index=["cluster", "size"],
                                                       columns="level", values="rank")
    summ = cache.add_prefix("cache_obj_").join(sieve.add_prefix("sieve_rank_"))
    absdiff = wide.groupby(["cluster", "size"])["diff"].apply(lambda s: s.abs().mean())
    summ["mean_abs_diff"] = absdiff
    pd.set_option("display.width", 200)
    print(summ.round(4).to_string())
    print("\nmean |diff| by size:", wide.groupby("size")["diff"].apply(lambda s: s.abs().mean())
          .round(4).to_dict())


if __name__ == "__main__":
    main()
