#!/usr/bin/env python3
"""Pre-fix TinyLFU against the paper's Figure 4 TinyLFU points (protocol: docs/tinylfu_dot_check_protocol.md).

  python3 -B scripts/tinylfu_dot_check.py run        # 8 runs (resumable), then writes the comparison
  python3 -B scripts/tinylfu_dot_check.py summarize  # from saved counters only
"""

from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sieve_repro.core import parse_counters
from sieve_repro.run import file_sha256

BINARY = ROOT / "build/paper-tinylfu/cmake/bin/cachesim"
OUT = ROOT / "local_results/tinylfu_dot_check"
RUNS = OUT / "runs.csv"
THEIRS = ROOT / "external_replication/sievereproduction_43fc450/fig4/fig4.csv"
PAPER = ROOT / "external_replication/sievereproduction_43fc450/fig4/fig4_paper_values.csv"
BASE = ROOT / "local_results/online_baselines_public_extension/public_twelve_subset.csv"
KV1 = ROOT / "local_results/metakv_trace1_candidate_six_policy.csv"
TRACES = {"meta_reag": ("metaCDN", "data/metaCDN/meta_reag.oracleGeneral.zst"), "meta_rprn": ("metaCDN", "data/metaCDN/meta_rprn.oracleGeneral.zst"),
          "meta_rnha": ("metaCDN", "data/metaCDN/meta_rnha.oracleGeneral.zst"), "wiki_2019t": ("wiki", "data/wiki/wiki_2019t.oracleGeneral.zst"),
          "metakv_trace1_candidate": ("metaKV", "data/metakv_candidate/meta_kvcache_traces_1.oracleGeneral.bin.zst")}
SAVED_PATCH_COUNTERS = {("meta_reag", 0.001): 20981408, ("meta_reag", 0.1): 15574226}   # saved before this protocol
# post-hoc: the trace each paper dot belongs to, as matched by SIEVEREPRODUCTION from SIEVE's value (summary.md); not used by the declared rule
DOT_INDEX = {"meta_rprn": 1, "meta_reag": 2, "meta_rnha": 3, "wiki_2019t": 3, "metakv_trace1_candidate": 2}
FIELDS = ("trace", "capacity_fraction", "capacity_objects", "requests", "misses", "binary_sha256")


def reduction(fifo: int, misses: int) -> float:
    return (fifo - misses) / max(fifo, misses)


def saved_rows() -> dict:
    rows = {}
    for r in csv.DictReader(BASE.open(newline="")):
        rows[(r["trace"], float(r["capacity_fraction"]), r["policy"])] = r
    for r in csv.DictReader(KV1.open(newline="")):
        rows[("metakv_trace1_candidate", float(r["capacity_fraction"]), r["policy"])] = r
    return rows


def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ref = saved_rows()
    done = {(r["trace"], float(r["capacity_fraction"])) for r in csv.DictReader(RUNS.open(newline=""))} if RUNS.exists() else set()
    with tempfile.TemporaryDirectory(prefix="tlfu_") as tmp, RUNS.open("a", newline="") as stream:
        writer = csv.DictWriter(stream, FIELDS)
        if stream.tell() == 0:
            writer.writeheader()
        for trace, (_, path) in TRACES.items():
            for fraction in (0.001, 0.1):
                if (trace, fraction) in done or (trace, fraction) in SAVED_PATCH_COUNTERS:
                    continue
                capacity = int(ref[(trace, fraction, "fifo")]["capacity_objects"])
                command = [str(BINARY), str(ROOT / path), "oracleGeneral", "wtinylfu", str(capacity), "--ignore-obj-size", "1", "--num-thread", "1",
                           "--warmup-sec", "-1", "--eviction-params", "main-cache=SLRU,window-size=0.01"]
                out = subprocess.run(command, cwd=tmp, capture_output=True, text=True, check=True).stdout
                line = [l for l in out.splitlines() if l.startswith("SIEVE_COUNTERS")][0]
                record = parse_counters("SIEVE_COUNTERS policy=X " + line.split(" ", 2)[2])
                if record["cache_size"] != capacity or record["n_req"] != int(ref[(trace, fraction, "fifo")]["requests"]):
                    raise RuntimeError(f"{trace} {fraction}: capacity or request count differs from the saved grid")
                writer.writerow({"trace": trace, "capacity_fraction": fraction, "capacity_objects": capacity, "requests": record["n_req"],
                                 "misses": record["n_miss"], "binary_sha256": file_sha256(BINARY)})
                stream.flush()
                print(trace, fraction, record["n_miss"], flush=True)
    summarize()


