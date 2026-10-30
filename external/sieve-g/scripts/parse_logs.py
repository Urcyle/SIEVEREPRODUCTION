#!/usr/bin/env python3
"""Collect miss ratios from run_sieveg.sh logs into one CSV, and compute reductions.

usage: parse_logs.py <log> [<log> ...] --dataset NAME -o out.csv

A copy of external/sieve-fig3/scripts/parse_logs.py for the SIEVE-G runs: one pass per log, the
algorithms and sizes are read from the log's "# algos" / "# sizes" header, and SIEVE-G's names
(SieveG-<ratio>, e.g. SieveG-0.50, and the fingerprint ghost SieveG-fp-<ratio>) are added. One row per (trace, cache size, algorithm):
    dataset, trace, size (small|large), algo, miss_ratio, reduction, vs_sieve, cache_size_obj,
    n_req, sample_ratio, max_req, wall_s, maxrss_kb
reduction (paper §4.1), against FIFO on the same trace and size:
    (mr_FIFO - mr) / mr_FIFO   if mr <= mr_FIFO
    (mr_FIFO - mr) / mr        otherwise          (keeps the value in [-1, 1])
vs_sieve: the same formula against SIEVE instead of FIFO (the pre-registered relative reduction of
SIEVE-G over SIEVE; empty for FIFO and SIEVE).
"""
import argparse
import csv
import re
import sys

# cachesim's cache name -> name used here
NAMES = {"FIFO": "FIFO", "Sieve": "SIEVE"}
LINE = re.compile(r"^result/\S+\s+(\S+) cache size\s+(\d+), (\d+) req, miss ratio ([0-9.]+)")


def name(cachesim_name):
    if cachesim_name in NAMES:
        return NAMES[cachesim_name]
    m = re.fullmatch(r"SieveG-(\d+\.\d+)", cachesim_name)
    if m:
        return f"SIEVE-G {m.group(1)}"
    m = re.fullmatch(r"SieveG-fp-(\d+\.\d+)", cachesim_name)
    if m:
        return f"SIEVE-G-fp {m.group(1)}"
    sys.exit(f"unknown cache name {cachesim_name}")


def reduction(mr_base, mr):
    if mr_base == 0 and mr == 0:
        return 0.0
    return (mr_base - mr) / (mr_base if mr <= mr_base else mr)


def parse(path):
    trace = sample = None
    max_req = -1
    algos = sizes = None
    wall = rss = None
    rows = []
    for line in open(path):
        line = re.sub(r"\x1b\[[0-9;]*m", "", line)
        if line.startswith("# trace "):
            trace = line.split()[2].rsplit("/", 1)[-1].split(".oracleGeneral")[0]
        elif line.startswith("# sample_ratio "):
            sample = float(line.split()[2])
        elif line.startswith("# max_req "):
            max_req = int(line.split()[2])
        elif line.startswith("# algos "):
            algos = line.split()[2].split(",")
        elif line.startswith("# sizes "):
            sizes = line.split()[2].split(",")
        elif line.startswith("# time "):
            wall, rss = re.search(r"wall_s=([\d.]+) maxrss_kb=(\d+)", line).groups()
        m = LINE.match(line)
        if m:
            nm, size, n_req, mr = m.groups()
            rows.append(dict(trace=trace, algo=name(nm), cache_size_obj=int(size), n_req=int(n_req),
                             miss_ratio=float(mr), sample_ratio=sample, max_req=max_req))
    want = len(algos) * len(sizes)
    if len(rows) != want:
        sys.exit(f"{path}: expected {want} results, got {len(rows)}")
    cs = sorted({r["cache_size_obj"] for r in rows})
    if len(cs) != 2:
        sys.exit(f"{path}: cache sizes {cs}, expected 2")
    for r in rows:
        r["size"] = "small" if r["cache_size_obj"] == cs[0] else "large"
        r["wall_s"], r["maxrss_kb"] = float(wall), int(rss)
    fifo = {r["size"]: r["miss_ratio"] for r in rows if r["algo"] == "FIFO"}
    sieve = {r["size"]: r["miss_ratio"] for r in rows if r["algo"] == "SIEVE"}
    for r in rows:
        r["reduction"] = round(reduction(fifo[r["size"]], r["miss_ratio"]), 6)
        r["vs_sieve"] = (round(reduction(sieve[r["size"]], r["miss_ratio"]), 6)
                         if r["algo"].startswith("SIEVE-G") else "")  # also SIEVE-G-fp
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    cols = ["dataset", "trace", "size", "algo", "miss_ratio", "reduction", "vs_sieve", "cache_size_obj",
            "n_req", "sample_ratio", "max_req", "wall_s", "maxrss_kb"]
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for p in sorted(a.logs):
            for r in parse(p):
                r["dataset"] = a.dataset
                w.writerow({k: r[k] for k in cols})


if __name__ == "__main__":
    main()
