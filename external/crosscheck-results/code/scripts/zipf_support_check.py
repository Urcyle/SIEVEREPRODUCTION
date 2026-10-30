#!/usr/bin/env python3
"""Figures 8 and 9 on a 10,000-object Zipf support (resolves the earlier Fig 8 gap).

Origin: the independent SIEVEREPRODUCTION repository stated that the paper's Figure 8a miss
ratios are reproduced when the Zipf support is 10,000 objects (10 M requests), whereas our
earlier grids used 100,000-1,000,000 objects. This script tests that claim with OUR generator
(`sieve_repro.zipf.generate_zipf`, NumPy PCG64, seeds 42-44) and OUR pinned simulator build,
saving exact integer counters. It uses nothing from the other repository.

Usage:  python3 -B scripts/zipf_support_check.py run        # miss ratios, resumable, a few minutes
        python3 -B scripts/zipf_support_check.py popular    # popular-object ratio (Figs 8b, 9b)
        python3 -B scripts/zipf_support_check.py popular-rank  # Fig 8b with the generating-rank popularity definition
        python3 -B scripts/zipf_support_check.py hand       # Fig 9c: SIEVE's hand (setup transplanted, see below)
        python3 -B scripts/zipf_support_check.py summarize  # CSVs from the saved runs only

Fig 9c setup (1,000,000 objects, a 1,000-object cache, curves cut at the 262,144th eviction) is the
other repository's post-hoc choice: it searched workload and cache sizes until the hand's behaviour
matched the paper. Running it here with our own generator/seeds tests whether it is reproducible,
not whether it was predicted.
"""

from __future__ import annotations

import csv
import os
from collections import defaultdict
import statistics
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sieve_repro.core import parse_counters
from sieve_repro.run import build_simulator_command, file_sha256
from sieve_repro.observer import parse_observer_output
from sieve_repro.zipf import frequency_counts, generate_zipf, top_ids
from sieve_repro.zipf8b_artifact_scale import summarize_observations

BINARY = ROOT / "build/counter-sim/bin/cachesim"
OUT = ROOT / "local_results/zipf_support_check"
RUNS = OUT / "runs.csv"
POPULAR = OUT / "popular_runs.csv"
POPULAR_RANK = OUT / "popular_runs_generating_rank.csv"
OBSERVER_BINARY = ROOT / "build/observer-sim/bin/cachesim"
OBSERVE_EVERY = 10_000   # requests between snapshots (the other repository's choice; ours used 100,000 at 100 M requests)
FIG8_PAPER = ROOT / "local_results/zipf8_paper_capacity_grid/figure8a_paper_vs_local.csv"
OBJECTS, REQUESTS = 10_000, 10_000_000
SEEDS = (42, 43, 44)
POLICIES = ("lru", "lfu", "arc", "sieve")
FIG8_CAPACITIES = (10, 30, 100, 300, 1000, 2000, 4000, 8000)   # 0.1 ... 80 % of 10,000
FIG9_ALPHAS = (0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6)
FIG9_CAPACITY = 1000                                            # 10 % of 10,000
POPULAR_FIELDS = ("alpha", "seed", "policy", "capacity_objects", "misses", "matches_counter_build",
                  "snapshots", "mean_popular_ratio", "final_popular_ratio", "observer_binary_sha256")
FIELDS = ("alpha", "seed", "policy", "capacity_objects", "objects", "requests", "misses",
          "miss_ratio", "unique_objects_observed", "trace_sha256", "binary_sha256")


def load_runs() -> list[dict]:
    if not RUNS.exists():
        return []
    with RUNS.open(newline="") as stream:
        return list(csv.DictReader(stream))


def wanted(alpha: float) -> tuple[int, ...]:
    caps = set(FIG8_CAPACITIES) if alpha == 1.0 else set()
    caps.add(FIG9_CAPACITY)
    return tuple(sorted(caps))


def simulate(trace: Path, policy: str, capacity: int, scratch: Path) -> dict:
    command = build_simulator_command(binary=BINARY, trace=trace, policy=policy,
                                      fraction=None, capacity_objects=capacity)
    done = subprocess.run(command, cwd=scratch, capture_output=True, text=True, check=True)
    lines = [line for line in done.stdout.splitlines() if line.startswith("SIEVE_COUNTERS")]
    if len(lines) != 1:
        raise RuntimeError("expected exactly one SIEVE_COUNTERS record")
    record = parse_counters(lines[0])
    if record["cache_size"] != capacity or record["n_req"] != REQUESTS:
        raise RuntimeError(f"unexpected counters {record}")
    return record