def summarize() -> None:
    ref = saved_rows()
    runs = {(r["trace"], float(r["capacity_fraction"])): int(r["misses"]) for r in csv.DictReader(RUNS.open(newline=""))} if RUNS.exists() else {}
    runs.update(SAVED_PATCH_COUNTERS)
    dots = defaultdict(list)
    dots_by_index = {}
    for r in csv.DictReader(PAPER.open(newline="")):
        if r["algo"] == "TinyLFU":
            dots[(r["dataset"], r["size"])].append(float(r["reduction"]))
            dots_by_index[(r["dataset"], r["size"], int(r["trace_idx"]))] = float(r["reduction"])
    rows = []
    for (trace, fraction), patched in sorted(runs.items()):
        dataset = TRACES[trace][0]
        size = "large" if fraction == 0.1 else "small"
        fifo = int(ref[(trace, fraction, "fifo")]["misses"])
        patched_red = reduction(fifo, patched)
        if (trace, fraction, "tinylfu_snapshot") in ref:
            pinned_red = reduction(fifo, int(ref[(trace, fraction, "tinylfu_snapshot")]["misses"]))
        else:   # Meta KV trace 1: our grid has no TinyLFU row; use the pinned TinyLFU of the SIEVEREPRODUCTION snapshot (4 decimals)
            theirs = [r for r in csv.DictReader(THEIRS.open(newline="")) if r["trace"] == "kvcache_traces_1" and r["size"] == size and r["algo"] == "TinyLFU"]
            pinned_red = float(theirs[0]["reduction"])
        candidates = dots[(dataset, size)]
        nearest = min(candidates, key=lambda d: abs(d - patched_red))
        nearest_pinned = min(candidates, key=lambda d: abs(d - pinned_red))
        rows.append({"trace": trace, "capacity_fraction": fraction, "blind": (trace, fraction) not in SAVED_PATCH_COUNTERS,
                     "patched_reduction": f"{patched_red:.4f}", "pinned_reduction": f"{pinned_red:.4f}", "nearest_paper_dot_to_patched": f"{nearest:.4f}",
                     "distance_patched": f"{abs(nearest - patched_red):.4f}", "distance_pinned": f"{abs(nearest_pinned - pinned_red):.4f}",
                     "dots_in_panel": len(candidates),
                     "posthoc_dot_of_this_trace": f"{dots_by_index[(dataset, size, DOT_INDEX[trace])]:.4f}",
                     "posthoc_distance_patched": f"{abs(dots_by_index[(dataset, size, DOT_INDEX[trace])] - patched_red):.4f}",
                     "posthoc_distance_pinned": f"{abs(dots_by_index[(dataset, size, DOT_INDEX[trace])] - pinned_red):.4f}"})
    with (OUT / "comparison.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    blind = [r for r in rows if r["blind"]]
    within = sum(float(r["distance_patched"]) <= 0.0005 for r in blind)
    closer = [r for r in blind if float(r["distance_pinned"]) > 0.0005]
    closer_ok = sum(float(r["distance_patched"]) < float(r["distance_pinned"]) for r in closer)
    near2 = sum(float(r["distance_patched"]) <= 0.002 for r in blind)
    verdict = "supported" if len(blind) == 8 and within >= 7 and closer_ok == len(closer) else (
        "partly supported" if len(blind) == 8 and near2 >= 6 else "not supported" if len(blind) == 8 else "incomplete")
    print(f"blind cells {len(blind)}: within 0.0005 of a paper dot {within}; within 0.002 {near2}; closer than pinned where pinned is off {closer_ok}/{len(closer)}; verdict: {verdict}")
    for r in rows:
        print(r)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"run", "summarize"}:
        raise SystemExit(__doc__)
    {"run": run, "summarize": summarize}[sys.argv[1]]()
