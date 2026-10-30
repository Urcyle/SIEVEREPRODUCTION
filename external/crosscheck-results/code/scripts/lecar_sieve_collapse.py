#!/usr/bin/env python3
"""LeCaR-SIEVE collapse on twitter_cluster50 (protocol: docs/lecar_sieve_collapse_protocol.md).

  python3 -B scripts/lecar_sieve_collapse.py run | summarize
Note: this run leaves SIEVE_RNG_SEED unset, so the generator is clock-seeded (as the artifact is by default); with fixed weights 0 and 1 no random draw
matters, and at 0.5 the draws average out over millions of evictions.
"""

from __future__ import annotations

import csv
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

import os
FIXED = os.environ.get("LECAR_FIXED") == "1"      # Amendment 1: corrected wrap rule
BINARY = ROOT / ("build/figure12-lecar-fixed/bin/cachesim" if FIXED else "build/figure12-lecar-sieve/bin/cachesim")
TRACE = ROOT / "data/twitter/cluster50.oracleGeneral.zst"
OUT = ROOT / ("local_results/lecar_sieve_collapse_fixed" if FIXED else "local_results/lecar_sieve_collapse")
RUNS = OUT / "runs.csv"
SAVED = ROOT / "local_results/figure12_public_selected_seven/figure12_public_selected_seven.csv"
WEIGHTS = (1.0, 0.5, 0.0)
FIELDS = ("capacity_fraction", "capacity_objects", "lru_type", "lru_weight", "requests", "misses", "binary_sha256")


def saved() -> dict:
    return {(float(r["capacity_fraction"]), r["policy"]): r for r in csv.DictReader(SAVED.open(newline="")) if r["trace"] == "twitter_cluster50"}


def one(fraction, lru_type, weight, capacity, scratch):
    params = f"update-weight=0,lru-weight={weight},lru-type={lru_type}"
    command = [str(BINARY), str(TRACE), "oracleGeneral", "lecar", str(capacity), "--ignore-obj-size", "1", "--num-thread", "1", "--warmup-sec", "-1",
               "--eviction-params", params]
    out = subprocess.run(command, cwd=scratch, capture_output=True, text=True, check=True).stdout
    line = [l for l in out.splitlines() if l.startswith("SIEVE_COUNTERS")][0]
    record = parse_counters("SIEVE_COUNTERS policy=X " + line.split(" ", 2)[2])
    return fraction, lru_type, weight, capacity, record


def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ref = saved()
    done = {(float(r["capacity_fraction"]), r["lru_type"], float(r["lru_weight"])) for r in csv.DictReader(RUNS.open(newline=""))} if RUNS.exists() else set()
    jobs = [(f, t, w, int(ref[(f, "fifo")]["capacity_objects"])) for f in (0.001, 0.1) for t in ("LRU", "SIEVE") for w in WEIGHTS if (f, t, w) not in done]
    with tempfile.TemporaryDirectory(prefix="lecar_") as tmp, ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda j: one(*j, tmp), jobs))
    with RUNS.open("a", newline="") as stream:
        writer = csv.DictWriter(stream, FIELDS)
        if stream.tell() == 0:
            writer.writeheader()
        for fraction, lru_type, weight, capacity, record in results:
            writer.writerow({"capacity_fraction": fraction, "capacity_objects": capacity, "lru_type": lru_type, "lru_weight": weight,
                             "requests": record["n_req"], "misses": record["n_miss"], "binary_sha256": file_sha256(BINARY)})
    summarize()


def summarize() -> None:
    ref = saved()
    runs = {(float(r["capacity_fraction"]), r["lru_type"], float(r["lru_weight"])): int(r["misses"]) for r in csv.DictReader(RUNS.open(newline=""))}
    rows = []
    for f in (0.001, 0.1):
        s, l, learned_s = (int(ref[(f, p)]["misses"]) for p in ("sieve", "lru", "lecar_sieve"))
        learned_l = int(ref[(f, "lecar")]["misses"])
        for t in ("LRU", "SIEVE"):
            for w in WEIGHTS:
                m = runs[(f, t, w)]
                rows.append({"capacity_fraction": f, "lru_type": t, "lru_weight": w, "misses": m, "plain_sieve_misses": s, "plain_lru_misses": l,
                             "learned_lecar_lru_misses": learned_l, "learned_lecar_sieve_misses": learned_s,
                             "ratio_to_plain_of_same_type": f"{m / (s if t == 'SIEVE' else l):.3f}"})
    with (OUT / "summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for r in rows:
        print(r)
    for f in (0.001, 0.1):
        s = int(ref[(f, "sieve")]["misses"]); learned = int(ref[(f, "lecar_sieve")]["misses"]); m = runs[(f, "SIEVE", 0.5)]
        a = m >= 1.5 * s
        b = m <= 1.2 * s and learned >= 2 * s
        print(f"cache {f}: M(0.5)/S = {m / s:.2f}, learned/S = {learned / s:.2f} -> {'(A) mixing' if a else '(B) learning' if b else 'inconclusive'}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"run", "summarize"}:
        raise SystemExit(__doc__)
    {"run": run, "summarize": summarize}[sys.argv[1]]()