def unique_ids(trace: Path) -> int:
    import numpy as np
    from sieve_repro.zipf import RECORD_DTYPE
    seen = np.zeros(OBJECTS, dtype=bool)
    with trace.open("rb") as stream:
        while True:
            rows = np.fromfile(stream, dtype=RECORD_DTYPE, count=2_000_000)
            if not len(rows):
                break
            seen[rows["id"].astype(np.int64)] = True
    return int(seen.sum())


def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = load_runs()
    done = {(float(r["alpha"]), int(r["seed"]), r["policy"], int(r["capacity_objects"])) for r in rows}
    binary_hash = file_sha256(BINARY)
    for alpha in FIG9_ALPHAS:
        for seed in SEEDS:
            todo = [(p, c) for p in POLICIES for c in wanted(alpha)
                    if (alpha, seed, p, c) not in done]
            if not todo:
                continue
            with tempfile.TemporaryDirectory(prefix="zipf_support_") as tmp:
                trace = Path(tmp) / "zipf.oracleGeneral"
                generate_zipf(trace, objects=OBJECTS, requests=REQUESTS, alpha=alpha, seed=seed)
                trace_hash = file_sha256(trace)
                unique = unique_ids(trace)
                scratch = Path(tmp) / "cwd"
                scratch.mkdir()
                with ThreadPoolExecutor(max_workers=4) as pool:
                    results = list(pool.map(lambda job: (job, simulate(trace, job[0], job[1], scratch)), todo))
            with RUNS.open("a", newline="") as stream:
                writer = csv.DictWriter(stream, FIELDS)
                if stream.tell() == 0:
                    writer.writeheader()
                for (policy, capacity), record in results:
                    writer.writerow({
                        "alpha": alpha, "seed": seed, "policy": policy,
                        "capacity_objects": capacity, "objects": OBJECTS, "requests": REQUESTS,
                        "misses": record["n_miss"], "miss_ratio": record["n_miss"] / record["n_req"],
                        "unique_objects_observed": unique, "trace_sha256": trace_hash,
                        "binary_sha256": binary_hash})
            print(f"alpha={alpha} seed={seed}: {len(results)} runs saved", flush=True)


def observe(trace: Path, hotset: Path, policy: str, capacity: int, scratch: Path) -> dict:
    command = build_simulator_command(binary=OBSERVER_BINARY, trace=trace, policy=policy,
                                      fraction=None, capacity_objects=capacity)
    env = dict(os.environ, SIEVE_OBSERVER_INTERVAL=str(OBSERVE_EVERY),
               SIEVE_OBSERVER_HOTSET=str(hotset))
    done = subprocess.run(command, cwd=scratch, env=env, capture_output=True, text=True, check=True)
    lines = [line for line in done.stdout.splitlines() if line.startswith("SIEVE_COUNTERS")]
    if len(lines) != 1:
        raise RuntimeError("expected exactly one SIEVE_COUNTERS record")
    record = parse_counters(lines[0])
    rows = parse_observer_output(done.stdout, n_req=record["n_req"], n_miss=record["n_miss"],
                                 cache_size=capacity, interval=OBSERVE_EVERY, policy=policy,
                                 has_hotset=True)
    return {**record, **summarize_observations(rows)}


