#!/usr/bin/env python3
"""Compare the independent SIEVEREPRODUCTION results with ours (saved files only, no simulation).

  python3 -B scripts/compare_independent_replication.py import /path/to/SIEVEREPRODUCTION
      copies the other repository's small result tables and figures into
      external_replication/sievereproduction_<commit>/ with a SHA-256 manifest (no code, no traces)
  python3 -B scripts/compare_independent_replication.py compare
      writes local_results/independent_replication/*.csv and summary.json

"Theirs" always means the snapshot; "ours" means files produced by this repository's own runs.
The two never share simulator output: they used the pinned artifact plus a build-fix patch, we
used the pinned artifact plus our counter patch.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

SNAP_GLOB = "external_replication/sievereproduction_*"
OUT = ROOT / "local_results/independent_replication"

# files copied from the other repository: (path inside it, path inside the snapshot)
COPY = [
    ("README.md", "UPSTREAM_README.md"),
    ("external/sieve-fig4/results/fig4.csv", "fig4/fig4.csv"),
    ("external/sieve-fig4/results/summary.md", "fig4/summary.md"),
    ("external/sieve-fig4/results/fig5_bars.csv", "fig5/fig5_bars.csv"),
    ("external/sieve-fig4/results/fig5_best.csv", "fig5/fig5_best.csv"),
    ("external/sieve-fig4/paper/fig4_paper_values.csv", "fig4/fig4_paper_values.csv"),
    ("external/sieve-fig4/paper/fig5_paper_values.csv", "fig5/fig5_paper_values.csv"),
    ("external/sieve-fig4/README.md", "fig4/README.md"),
    ("external/sieve-fig4/fig5/README.md", "fig5/README.md"),
    ("external/sieve-fig4/fig4/fig4_side_by_side.png", "fig4/fig4_side_by_side.png"),
    ("external/sieve-fig4/fig5/fig5_side_by_side.png", "fig5/fig5_side_by_side.png"),
    ("external/sieve-fig3/README.md", "fig3/README.md"),
    ("external/sieve-fig3/results/twitter.csv", "fig3/twitter.csv"),
    ("external/sieve-fig3/results/summary.md", "fig3/summary.md"),
    ("external/sieve-fig3/manifests/twitter_choice.tsv", "fig3/twitter_choice.tsv"),
    ("external/sieve-fig3/paper/fig3_paper_values.csv", "fig3/fig3_paper_values.csv"),
    ("external/sieve-fig3/fig3c/comparison.csv", "fig3/fig3c_comparison.csv"),
    ("external/sieve-fig3/fig3f/comparison.csv", "fig3/fig3f_comparison.csv"),
    ("external/sieve-fig3/fig3cf_side_by_side.png", "fig3/fig3cf_side_by_side.png"),
    ("external/fig8/fig8/README.md", "fig8/README.md"),
    ("external/fig8/results/fig8_comparison.csv", "fig8/fig8_comparison.csv"),
    ("external/fig8/results/fig8_raw.tsv", "fig8/fig8_raw.tsv"),
    ("external/fig8/paper/fig8_paper_values.csv", "fig8/fig8_paper_values.csv"),
    ("external/fig8/fig8/fig8_side_by_side.png", "fig8/fig8_side_by_side.png"),
    ("external/fig9/fig9/README.md", "fig9/README.md"),
    ("external/fig9/results/fig9_comparison.csv", "fig9/fig9_comparison.csv"),
    ("external/fig9/results/fig9ab_raw.tsv", "fig9/fig9ab_raw.tsv"),
    ("external/fig9/results/fig9c_summary.tsv", "fig9/fig9c_summary.tsv"),
    ("external/fig9/paper/fig9_paper_values.csv", "fig9/fig9_paper_values.csv"),
    ("external/fig9/fig9/fig9_side_by_side.png", "fig9/fig9_side_by_side.png"),
    ("patches/NSDI24-SIEVE-build-fix.patch", "NSDI24-SIEVE-build-fix.patch"),
]

POLICY_LABEL = {"sieve": "SIEVE", "arc": "ARC", "lru": "LRU", "clock": "CLOCK", "twoq": "TwoQ",
                "lirs": "LIRS", "lhd": "LHD", "cacheus": "CACHEUS", "hyperbolic": "Hyperbolic",
                "tinylfu_snapshot": "TinyLFU", "blru": "B-LRU", "fifo": "FIFO"}
SIZE_OF_FRACTION = {"0.1": "large", "0.001": "small"}
DATASET_OF_TRACE = {"meta_reag": "metaCDN", "meta_rnha": "metaCDN", "meta_rprn": "metaCDN",
                    "kvcache_traces_1": "metaKV", "wiki_2019t": "wiki"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path, delimiter: str = ",") -> list[dict]:
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream, delimiter=delimiter))


def write_csv(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        writer.writerows(rows)


def reduction(fifo_miss: float, miss: float) -> float:
    """The paper's metric: (f - a) / max(f, a), so it stays within [-1, 1]."""
    top = max(fifo_miss, miss)
    return 0.0 if top == 0 else (fifo_miss - miss) / top


