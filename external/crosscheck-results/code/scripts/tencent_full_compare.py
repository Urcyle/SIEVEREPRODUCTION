#!/usr/bin/env python3
"""Checks 1-4 of docs/tencent_full_protocol.md on whatever Tencent runs have finished.

  python3 -B scripts/tencent_full_run.py summarize && python3 -B scripts/tencent_full_compare.py
"""

from __future__ import annotations

import csv
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "external_replication/sievereproduction_43fc450/fig4"
OUT = ROOT / "local_results/tencent_full"
LABEL = {"fifo": "FIFO", "lru": "LRU", "clock": "CLOCK", "sieve": "SIEVE", "arc": "ARC", "twoq": "TwoQ", "lirs": "LIRS", "lhd": "LHD",
         "hyperbolic": "Hyperbolic", "tinylfu_snapshot": "TinyLFU", "cacheus": "CACHEUS", "blru": "B-LRU"}
RANDOM = {"LHD", "CACHEUS"}
DOT_INDEX = {"tencent_photo2": 1, "tencent_photo1": 2}      # paper dot of each trace, as matched by SIEVEREPRODUCTION (fig4/summary.md)
SIZE = {0.001: "small", 0.1: "large"}
SPREAD_SEEDS = tuple(range(1, 9)) + (42,)


def read(path: Path) -> list[dict]:
    return list(csv.DictReader(path.open(newline="")))


def reduction(f: float, m: float) -> float:
    return 0.0 if max(f, m) == 0 else (f - m) / max(f, m)


