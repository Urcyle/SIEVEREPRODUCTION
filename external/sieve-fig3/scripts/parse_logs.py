#!/usr/bin/env python3
"""Collect miss ratios from run_trace.sh logs into one CSV, and compute miss ratio reductions.

usage: parse_logs.py <log> [<log> ...] --dataset NAME -o out.csv

One row per (trace, cache size, algorithm):
    dataset, trace, size (small|large), algo, miss_ratio, cache_size_obj, n_req,
    sample_ratio, max_req, reduction
reduction follows paper §4.1, which compares against FIFO's miss ratio on the same trace and size:
    (mr_FIFO - mr) / mr_FIFO   if mr <= mr_FIFO
    (mr_FIFO - mr) / mr        otherwise          (keeps the value in [-1, 1])
"""
import argparse
import csv
import re
import sys

# cachesim's cache name -> name in the paper's figure
NAMES = {"FIFO": "FIFO", "LRU": "LRU", "Clock": "CLOCK", "ARC": "ARC", "TwoQ": "TwoQ",
         "LIRS": "LIRS", "LHD": "LHD", "Cacheus": "CACHEUS", "Hyperbolic": "Hyperbolic",
         "WTinyLFU-w0.01-SLRU": "TinyLFU", "Sieve": "SIEVE"}
LINE = re.compile(r"^result/\S+\s+(\S+) cache size\s+(\d+), (\d+) req, miss ratio ([0-9.]+)")


def reduction(mr_fifo, mr):
    if mr_fifo == 0 and mr == 0:
        return 0.0
    return (mr_fifo - mr) / (mr_fifo if mr <= mr_fifo else mr)


def parse(path):
    trace = sample = None
    max_req = -1
    pass_name = None
    rows = []
    for line in open(path):
        if line.startswith("# trace "):
            trace = line.split()[2].rsplit("/", 1)[-1].split(".oracleGeneral")[0]
        elif line.startswith("# sample_ratio "):
            sample = float(line.split()[2])
        elif line.startswith("# max_req "):
            max_req = int(line.split()[2])
        elif line.startswith("# pass "):
            pass_name = line.split()[2]
        m = LINE.match(line)
        if m:
            name, size, n_req, mr = m.groups()
            algo = "B-LRU" if pass_name == "blru" else NAMES[name]
            rows.append(dict(trace=trace, algo=algo, cache_size_obj=int(size),
                             n_req=int(n_req), miss_ratio=float(mr), sample_ratio=sample,
                             max_req=max_req, **{"pass": pass_name}))
    if len(rows) != 24:
        sys.exit(f"{path}: expected 24 results, got {len(rows)}")
    # Label sizes within each pass. For traces over 1 GB, cachesim estimates the footprint
    # from a hash sample of object IDs; a re-run pass can then differ by a fraction of a
    # percent (e.g. cluster8: 267 vs 268 objects), so the passes are not required to match.
    for p in ("main", "blru"):
        sizes = sorted({r["cache_size_obj"] for r in rows if r["pass"] == p})
        if len(sizes) != 2:
            sys.exit(f"{path}: pass {p} has cache sizes {sizes}, expected 2")
        for r in rows:
            if r["pass"] == p:
                r["size"] = "small" if r["cache_size_obj"] == sizes[0] else "large"
    fifo = {r["size"]: r["miss_ratio"] for r in rows if r["algo"] == "FIFO"}
    for r in rows:
        r["reduction"] = round(reduction(fifo[r["size"]], r["miss_ratio"]), 6)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    cols = ["dataset", "trace", "size", "algo", "miss_ratio", "reduction", "cache_size_obj",
            "n_req", "sample_ratio", "max_req"]
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for p in sorted(a.logs):
            for r in parse(p):
                r["dataset"] = a.dataset
                w.writerow({k: r[k] for k in cols})


if __name__ == "__main__":
    main()
