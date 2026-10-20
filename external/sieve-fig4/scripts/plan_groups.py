#!/usr/bin/env python3
"""Split the 11 algorithms into large-cache groups that each fit in the memory budget.

usage: plan_groups.py <large cache size in objects> [budget_GB]   -> prints "a,b;c;d,e"

Memory per cached object was measured by running each algorithm alone on meta_reag at its large
size (1,226,253 objects, peak RSS minus the 150 MB of a run with a tiny cache):
  FIFO/LRU/CLOCK/SIEVE ~80 B, ARC ~160 B, LHD ~250 B, TinyLFU ~350 B, TwoQ ~440 B,
  LIRS ~560 B, CACHEUS ~1270 B; Hyperbolic stayed under the baseline (counted as 80 B).
Each cachesim thread also needs ~0.3 GB of its own (trace reader buffers). Groups are filled
largest-first (first-fit decreasing). The default budget, 6 GB, lets two passes run at once
(scripts/run_trace.sh, SLOTS=2): measured peaks are about half of these estimates (e.g.
CACHEUS+LIRS+ARC at 3.5 M objects: estimated 7.9 GB, measured 3.9 GB). An algorithm that
alone exceeds the budget gets its own group, and the planner says so on stderr.
"""
import sys

BYTES = {"cacheus": 1270, "lirs": 560, "twoq": 440, "tinyLFU": 350, "lhd": 250, "arc": 160,
         "fifo": 80, "lru": 80, "clock": 80, "sieve": 80, "hyperbolic": 80}
THREAD_GB = 0.3

size = int(sys.argv[1])
budget = float(sys.argv[2]) if len(sys.argv) > 2 else 6.0
need = {a: b * size / 1e9 + THREAD_GB for a, b in BYTES.items()}
groups = []
for a in sorted(need, key=need.get, reverse=True):
    if need[a] > budget:
        print(f"warning: {a} alone needs ~{need[a]:.1f} GB > {budget} GB", file=sys.stderr)
    for g in groups:
        if sum(need[x] for x in g) + need[a] <= budget:
            g.append(a)
            break
    else:
        groups.append([a])
print(";".join(",".join(g) for g in groups))
