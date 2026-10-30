#!/usr/bin/env python3
"""Figure 10 (workload change) at the 10,000-object support found for Figure 8.

The paper does not state Figure 10's object count, cache size or request count. Figure 8's
support (10,000 objects, `docs/independent_replication_comparison.md`) is the only size known to
reproduce a paper figure, so it is tried here. The cache size is the one free parameter: the
sweep below was declared before the run, and the size is chosen by the LRU phase-1 steady-state
miss ratio alone (the paper's plot shows about 0.188); the other three policies' levels and both
popularity panels are then a test, not a fit.

  python3 -B scripts/zipf10_support_check.py run        # resumable
  python3 -B scripts/zipf10_support_check.py summarize  # tables from saved samples only
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
from sieve_repro.observer import parse_observer_output
from sieve_repro.run import build_simulator_command, file_sha256
from sieve_repro.zipf import generate_phase_change, phase_change_frequency_counts, top_ids

OBSERVER = ROOT / "build/observer-sim/bin/cachesim"
OUT = ROOT / "local_results/zipf10_support_check"
SAMPLES = OUT / "samples.csv"
OBJECTS, PER_PHASE, ALPHA, INTERVAL = 10_000, 5_000_000, 1.0, 100_000
SEED_PAIRS = ((42, 43), (44, 45))
CAPACITIES = (1000, 2000, 3000, 4000)          # 10, 20, 30, 40 % of the support (declared before running)
POLICIES = ("lru", "lfu", "arc", "sieve")
FIELDS = ("seed_pair", "policy", "capacity_objects", "n_req", "kind", "interval_miss_ratio",
          "popular_ratio", "trace_sha256", "binary_sha256")
# read by eye from the paper's Figure 10 (about +/-0.01); used only for the comparison table
PAPER_MISS_PHASE1 = {"ARC": 0.165, "LRU": 0.188, "LFU": 0.155, "SIEVE": 0.150}
PAPER_POPULAR_PHASE1 = {"SIEVE": 0.75, "LFU": 0.71, "ARC": 0.65, "LRU": 0.54}


def load() -> list[dict]:
    return list(csv.DictReader(SAMPLES.open(newline=""))) if SAMPLES.exists() else []


def observe(trace, hot1, hot2, policy, capacity, scratch):
    command = build_simulator_command(binary=OBSERVER, trace=trace, policy=policy, fraction=None,
                                      capacity_objects=capacity)
    env = dict(os.environ, SIEVE_OBSERVER_INTERVAL=str(INTERVAL), SIEVE_OBSERVER_HOTSET=str(hot1),
               SIEVE_OBSERVER_HOTSET_NEXT=str(hot2), SIEVE_OBSERVER_SWITCH_AFTER=str(PER_PHASE))
    out = subprocess.run(command, cwd=scratch, env=env, capture_output=True, text=True, check=True).stdout
    record = parse_counters([l for l in out.splitlines() if l.startswith("SIEVE_COUNTERS")][0])
    return parse_observer_output(out, n_req=record["n_req"], n_miss=record["n_miss"], cache_size=capacity,
                                 interval=INTERVAL, policy=policy, has_hotset=True, switch_after=PER_PHASE)


def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    done = {(r["seed_pair"], r["policy"], int(r["capacity_objects"])) for r in load()}
    binary = file_sha256(OBSERVER)
    for seeds in SEED_PAIRS:
        tag = f"{seeds[0]}-{seeds[1]}"
        todo = [(p, c) for c in CAPACITIES for p in POLICIES if (tag, p, c) not in done]
        if not todo:
            continue
        with tempfile.TemporaryDirectory(prefix="zipf10_") as tmp:
            trace = Path(tmp) / "phase.oracleGeneral"
            generate_phase_change(trace, objects=OBJECTS, requests_per_phase=PER_PHASE, alpha=ALPHA, seeds=seeds)
            digest = file_sha256(trace)
            counts = phase_change_frequency_counts(trace, objects=OBJECTS, requests_per_phase=PER_PHASE)
            scratch = Path(tmp) / "cwd"
            scratch.mkdir()
            hot = {}
            for c in {c for _, c in todo}:
                paths = []
                for phase in (0, 1):
                    path = Path(tmp) / f"hot_{phase}_{c}.txt"
                    path.write_text("".join(f"{int(k)}\n" for k in top_ids(counts[phase], c, id_offset=phase * OBJECTS)))
                    paths.append(path)
                hot[c] = paths
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda j: (j, observe(trace, *hot[j[1]], j[0], j[1], scratch)), todo))
        with SAMPLES.open("a", newline="") as stream:
            writer = csv.DictWriter(stream, FIELDS)
            if stream.tell() == 0:
                writer.writeheader()
            for (policy, cap), rows in results:
                for r in rows:
                    if r["kind"] == "hand":
                        continue
                    writer.writerow({"seed_pair": tag, "policy": policy, "capacity_objects": cap, "n_req": r["n_req"],
                                     "kind": r["kind"], "interval_miss_ratio": "" if r["interval_miss_ratio"] is None else f"{r['interval_miss_ratio']:.6f}",
                                     "popular_ratio": "" if r["popular_ratio"] is None else f"{r['popular_ratio']:.6f}",
                                     "trace_sha256": digest, "binary_sha256": binary})
        print(f"seeds {tag}: {len(results)} runs saved", flush=True)


def window(rows, lo, hi, key):
    vals = [float(r[key]) for r in rows if lo < int(r["n_req"]) <= hi and r["kind"] == "sample" and r[key] != ""]
    return statistics.fmean(vals)


def summarize() -> None:
    rows = load()
    if not rows:
        raise SystemExit("no saved samples")
    groups = {}
    for r in rows:
        groups.setdefault((r["seed_pair"], r["policy"], int(r["capacity_objects"])), []).append(r)
    half = PER_PHASE
    table = []
    for (tag, policy, cap), g in sorted(groups.items()):
        table.append({"seed_pair": tag, "policy": policy.upper(), "capacity_objects": cap,
                      "phase1_miss_second_half": f"{window(g, half // 2, half, 'interval_miss_ratio'):.4f}",
                      "phase1_miss_first_interval_after_switch": f"{[float(r['interval_miss_ratio']) for r in g if int(r['n_req']) == half + INTERVAL][0]:.4f}",
                      "phase2_miss_second_half": f"{window(g, half + half // 2, 2 * half, 'interval_miss_ratio'):.4f}",
                      "phase1_popular_second_half": f"{window(g, half // 2, half, 'popular_ratio'):.4f}",
                      "popular_at_switch_instant": f"{[float(r['popular_ratio']) for r in g if r['kind'] == 'switch'][0]:.4f}",
                      "popular_first_sample_after_switch": f"{[float(r['popular_ratio']) for r in g if int(r['n_req']) == half + INTERVAL][0]:.4f}",
                      "phase2_popular_final": f"{[float(r['popular_ratio']) for r in g if int(r['n_req']) == 2 * half][-1]:.4f}"})
    with (OUT / "steady_state.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, tuple(table[0]))
        writer.writeheader()
        writer.writerows(table)
    # the one fitted choice: capacity whose mean LRU phase-1 level is closest to the paper's
    lru = {}
    for r in table:
        if r["policy"] == "LRU":
            lru.setdefault(r["capacity_objects"], []).append(float(r["phase1_miss_second_half"]))
    best = min(lru, key=lambda c: abs(statistics.fmean(lru[c]) - PAPER_MISS_PHASE1["LRU"]))
    compare = []
    for policy in ("ARC", "LRU", "LFU", "SIEVE"):
        sel = [r for r in table if r["policy"] == policy and r["capacity_objects"] == best]
        compare.append({"policy": policy, "cache_objects": best,
                        "paper_phase1_miss_by_eye": PAPER_MISS_PHASE1[policy],
                        "ours_phase1_miss": f"{statistics.fmean(float(r['phase1_miss_second_half']) for r in sel):.4f}",
                        "paper_phase1_popular_by_eye": PAPER_POPULAR_PHASE1[policy],
                        "ours_phase1_popular": f"{statistics.fmean(float(r['phase1_popular_second_half']) for r in sel):.4f}",
                        "ours_miss_first_interval_after_switch": f"{statistics.fmean(float(r['phase1_miss_first_interval_after_switch']) for r in sel):.4f}",
                        "ours_popular_first_sample_after_switch": f"{statistics.fmean(float(r['popular_first_sample_after_switch']) for r in sel):.4f}",
                        "ours_popular_final": f"{statistics.fmean(float(r['phase2_popular_final']) for r in sel):.4f}"})
    with (OUT / "paper_comparison.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, tuple(compare[0]))
        writer.writeheader()
        writer.writerows(compare)
    # post-hoc sensitivity: the miss-ratio bump after the switch, averaged over the first k intervals of 100,000 requests
    bump = []
    for policy in ("lru", "arc", "sieve", "lfu"):
        for k in (1, 2, 3, 4, 5, 10):
            values = []
            for (tag, pol, cap), g in groups.items():
                if pol != policy or cap != best:
                    continue
                by_n = {int(r["n_req"]): float(r["interval_miss_ratio"]) for r in g if r["kind"] == "sample"}
                before = statistics.fmean(by_n[x] for x in range(half // 2 + INTERVAL, half + 1, INTERVAL))
                after = statistics.fmean(by_n[half + INTERVAL * i] for i in range(1, k + 1))
                values.append(after - before)
            bump.append({"policy": policy.upper(), "cache_objects": best, "interval_requests": INTERVAL * k,
                         "mean_bump_after_switch": f"{statistics.fmean(values):.4f}"})
    with (OUT / "bump_vs_interval.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, tuple(bump[0]))
        writer.writeheader()
        writer.writerows(bump)
    print("chosen cache (by LRU only):", best)
    for c in compare:
        print(c)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"run", "summarize"}:
        raise SystemExit(__doc__)
    {"run": run, "summarize": summarize}[sys.argv[1]]()
