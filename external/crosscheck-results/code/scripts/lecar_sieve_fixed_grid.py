#!/usr/bin/env python3
"""Corrected LeCaR-SIEVE on the seven Figure 12 traces (protocol: docs/lecar_sieve_collapse_protocol.md, Amendment 1).

  python3 -B scripts/lecar_sieve_fixed_grid.py run | summarize
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

BINARY = ROOT / "build/figure12-lecar-fixed/bin/cachesim"
SAVED = ROOT / "local_results/figure12_public_selected_seven/figure12_public_selected_seven.csv"
OUT = ROOT / "local_results/lecar_sieve_fixed_grid"
RUNS = OUT / "runs.csv"
SEED = 42
TRACES = {"meta_reag": "data/metaCDN/meta_reag.oracleGeneral.zst", "meta_rprn": "data/metaCDN/meta_rprn.oracleGeneral.zst",
          "meta_rnha": "data/metaCDN/meta_rnha.oracleGeneral.zst", "wiki_2019t": "data/wiki/wiki_2019t.oracleGeneral.zst",
          "twitter_cluster10": "data/twitter/cluster10.oracleGeneral.zst", "twitter_cluster26": "data/twitter/cluster26.oracleGeneral.zst",
          "twitter_cluster50": "data/twitter/cluster50.oracleGeneral.zst"}
FIELDS = ("trace", "capacity_fraction", "capacity_objects", "requests", "misses", "rng_seed", "binary_sha256")


def saved() -> dict:
    return {(r["trace"], float(r["capacity_fraction"]), r["policy"]): r for r in csv.DictReader(SAVED.open(newline=""))}


def one(trace, fraction, capacity, scratch):
    env = dict(os.environ, SIEVE_RNG_SEED=str(SEED))
    command = [str(BINARY), str(ROOT / TRACES[trace]), "oracleGeneral", "lecar", str(capacity), "--ignore-obj-size", "1", "--num-thread", "1",
               "--warmup-sec", "-1", "--eviction-params", "lru-type=SIEVE"]
    out = subprocess.run(command, env=env, cwd=scratch, capture_output=True, text=True, check=True).stdout
    line = [l for l in out.splitlines() if l.startswith("SIEVE_COUNTERS")][0]
    return trace, fraction, capacity, parse_counters("SIEVE_COUNTERS policy=X " + line.split(" ", 2)[2])


def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ref = saved()
    done = {(r["trace"], float(r["capacity_fraction"])) for r in csv.DictReader(RUNS.open(newline=""))} if RUNS.exists() else set()
    jobs = [(t, f, int(ref[(t, f, "lecar")]["capacity_objects"])) for t in TRACES for f in (0.001, 0.1) if (t, f) not in done]
    with tempfile.TemporaryDirectory(prefix="lecarfix_") as tmp, ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda j: one(*j, tmp), jobs))
    with RUNS.open("a", newline="") as stream:
        writer = csv.DictWriter(stream, FIELDS)
        if stream.tell() == 0:
            writer.writeheader()
        for trace, fraction, capacity, record in results:
            if record["n_req"] != int(ref[(trace, fraction, "lecar")]["requests"]) or record["cache_size"] != capacity:
                raise RuntimeError("request count or capacity differs from the saved grid")
            writer.writerow({"trace": trace, "capacity_fraction": fraction, "capacity_objects": capacity, "requests": record["n_req"],
                             "misses": record["n_miss"], "rng_seed": SEED, "binary_sha256": file_sha256(BINARY)})
    summarize()


def reduction(f, m):
    return (f - m) / max(f, m)


def summarize() -> None:
    ref = saved()
    fixed = {(r["trace"], float(r["capacity_fraction"])): int(r["misses"]) for r in csv.DictReader(RUNS.open(newline=""))}
    rows = []
    for (trace, f), m in sorted(fixed.items()):
        fifo = int(ref[(trace, f, "fifo")]["misses"])
        rows.append({"trace": trace, "capacity_fraction": f, "fifo_misses": fifo, "lecar_lru_reduction": f"{float(ref[(trace, f, 'lecar')]['reduction_from_fifo']):.4f}",
                     "lecar_sieve_original_reduction": f"{float(ref[(trace, f, 'lecar_sieve')]['reduction_from_fifo']):.4f}",
                     "lecar_sieve_corrected_reduction": f"{reduction(fifo, m):.4f}", "sieve_reduction": f"{float(ref[(trace, f, 'sieve')]['reduction_from_fifo']):.4f}",
                     "lru_reduction": f"{float(ref[(trace, f, 'lru')]['reduction_from_fifo']):.4f}", "corrected_misses": m})
    with (OUT / "per_trace.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    means = []
    for f in (0.001, 0.1):
        for group, test in (("all 7", lambda t: True), ("CDN and Wiki (4)", lambda t: not t.startswith("twitter")), ("Twitter (3)", lambda t: t.startswith("twitter"))):
            sel = [r for r in rows if r["capacity_fraction"] == f and test(r["trace"])]
            mean = lambda k: statistics.fmean(float(r[k]) for r in sel)
            means.append({"capacity_fraction": f, "group": group, "lecar_lru": f"{mean('lecar_lru_reduction'):.4f}", "lecar_sieve_original": f"{mean('lecar_sieve_original_reduction'):.4f}",
                          "lecar_sieve_corrected": f"{mean('lecar_sieve_corrected_reduction'):.4f}", "sieve": f"{mean('sieve_reduction'):.4f}", "lru": f"{mean('lru_reduction'):.4f}"})
    with (OUT / "means.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, tuple(means[0]))
        writer.writeheader()
        writer.writerows(means)
    for m in means:
        print(m)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"run", "summarize"}:
        raise SystemExit(__doc__)
    {"run": run, "summarize": summarize}[sys.argv[1]]()
