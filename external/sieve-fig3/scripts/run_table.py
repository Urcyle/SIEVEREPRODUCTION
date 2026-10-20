#!/usr/bin/env python3
"""Per-cluster table of what was simulated and what it cost, from the raw logs.

usage: run_table.py > results/twitter_runs.md

Columns: cluster, trace file used, requests simulated, footprint (unique objects, = 1000 x the
small cache), small/large cache in objects, wall time of both cachesim passes, peak memory.
"""
import glob
import os
import re

rows = []
for p in glob.glob("results/raw/twitter/*.log"):
    txt = open(p).read()
    trace = re.search(r"^# trace (\S+)", txt, re.M).group(1).rsplit("/", 1)[-1]
    sample = re.search(r"^# sample_ratio (\S+)", txt, re.M).group(1)
    main = txt.split("# pass blru")[0]
    sizes = sorted({int(x) for x in re.findall(r"cache size\s+(\d+),", main)})
    n_req = int(re.search(r"cache size\s+\d+, (\d+) req", main).group(1))
    walls = [float(x) for x in re.findall(r"wall_s=([0-9.]+)", txt)]
    rss = max(int(x) for x in re.findall(r"maxrss_kb=(\d+)", txt))
    c = int(re.search(r"cluster(\d+)", trace).group(1))
    rows.append((c, trace + ("" if sample == "1" else f" (+ cachesim -s {sample})"),
                 n_req, sizes[0], sizes[1], sum(walls), rss))

rows.sort()
print("| cluster | trace file simulated | requests | small cache (obj) | large cache (obj) |"
      " wall time | peak memory |")
print("|---|---|---|---|---|---|---|")
for c, t, n, s, l, w, m in rows:
    print(f"| {c} | `{t}` | {n:,} | {s:,} | {l:,} | {w / 60:.0f} min | {m / 1e6:.1f} GB |")
tot = sum(r[5] for r in rows)
print(f"\n{len(rows)} clusters, {sum(r[2] for r in rows):,} requests, total wall time "
      f"{tot / 3600:.1f} h, longest run {max(r[5] for r in rows) / 60:.0f} min, "
      f"peak memory {max(r[6] for r in rows) / 1e6:.1f} GB.")