def main() -> None:
    ours = read(OUT / "tencent_full.csv")
    theirs = {(r["trace"], r["size"], r["algo"]): r for r in read(SNAP / "fig4.csv") if r["dataset"] == "tencentPhoto"}
    dots = {(int(r["trace_idx"]), r["size"], r["algo"]): float(r["reduction"]) for r in read(SNAP / "fig4_paper_values.csv") if r["dataset"] == "tencentPhoto"}
    sample = {(r["trace"], float(r["fraction"]), r["policy"], int(r["seed"])): r for r in ours if r["family"] == "sample"}
    full = {(r["trace"], float(r["fraction"]), r["policy"]): r for r in ours if r["family"] == "full" and r["seed"] == "42"}

    rows, c1, c1_bad, c1_sample_mismatch, c2 = [], 0, [], [], []
    for (trace, frac, policy, seed), r in sorted(sample.items()):
        if seed != 42:
            continue
        size, algo = SIZE[frac], LABEL[policy]
        t = theirs.get((trace, size, algo))
        fifo = sample.get((trace, frac, "fifo", 42))
        mr = int(r["misses"]) / int(r["requests"])
        red = reduction(int(fifo["misses"]) / int(fifo["requests"]), mr) if fifo else None
        dot = dots.get((DOT_INDEX[trace], size, algo))
        row = {"trace": trace, "size": size, "algo": algo, "our_miss_ratio": f"{mr:.4f}", "theirs_miss_ratio": t["miss_ratio"] if t else "",
               "difference": f"{mr - float(t['miss_ratio']):+.4f}" if t else "", "our_requests": r["requests"], "theirs_requests": t["requests"] if t else "",
               "our_cache": r["cache_objects"], "theirs_cache": t["cache_size"] if t else "",
               "our_reduction": f"{red:.4f}" if red is not None else "", "paper_dot": f"{dot:.4f}" if dot is not None else "",
               "distance_to_paper": f"{abs(red - dot):.4f}" if red is not None and dot is not None else ""}
        rows.append(row)
        if t and (int(r["requests"]) != int(t["requests"]) or int(r["cache_objects"]) != int(t["cache_size"])):
            c1_sample_mismatch.append((trace, size, algo))
        elif t and algo not in RANDOM:
            c1 += 1
            if abs(mr - float(t["miss_ratio"])) > 0.0005 + 1e-9:
                c1_bad.append((trace, size, algo, row["difference"]))
        if algo == "SIEVE" and red is not None and dot is not None:
            c2.append((trace, size, abs(red - dot)))
    if rows:
        with (OUT / "comparison.csv").open("w", newline="") as stream:
            w = csv.DictWriter(stream, tuple(rows[0]))
            w.writeheader()
            w.writerows(rows)
    print(f"check 1: {c1 - len(c1_bad)} of {c1} deterministic sample cells within 0.0005 of SIEVEREPRODUCTION (TinyLFU included); exceptions {c1_bad}; "
          f"cells whose sample (requests or cache) differs from theirs: {c1_sample_mismatch}")
    print(f"check 2: SIEVE within 0.0005 of the paper's dot: {sum(x[2] <= 0.0005 for x in c2)} of {len(c2)}; " + "; ".join(f"{a} {b} {c:.4f}" for a, b, c in c2))

    print("check 3 (H-T), tencent_photo2, CACHEUS on the 10% sample:")
    for frac in (0.1, 0.001):
        size = SIZE[frac]
        fifo = sample.get(("tencent_photo2", frac, "fifo", 42))
        sieve = sample.get(("tencent_photo2", frac, "sieve", 42))
        reds = {}
        for seed in SPREAD_SEEDS:
            r = sample.get(("tencent_photo2", frac, "cacheus", seed))
            if r and fifo:
                reds[seed] = reduction(int(fifo["misses"]) / int(fifo["requests"]), int(r["misses"]) / int(r["requests"]))
        if not reds or not sieve:
            print(f"  {size}: not enough runs yet ({len(reds)} CACHEUS seeds)")
            continue
        s_red = reduction(int(fifo["misses"]) / int(fifo["requests"]), int(sieve["misses"]) / int(sieve["requests"]))
        dot = dots[(1, size, "CACHEUS")]
        lo, hi = min(reds.values()), max(reds.values())
        above = sum(v > s_red for v in reds.values())
        verdict = "supported" if (hi - lo) > 0.01 and lo - 0.005 <= dot <= hi + 0.005 else "not supported"
        print(f"  {size}: {len(reds)} seeds, CACHEUS reduction range {lo:.4f}-{hi:.4f} (width {hi - lo:.4f}), mean {statistics.fmean(reds.values()):.4f}; "
              f"paper CACHEUS dot {dot:.4f}; SIEVE {s_red:.4f}; seeds with CACHEUS above SIEVE: {above} of {len(reds)}; rule (width > 0.01 and dot within the range +-0.005): {verdict}"
              + ("   <- the pre-declared test is the large cache" if size == "large" else ""))
        with (OUT / f"cacheus_spread_{size}.csv").open("w", newline="") as stream:
            w = csv.writer(stream)
            w.writerow(["seed", "reduction_from_fifo", "sieve_reduction", "paper_cacheus_dot"])
            for seed, v in sorted(reds.items()):
                w.writerow([seed, f"{v:.6f}", f"{s_red:.6f}", f"{dot:.4f}"])

    print("check 4 (descriptive), full size against the sample:")
    out4 = []
    for (trace, frac, policy), r in sorted(full.items()):
        fifo_full = full.get((trace, frac, "fifo"))
        if not fifo_full:
            continue
        red_full = reduction(int(fifo_full["misses"]) / int(fifo_full["requests"]), int(r["misses"]) / int(r["requests"]))
        s = sample.get((trace, frac, policy, 42))
        fifo_s = sample.get((trace, frac, "fifo", 42))
        red_s = reduction(int(fifo_s["misses"]) / int(fifo_s["requests"]), int(s["misses"]) / int(s["requests"])) if s and fifo_s else None
        out4.append({"trace": trace, "size": SIZE[frac], "algo": LABEL[policy], "full_reduction": f"{red_full:.4f}",
                     "sample_reduction": f"{red_s:.4f}" if red_s is not None else "", "gap": f"{red_full - red_s:+.4f}" if red_s is not None else ""})
    if out4:
        with (OUT / "full_vs_sample.csv").open("w", newline="") as stream:
            w = csv.DictWriter(stream, tuple(out4[0]))
            w.writeheader()
            w.writerows(out4)
    for row in out4:
        print("  ", row)
    omitted = OUT / "omitted.csv"
    if omitted.exists():
        print("omissions:", [(r["family"], r["trace"], r["fraction"], r["policy"], r["seed"]) for r in read(omitted)])


if __name__ == "__main__":
    main()