def snapshot_dir() -> Path:
    found = sorted((ROOT).glob(SNAP_GLOB))
    if len(found) != 1:
        raise SystemExit("expected exactly one external_replication/sievereproduction_* snapshot")
    return found[0]


# ---------------------------------------------------------------- import

def import_snapshot(clone: Path) -> None:
    commit = subprocess.run(["git", "-C", str(clone), "rev-parse", "--short=7", "HEAD"],
                            capture_output=True, text=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(clone), "status", "--porcelain"],
                           capture_output=True, text=True, check=True).stdout.strip()
    if dirty:
        raise SystemExit("the clone has local changes; import only a clean checkout")
    target = ROOT / f"external_replication/sievereproduction_{commit}"
    if target.exists():
        raise SystemExit(f"{target} exists; refusing to overwrite a saved snapshot")
    manifest = []
    for source, destination in COPY:
        src, dst = clone / source, target / destination
        if not src.is_file():
            raise SystemExit(f"missing in clone: {source}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        manifest.append(f"{sha256(dst)}  {destination}  <-  {source}")
    (target / "MANIFEST.sha256").write_text("\n".join(manifest) + "\n")
    print(f"imported {len(COPY)} files into {target.relative_to(ROOT)} (clone commit {commit})")


# ---------------------------------------------------------------- Fig 4

def fig4_overlap(snap: Path) -> tuple[list[dict], list[dict]]:
    theirs = {(r["trace"], r["size"], r["algo"]): r for r in read_csv(snap / "fig4/fig4.csv")}
    ours = {}
    for r in read_csv(ROOT / "local_results/online_baselines_public_extension/public_twelve_subset.csv"):
        if r["trace"] in DATASET_OF_TRACE and r["policy"] in POLICY_LABEL:
            ours[(r["trace"], SIZE_OF_FRACTION[r["capacity_fraction"]], POLICY_LABEL[r["policy"]])] = r
    for r in read_csv(ROOT / "local_results/metakv_trace1_candidate_six_policy.csv"):
        if r["policy"] in POLICY_LABEL:
            ours[("kvcache_traces_1", SIZE_OF_FRACTION[r["capacity_fraction"]], POLICY_LABEL[r["policy"]])] = r
    paper = defaultdict(list)
    for r in read_csv(snap / "fig4/fig4_paper_values.csv"):
        paper[(r["dataset"], r["size"], r["algo"])].append(float(r["reduction"]))
    overlap, dots = [], []
    for (trace, size, algo), mine in sorted(ours.items()):
        if algo == "FIFO":
            continue
        other = theirs.get((trace, size, algo))
        fifo = ours.get((trace, size, "FIFO"))
        if other is not None:
            diff = float(mine["miss_ratio"]) - float(other["miss_ratio"])
            overlap.append({"trace": trace, "size": size, "algo": algo,
                            "ours_miss_ratio": f"{float(mine['miss_ratio']):.4f}",
                            "theirs_miss_ratio": other["miss_ratio"], "difference": f"{diff:+.4f}",
                            "ours_cache_objects": mine["capacity_objects"],
                            "theirs_cache_objects": other["cache_size"],
                            "ours_requests": mine["requests"], "theirs_requests": other["requests"],
                            "theirs_sample_ratio": other["sample_ratio"]})
        if fifo is not None and (DATASET_OF_TRACE[trace], size, algo) in paper:
            mine_red = reduction(float(fifo["miss_ratio"]), float(mine["miss_ratio"]))
            candidates = paper[(DATASET_OF_TRACE[trace], size, algo)]
            nearest = min(candidates, key=lambda value: abs(value - mine_red))
            dots.append({"trace": trace, "size": size, "algo": algo,
                         "our_reduction": f"{mine_red:.4f}", "nearest_paper_dot": f"{nearest:.4f}",
                         "distance": f"{abs(nearest - mine_red):.4f}",
                         "dots_in_that_panel": len(candidates)})
    return overlap, dots


def fig4_theirs_vs_paper(snap: Path) -> list[dict]:
    """Mapping-free check of the other repository's claim: nearest paper dot for each of its reductions."""
    paper = defaultdict(list)
    for r in read_csv(snap / "fig4/fig4_paper_values.csv"):
        paper[(r["dataset"], r["size"], r["algo"])].append(float(r["reduction"]))
    out = []
    for r in read_csv(snap / "fig4/fig4.csv"):
        if r["algo"] == "FIFO":
            continue
        dots = paper.get((r["dataset"], r["size"], r["algo"]))
        if not dots:
            continue
        value = float(r["reduction"])
        nearest = min(dots, key=lambda d: abs(d - value))
        out.append({"dataset": r["dataset"], "trace": r["trace"], "size": r["size"], "algo": r["algo"],
                    "theirs_reduction": r["reduction"], "nearest_paper_dot": f"{nearest:.4f}",
                    "distance": f"{abs(nearest - value):.4f}", "dots_in_that_panel": len(dots)})
    return out


# ---------------------------------------------------------------- Fig 3

def cluster_number(name: str) -> int:
    """twitter_cluster13 -> 13; twitter_cluster37_sample100 -> 37 (only the number after 'cluster')."""
    import re
    return int(re.search(r"cluster(\d+)", name).group(1))


def all_twitter_records() -> dict:
    """{(cluster, size, policy label): (miss_ratio, reduction)} from every saved Twitter run, partial sets included."""
    paths = sorted((ROOT / "local_results").glob("twitter_cluster*_policy.csv"))
    paths += sorted((ROOT / "local_results").glob("online_baselines_cluster*_extension/*policy.csv"))
    paths.append(ROOT / "local_results/online_baselines_public_extension/public_twelve_subset.csv")
    found = {}
    for path in paths:
        for r in read_csv(path):
            name = r.get("workload") or r.get("trace")
            if not name.startswith("twitter_cluster") or r["policy"] not in POLICY_LABEL:
                continue
            size = SIZE_OF_FRACTION.get(r["capacity_fraction"])
            if size is None:
                continue
            found.setdefault((cluster_number(name), size, POLICY_LABEL[r["policy"]]),
                             (float(r["miss_ratio"]), float(r["reduction_from_fifo"])))
    return found


def fig3_tables(snap: Path):
    from build_paper_figures import FIG3_FULL, twitter_complete_sets
    labels = {pol: label for pol, label in FIG3_FULL}
    theirs = defaultdict(lambda: defaultdict(dict))
    their_miss = {}
    for r in read_csv(snap / "fig3/twitter.csv"):
        if r["pass"] == "main":
            their_miss[(int(r["trace"].removeprefix("cluster")), r["size"], r["algo"])] = float(r["miss_ratio"])
        if r["pass"] == "blru" and r["algo"] != "B-LRU":
            continue
        theirs[r["size"]][int(r["trace"].removeprefix("cluster"))][r["algo"]] = float(r["reduction"])
    ours_sets = twitter_complete_sets()
    ours = {}
    for fraction, size in (("0.1", "large"), ("0.001", "small")):
        ours[size] = {cluster_number(t): {labels[p]: v[p] for p in labels} for t, v in ours_sets[fraction].items()}
    paper = {(r["panel"], r["algo"]): float(r["mean"]) for r in read_csv(snap / "fig3/fig3_paper_values.csv")}
    paper_panel = {"large": "c", "small": "f"}
    order = [label for _, label in FIG3_FULL]
    # per-cluster comparison where both repositories have a complete record
    overlap = []
    records = all_twitter_records()
    choice = {int(r["cluster"].removeprefix("cluster")): r for r in read_csv(snap / "fig3/twitter_choice.tsv", "\t")}
    for (cluster, size, algo), (miss, _) in sorted(records.items()):
        key = (cluster, size, "B-LRU" if algo == "B-LRU" else algo)
        if cluster not in theirs[size] or key not in their_miss:
            continue
        pick = choice[cluster]
        overlap.append({"cluster": cluster, "size": size, "algo": algo,
                        "theirs_trace_version": pick["version"] + (f" first {pick['max_req']} requests" if pick["max_req"] != "-1" else ""),
                        "ours_miss_ratio": f"{miss:.4f}", "theirs_miss_ratio": f"{their_miss[key]:.4f}",
                        "difference": f"{round(miss, 4) - their_miss[key]:+.4f}"})
    # sample100 extension (docs/twitter_sampled_extension_protocol.md): only traces with all 11 algorithms and FIFO
    extension = defaultdict(lambda: defaultdict(dict))
    for ext_path in (ROOT / "local_results/twitter_sampled_extension/sample100_extension.csv",
                     ROOT / "local_results/twitter_sample10_extension/sample10_extension.csv",
                     ROOT / "local_results/twitter_gated_extension/gated_extension.csv"):   # clusters 29, 41, 32 once CACHEUS ran (gated protocol, amendment 2)
        if ext_path.exists():
            for r in read_csv(ext_path):
                size = SIZE_OF_FRACTION[r["capacity_fraction"]]
                extension[size][cluster_number(r["trace"])][r["algo"]] = float(r["reduction_from_fifo"])
    needed = set(order) | {"FIFO"}
    means = []
    for size in ("large", "small"):
        union = {c: v for c, v in theirs[size].items()}
        added = sorted(set(ours[size]) - set(theirs[size]))
        for c in added:
            union[c] = ours[size][c]
        ext_added = sorted(c for c, v in extension[size].items() if set(order) <= set(v) and c not in union)
        for c in ext_added:
            union[c] = {a: extension[size][c][a] for a in order}
        for algo in order:
            their_vals = [v[algo] for v in theirs[size].values() if algo in v]
            union_vals = [v[algo] for v in union.values() if algo in v]
            our_vals = [v[algo] for v in ours[size].values()]
            means.append({"size": size, "algo": algo,
                          "paper_mean": paper.get((paper_panel[size], algo), ""),
                          "theirs_n": len(their_vals), "theirs_mean": f"{statistics.fmean(their_vals):.4f}",
                          "ours_n": len(our_vals), "ours_mean": f"{statistics.fmean(our_vals):.4f}",
                          "union_n": len(union_vals), "union_mean": f"{statistics.fmean(union_vals):.4f}",
                          "union_clusters_added_from_ours": " ".join(map(str, added)),
                          "union_clusters_added_from_sample100_extension": " ".join(map(str, ext_added))})
    return overlap, means


def spearman(x: list[float], y: list[float]) -> float:
    def ranks(values):
        order = sorted(range(len(values)), key=lambda i: values[i])
        out = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            for k in range(i, j + 1):
                out[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return out
    rx, ry = ranks(x), ranks(y)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den


# ---------------------------------------------------------------- Fig 5

def fig5_check(snap: Path) -> list[dict]:
    rows = read_csv(snap / "fig5/fig5_bars.csv")
    paper = {(r["dataset"], r["size"]): r for r in rows if r["source"] == "paper Figure 5"}
    out = []
    for r in rows:
        if r["source"] != "replication":
            continue
        ref = paper.get((r["dataset"], r["size"]))
        if ref is None:
            continue
        diffs = {k: abs(float(r[k]) - float(ref[k])) for k in ("SIEVE", "ARC", "TwoQ", "LHD", "Others")}
        out.append({"dataset": r["dataset"], "size": r["size"], "traces": r["traces"],
                    **{f"theirs_{k}": r[k] for k in diffs}, **{f"paper_{k}": ref[k] for k in diffs},
                    "max_abs_difference": f"{max(diffs.values()):.4f}"})
    return out


# ---------------------------------------------------------------- Fig 8 / 9

def fig8_three_way(snap: Path) -> list[dict]:
    mine = {(float(r["capacity_percent"]), r["policy"]): r
            for r in read_csv(ROOT / "local_results/zipf_support_check/figure8a_10k_objects_vs_paper.csv")}
    old = {(float(r["capacity_percent"]), r["policy"]): r
           for r in read_csv(ROOT / "local_results/zipf8_paper_capacity_grid/figure8a_paper_vs_local.csv")}
    out = []
    for r in read_csv(snap / "fig8/fig8_comparison.csv"):
        if r["panel"] != "a":
            continue
        key = (float(r["pct"]), r["algo"])
        out.append({"capacity_percent": key[0], "policy": key[1], "paper_their_extraction": r["paper"],
                    "paper_our_extraction": mine[key]["paper_digitized"],
                    "theirs_seed1_10k_objects": r["seed1"],
                    "ours_mean_10k_objects": mine[key]["mean_miss_ratio"],
                    "ours_earlier_1M_objects": f"{float(old[key]['local_mean_miss_ratio']):.6f}"})
    return out


def fig9_three_way(snap: Path) -> list[dict]:
    mine = {(float(r["alpha"]), r["policy"]): r
            for r in read_csv(ROOT / "local_results/zipf_support_check/figure9a_10k_objects_miss_ratio.csv")}
    out = []
    for r in read_csv(snap / "fig9/fig9_comparison.csv"):
        if r["panel"] != "a":
            continue
        key = (float(r["alpha"]), r["algo"])
        m = mine[key]
        out.append({"alpha": key[0], "policy": key[1], "paper_their_extraction": r["paper"],
                    "theirs_seed1": r["seed1"], "ours_mean": m["mean_miss_ratio"],
                    "ours_minus_paper": f"{float(m['mean_miss_ratio']) - float(r['paper']):+.4f}"})
    return out


def popular_three_way(snap: Path) -> list[dict]:
    mine = {(float(r["alpha"]), r["policy"], int(r["cache_objects"])): r
            for r in read_csv(ROOT / "local_results/zipf_support_check/popular_ratio_10k_objects.csv")}
    out = []
    for name, file, key_col, objects in (("fig8b", "fig8/fig8_comparison.csv", "pct", 10_000),
                                         ("fig9b", "fig9/fig9_comparison.csv", "alpha", None)):
        for r in read_csv(snap / file):
            if r["panel"] != "b":
                continue
            if name == "fig8b":
                alpha, cap = 1.0, round(float(r["pct"]) * objects / 100)
            else:
                alpha, cap = float(r["alpha"]), 1000
            o = mine[(alpha, r["algo"], cap)]
            out.append({"figure": name, "alpha": alpha, "cache_objects": cap, "policy": r["algo"],
                        "paper_their_extraction": r["paper"], "theirs_seed1": r["seed1"],
                        "ours_mean": o["mean_popular_ratio"],
                        "ours_minus_paper": f"{float(o['mean_popular_ratio']) - float(r['paper']):+.4f}"})
    return out


def popular_variants(snap: Path) -> list[dict]:
    """Does the way the popular-object ratio is averaged, or defined, explain the Figure 8b residual?"""
    paper = {(r["algo"], float(r["cache_pct"])): float(r["value"])
             for r in read_csv(snap / "fig8/fig8_paper_values.csv") if r["panel"] == "b"}
    variants = {}
    raw = read_csv(snap / "fig8/fig8_raw.tsv", "\t")
    for column, label in (("popular_mean", "theirs: mean over the whole trace"), ("popular_mean_2nd_half", "theirs: mean over the second half"),
                          ("popular_at_end", "theirs: value at the end")):
        grouped = defaultdict(list)
        for r in raw:
            grouped[(r["algo"], float(r["cache_pct"]))].append(float(r[column]))
        variants[label] = {k: statistics.fmean(v) for k, v in grouped.items()}
    for name, file, column, label in (
            ("popular_runs.csv", None, "mean_popular_ratio", "ours: mean over the whole trace, empirical top-C"),
            ("popular_runs.csv", None, "final_popular_ratio", "ours: value at the end, empirical top-C"),
            ("popular_runs_generating_rank.csv", None, "mean_popular_ratio", "ours: mean over the whole trace, generating-rank top-C")):
        grouped = defaultdict(list)
        for r in read_csv(ROOT / "local_results/zipf_support_check" / name):
            if float(r["alpha"]) == 1.0:
                grouped[(r["policy"].upper(), int(r["capacity_objects"]) / 100)].append(float(r[column]))
        variants[label] = {k: statistics.fmean(v) for k, v in grouped.items()}
    out = []
    for label, values in variants.items():
        diffs = [abs(values[k] - paper[k]) for k in paper]
        out.append({"variant": label, "mean_abs_difference_to_paper": f"{statistics.fmean(diffs):.4f}",
                    "max_abs_difference_to_paper": f"{max(diffs):.4f}", "points": len(diffs)})
    return out


def order_agreement(rows: list[dict], group: str, paper_col: str, value_col: str) -> tuple[int, int]:
    """(groups where the full ordering of the policies equals the paper's, number of groups)."""
    groups = defaultdict(list)
    for r in rows:
        groups[r[group]].append(r)
    same = sum([r["policy"] for r in sorted(g, key=lambda r: float(r[paper_col]))] ==
               [r["policy"] for r in sorted(g, key=lambda r: float(r[value_col]))]
               for g in groups.values())
    return same, len(groups)


def compare() -> None:
    snap = snapshot_dir()
    OUT.mkdir(parents=True, exist_ok=True)
    overlap, dots = fig4_overlap(snap)
    write_csv(OUT / "fig4_ours_vs_theirs.csv", tuple(overlap[0]), overlap)
    write_csv(OUT / "fig4_ours_vs_paper_dots.csv", tuple(dots[0]), dots)
    theirs_dots = fig4_theirs_vs_paper(snap)
    write_csv(OUT / "fig4_theirs_vs_paper_dots.csv", tuple(theirs_dots[0]), theirs_dots)
    f3_overlap, f3_means = fig3_tables(snap)
    write_csv(OUT / "fig3_twitter_overlap.csv", tuple(f3_overlap[0]), f3_overlap)
    write_csv(OUT / "fig3_twitter_means.csv", tuple(f3_means[0]), f3_means)
    f5 = fig5_check(snap)
    write_csv(OUT / "fig5_theirs_vs_paper.csv", tuple(f5[0]), f5)
    f8 = fig8_three_way(snap)
    write_csv(OUT / "fig8a_three_way.csv", tuple(f8[0]), f8)
    f9 = fig9_three_way(snap)
    write_csv(OUT / "fig9a_three_way.csv", tuple(f9[0]), f9)
    write_csv(OUT / "popular_ratio_averaging_variants.csv", ("variant", "mean_abs_difference_to_paper", "max_abs_difference_to_paper", "points"), popular_variants(snap))
    pop = popular_three_way(snap)
    write_csv(OUT / "popular_ratio_three_way.csv", tuple(pop[0]), pop)

    by_algo = defaultdict(list)
    for r in overlap:
        by_algo[r["algo"]].append(abs(float(r["difference"])))
    summary = {
        "snapshot": snap.name,
        "fig4_overlap_cells": len(overlap),
        "fig4_max_abs_miss_ratio_difference_by_algo": {a: max(v) for a, v in sorted(by_algo.items())},
        "fig4_cells_with_different_cache_size": sum(r["ours_cache_objects"] != r["theirs_cache_objects"] for r in overlap),
        "fig4_paper_dot_cells": len(dots),
        "fig4_paper_dot_max_distance": max(float(r["distance"]) for r in dots),
        "fig4_paper_dot_cells_within_0.0005": sum(float(r["distance"]) <= 0.0005 for r in dots),
        "fig4_theirs_cells_vs_paper_dots": len(theirs_dots),
        "fig4_theirs_sieve_max_distance_to_nearest_dot": max(float(r["distance"]) for r in theirs_dots if r["algo"] == "SIEVE"),
        "fig4_theirs_sieve_cells": sum(r["algo"] == "SIEVE" for r in theirs_dots),
        "fig4_theirs_deterministic_cells_within_0.0005": sum(float(r["distance"]) <= 0.0005 for r in theirs_dots if r["algo"] not in {"CACHEUS", "LHD", "TinyLFU"}),
        "fig4_theirs_deterministic_cells": sum(r["algo"] not in {"CACHEUS", "LHD", "TinyLFU"} for r in theirs_dots),
        "fig3_overlap_clusters": sorted({r["cluster"] for r in f3_overlap}),
        "fig3_overlap_max_abs_miss_ratio_difference": max(abs(float(r["difference"])) for r in f3_overlap),
        "fig3_spearman_of_means_vs_paper": {},
        "fig5_max_abs_difference_to_paper_by_dataset_size": {
            f"{r['dataset']}/{r['size']}": float(r["max_abs_difference"]) for r in f5},
        "fig8a_max_abs_ours10k_minus_paper_excluding_LFU": max(
            abs(float(r["ours_mean_10k_objects"]) - float(r["paper_our_extraction"]))
            for r in f8 if r["policy"] != "LFU"),
        "fig8a_max_abs_ours1M_minus_paper": max(
            abs(float(r["ours_earlier_1M_objects"]) - float(r["paper_our_extraction"])) for r in f8),
        "fig9a_max_abs_ours_minus_paper": max(abs(float(r["ours_minus_paper"])) for r in f9),
        "fig8b_max_abs_ours_minus_paper": max(abs(float(r["ours_minus_paper"])) for r in pop if r["figure"] == "fig8b"),
        "fig8b_mean_abs_ours_minus_paper": statistics.fmean(abs(float(r["ours_minus_paper"])) for r in pop if r["figure"] == "fig8b"),
        "fig9b_max_abs_ours_minus_paper": max(abs(float(r["ours_minus_paper"])) for r in pop if r["figure"] == "fig9b"),
        "fig9b_mean_abs_ours_minus_paper": statistics.fmean(abs(float(r["ours_minus_paper"])) for r in pop if r["figure"] == "fig9b"),
        "full_order_matches_paper_ours_vs_theirs": {
            name: {"ours": order_agreement(rows, group, "paper_their_extraction", "ours_mean" if "ours_mean" in rows[0] else "ours_mean_10k_objects"),
                   "theirs": order_agreement(rows, group, "paper_their_extraction",
                                             "theirs_seed1" if "theirs_seed1" in rows[0] else "theirs_seed1_10k_objects")}
            for name, rows, group in (
                ("fig8a_miss_by_capacity", f8, "capacity_percent"), ("fig9a_miss_by_alpha", f9, "alpha"),
                ("fig8b_popular_by_capacity", [r for r in pop if r["figure"] == "fig8b"], "cache_objects"),
                ("fig9b_popular_by_alpha", [r for r in pop if r["figure"] == "fig9b"], "alpha"))},
    }
    for size in ("large", "small"):
        rows = [r for r in f3_means if r["size"] == size and r["paper_mean"] != ""]
        for source in ("theirs_mean", "union_mean"):
            summary["fig3_spearman_of_means_vs_paper"][f"{size}/{source}"] = round(
                spearman([float(r["paper_mean"]) for r in rows], [float(r[source]) for r in rows]), 3)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "import":
        import_snapshot(Path(sys.argv[2]).resolve())
    elif len(sys.argv) == 2 and sys.argv[1] == "compare":
        compare()
    else:
        raise SystemExit(__doc__)