def popular(rank: bool = False) -> None:
    """Mean fraction of the C most frequent objects resident in the cache (observer build).

    rank=True uses the generating ranks instead (IDs 0..C-1, the C most probable objects), only for
    alpha = 1.0, to test whether the popularity definition explains the residual against Figure 8b."""
    OUT.mkdir(parents=True, exist_ok=True)
    popular_path = POPULAR_RANK if rank else POPULAR
    plain = {(float(r["alpha"]), int(r["seed"]), r["policy"], int(r["capacity_objects"])): int(r["misses"])
             for r in load_runs()}
    done = set()
    if popular_path.exists():
        done = {(float(r["alpha"]), int(r["seed"]), r["policy"], int(r["capacity_objects"]))
                for r in csv.DictReader(popular_path.open(newline=""))}
    binary_hash = file_sha256(OBSERVER_BINARY)
    for alpha in ((1.0,) if rank else FIG9_ALPHAS):
        for seed in SEEDS:
            todo = [(p, c) for p in POLICIES for c in wanted(alpha) if (alpha, seed, p, c) not in done]
            if not todo:
                continue
            with tempfile.TemporaryDirectory(prefix="zipf_support_") as tmp:
                trace = Path(tmp) / "zipf.oracleGeneral"
                generate_zipf(trace, objects=OBJECTS, requests=REQUESTS, alpha=alpha, seed=seed)
                counts = frequency_counts(trace, objects=OBJECTS)
                scratch = Path(tmp) / "cwd"
                scratch.mkdir()
                jobs = []
                for policy, capacity in todo:
                    hotset = Path(tmp) / f"hot_{capacity}.txt"
                    if not hotset.exists():
                        ids = range(capacity) if rank else top_ids(counts, capacity)
                        hotset.write_text("".join(f"{int(k)}\n" for k in ids))
                    jobs.append((policy, capacity, hotset))
                with ThreadPoolExecutor(max_workers=4) as pool:
                    results = list(pool.map(lambda j: (j, observe(trace, j[2], j[0], j[1], scratch)), jobs))
            with popular_path.open("a", newline="") as stream:
                writer = csv.DictWriter(stream, POPULAR_FIELDS)
                if stream.tell() == 0:
                    writer.writeheader()
                for (policy, capacity, _), record in results:
                    baseline = plain.get((alpha, seed, policy, capacity))
                    if baseline is not None and baseline != record["n_miss"]:
                        raise RuntimeError("observer build disagrees with the exact-counter build")
                    writer.writerow({"alpha": alpha, "seed": seed, "policy": policy,
                                     "capacity_objects": capacity, "misses": record["n_miss"],
                                     "matches_counter_build": baseline is not None,
                                     "snapshots": record["snapshot_count"],
                                     "mean_popular_ratio": f"{record['mean_popular_ratio']:.6f}",
                                     "final_popular_ratio": f"{record['final_popular_ratio']:.6f}",
                                     "observer_binary_sha256": binary_hash})
            print(f"popular alpha={alpha} seed={seed}: {len(results)} runs saved", flush=True)


HAND_ALPHAS = {0.8: 400_000, 1.0: 600_000, 1.2: 1_500_000}   # requests generated; curves are cut later
HAND_OBJECTS, HAND_CACHE, HAND_EVICTIONS, HAND_EVERY = 1_000_000, 1000, 262_144, 10
HAND_FIELDS = ("alpha", "seed", "n_req", "n_miss", "occupancy", "hand_normalized")


def hand() -> None:
    """Sample SIEVE's hand position every 10 requests (about one eviction; 250 was too coarse and missed wraps) with the observer build."""
    OUT.mkdir(parents=True, exist_ok=True)
    done = set()
    if (OUT / "hand_summary.csv").exists():
        done = {(float(r["alpha"]), int(r["seed"])) for r in csv.DictReader((OUT / "hand_summary.csv").open(newline=""))}
    for alpha, requests in HAND_ALPHAS.items():
        for seed in SEEDS:
            if (alpha, seed) in done:
                continue
            with tempfile.TemporaryDirectory(prefix="zipf_hand_") as tmp:
                trace = Path(tmp) / "zipf.oracleGeneral"
                generate_zipf(trace, objects=HAND_OBJECTS, requests=requests, alpha=alpha, seed=seed)
                scratch = Path(tmp) / "cwd"
                scratch.mkdir()
                command = build_simulator_command(binary=OBSERVER_BINARY, trace=trace, policy="sieve",
                                                  fraction=None, capacity_objects=HAND_CACHE)
                env = dict(os.environ, SIEVE_OBSERVER_INTERVAL=str(requests),
                           SIEVE_OBSERVER_HAND_INTERVAL=str(HAND_EVERY))
                out = subprocess.run(command, cwd=scratch, env=env, capture_output=True, text=True, check=True).stdout
            lines = [line for line in out.splitlines() if line.startswith("SIEVE_COUNTERS")]
            record = parse_counters(lines[0])
            observed = parse_observer_output(out, n_req=record["n_req"], n_miss=record["n_miss"],
                                             cache_size=HAND_CACHE, interval=requests, policy="sieve",
                                             has_hotset=False, hand_interval=HAND_EVERY)
            cut = HAND_CACHE + HAND_EVICTIONS
            keep = [r for r in observed if r["kind"] == "hand" and r["n_miss"] <= cut]
            if not keep or record["n_miss"] < cut:
                raise RuntimeError(f"alpha={alpha} seed={seed}: trace too short for {HAND_EVICTIONS} evictions")
            points = [(r["n_req"], r["hand_normalized"]) for r in keep]
            wraps = [i for i in range(1, len(points)) if points[i][1] < points[i - 1][1] - 0.5]
            above = [t for t, p in points if p > 0.9]
            near = {j for i in wraps for j in (i - 1, i)}
            thin = [r for i, r in enumerate(keep) if i % 40 == 0 or i in near or i == len(keep) - 1]
            with (OUT / "hand_summary.csv").open("a", newline="") as stream:
                writer = csv.DictWriter(stream, ("alpha", "seed", "curve_ends_at_request", "wraps", "wrap_times", "first_above_0.9"))
                if stream.tell() == 0:
                    writer.writeheader()
                writer.writerow({"alpha": alpha, "seed": seed, "curve_ends_at_request": points[-1][0], "wraps": len(wraps),
                                 "wrap_times": " ".join(str(points[i][0]) for i in wraps),
                                 "first_above_0.9": above[0] if above else -1})
            with (OUT / "hand_samples_thinned.csv").open("a", newline="") as stream:
                writer = csv.DictWriter(stream, HAND_FIELDS)
                if stream.tell() == 0:
                    writer.writeheader()
                for r in thin:
                    writer.writerow({"alpha": alpha, "seed": seed, "n_req": r["n_req"], "n_miss": r["n_miss"],
                                     "occupancy": r["occupancy"], "hand_normalized": f"{r['hand_normalized']:.4f}"})
            keep = thin
            print(f"hand alpha={alpha} seed={seed}: {len(keep)} samples", flush=True)


