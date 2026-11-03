#!/usr/bin/env python3
"""TinyLFU capacity sensitivity on Meta KV trace 1 (protocol: docs/tinylfu_dot_check_protocol.md, follow-up of 2026-10-23).

  python3 -B scripts/tinylfu_capacity_sensitivity.py run | summarize
"""

from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sieve_repro.core import parse_counters

TRACE = ROOT / "data/metakv_split/kvcache_traces_1.valid.oracleGeneral.zst"
PINNED = ROOT / "build/counter-sim/bin/cachesim"
PREFIX = ROOT / "build/paper-tinylfu/cmake/bin/cachesim"
OUT = ROOT / "local_results/tinylfu_capacity_sensitivity"
RUNS = OUT / "runs.csv"
THEIRS = {16982: 0.2903, 1698213: 0.0823}      # SIEVEREPRODUCTION's TinyLFU miss ratios at its capacities
PAPER_DOT = {16982: 0.1397, 1698213: 0.0896}  # paper dots of trace 1 (dot 2)
JOBS = [("pinned", 16982), ("prefix", 16982), ("pinned", 1698213), ("prefix", 1698213),
        ("pinned", 16980), ("pinned", 16984), ("pinned", 16990), ("pinned", 17000)]


def one(build, capacity, scratch):
    command = [str(PINNED if build == "pinned" else PREFIX), str(TRACE), "oracleGeneral", "wtinylfu", str(capacity), "--ignore-obj-size", "1",
               "--num-thread", "1", "--warmup-sec", "-1", "--eviction-params", "main-cache=SLRU,window-size=0.01"]
    out = subprocess.run(command, cwd=scratch, capture_output=True, text=True, check=True).stdout
    line = [l for l in out.splitlines() if l.startswith("SIEVE_COUNTERS")][0]
    return build, capacity, parse_counters("SIEVE_COUNTERS policy=X " + line.split(" ", 2)[2])


def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    done = {(r["build"], int(r["capacity_objects"])) for r in csv.DictReader(RUNS.open(newline=""))} if RUNS.exists() else set()
    jobs = [j for j in JOBS if j not in done]
    with tempfile.TemporaryDirectory(prefix="tlcap_") as tmp, ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda j: one(*j, tmp), jobs))
    with RUNS.open("a", newline="") as stream:
        w = csv.DictWriter(stream, ("build", "capacity_objects", "requests", "misses", "miss_ratio"))
        if stream.tell() == 0:
            w.writeheader()
        for build, cap, rec in results:
            w.writerow({"build": build, "capacity_objects": cap, "requests": rec["n_req"], "misses": rec["n_miss"], "miss_ratio": f"{rec['n_miss'] / rec['n_req']:.4f}"})
    summarize()


def summarize() -> None:
    rows = {(r["build"], int(r["capacity_objects"])): float(r["miss_ratio"]) for r in csv.DictReader(RUNS.open(newline=""))}
    for (b, c), m in sorted(rows.items()):
        print(b, c, m)
    a = abs(rows[("pinned", 16982)] - THEIRS[16982])
    spread = max(rows[("pinned", c)] for c in (16980, 16984, 16990, 17000)) - min(rows[("pinned", c)] for c in (16980, 16984, 16990, 17000))
    print(f"(a) pinned at 16,982 vs SIEVEREPRODUCTION {THEIRS[16982]}: difference {a:.4f}; (b) spread over 16,980/16,984/16,990/17,000: {spread:.4f}")
    print("H-cap:", "supported" if a <= 0.0005 and spread > 0.002 else "not supported")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"run", "summarize"}:
        raise SystemExit(__doc__)
    {"run": run, "summarize": summarize}[sys.argv[1]]()
