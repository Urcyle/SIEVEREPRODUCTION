#!/usr/bin/env python3
"""TinyLFU on Meta KV traces 3 and 5 at the capacities of SIEVEREPRODUCTION's simulator (docs/remaining_work_plan_20261106.md, amendment 3
to docs/metakv_split_protocol.md).

  python3 -B scripts/metakv_tinylfu_theirs_capacity.py run | summarize
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
sys.path.insert(0, str(ROOT / "scripts"))

from sieve_repro.core import parse_counters
from sieve_repro.run import file_sha256
import metakv_split_compare as mk

SNAP = ROOT / "external_replication/sievereproduction_43fc450/fig4"
PINNED = ROOT / "build/counter-sim/bin/cachesim"
PREFIX = ROOT / "build/paper-tinylfu/cmake/bin/cachesim"
OUT = ROOT / "local_results/metakv_tinylfu_theirs_capacity"
RUNS = OUT / "runs.csv"
TRACES = (3, 5)


def theirs() -> dict:
    return {(int(r["trace"].rsplit("_", 1)[1]), r["size"]): r for r in csv.DictReader((SNAP / "fig4.csv").open(newline=""))
            if r["dataset"] == "metaKV" and r["algo"] == "TinyLFU" and int(r["trace"].rsplit("_", 1)[1]) in TRACES}


def one(job, scratch):
    build, trace, size, capacity = job
    path = ROOT / f"data/metakv_split/kvcache_traces_{trace}.valid.oracleGeneral.zst"
    command = [str(PINNED if build == "pinned" else PREFIX), str(path), "oracleGeneral", "wtinylfu", str(capacity), "--ignore-obj-size", "1",
               "--num-thread", "1", "--warmup-sec", "-1", "--eviction-params", "main-cache=SLRU,window-size=0.01"]
    text = subprocess.run(command, cwd=scratch, capture_output=True, text=True, check=True).stdout
    line = [l for l in text.splitlines() if l.startswith("SIEVE_COUNTERS")][0]
    return job, parse_counters("SIEVE_COUNTERS policy=X " + line.split(" ", 2)[2])


def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    t = theirs()
    jobs = [(b, n, s, int(t[(n, s)]["cache_size"])) for n in TRACES for s in ("small", "large") for b in ("pinned", "prefix")]
    done = {(r["build"], int(r["trace"]), r["size"]) for r in csv.DictReader(RUNS.open(newline=""))} if RUNS.exists() else set()
    with tempfile.TemporaryDirectory(prefix="kvth_") as tmp, ThreadPoolExecutor(max_workers=2) as pool:
        for (build, trace, size, cap), rec in pool.map(lambda j: one(j, tmp), [j for j in jobs if j[:3] not in done]):
            with RUNS.open("a", newline="") as stream:
                w = csv.DictWriter(stream, ("build", "trace", "size", "capacity_objects", "requests", "misses", "binary_sha256"))
                if stream.tell() == 0:
                    w.writeheader()
                w.writerow({"build": build, "trace": trace, "size": size, "capacity_objects": cap, "requests": rec["n_req"], "misses": rec["n_miss"],
                            "binary_sha256": file_sha256(PINNED if build == "pinned" else PREFIX)})
            print(build, trace, size, cap, rec["n_miss"], flush=True)
    summarize()


def summarize() -> None:
    t = theirs()
    ours = mk.records()
    dots = {}
    for r in csv.DictReader((SNAP / "fig4_paper_values.csv").open(newline="")):
        if r["dataset"] == "metaKV" and r["algo"] == "TinyLFU":
            dots[(int(r["trace_idx"]), r["size"])] = float(r["reduction"])
    rows = []
    for r in csv.DictReader(RUNS.open(newline="")):
        n, size, build = int(r["trace"]), r["size"], r["build"]
        frac = 0.001 if size == "small" else 0.1
        m = int(r["misses"]) / int(r["requests"])
        fifo_ours = ours[(n, frac, "FIFO")]["n_miss"] / ours[(n, frac, "FIFO")]["n_req"]
        fifo_theirs = float(t[(n, size)]["fifo_miss_ratio"])
        dot = dots[(mk.DOT_OF_TRACE[n], size)]
        red_o, red_t = mk.reduction(fifo_ours, m), mk.reduction(fifo_theirs, m)
        rows.append({"trace": n, "size": size, "build": build, "capacity_objects": r["capacity_objects"], "miss_ratio": f"{m:.4f}",
                     "reduction_vs_our_fifo": f"{red_o:.4f}", "reduction_vs_their_fifo": f"{red_t:.4f}", "paper_dot": f"{dot:.4f}",
                     "distance_ours_fifo": f"{abs(red_o - dot):.4f}", "distance_their_fifo": f"{abs(red_t - dot):.4f}"})
    rows.sort(key=lambda r: (r["trace"], r["size"], r["build"]))
    with (OUT / "summary.csv").open("w", newline="") as stream:
        w = csv.DictWriter(stream, tuple(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(r)
    for n in TRACES:
        for size in ("small", "large"):
            x = [r for r in rows if r["trace"] == n and r["size"] == size and r["build"] == "prefix"]
            if x:
                print(f"trace {n} {size}: pre-fix at their capacity within 0.0005 of the paper's dot (reading vs our FIFO): "
                      f"{float(x[0]['distance_ours_fifo']) <= 0.0005}  (vs their FIFO: {float(x[0]['distance_their_fifo']) <= 0.0005})")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"run", "summarize"}:
        raise SystemExit(__doc__)
    {"run": run, "summarize": summarize}[sys.argv[1]]()