def write_csv(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        writer.writerows(rows)


def summarize() -> None:
    rows = load_runs()
    if not rows:
        raise SystemExit("no saved runs; run `run` first")
    paper8 = {(float(r["capacity_fraction"]), r["policy"]): float(r["digitized_paper_miss_ratio"])
              for r in csv.DictReader(FIG8_PAPER.open(newline=""))}
    by = {}
    for r in rows:
        by.setdefault((float(r["alpha"]), r["policy"].upper(), int(r["capacity_objects"])), []).append(float(r["miss_ratio"]))
    fig8 = []
    for (alpha, policy, cap), values in sorted(by.items()):
        if alpha != 1.0 or cap not in FIG8_CAPACITIES:
            continue
        fraction = cap / OBJECTS
        paper = paper8[(fraction, policy)]
        mean = statistics.fmean(values)
        fig8.append({"capacity_percent": 100 * fraction, "policy": policy, "paper_digitized": f"{paper:.6f}",
                     "mean_miss_ratio": f"{mean:.6f}", "min_seed": f"{min(values):.6f}",
                     "max_seed": f"{max(values):.6f}", "mean_minus_paper": f"{mean - paper:+.6f}",
                     "seeds": len(values)})
    write_csv(OUT / "figure8a_10k_objects_vs_paper.csv",
              ("capacity_percent", "policy", "paper_digitized", "mean_miss_ratio", "min_seed",
               "max_seed", "mean_minus_paper", "seeds"), fig8)
    fig9 = []
    for (alpha, policy, cap), values in sorted(by.items()):
        if cap == FIG9_CAPACITY:
            fig9.append({"alpha": alpha, "policy": policy, "cache_objects": cap,
                         "mean_miss_ratio": f"{statistics.fmean(values):.6f}",
                         "min_seed": f"{min(values):.6f}", "max_seed": f"{max(values):.6f}",
                         "seeds": len(values)})
    write_csv(OUT / "figure9a_10k_objects_miss_ratio.csv",
              ("alpha", "policy", "cache_objects", "mean_miss_ratio", "min_seed", "max_seed", "seeds"), fig9)
    if POPULAR.exists():
        pop = {}
        for r in csv.DictReader(POPULAR.open(newline="")):
            pop.setdefault((float(r["alpha"]), r["policy"].upper(), int(r["capacity_objects"])), []).append(float(r["mean_popular_ratio"]))
        rows_p = [{"alpha": a, "policy": p, "cache_objects": c, "mean_popular_ratio": f"{statistics.fmean(v):.6f}",
                   "min_seed": f"{min(v):.6f}", "max_seed": f"{max(v):.6f}", "seeds": len(v)}
                  for (a, p, c), v in sorted(pop.items())]
        write_csv(OUT / "popular_ratio_10k_objects.csv",
                  ("alpha", "policy", "cache_objects", "mean_popular_ratio", "min_seed", "max_seed", "seeds"), rows_p)
    worst = max(abs(float(r["mean_minus_paper"])) for r in fig8)
    print(f"Figure 8a: {len(fig8)} points, largest |mean - paper| = {worst:.4f}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"run", "popular", "popular-rank", "hand", "summarize"}:
        raise SystemExit(__doc__)
    {"run": run, "popular": popular, "popular-rank": lambda: popular(rank=True), "hand": hand, "summarize": summarize}[sys.argv[1]]()
