#!/usr/bin/env python3
"""CACHEUS seed spread on meta_rnha (protocol: docs/cacheus_seed_spread_protocol.md).

  python3 -B scripts/cacheus_seed_spread.py run        # 16 runs (seeds 1-8, two caches), resumable
  python3 -B scripts/cacheus_seed_spread.py summarize
"""

from __future__ import annotations

import csv
import os
import statistics
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sieve_repro.core import parse_counters
from sieve_repro.run import file_sha256

BINARY = ROOT / "build/seeded-baselines/bin/cachesim"
TRACE = ROOT / "data/metaCDN/meta_rnha.oracleGeneral.zst"
OUT = ROOT / "local_results/cacheus_seed_spread"
RUNS = OUT / "runs.csv"
BASE = ROOT / "local_results/online_baselines_public_extension/public_twelve_subset.csv"
CAPS = {0.001: 35040, 0.1: 3504028}
SEEDS = tuple(range(1, 9))
PAPER = {0.001: 0.0148, 0.1: 0.0481}      # paper dots of meta_rnha (SIEVEREPRODUCTION's extraction)
THEIRS = {0.001: 0.0187, 0.1: 0.0583}      # SIEVEREPRODUCTION, default (clock-seeded) run
FIELDS = ("seed", "capacity_fraction", "capacity_objects", "requests", "misses", "binary_sha256")


def fifo_misses() -> dict:
    return {float(r["capacity_fraction"]): int(r["misses"]) for r in csv.DictReader(BASE.open(newline="")) if r["trace"] == "meta_rnha" and r["policy"] == "fifo"}


def one(seed, fraction, scratch):
    env = dict(os.environ, SIEVE_RNG_SEED=str(seed))
    command = [str(BINARY), str(TRACE), "oracleGeneral", "cacheus", str(CAPS[fraction]), "--ignore-obj-size", "1", "--num-thread", "1", "--warmup-sec", "-1"]
    out = subprocess.run(command, cwd=scratch, env=env, capture_output=True, text=True, check=True).stdout
    line = [l for l in out.splitlines() if l.startswith("SIEVE_COUNTERS")][0]
    record = parse_counters("SIEVE_COUNTERS policy=X " + line.split(" ", 2)[2])
    if record["cache_size"] != CAPS[fraction]:
        raise RuntimeError("capacity differs")
    return seed, fraction, record


def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    done = {(int(r["seed"]), float(r["capacity_fraction"])) for r in csv.DictReader(RUNS.open(newline=""))} if RUNS.exists() else set()
    jobs = [(s, f) for f in CAPS for s in SEEDS if (s, f) not in done]
    with tempfile.TemporaryDirectory(prefix="cacheus_") as tmp:
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(lambda j: one(j[0], j[1], tmp), jobs))
    with RUNS.open("a", newline="") as stream:
        writer = csv.DictWriter(stream, FIELDS)
        if stream.tell() == 0:
            writer.writeheader()
        for seed, fraction, record in results:
            writer.writerow({"seed": seed, "capacity_fraction": fraction, "capacity_objects": CAPS[fraction], "requests": record["n_req"],
                             "misses": record["n_miss"], "binary_sha256": file_sha256(BINARY)})
    summarize()


def summarize() -> None:
    fifo = fifo_misses()
    values = {}
    for r in csv.DictReader(RUNS.open(newline="")):
        f = float(r["capacity_fraction"])
        m = int(r["misses"])
        values.setdefault(f, {})[int(r["seed"])] = (fifo[f] - m) / max(fifo[f], m)
    rows, verdict = [], []
    for f, v in sorted(values.items()):
        lo, hi = min(v.values()), max(v.values())
        spread = hi - lo
        covers = all(lo - 0.002 <= x <= hi + 0.002 for x in (PAPER[f], THEIRS[f]))
        threshold = 0.004 if f == 0.001 else 0.010
        rows.append({"capacity_fraction": f, "seeds": len(v), "min": f"{lo:.4f}", "max": f"{hi:.4f}", "mean": f"{statistics.fmean(v.values()):.4f}",
                     "range": f"{spread:.4f}", "paper": PAPER[f], "sievereproduction_default_run": THEIRS[f],
                     "per_seed": " ".join(f"{s}:{x:.4f}" for s, x in sorted(v.items()))})
        verdict.append(spread >= threshold and covers)
    with (OUT / "spread.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for r in rows:
        print(r)
    print("verdict:", "supported" if all(verdict) and len(verdict) == 2 else "not supported")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"run", "summarize"}:
        raise SystemExit(__doc__)
    {"run": run, "summarize": summarize}[sys.argv[1]]()
