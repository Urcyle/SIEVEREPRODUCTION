#!/usr/bin/env python3
"""Compare the five Meta KV traces (split from the merged file) with SIEVEREPRODUCTION and the paper (protocol: docs/metakv_split_protocol.md).

  python3 -B scripts/metakv_split_compare.py compare     # checks 1 and 2 (and 3 once the pre-fix runs exist); works on partial data
  python3 -B scripts/metakv_split_compare.py prefix      # run the pre-fix TinyLFU build on the cells that have a saved exact capacity (one run at a time)
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sieve_repro.core import parse_counters
from sieve_repro.run import file_sha256

EXT = ROOT / "local_results/metakv_split_extension"
OUT = EXT
SNAP = ROOT / "external_replication/sievereproduction_43fc450/fig4"
PREFIX_BINARY = ROOT / "build/paper-tinylfu/cmake/bin/cachesim"
PREFIX_RUNS = EXT / "tinylfu_prefix_runs.csv"
LABELS = {"fifo": "FIFO", "lru": "LRU", "clock": "CLOCK", "sieve": "SIEVE", "arc": "ARC", "twoq": "TwoQ", "lirs": "LIRS", "tinylfu_snapshot": "TinyLFU",
          "blru": "B-LRU", "hyperbolic": "Hyperbolic", "lhd": "LHD", "cacheus": "CACHEUS"}
RANDOM = {"LHD", "CACHEUS"}
# paper dot (1 = most opaque) of each trace, as matched by SIEVEREPRODUCTION from SIEVE's value (its summary.md); NOT the trace number
DOT_OF_TRACE = {5: 1, 1: 2, 3: 3, 4: 4, 2: 5}


def records() -> dict:
    out = {}
    for path in EXT.glob("worker*/runs/*/complete.json"):
        r = json.loads(path.read_text())
        spec = r["spec"]
        label = spec.get("trace_label") or spec.get("workload_label")
        policy = spec.get("policy_label") or spec.get("policy")
        fraction = spec.get("capacity_fraction")
        if label and label.startswith("metakv_trace") and fraction is not None and policy in LABELS:
            out[(int(label.removeprefix("metakv_trace")), fraction, LABELS[policy])] = r
    return out


def reduction(f, m):
    return (f - m) / max(f, m)


def compare() -> None:
    ours = records()
    theirs = {(int(r["trace"].rsplit("_", 1)[1].split(".")[0]), "large" if r["size"] == "large" else "small", r["algo"]): r
              for r in csv.DictReader((SNAP / "fig4.csv").open(newline="")) if r["dataset"] == "metaKV"}
    dots = {}
    for r in csv.DictReader((SNAP / "fig4_paper_values.csv").open(newline="")):
        if r["dataset"] == "metaKV":
            dots[(int(r["trace_idx"]), r["size"], r["algo"])] = float(r["reduction"])
    prefix = {}
    if PREFIX_RUNS.exists():
        for r in csv.DictReader(PREFIX_RUNS.open(newline="")):
            prefix[(int(r["trace"]), float(r["capacity_fraction"]))] = int(r["misses"])
    rows, c1_bad, c2 = [], [], []
    for (n, f, algo), r in sorted(ours.items()):
        if algo == "FIFO":
            continue
        size = "large" if f == 0.1 else "small"
        fifo = ours.get((n, f, "FIFO"))
        if fifo is None:
            continue
        red = reduction(fifo["n_miss"], r["n_miss"])
        mr = r["n_miss"] / r["n_req"]
        t = theirs.get((n, size, algo))
        d = dots.get((DOT_OF_TRACE[n], size, algo))
        row = {"trace": n, "size": size, "algo": algo, "our_miss_ratio": f"{mr:.4f}", "theirs_miss_ratio": t["miss_ratio"] if t else "",
               "difference": f"{mr - float(t['miss_ratio']):+.4f}" if t else "", "our_reduction": f"{red:.4f}",
               "paper_dot_of_this_trace": f"{d:.4f}" if d is not None else "", "distance_to_paper": f"{abs(red - d):.4f}" if d is not None else ""}
        rows.append(row)
        if t and algo not in RANDOM and abs(mr - float(t["miss_ratio"])) > 0.0005 + 1e-9:
            c1_bad.append((n, size, algo, row["difference"]))
        if algo == "SIEVE" and d is not None:
            c2.append(abs(red - d))
    tl = []
    for (n, f), m in sorted(prefix.items()):
        size = "large" if f == 0.1 else "small"
        fifo = ours.get((n, f, "FIFO"))
        pinned = ours.get((n, f, "TinyLFU"))
        d = dots.get((DOT_OF_TRACE[n], size, "TinyLFU"))
        if fifo is None or d is None:
            continue
        tl.append({"trace": n, "size": size, "paper_dot": f"{d:.4f}", "prefix_reduction": f"{reduction(fifo['n_miss'], m):.4f}",
                   "pinned_reduction": f"{reduction(fifo['n_miss'], pinned['n_miss']):.4f}" if pinned else "",
                   "prefix_distance": f"{abs(reduction(fifo['n_miss'], m) - d):.4f}",
                   "pinned_distance": f"{abs(reduction(fifo['n_miss'], pinned['n_miss']) - d):.4f}" if pinned else ""})
    if rows:
        with (OUT / "comparison.csv").open("w", newline="") as stream:
            w = csv.DictWriter(stream, tuple(rows[0]))
            w.writeheader()
            w.writerows(rows)
    if tl:
        with (OUT / "tinylfu_prefix_vs_pinned.csv").open("w", newline="") as stream:
            w = csv.DictWriter(stream, tuple(tl[0]))
            w.writeheader()
            w.writerows(tl)
    done_cells = {(n, f) for (n, f, a) in ours}
    print(f"runs saved: {len(ours)}; trace/size cells with a FIFO baseline: {sum(1 for c in done_cells if (c[0], c[1], 'FIFO') in ours)}")
    print(f"check 1 (deterministic policies within 0.0005 of SIEVEREPRODUCTION): {len([r for r in rows if r['theirs_miss_ratio'] and r['algo'] not in RANDOM]) - len(c1_bad)} of "
          f"{len([r for r in rows if r['theirs_miss_ratio'] and r['algo'] not in RANDOM])} agree; exceptions {c1_bad[:6]}")
    print(f"check 2 (SIEVE within 0.0005 of the paper's dot for the trace): {sum(x <= 0.0005 for x in c2)} of {len(c2)}; max {max(c2) if c2 else None}")
    print(f"check 3 (TinyLFU pre-fix vs pinned vs paper, descriptive): {len(tl)} cells")
    for r in tl:
        print("  ", r)


def prefix() -> None:
    ours = records()
    done = {(int(r["trace"]), float(r["capacity_fraction"])) for r in csv.DictReader(PREFIX_RUNS.open(newline=""))} if PREFIX_RUNS.exists() else set()
    cells = sorted({(n, f) for (n, f, a), r in ours.items() if a == "FIFO"})
    with tempfile.TemporaryDirectory(prefix="kvpre_") as tmp, PREFIX_RUNS.open("a", newline="") as stream:
        w = csv.DictWriter(stream, ("trace", "capacity_fraction", "capacity_objects", "requests", "misses", "binary_sha256"))
        if stream.tell() == 0:
            w.writeheader()
        for n, f in cells:
            if (n, f) in done:
                continue
            ref = ours[(n, f, "FIFO")]
            trace = ROOT / f"data/metakv_split/kvcache_traces_{n}.valid.oracleGeneral.zst"
            command = [str(PREFIX_BINARY), str(trace), "oracleGeneral", "wtinylfu", str(ref["cache_size"]), "--ignore-obj-size", "1", "--num-thread", "1",
                       "--warmup-sec", "-1", "--eviction-params", "main-cache=SLRU,window-size=0.01"]
            out = subprocess.run(command, cwd=tmp, capture_output=True, text=True, check=True).stdout
            line = [l for l in out.splitlines() if l.startswith("SIEVE_COUNTERS")][0]
            rec = parse_counters("SIEVE_COUNTERS policy=X " + line.split(" ", 2)[2])
            if rec["n_req"] != ref["n_req"] or rec["cache_size"] != ref["cache_size"]:
                raise RuntimeError("request count or capacity differs from the baseline")
            w.writerow({"trace": n, "capacity_fraction": f, "capacity_objects": ref["cache_size"], "requests": rec["n_req"], "misses": rec["n_miss"],
                        "binary_sha256": file_sha256(PREFIX_BINARY)})
            stream.flush()
            print(n, f, rec["n_miss"], flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"compare", "prefix"}:
        raise SystemExit(__doc__)
    {"compare": compare, "prefix": prefix}[sys.argv[1]]()
