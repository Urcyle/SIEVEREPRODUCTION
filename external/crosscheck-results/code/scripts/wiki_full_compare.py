#!/usr/bin/env python3
"""wiki_2016u and wiki_2019u against SIEVEREPRODUCTION and the paper (protocol: docs/wiki_full_extension_protocol.md).

  python3 -B scripts/wiki_full_compare.py tinylfu 2016u|2019u   # pre-fix and pinned TinyLFU at SIEVEREPRODUCTION's capacities, pre-fix at ours
  python3 -B scripts/wiki_full_compare.py compare               # checks 1-4 on whatever has finished
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sieve_repro.core import parse_counters
from sieve_repro.run import file_sha256

SNAP = ROOT / "external_replication/sievereproduction_43fc450"
PINNED = ROOT / "build/counter-sim/bin/cachesim"
PREFIX = ROOT / "build/paper-tinylfu/cmake/bin/cachesim"
LABELS = {"fifo": "FIFO", "lru": "LRU", "clock": "CLOCK", "sieve": "SIEVE", "arc": "ARC", "twoq": "TwoQ", "lirs": "LIRS", "tinylfu_snapshot": "TinyLFU",
          "blru": "B-LRU", "hyperbolic": "Hyperbolic", "lhd": "LHD", "cacheus": "CACHEUS"}
RANDOM = {"LHD", "CACHEUS"}
DOT = {"wiki_2016u": 1, "wiki_2019u": 2}     # paper dot of each trace in both panels, as matched by SIEVEREPRODUCTION (fig4/summary.md)
SIZE = {0.001: "small", 0.1: "large"}


def out_dir(label: str) -> Path:
    return ROOT / f"local_results/{label}_extension"


def records(label: str) -> dict:
    out = {}
    for path in out_dir(label).glob("worker*/runs/*/complete.json"):
        r = json.loads(path.read_text())
        spec = r["spec"]
        policy = spec.get("policy_label") or spec.get("policy")
        fraction = spec.get("capacity_fraction")
        if (spec.get("trace_label") or spec.get("workload_label")) == label and fraction is not None and policy in LABELS:
            out[(fraction, LABELS[policy])] = r
    return out


def theirs_rows(label: str) -> dict:
    return {(r["size"], r["algo"]): r for r in csv.DictReader((SNAP / "fig4/fig4.csv").open(newline="")) if r["trace"] == label}


def reduction(f, m):
    return (f - m) / max(f, m)


def tinylfu(short: str) -> None:
    label = f"wiki_{short}"
    ours = records(label)
    theirs = theirs_rows(label)
    trace = ROOT / f"data/wiki/{label}.oracleGeneral.zst"
    jobs = []
    for fraction, size in SIZE.items():
        jobs += [("pinned", size, int(theirs[(size, "SIEVE")]["cache_size"])), ("prefix", size, int(theirs[(size, "SIEVE")]["cache_size"])),
                 ("prefix", size, ours[(fraction, "FIFO")]["cache_size"])]
    path = out_dir(label) / "tinylfu_builds.csv"
    done = {(r["build"], r["size"], int(r["capacity_objects"])) for r in csv.DictReader(path.open(newline=""))} if path.exists() else set()

    def one(job, tmp):
        build, size, cap = job
        command = [str(PINNED if build == "pinned" else PREFIX), str(trace), "oracleGeneral", "wtinylfu", str(cap), "--ignore-obj-size", "1", "--num-thread", "1",
                   "--warmup-sec", "-1", "--eviction-params", "main-cache=SLRU,window-size=0.01"]
        text = subprocess.run(command, cwd=tmp, capture_output=True, text=True, check=True).stdout
        line = [l for l in text.splitlines() if l.startswith("SIEVE_COUNTERS")][0]
        return job, parse_counters("SIEVE_COUNTERS policy=X " + line.split(" ", 2)[2])

    with tempfile.TemporaryDirectory(prefix="wikitl_") as tmp, ThreadPoolExecutor(max_workers=3) as pool:
        for (build, size, cap), rec in pool.map(lambda j: one(j, tmp), [j for j in jobs if j not in done]):
            with path.open("a", newline="") as stream:
                w = csv.DictWriter(stream, ("build", "size", "capacity_objects", "requests", "misses", "binary_sha256"))
                if stream.tell() == 0:
                    w.writeheader()
                w.writerow({"build": build, "size": size, "capacity_objects": cap, "requests": rec["n_req"], "misses": rec["n_miss"],
                            "binary_sha256": file_sha256(PINNED if build == "pinned" else PREFIX)})
            print(label, build, size, cap, rec["n_miss"], flush=True)


def compare() -> None:
    dots = {}
    for r in csv.DictReader((SNAP / "fig4/fig4_paper_values.csv").open(newline="")):
        if r["dataset"] == "wiki":
            dots[(int(r["trace_idx"]), r["size"], r["algo"])] = float(r["reduction"])
    best_theirs = {(r["trace"], r["size"]): r for r in csv.DictReader((SNAP / "fig5/fig5_best.csv").open(newline="")) if r["source"] == "replication"}
    rows, c1, c1_bad, c2, c3, c4 = [], 0, [], [], [], []
    for label in DOT:
        ours = records(label)
        if not ours:
            continue
        theirs = theirs_rows(label)
        for fraction, size in SIZE.items():
            fifo = ours.get((fraction, "FIFO"))
            if fifo is None:
                continue
            for algo in sorted({a for (f, a) in ours if f == fraction} - {"FIFO"}):
                r = ours[(fraction, algo)]
                mr, red = r["n_miss"] / r["n_req"], reduction(fifo["n_miss"], r["n_miss"])
                t = theirs.get((size, algo))
                d = dots.get((DOT[label], size, algo))
                nearest = min((abs(red - v) for (i, s, a), v in dots.items() if s == size and a == algo), default=None)
                rows.append({"trace": label, "size": size, "algo": algo, "our_miss_ratio": f"{mr:.4f}", "theirs_miss_ratio": t["miss_ratio"] if t else "",
                             "difference": f"{mr - float(t['miss_ratio']):+.4f}" if t else "", "our_reduction": f"{red:.4f}",
                             "paper_dot_of_this_trace": f"{d:.4f}" if d is not None else "",
                             "distance_to_paper": f"{abs(red - d):.4f}" if d is not None else "",
                             "distance_to_nearest_dot": f"{nearest:.4f}" if nearest is not None else ""})
                if t and algo not in RANDOM | {"TinyLFU"}:
                    c1 += 1
                    if abs(mr - float(t["miss_ratio"])) > 0.0005 + 1e-9:
                        c1_bad.append((label, size, algo, rows[-1]["difference"]))
                if algo == "SIEVE" and d is not None:
                    c2.append((label, size, abs(red - d), nearest))
            reds = {a: reduction(fifo["n_miss"], ours[(fraction, a)]["n_miss"]) for (f, a) in ours if f == fraction and a != "FIFO"}
            if reds:
                top = max(reds, key=reds.get)
                bt = best_theirs.get((label, size))
                c4.append({"trace": label, "size": size, "our_best_of_run": top, "our_best_reduction": f"{reds[top]:.4f}", "theirs_best_of_12": bt["best"] if bt else "",
                           "algorithms_we_did_not_run": " ".join(sorted(set(LABELS.values()) - set(a for (f, a) in ours if f == fraction)))})
        tl = out_dir(label) / "tinylfu_builds.csv"
        if tl.exists():
            for r in csv.DictReader(tl.open(newline="")):
                size = r["size"]
                fraction = 0.001 if size == "small" else 0.1
                f_theirs = theirs.get((size, "SIEVE"))
                d = dots.get((DOT[label], size, "TinyLFU"))
                if f_theirs is None or d is None:
                    continue
                m = int(r["misses"]) / int(r["requests"])
                red = reduction(float(f_theirs["fifo_miss_ratio"]), m)
                c3.append({"trace": label, "size": size, "build": r["build"], "capacity_objects": r["capacity_objects"],
                           "is_simulator_capacity": int(r["capacity_objects"]) == int(f_theirs["cache_size"]), "miss_ratio": f"{m:.4f}",
                           "reduction_vs_their_fifo": f"{red:.4f}", "paper_dot": f"{d:.4f}", "distance_to_paper": f"{abs(red - d):.4f}"})
    if rows:
        write(ROOT / "local_results/wiki_full_comparison.csv", rows)
    if c3:
        write(ROOT / "local_results/wiki_full_tinylfu_builds.csv", c3)
    print(f"check 1: {c1 - len(c1_bad)} of {c1} deterministic cells within 0.0005 of SIEVEREPRODUCTION; exceptions {c1_bad[:10]}")
    print(f"check 2: SIEVE within 0.0005 of the paper's dot: {sum(x[2] <= 0.0005 for x in c2)} of {len(c2)}; "
          + "; ".join(f"{a} {b} dot {c:.4f} nearest {d:.4f}" for a, b, c, d in c2))
    print("check 3 (TinyLFU, descriptive):")
    for r in c3:
        print("  ", r)
    print("check 4 (best algorithm among those run, descriptive):")
    for r in c4:
        print("  ", r)


def write(path: Path, rows: list) -> None:
    with path.open("w", newline="") as stream:
        w = csv.DictWriter(stream, tuple(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in {"compare", "tinylfu"}:
        raise SystemExit(__doc__)
    tinylfu(sys.argv[2]) if sys.argv[1] == "tinylfu" else compare()
