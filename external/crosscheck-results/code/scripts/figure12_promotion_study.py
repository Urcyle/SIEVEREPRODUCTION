#!/usr/bin/env python3
"""Figure 12 promotion study (protocol: docs/figure12_promotion_protocol.md, frozen before any run).

  python3 -B scripts/figure12_promotion_study.py run        # control + 28 variant runs, resumable
  python3 -B scripts/figure12_promotion_study.py summarize  # tables and the protocol's decision rule, from saved counters
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

BINARY = ROOT / "build/figure12-promote/bin/cachesim"
SAVED = ROOT / "local_results/figure12_public_selected_seven/figure12_public_selected_seven.csv"
OUT = ROOT / "local_results/figure12_promotion"
RUNS = OUT / "runs.csv"
TRACES = {"meta_reag": "data/metaCDN/meta_reag.oracleGeneral.zst", "meta_rprn": "data/metaCDN/meta_rprn.oracleGeneral.zst",
          "meta_rnha": "data/metaCDN/meta_rnha.oracleGeneral.zst", "wiki_2019t": "data/wiki/wiki_2019t.oracleGeneral.zst",
          "twitter_cluster10": "data/twitter/cluster10.oracleGeneral.zst", "twitter_cluster26": "data/twitter/cluster26.oracleGeneral.zst",
          "twitter_cluster50": "data/twitter/cluster50.oracleGeneral.zst"}
# label -> (cachesim algorithm, eviction parameters, saved-grid policy name for the control, or None)
CONFIGS = {
    "arc_lru_control": ("arc", None, "arc"),
    "arc_sieve_control": ("arc", "T2-type=SIEVE", "arc_sieve"),
    "twoq_lru_control": ("twoq", None, "twoq"),
    "twoq_sieve_control": ("twoq", "Am-type=SIEVE", "twoq_sieve"),
    "arc_sieve_visited": ("arc", "T2-type=SIEVE,T2-promote=visited", None),
    "twoq_sieve_visited": ("twoq", "Am-type=SIEVE,Am-promote=visited", None),
}
CONTROL_TRACE = "meta_reag"
FIELDS = ("trace", "capacity_fraction", "config", "capacity_objects", "requests", "misses", "trace_sha256", "binary_sha256")


def saved() -> dict:
    return {(r["trace"], float(r["capacity_fraction"]), r["policy"]): r for r in csv.DictReader(SAVED.open(newline=""))}


def load() -> list[dict]:
    return list(csv.DictReader(RUNS.open(newline=""))) if RUNS.exists() else []


def simulate(trace_label: str, fraction: float, config: str, capacity: int, scratch: Path) -> dict:
    algo, params, _ = CONFIGS[config]
    command = [str(BINARY), str(ROOT / TRACES[trace_label]), "oracleGeneral", algo, str(capacity), "--ignore-obj-size", "1",
               "--num-thread", "1", "--warmup-sec", "-1"]
    if params:
        command += ["--eviction-params", params]
    out = subprocess.run(command, cwd=scratch, capture_output=True, text=True, check=True).stdout
    lines = [l for l in out.splitlines() if l.startswith("SIEVE_COUNTERS")]
    if len(lines) != 1:
        raise RuntimeError(f"{trace_label} {config}: expected one SIEVE_COUNTERS record")
    # the exact-counter regex excludes dots in policy names; normalise the policy token like the baseline runner does
    line = "SIEVE_COUNTERS policy=X " + lines[0].split(" ", 2)[2]
    record = parse_counters(line)
    if record["cache_size"] != capacity:
        raise RuntimeError("simulator capacity differs from the saved capacity")
    return record


def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ref = saved()
    done = {(r["trace"], float(r["capacity_fraction"]), r["config"]) for r in load()}
    binary_hash = file_sha256(BINARY)
    jobs = []
    for trace in TRACES:
        for fraction in (0.001, 0.1):
            for config, (_, _, control) in CONFIGS.items():
                if control and trace != CONTROL_TRACE:
                    continue
                if (trace, fraction, config) not in done:
                    jobs.append((trace, fraction, config))
    hashes = {}
    with tempfile.TemporaryDirectory(prefix="promo_") as tmp:
        scratch = Path(tmp)

        def work(job):
            trace, fraction, config = job
            row = ref[(trace, fraction, "arc")]
            capacity = int(row["capacity_objects"])
            record = simulate(trace, fraction, config, capacity, scratch)
            control = CONFIGS[config][2]
            if control:
                expected = ref[(trace, fraction, control)]
                if int(expected["misses"]) != record["n_miss"] or int(expected["requests"]) != record["n_req"]:
                    raise RuntimeError(f"CONTROL FAILED {trace} {fraction} {config}: {record['n_miss']} vs saved {expected['misses']}")
            elif record["n_req"] != int(row["requests"]):
                raise RuntimeError("request count differs from the saved grid")
            return job, capacity, record, row["trace_sha256"]

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(work, jobs))
    with RUNS.open("a", newline="") as stream:
        writer = csv.DictWriter(stream, FIELDS)
        if stream.tell() == 0:
            writer.writeheader()
        for (trace, fraction, config), capacity, record, trace_hash in results:
            writer.writerow({"trace": trace, "capacity_fraction": fraction, "config": config, "capacity_objects": capacity,
                             "requests": record["n_req"], "misses": record["n_miss"], "trace_sha256": trace_hash,
                             "binary_sha256": binary_hash})
    print(f"{len(results)} runs saved; controls (if any) matched the saved counters exactly")


def reduction(fifo: int, misses: int) -> float:
    top = max(fifo, misses)
    return 0.0 if top == 0 else (fifo - misses) / top


def summarize() -> None:
    ref, runs = saved(), {(r["trace"], float(r["capacity_fraction"]), r["config"]): r for r in load()}
    rows, verdicts = [], []
    for fraction in (0.001, 0.1):
        for family, lru_name, unvisited_name, visited in (("ARC", "arc", "arc_sieve", "arc_sieve_visited"),
                                                          ("TwoQ", "twoq", "twoq_sieve", "twoq_sieve_visited")):
            per = []
            for trace in TRACES:
                fifo = int(ref[(trace, fraction, "fifo")]["misses"])
                lru, unv, vis = (int(ref[(trace, fraction, lru_name)]["misses"]), int(ref[(trace, fraction, unvisited_name)]["misses"]),
                                 int(runs[(trace, fraction, visited)]["misses"]))
                rows.append({"family": family, "trace": trace, "capacity_fraction": fraction, "fifo_misses": fifo,
                             "lru_original_misses": lru, "sieve_unvisited_misses": unv, "sieve_visited_misses": vis,
                             "reduction_lru_original": f"{reduction(fifo, lru):.6f}", "reduction_unvisited": f"{reduction(fifo, unv):.6f}",
                             "reduction_visited": f"{reduction(fifo, vis):.6f}"})
                per.append((reduction(fifo, lru), reduction(fifo, unv), reduction(fifo, vis), vis < unv))
            wins = sum(p[3] for p in per)
            means = [statistics.fmean(p[i] for p in per) for i in range(3)]
            beats_unvisited = wins >= 5
            beats_original = means[2] > means[0]
            verdicts.append({"family": family, "capacity_fraction": fraction, "mean_lru_original": f"{means[0]:.6f}",
                             "mean_unvisited": f"{means[1]:.6f}", "mean_visited": f"{means[2]:.6f}",
                             "traces_where_visited_beats_unvisited": f"{wins}/7",
                             "verdict": "supported" if beats_unvisited and beats_original else
                                        "partly supported" if beats_unvisited else "not supported"})
    for name, table in (("per_trace.csv", rows), ("verdict.csv", verdicts)):
        with (OUT / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, tuple(table[0]))
            writer.writeheader()
            writer.writerows(table)
    # Post-hoc split (declared as post-hoc in the report): the same rows by family of trace
    split = []
    for family in ("ARC", "TwoQ"):
        for fraction in (0.001, 0.1):
            for group, test in (("CDN and Wiki (4 traces)", lambda t: not t.startswith("twitter")), ("Twitter (3 traces)", lambda t: t.startswith("twitter"))):
                sel = [r for r in rows if r["family"] == family and float(r["capacity_fraction"]) == fraction and test(r["trace"])]
                mean = lambda key: statistics.fmean(float(r[key]) for r in sel)
                split.append({"family": family, "capacity_fraction": fraction, "group": group, "traces": len(sel),
                              "mean_lru_original": f"{mean('reduction_lru_original'):.6f}", "mean_unvisited": f"{mean('reduction_unvisited'):.6f}",
                              "mean_visited": f"{mean('reduction_visited'):.6f}"})
    with (OUT / "posthoc_split_by_trace_family.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, tuple(split[0]))
        writer.writeheader()
        writer.writerows(split)
    # LeCaR has no promotion step; its saved grid is split the same way (post-hoc, no new runs)
    lecar = []
    for fraction in (0.001, 0.1):
        for group, test in (("CDN and Wiki (4 traces)", lambda t: not t.startswith("twitter")), ("Twitter (3 traces)", lambda t: t.startswith("twitter"))):
            names = [t for t in TRACES if test(t)]
            value = lambda policy: statistics.fmean(float(ref[(t, fraction, policy)]["reduction_from_fifo"]) for t in names)
            lecar.append({"capacity_fraction": fraction, "group": group, "traces": len(names), "lecar_lru": f"{value('lecar'):.6f}",
                          "lecar_sieve": f"{value('lecar_sieve'):.6f}", "lru": f"{value('lru'):.6f}", "sieve": f"{value('sieve'):.6f}"})
    with (OUT / "posthoc_lecar_split_by_trace_family.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, tuple(lecar[0]))
        writer.writeheader()
        writer.writerows(lecar)
    for v in verdicts:
        print(v)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"run", "summarize"}:
        raise SystemExit(__doc__)
    {"run": run, "summarize": summarize}[sys.argv[1]]()
