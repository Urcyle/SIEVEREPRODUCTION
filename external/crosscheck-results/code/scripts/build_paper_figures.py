#!/usr/bin/env python3
"""Redraw the paper's Figures 1-14 in the paper's layout from our saved results.

Every panel is drawn from saved counters, tables or run logs; nothing is simulated here and no
paper graph is copied. Where the paper's plotted values are available as data (config/paper_values.csv,
config/paper_fig4_points.csv, config/paper_fig5_sieve.csv, paper_reference/figure8a_published_digitized.csv)
they are drawn separately (hollow or grey) and labeled "paper". Panels that need data we do not have
(proprietary CDN traces, CacheLib, LRB) are drawn as labeled empty panels instead of being omitted.

  python3 -B scripts/build_paper_figures.py [fig01 fig03 ...]    # default: all
Outputs: local_results/paper_figures/figNN_<name>.{png,svg,pdf}
"""

import csv
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch, Rectangle

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sieve_repro.core import SieveReference  # noqa: E402
from sieve_repro.plot_export import save_figure_exports  # noqa: E402

OUT = Path(os.environ.get("SIEVE_PAPER_FIGURE_DIR", ROOT / "local_results/paper_figures"))
LR = ROOT / "local_results"
SIEVE_C, ARC_C, LRU_C, LFU_C = "#ff7f0e", "#000080", "#2ca02c", "#5b9bd5"
GREY = "#8c8c8c"
DATASET_STYLE = {"metaKV": ("Meta (KV)", "#ff7f0e", "o"), "metaCDN": ("Meta (CDN)", "#d62728", "D"),
                 "tencentPhoto": ("Tencent", "#6fa8dc", ">"), "wiki": ("Wiki", "#2ca02c", "s")}
plt.rcParams.update({"font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8, "legend.fontsize": 7,
                     "xtick.labelsize": 7, "ytick.labelsize": 7, "axes.grid": False,
                     "font.family": "DejaVu Sans"})


def rows(path):
    with open(ROOT / path, newline="") as handle:
        return list(csv.DictReader(handle))


def paper_values():
    return rows("config/paper_values.csv")


def note(fig, text):
    fig.text(0.01, -0.015, text, fontsize=6.5, va="top", ha="left", color="#333333", wrap=True)


def caption(ax, text, y=-0.30):
    ax.text(0.5, y, text, transform=ax.transAxes, ha="center", va="top", fontsize=7.5, family="serif")


def box_stats(values):
    v = np.asarray(values, float)
    return {"p10": np.percentile(v, 10), "p25": np.percentile(v, 25), "p75": np.percentile(v, 75),
            "p90": np.percentile(v, 90), "mean": v.mean(), "median": np.median(v)}


def draw_box(ax, x, values, color, width=0.6):
    s = box_stats(values)
    ax.add_patch(Rectangle((x - width / 2, s["p25"]), width, s["p75"] - s["p25"], facecolor=color,
                           edgecolor="black", linewidth=0.7, zorder=2))
    ax.plot([x - width / 2, x + width / 2], [s["median"]] * 2, color="black", linewidth=0.9, zorder=3)
    ax.plot([x, x], [s["p10"], s["p25"]], color="black", linewidth=0.7, zorder=1)
    ax.plot([x, x], [s["p75"], s["p90"]], color="black", linewidth=0.7, zorder=1)
    for y in (s["p10"], s["p90"]):
        ax.plot([x - width / 4, x + width / 4], [y, y], color="black", linewidth=0.7)
    ax.plot(x, s["mean"], marker="v", color="#8b1a1a", markersize=4, zorder=4, linestyle="none")
    return s


def unavailable(ax, title, reason, headline="not reproducible here"):
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_facecolor("#f1f1f1")
    for spine in ax.spines.values():
        spine.set_linestyle(":")
        spine.set_color(GREY)
    ax.text(0.5, 0.55, headline, ha="center", va="center", fontsize=8, color="#444444",
            transform=ax.transAxes, weight="bold")
    ax.text(0.5, 0.36, reason, ha="center", va="center", fontsize=6.5, color="#444444",
            transform=ax.transAxes)
    caption(ax, title)


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    save_figure_exports(fig, OUT, name, dpi=200)
    plt.close(fig)
    print("wrote", name)


# ----------------------------------------------------------------------------- Figure 1
def fig01():
    data = rows("local_results/online_baselines_public_extension/public_twelve_subset.csv")
    by = defaultdict(list)
    for r in data:
        if r["capacity_fraction"] == "0.1" and r["policy"] != "fifo":
            by[r["policy"]].append(float(r["reduction_from_fifo"]))
    order = [("cacheus", "CACHEUS"), ("lhd", "LHD"), ("lirs", "LIRS"), ("arc", "ARC"), ("lru", "LRU"),
             ("clock", "CLOCK"), ("sieve", "SIEVE")]
    paper = {r["algo"]: float(r["value"]) for r in paper_values() if r["figure"] == "fig1"}
    every = defaultdict(list)  # all public traces at the 10% cache, the four algorithms we ran on all of them
    for (dataset, cap), traces in six_policy_misses().items():
        if cap == "0.1":
            for misses in traces.values():
                f = misses["fifo"]
                for pol in ("sieve", "arc", "lru", "clock"):
                    a = misses[pol]
                    every[pol].append((f - a) / max(f, a) if max(f, a) else 0.0)
    n_all = len(every["sieve"])
    fig, ax = plt.subplots(figsize=(6.0, 3.5))
    y = np.arange(len(order))[::-1]
    for yi, (key, label) in zip(y, order):
        ours = np.mean(by[key])
        ax.barh(yi + 0.26, ours, height=0.24, color=SIEVE_C if key == "sieve" else "#dbe9fb",
                edgecolor="black", linewidth=0.6)
        ax.text(ours + 0.004, yi + 0.26, f"{ours:.4f}", va="center", fontsize=6)
        if key in every:
            allv = np.mean(every[key])
            ax.barh(yi, allv, height=0.24, color="#ffb870" if key == "sieve" else "#c7e5c0", edgecolor="black", linewidth=0.6)
            ax.text(allv + 0.004, yi, f"{allv:.4f}", va="center", fontsize=6)
        ax.barh(yi - 0.26, paper[label], height=0.24, color="white", edgecolor=GREY, hatch="////", linewidth=0.6)
        ax.text(paper[label] + 0.004, yi - 0.26, f"{paper[label]:.4f}", va="center", fontsize=6, color=GREY)
    ax.set_yticks(y, [l for _, l in order])
    ax.set_xlim(0, 0.24)
    ax.set_xlabel("Mean miss ratio reduction from FIFO")
    ax.legend(handles=[Rectangle((0, 0), 1, 1, facecolor="#dbe9fb", edgecolor="black", label="ours: 7 traces with all 12 policies, 10% cache"),
                       Rectangle((0, 0), 1, 1, facecolor="#c7e5c0", edgecolor="black", label=f"ours: all {n_all} public traces we ran, 4 algorithms only"),
                       Rectangle((0, 0), 1, 1, facecolor="white", edgecolor=GREY, hatch="////", label="paper (printed values): 1,559 traces")],
              loc="upper center", bbox_to_anchor=(0.45, -0.17), ncol=1, frameon=False, fontsize=6.5)
    ax.set_title("Figure 1 - SIEVE is simple and efficient (mean miss ratio reduction from FIFO)")
    note(fig, "Ours (blue): mean per-trace reduction over 7 public traces (3 Meta CDN, 1 Wiki, 3 Twitter) at a 10% cache, "
              "12-policy run. Ours (green): the same mean over every public trace we ran at 10% (Meta CDN 3, Wiki 1, Meta KV 3, Twitter 12), possible for ARC, LRU, CLOCK and SIEVE only. The paper averages 1,559 traces, 82% of them proprietary; the means are not comparable in size, only in order.")
    fig.tight_layout()
    save(fig, "fig01_mean_reduction")


# ----------------------------------------------------------------------------- Figure 2
class ClockModel:
    """FIFO-Reinsertion/CLOCK: survivors are moved to the head when the sweep passes them."""

    def __init__(self, capacity):
        self.capacity, self.q, self.v = capacity, [], {}  # q: head first

    def access(self, key):
        if key in self.v:
            self.v[key] = 1
            return True
        if len(self.q) == self.capacity:
            while True:
                tail = self.q[-1]
                if self.v[tail]:
                    self.v[tail] = 0
                    self.q.pop()
                    self.q.insert(0, tail)
                else:
                    self.q.pop()
                    del self.v[tail]
                    break
        self.q.insert(0, key)
        self.v[key] = 0
        return False


def draw_queue(ax, x0, ids, visited, title, hand=None, new=None):
    ax.text(x0 + 0.5, len(ids) + 0.45, title, ha="center", va="bottom", fontsize=6.5)
    for i, key in enumerate(ids):  # head at top
        y = len(ids) - 1 - i
        color = "#f4a6a6" if visited.get(key) else "#a8c8ee"
        if key == new:
            color = "#9fe0a3"
        ax.add_patch(FancyBboxPatch((x0, y), 1, 0.8, boxstyle="round,pad=0.02,rounding_size=0.12",
                                    facecolor=color, edgecolor="black", linewidth=0.6))
        ax.text(x0 + 0.5, y + 0.4, key, ha="center", va="center", fontsize=8, weight="bold")
        if key == hand:
            ax.annotate("hand", xy=(x0 - 0.02, y + 0.4), xytext=(x0 - 0.9, y + 0.4), fontsize=6.5, color="#1b4f9c",
                        va="center", arrowprops=dict(arrowstyle="->", color="#1b4f9c", lw=0.9))


def fig02():
    letters = "ABCDEFG"
    cap = 7
    sieve, clock = SieveReference(cap), ClockModel(cap)
    for k in letters:
        sieve.access(k)
        clock.access(k)
    for k in "ADGE":  # hits mark objects as visited
        sieve.access(k)
        clock.access(k)
    s_before_q, s_hand = sieve.snapshot()
    s_before = ([k for k, _ in s_before_q], {k: b for k, b in s_before_q}, s_hand)
    c_before = (list(clock.q), dict(clock.v))
    sieve.access("H")
    clock.access("H")
    s_after_q, s_hand_after = sieve.snapshot()
    fig, ax = plt.subplots(figsize=(7.2, 3.3))
    ax.set_xlim(-1.5, 15.2)
    ax.set_ylim(-1.3, cap + 1.4)
    ax.axis("off")
    ax.text(-1.4, cap + 1.15, "FIFO-Reinsertion / CLOCK  (survivors move to the head)", fontsize=7.5, color="#1b4f9c", weight="bold")
    draw_queue(ax, 0.8, c_before[0], c_before[1], "before eviction")
    draw_queue(ax, 4.0, clock.q, clock.v, "after request H", new="H")
    ax.annotate("", xy=(3.7, 3.5), xytext=(2.0, 3.5), arrowprops=dict(arrowstyle="->"))
    ax.text(8.6, cap + 1.15, "SIEVE  (survivors stay in place; the hand moves)", fontsize=7.5, color="#c05a00", weight="bold")
    draw_queue(ax, 9.9, s_before[0], s_before[1], "before eviction", hand=s_before[2])
    draw_queue(ax, 13.1, [k for k, _ in s_after_q], {k: b for k, b in s_after_q}, "after request H", hand=s_hand_after, new="H")
    ax.annotate("", xy=(12.8, 3.5), xytext=(11.1, 3.5), arrowprops=dict(arrowstyle="->"))
    ax.text(7.2, -0.9, "red = visited (hit since insertion), blue = not visited, green = newly inserted. Head (newest) at the top.\n"
                       "Cache of 7; requests A..G, then hits on A, D, G, E, then a miss on H.", ha="center", fontsize=6.5)
    ax.set_title("Figure 2 - An illustration of SIEVE versus FIFO-Reinsertion (generated from our reference models)")
    note(fig, "Drawn from the independent SIEVE reference model (tested against the simulator after every request) and a small CLOCK model; this is an illustration, not measured data.")
    fig.tight_layout()
    save(fig, "fig02_illustration")


# ----------------------------------------------------------------------------- Figure 3
FIG3_ORDER = ["SIEVE", "ARC", "CLOCK", "LRU"]
POLICY_LABEL = {"sieve": "SIEVE", "arc": "ARC", "clock": "CLOCK", "lru": "LRU", "lfu": "LFU"}


def twitter_reductions(path):
    by = defaultdict(list)
    for r in rows(path):
        if r["policy"] in POLICY_LABEL:
            by[POLICY_LABEL[r["policy"]]].append(float(r["fifo_normalized_reduction"]))
    return by


FIG3_FULL = [("sieve", "SIEVE"), ("arc", "ARC"), ("tinylfu_snapshot", "TinyLFU"), ("twoq", "TwoQ"), ("lirs", "LIRS"), ("lhd", "LHD"),
             ("cacheus", "CACHEUS"), ("hyperbolic", "Hyperbolic"), ("clock", "CLOCK"), ("lru", "LRU"), ("blru", "B-LRU")]


def twitter_complete_sets():
    """{capacity: {trace: {policy: reduction_from_fifo}}} for Twitter traces that have all 11 of the paper's algorithms."""
    by = defaultdict(lambda: defaultdict(dict))
    paths = sorted((ROOT / "local_results").glob("online_baselines_cluster*_extension/*policy.csv"))
    sources = [(r["workload"], r["capacity_fraction"], r["policy"], r["reduction_from_fifo"]) for p in paths for r in rows(str(p.relative_to(ROOT)))]
    sources += [(r["trace"], r["capacity_fraction"], r["policy"], r["reduction_from_fifo"])
                for r in rows("local_results/online_baselines_public_extension/public_twelve_subset.csv") if r["trace"].startswith("twitter")]
    for trace, cap, policy, red in sources:
        by[cap][trace].setdefault(policy, float(red))  # extension files win over the subset file for duplicates
    need = {p for p, _ in FIG3_FULL}
    return {cap: {t: v for t, v in traces.items() if need <= set(v)} for cap, traces in by.items()}


def fig03():
    sets = twitter_complete_sets()
    paper = {(r["figure"], r["algo"]): float(r["value"]) for r in paper_values()
             if r["figure"] in ("fig3c", "fig3f") and r["metric"] == "mean"}
    fig, axes = plt.subplots(2, 3, figsize=(12.4, 5.8), gridspec_kw={"width_ratios": [1, 1, 2.1]})
    for ax, spec in zip(axes.flat, [("(a) CDN1, large cache\n1273 traces", "CDN1 traces are proprietary\nand were never released"),
                                    ("(b) CDN2, large cache\n219 traces", "CDN2 traces are proprietary\nand were never released"), None,
                                    ("(d) CDN1, small cache\n1273 traces", "CDN1 traces are proprietary\nand were never released"),
                                    ("(e) CDN2, small cache\n219 traces", "CDN2 traces are proprietary\nand were never released"), None]):
        if spec:
            unavailable(ax, spec[0], spec[1])
    for ax, cap, tag, fig_id, color in ((axes[0, 2], "0.1", "(c) Twitter, large cache (10%)", "fig3c", "#f5a623"),
                                        (axes[1, 2], "0.001", "(f) Twitter, small cache (0.1%)", "fig3f", "#a7d3e8")):
        traces = sets[cap]
        for i, (pol, label) in enumerate(FIG3_FULL):
            vals = [traces[t][pol] for t in traces]
            draw_box(ax, i, vals, color)
            ax.scatter([i] * len(vals), vals, s=7, color="black", zorder=6, alpha=0.65)
            if (fig_id, label) in paper:
                ax.plot(i + 0.28, paper[(fig_id, label)], marker="D", markersize=4.5, markerfacecolor="none", markeredgecolor=GREY, linestyle="none", zorder=5)
        ax.set_xticks(range(len(FIG3_FULL)), [l for _, l in FIG3_FULL], rotation=45, ha="right")
        ax.set_ylabel("Miss Ratio Reduction\nfrom FIFO")
        ax.axhline(0, color="black", linewidth=0.5)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        caption(ax, f"{tag}\n{len(traces)} of 54 traces with all 11 algorithms", y=-0.52)
    axes[0, 2].plot([], [], marker="v", color="#8b1a1a", linestyle="none", label="our mean")
    axes[0, 2].plot([], [], marker="D", markerfacecolor="none", markeredgecolor=GREY, linestyle="none", label="paper mean (read off, about +/-0.01)")
    axes[0, 2].plot([], [], marker="o", color="black", markersize=3, linestyle="none", label="one point per trace")
    axes[0, 2].legend(loc="upper center", bbox_to_anchor=(0.5, 1.33), ncol=3, frameon=False, fontsize=6)
    fig.suptitle("Figure 3 - Miss ratio reduction from FIFO over all traces in a dataset", fontsize=9)
    note(fig, "Box: P25-P75, whiskers P10-P90, line = median, triangle = mean (the paper's convention); with only 5-7 traces the percentiles are rough, so every trace is also drawn as a dot. "
              "Ours: the Twitter traces on which all 11 of the paper's algorithms were run (0.1%: clusters 3, 10, 26, 45, 49, 50, 53; 10%: clusters 3, 10, 26, 49, 50). 'TinyLFU' is the pinned-snapshot version. "
              "The four-algorithm version on all 16 and 12 Twitter traces is the companion fig03b. Panels a, b, d, e need the proprietary CDN1/CDN2 traces.")
    fig.tight_layout(h_pad=3.2)
    save(fig, "fig03_boxplots")


def fig03b():
    large = twitter_reductions("local_results/twitter12_10pct/exact_counters.csv")
    small = twitter_reductions("local_results/twitter16_0p1pct/exact_counters.csv")
    paper = {(r["figure"], r["algo"]): float(r["value"]) for r in paper_values()
             if r["figure"] in ("fig3c", "fig3f") and r["metric"] == "mean"}
    fig, axes = plt.subplots(2, 3, figsize=(8.6, 5.6))
    panels = [("(a) CDN1, large cache\n1273 traces", "CDN1 traces are proprietary\nand were never released"),
              ("(b) CDN2, large cache\n219 traces", "CDN2 traces are proprietary\nand were never released"),
              None,
              ("(d) CDN1, small cache\n1273 traces", "CDN1 traces are proprietary\nand were never released"),
              ("(e) CDN2, small cache\n219 traces", "CDN2 traces are proprietary\nand were never released"),
              None]
    for ax, spec in zip(axes.flat, panels):
        if spec:
            unavailable(ax, spec[0], spec[1])
    for ax, data, tag, fig_id, color, label in (
            (axes[0, 2], large, "(c) Twitter, large cache (10%)\n12 of 54 traces", "fig3c", "#f5a623", "large"),
            (axes[1, 2], small, "(f) Twitter, small cache (0.1%)\n16 of 54 traces", "fig3f", "#a7d3e8", "small")):
        for i, algo in enumerate(FIG3_ORDER):
            draw_box(ax, i, data[algo], color)
            if (fig_id, algo) in paper:
                ax.plot(i, paper[(fig_id, algo)], marker="D", markersize=4.5, markerfacecolor="none",
                        markeredgecolor=GREY, linestyle="none", zorder=5)
        ax.set_xticks(range(len(FIG3_ORDER)), FIG3_ORDER, rotation=45, ha="right")
        ax.set_ylabel("Miss Ratio Reduction\nfrom FIFO")
        ax.axhline(0, color="black", linewidth=0.5)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        caption(ax, tag)
    axes[0, 2].plot([], [], marker="v", color="#8b1a1a", linestyle="none", label="our mean")
    axes[0, 2].plot([], [], marker="D", markerfacecolor="none", markeredgecolor=GREY, linestyle="none", label="paper mean (read off, about +/-0.01)")
    axes[0, 2].legend(loc="upper center", bbox_to_anchor=(0.5, 1.28), frameon=False, fontsize=6)
    fig.suptitle("Figure 3 (companion) - four algorithms on every Twitter trace we ran", fontsize=9)
    note(fig, "Box: P25-P75, whiskers P10-P90, line = median, triangle = mean (the paper's convention). Only the six policies run on all these traces are shown "
              "(no TinyLFU/TwoQ/LIRS/LHD/CACHEUS/Hyperbolic/B-LRU on the full Twitter set; LFU, which the paper does not plot, is off-scale at a median of -62% / -36% and is omitted). Ours: 12 of the paper's 54 Twitter traces at 10% and 16 at 0.1%. Panels a, b, d, e need the proprietary CDN1/CDN2 traces.")
    fig.tight_layout(h_pad=3.2)
    save(fig, "fig03b_boxplots_four_algorithms_all_twitter")


# ----------------------------------------------------------------------------- Figure 4
FIG4_ALGOS = [("sieve", "SIEVE"), ("arc", "ARC"), ("tinylfu_snapshot", "TinyLFU"), ("twoq", "TwoQ"), ("lirs", "LIRS"),
              ("lhd", "LHD"), ("cacheus", "CACHEUS"), ("hyperbolic", "Hyperbolic"), ("clock", "CLOCK"),
              ("lru", "LRU"), ("blru", "B-LRU")]
DATASET_OF = {"meta_reag": "metaCDN", "meta_rnha": "metaCDN", "meta_rprn": "metaCDN", "wiki_2019t": "wiki",
              "metakv_202206": "metaKV", "metakv_202210": "metaKV", "metakv_trace1_candidate": "metaKV"}


def fig04():
    pts = defaultdict(list)  # (cap, dataset, policy) -> [reduction]
    for r in rows("local_results/online_baselines_public_extension/public_twelve_subset.csv"):
        if r["trace"] in DATASET_OF and r["policy"] != "fifo":
            pts[(r["capacity_fraction"], DATASET_OF[r["trace"]], r["policy"])].append(float(r["reduction_from_fifo"]))
    # the five Meta KV traces split from the merged file (docs/metakv_split_protocol.md) and the two other Wiki traces (docs/wiki_full_extension_protocol.md)
    split_rows = rows("local_results/metakv_split_extension/metakv_split_extension.csv") if (ROOT / "local_results/metakv_split_extension/metakv_split_extension.csv").exists() else []
    for r in split_rows + [x for w in ("2016u", "2019u") for x in rows(f"local_results/wiki_{w}_extension/wiki_{w}_extension.csv")
                           if (ROOT / f"local_results/wiki_{w}_extension/wiki_{w}_extension.csv").exists()]:
        if r["policy"] != "fifo":
            pts[(r["capacity_fraction"], "metaKV" if r["trace"].startswith("metakv") else "wiki", r["policy"])].append(float(r["reduction_from_fifo"]))
    for name in ("metakv_202206", "metakv_202210", "metakv_trace1_candidate"):
        if split_rows and name != "metakv_202210":    # the split supersedes the merged file and the separately downloaded trace 1
            continue
        src = [f"local_results/{name}_0p1pct_six_policy.csv", f"local_results/{name}_10pct_six_policy.csv"] \
            if name != "metakv_trace1_candidate" else ["local_results/metakv_trace1_candidate_six_policy.csv"]
        for path in src:
            for r in rows(path):
                cap = str(r.get("capacity_fraction") or "")
                if r["policy"] in ("sieve", "arc", "lru", "clock") and cap in ("0.001", "0.1"):
                    fifo = [x for x in rows(path) if x["policy"] == "fifo" and x["capacity_fraction"] == cap][0]
                    pts[(cap, "metaKV", r["policy"])].append(float(r.get("reduction_from_fifo") or
                                                                    (1 - float(r["misses"]) / float(fifo["misses"]))))
    paper = defaultdict(list)
    for r in rows("config/paper_fig4_points.csv"):
        paper[(r["size_label"], r["dataset"], r["algo"])].append(float(r["value"]))
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.2))
    for ax, cap, size, tag in ((axes[0], "0.1", "large", "(a) Large cache"), (axes[1], "0.001", "small", "(b) Small cache")):
        for j, (pol, label) in enumerate(FIG4_ALGOS):
            for ds, (dlabel, color, marker) in DATASET_STYLE.items():
                for v in paper.get((size, ds, label), []):
                    ax.scatter(j + 0.14, v, marker=marker, s=14, facecolors="none", edgecolors=color, linewidths=0.6, alpha=0.7, zorder=2)
                for v in pts.get((cap, ds, pol), []):
                    ax.scatter(j - 0.14, v, marker=marker, s=22, color=color, zorder=3, edgecolors="black", linewidths=0.3)
        ax.set_xticks(range(len(FIG4_ALGOS)), [l for _, l in FIG4_ALGOS], rotation=45, ha="right")
        ax.set_ylabel("Miss Ratio Reduction from FIFO")
        ax.axhline(0, color="black", linewidth=0.5)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        caption(ax, tag)
    handles = [plt.Line2D([], [], marker=m, color=c, linestyle="none", markersize=4, label=n) for n, c, m in DATASET_STYLE.values()]
    handles += [plt.Line2D([], [], marker="o", markerfacecolor="none", markeredgecolor=GREY, linestyle="none", label="hollow, right of tick: paper's points"),
                plt.Line2D([], [], marker="o", color=GREY, linestyle="none", label="filled, left of tick: ours")]
    fig.legend(handles=handles, ncol=6, loc="lower center", bbox_to_anchor=(0.5, -0.02), frameon=False, fontsize=6.5)
    fig.suptitle("Figure 4 - Miss ratio reduction on Meta (KV + CDN), Wiki CDN and Tencent Photo", fontsize=9)
    note(fig, "\nOurs: filled markers, one per public trace (Meta CDN 3, Wiki 3, Meta KV 5 split from the merged file plus the 2022-10 file; Tencent Photo not run). All 11 algorithms run except CACHEUS on Wiki 2019u (memory gate and disk); the 2022-10 Meta KV file has only SIEVE/ARC/LRU/CLOCK. "
              "'TinyLFU' is the pinned-snapshot version (the paper's TinyLFU differs; see README). Paper: hollow markers read from the PDF, trace identity unlabeled.")
    fig.tight_layout()
    save(fig, "fig04_public_scatter")


# ----------------------------------------------------------------------------- Figure 5
def fig05b():
    winners = rows("local_results/online_baselines_public_extension/public_twelve_subset_point_winners.csv")
    fam = {"meta_reag": "Meta (CDN)", "meta_rnha": "Meta (CDN)", "meta_rprn": "Meta (CDN)", "wiki_2019t": "Wiki",
           "twitter_cluster10": "Twitter", "twitter_cluster26": "Twitter", "twitter_cluster50": "Twitter"}
    shares = defaultdict(lambda: defaultdict(float))
    counts = defaultdict(float)
    for r in winners:
        names = [w for w in re.split(r"[;,| ]+", r["winners"]) if w]
        for w in names:
            shares[(r["capacity_fraction"], fam[r["trace"]])][w] += 1 / len(names)
        counts[(r["capacity_fraction"], fam[r["trace"]])] += 1
    paper = {(r["size_label"], r["dataset"]): float(r["sieve_win_fraction"]) for r in rows("config/paper_fig5_sieve.csv")}
    ds_map = {"Wiki": "wiki", "Meta (CDN)": "metaCDN", "Twitter": "twitter"}
    rows_order = ["Wiki", "Tencent", "Meta (CDN)", "Meta (KV)", "CDN1", "CDN2", "Twitter"]
    keep = [("sieve", "SIEVE", SIEVE_C, ""), ("arc", "ARC", "#d9d9d9", "\\\\"), ("twoq", "TwoQ", "#f6c28b", "//"),
            ("lhd", "LHD", "#bfbfbf", "||")]
    fig, axes = plt.subplots(1, 2, figsize=(8.8, 3.4), sharey=True)
    for ax, cap, size, tag in ((axes[0], "0.1", "large", "(a) Large cache"), (axes[1], "0.001", "small", "(b) Small cache")):
        for yi, name in enumerate(rows_order):
            key = (cap, name)
            pv = paper.get((size, name))
            if pv is not None:
                ax.plot([pv, pv], [yi - 0.42, yi + 0.42], color="black", linewidth=1.6, zorder=6)
            if key not in shares:
                ax.barh(yi, 1.0, color="#f1f1f1", edgecolor=GREY, linestyle=":")
                ax.text(0.5, yi, "no local data" if name not in ("CDN1", "CDN2") else "proprietary", ha="center", va="center", fontsize=6, color="#555555")
                continue
            left = 0
            n = counts[key]
            other = 1.0
            for pol, label, color, hatch in keep:
                share = shares[key].get(pol, 0) / n
                if share:
                    ax.barh(yi, share, left=left, color=color, hatch=hatch, edgecolor="black", linewidth=0.4)
                    left += share
                    other -= share
            if other > 1e-9:
                ax.barh(yi, other, left=left, color="white", hatch="xxx", edgecolor="black", linewidth=0.4)
            ax.text(1.02, yi, f"n={int(n)}", va="center", fontsize=6)
        ax.set_yticks(range(len(rows_order)), rows_order)
        ax.set_xlim(0, 1.12)
        ax.set_xticks([0, .2, .4, .6, .8, 1.0])
        caption(ax, tag)
    legend = [Rectangle((0, 0), 1, 1, facecolor=c, hatch=h, edgecolor="black", label=l) for _, l, c, h in keep]
    legend.append(Rectangle((0, 0), 1, 1, facecolor="white", hatch="xxx", edgecolor="black", label="Others"))
    legend.append(plt.Line2D([], [], color="black", linewidth=1.6, label="paper's SIEVE share"))
    fig.legend(handles=legend, ncol=6, loc="upper center", bbox_to_anchor=(0.5, 0.94), frameon=False, fontsize=6.5)
    fig.suptitle("Figure 5 (companion) - 11 candidate algorithms, 7 selected traces only", y=0.99, fontsize=9)
    note(fig, "Ours: share of traces on which each algorithm has the lowest miss ratio among 11 candidates (ties shared), 7 selected traces (3 Meta CDN, 1 Wiki, 3 Twitter); n is the trace count. "
              "The black tick marks SIEVE's share in the paper's bar (extracted from the PDF). The paper's other segments cannot be extracted exactly and are not drawn.")
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    save(fig, "fig05b_best_algorithm_share_11_candidates")


# ----------------------------------------------------------------------------- Figure 6
def six_policy_misses():
    """{(dataset, capacity): {trace: {policy: misses}}} for every trace with the common six-policy set."""
    table = defaultdict(lambda: defaultdict(dict))

    def add(dataset, trace, cap, policy, misses):
        table[(dataset, cap)][trace][policy] = int(misses)

    for r in rows("local_results/public_six.csv"):
        ds = {"wiki_2019t": "Wiki"}.get(r["workload"], "Meta (CDN)" if r["workload"].startswith("meta_") else None)
        if ds:
            add(ds, r["workload"], r["capacity_fraction"], r["policy"], r["misses"])
    for name in ("metakv_202206", "metakv_202210"):
        for cap in ("0p1pct", "10pct"):
            for r in rows(f"local_results/{name}_{cap}_six_policy.csv"):
                add("Meta (KV)", name, r["capacity_fraction"], r["policy"], r["misses"])
    for r in rows("local_results/metakv_trace1_candidate_six_policy.csv"):
        add("Meta (KV)", "metakv_trace1_candidate", r["capacity_fraction"], r["policy"], r["misses"])
    for path in ("local_results/twitter16_0p1pct/exact_counters.csv", "local_results/twitter12_10pct/exact_counters.csv"):
        for r in rows(path):
            add("Twitter", r["trace"], r["capacity_fraction"], r["policy"], r["misses"])
    return table


SIX_CONTENDERS = ("sieve", "arc", "clock", "lru", "lfu")


def winner_shares(table):
    """Share of traces on which each policy has the fewest misses among the contenders (exact ties shared)."""
    out = {}
    for key, traces in table.items():
        share = defaultdict(float)
        for trace, misses in traces.items():
            best = min(misses[p] for p in SIX_CONTENDERS)
            winners = [p for p in SIX_CONTENDERS if misses[p] == best]
            for w in winners:
                share[w] += 1 / len(winners)
        out[key] = ({w: v / len(traces) for w, v in share.items()}, len(traces))
    return out


def fig05():
    shares = winner_shares(six_policy_misses())
    paper = {(r["size_label"], r["dataset"]): float(r["sieve_win_fraction"]) for r in rows("config/paper_fig5_sieve.csv")}
    rows_order = ["Wiki", "Tencent", "Meta (CDN)", "Meta (KV)", "CDN1", "CDN2", "Twitter"]
    keep = [("sieve", "SIEVE", SIEVE_C, ""), ("arc", "ARC", "#d9d9d9", "\\\\"), ("clock", "CLOCK", "#f6c28b", "//"),
            ("lru", "LRU", "#bfbfbf", "||"), ("lfu", "LFU", "#9ecae1", "..")]
    fig, axes = plt.subplots(1, 2, figsize=(8.8, 3.4), sharey=True)
    for ax, cap, size, tag in ((axes[0], "0.1", "large", "(a) Large cache (10%)"), (axes[1], "0.001", "small", "(b) Small cache (0.1%)")):
        for yi, name in enumerate(rows_order):
            pv = paper.get((size, name))
            if pv is not None:
                ax.plot([pv, pv], [yi - 0.42, yi + 0.42], color="black", linewidth=1.6, zorder=6)
            key = (name, cap)
            if key not in shares:
                ax.barh(yi, 1.0, color="#f1f1f1", edgecolor=GREY, linestyle=":")
                ax.text(0.5, yi, "proprietary" if name in ("CDN1", "CDN2") else "not run (file too large)", ha="center", va="center", fontsize=6, color="#555555")
                continue
            share, n = shares[key]
            left = 0
            for pol, label, color, hatch in keep:
                v = share.get(pol, 0)
                if v:
                    ax.barh(yi, v, left=left, color=color, hatch=hatch, edgecolor="black", linewidth=0.4)
                    left += v
            ax.text(1.02, yi, f"n={n}", va="center", fontsize=6)
        ax.set_yticks(range(len(rows_order)), rows_order)
        ax.set_xlim(0, 1.12)
        ax.set_xticks([0, .2, .4, .6, .8, 1.0])
        caption(ax, tag)
    legend = [Rectangle((0, 0), 1, 1, facecolor=c, hatch=h, edgecolor="black", label=l) for _, l, c, h in keep]
    legend.append(plt.Line2D([], [], color="black", linewidth=1.6, label="paper's SIEVE share"))
    fig.legend(handles=legend, ncol=6, loc="upper center", bbox_to_anchor=(0.5, 0.94), frameon=False, fontsize=6.5)
    fig.suptitle("Figure 5 - Best-performing algorithms on each dataset", y=0.99, fontsize=9)
    note(fig, "Ours: for every public trace we ran, the share of traces on which each policy has the fewest misses among the same five contenders (SIEVE, ARC, CLOCK, LRU, LFU; exact ties shared); "
              "n = traces (Twitter: 16 at the small cache, 12 at the large; Meta KV: 3; Meta CDN: 3; Wiki: 1). The paper compares 11 algorithms, including TwoQ, LHD, TinyLFU and LIRS, so its bars have more room for 'others' and its SIEVE shares are not directly comparable. "
              "The companion figure fig05b uses 11 candidates on 7 traces. The black tick is SIEVE's share in the paper's bar. Tencent Photo files are 35-37 GB each and were not run.")
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    save(fig, "fig05_best_algorithm_share")


def fig06():
    cells = rows("local_results/throughput/throughput_cells_all_round2.csv")
    style = {"sieve_sharded16": ("SIEVE (16 partitions)", SIEVE_C, "o", "-"), "sieve": ("SIEVE (one miss lock)", "#f6b26b", "o", "--"),
             "lru_sharded16": ("LRU (16 partitions)", "#00008b", "^", "-"), "lru_trylock": ("LRU try-lock", LRU_C, "D", "--"),
             "lru_strict": ("LRU strict (global lock)", LFU_C, "s", "-.")}
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.0))
    for ax, cap, tag in ((axes[0], "large", "(a) Large cache (100k objects/thread)"), (axes[1], "small", "(b) Small cache (10k objects/thread)")):
        for pol, (label, color, marker, ls) in style.items():
            pts = sorted((int(r["threads"]), float(r["median_mops"]), float(r["min_mops"]), float(r["max_mops"]))
                         for r in cells if r["capacity"] == cap and r["policy"] == pol)
            x = [p[0] for p in pts]
            ax.errorbar(x, [p[1] for p in pts], yerr=[[p[1] - p[2] for p in pts], [p[3] - p[1] for p in pts]], color=color,
                        marker=marker, linestyle=ls, markersize=4, linewidth=1, capsize=2, label=label)
        ax.set_xscale("log", base=2)
        ax.set_xticks([1, 2, 4, 8], ["1", "2", "4", "8"])
        ax.axvspan(4.5, 9, color="#eeeeee", zorder=0)
        ax.text(6.5, ax.get_ylim()[1] * 0.04, "SMT", ha="center", fontsize=6, color="#555555")
        ax.set_xlabel("Number of Threads")
        ax.set_ylabel("Throughput (Mops)")
        ax.set_ylim(bottom=0)
        caption(ax, tag)
    axes[0].legend(loc="upper left", frameon=False, fontsize=6)
    fig.suptitle("Figure 6 - Throughput scaling with CPU threads: laptop adaptation, own harness (not CacheLib)", fontsize=9)
    note(fig, "Ours: 4-core/8-thread laptop, independent C++ harness, synthetic Zipf alpha 1.0 with disjoint per-thread IDs, median and min-max of 7 passes (280 runs, quiet machine). "
              "The paper used CacheLib on a 16-core server with Meta and Twitter KV traces and 1-16 threads; absolute numbers are not comparable and 16 threads were not run.")
    fig.tight_layout()
    save(fig, "fig06_throughput_adaptation")


# ----------------------------------------------------------------------------- Figure 7
def cumulative_curve(run_id):
    rec = json.loads((LR / "runs" / run_id / "complete.json").read_text())
    text = Path(rec["log"]).read_text()
    return [(float(h) / 24.0, float(m)) for h, _, m in re.findall(r"([\d.]+) hour: (\d+) requests, miss ratio ([\d.]+)", text)]


def fig07():
    state = rows("local_results/figure7a_state_fixture/fixture_state.csv")
    fig = plt.figure(figsize=(9.4, 3.4))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.35, 1, 1])
    ax = fig.add_subplot(gs[0])
    parsed = []
    for r in state:
        q = json.loads(r["queue_head_to_tail_json"])
        parsed.append((r, [str(o["object_id"]) for o in q], {str(o["object_id"]): o["visited"] for o in q}, r["hand_object_id"] or None))
    depth = max(len(ids) for _, ids, _, _ in parsed)
    ax.set_xlim(-0.5, len(parsed) * 1.4)
    ax.set_ylim(-1.1, depth * 0.95 + 1.5)
    ax.axis("off")
    for i, (r, ids, vis, hand) in enumerate(parsed):
        x0 = i * 1.4
        for j, key in enumerate(ids):  # head at the top
            y = (depth - 1 - j) * 0.95 + 0.0
            ax.add_patch(FancyBboxPatch((x0, y), 1.0, 0.8, boxstyle="round,pad=0.02,rounding_size=0.1",
                                        facecolor="#f4a6a6" if vis[key] else "#a8c8ee", edgecolor="black", linewidth=0.6))
            ax.text(x0 + 0.5, y + 0.4, key, ha="center", va="center", fontsize=8, weight="bold")
            if hand == key:
                ax.annotate("", xy=(x0 - 0.03, y + 0.4), xytext=(x0 - 0.33, y + 0.4), arrowprops=dict(arrowstyle="-|>", color="#1b4f9c", lw=1.2))
        verdict = "hit" if r["hit"] == "1" else "miss"
        ax.text(x0 + 0.5, depth * 0.95 + 0.2, f"r{r['request']}\nreq {r['object_id']}\n{verdict}", ha="center", va="bottom", fontsize=5.8, color="#333333", linespacing=1.15)
    ax.text(-0.4, -0.85, "Head (newest) at top, tail at bottom. Blue arrow = hand. Red = visited bit set.", fontsize=6.3)
    caption(ax, "(a) Queue after each of 8 requests (fixture)", y=-0.02)
    for k, (trace, label, tag) in enumerate((("meta_reag", "Meta CDN meta_reag", "(b) meta_reag, full trace (8 days), 10% cache"),
                                              ("twitter_cluster26", "Twitter cluster26", "(c) Twitter cluster26, full trace, 10% cache"))):
        axk = fig.add_subplot(gs[k + 1])
        for pol, color, ls, name in (("arc", ARC_C, "-.", "ARC"), ("lru", LRU_C, "--", "LRU"), ("sieve", SIEVE_C, "-", "SIEVE")):
            rid = None
            for r in rows("local_results/public_six.csv"):
                if r["workload"] == trace and r["policy"] == pol and r["capacity_fraction"] == "0.1":
                    rid = r["run_id"]
            if rid is None:
                for r in rows("local_results/online_baselines_public_extension/public_twelve_subset.csv"):
                    if r["trace"] == trace and r["policy"] == pol and r["capacity_fraction"] == "0.1":
                        rid = r["run_id"]
            xs, ys = zip(*cumulative_curve(rid))
            axk.plot(xs, ys, color=color, linestyle=ls, marker="o", markersize=2.5, linewidth=1, label=name)
        axk.set_xlabel("Trace time (days)")
        axk.set_ylabel("Cumulative miss ratio")
        axk.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, fontsize=6.5)
        caption(axk, tag.replace(", full trace", "\nfull trace"))
    fig.suptitle("Figure 7 - Sifting illustration (a) and cumulative miss ratio over time (b, c), on our public traces", fontsize=9)
    note(fig, "(a) is an eight-request fixture checked against the independent model, not the paper's production-trace illustration. (b, c) use our own public traces, not the paper's two unnamed production traces, "
              "and the simulator reports the cumulative ratio once per trace day, so each curve has only 7-8 points. "
              "On meta_reag ARC stays below SIEVE, so the paper's 'SIEVE's gap widens over time' is not seen on this trace; on cluster26 the three are indistinguishable.")
    fig.tight_layout()
    save(fig, "fig07_sifting_and_time")


# ----------------------------------------------------------------------------- Figure 8
ZSC = "local_results/zipf_support_check"
SNAP = sorted(ROOT.glob("external_replication/sievereproduction_*"))[0].relative_to(ROOT)
ZIPF_STYLE = {"LRU": (LRU_C, "s", "--"), "LFU": (LFU_C, "*", "-."), "ARC": (ARC_C, "o", "-"), "SIEVE": (SIEVE_C, "o", "-")}


def fig08():
    miss = rows(f"{ZSC}/figure8a_10k_objects_vs_paper.csv")
    pop = [r for r in rows(f"{ZSC}/popular_ratio_10k_objects.csv") if float(r["alpha"]) == 1.0]
    paper_a = rows("paper_reference/figure8a_published_digitized.csv")
    paper_b = [r for r in rows(f"{SNAP}/fig8/fig8_paper_values.csv") if r["panel"] == "b"]
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.0))
    for pol, (color, marker, ls) in ZIPF_STYLE.items():
        pts = sorted((float(r["capacity_percent"]), float(r["mean_miss_ratio"])) for r in miss if r["policy"] == pol)
        axes[0].plot([p[0] for p in pts], [p[1] for p in pts], color=color, marker=marker, linestyle=ls, markersize=3.5, linewidth=1, label=pol)
        pp = sorted((float(r["capacity_percent"]), float(r["digitized_miss_ratio"])) for r in paper_a if r["policy"] == pol)
        axes[0].plot([p[0] for p in pp], [p[1] for p in pp], linestyle="none", marker=marker, markerfacecolor="none", markeredgecolor=color, markersize=4.5, alpha=0.9)
        pq = sorted((int(r["cache_objects"]) / 100, float(r["mean_popular_ratio"])) for r in pop if r["policy"] == pol)
        axes[1].plot([p[0] for p in pq], [p[1] for p in pq], color=color, marker=marker, linestyle=ls, markersize=3.5, linewidth=1, label=pol)
        pb = sorted((float(r["cache_pct"]), float(r["value"])) for r in paper_b if r["algo"] == pol)
        axes[1].plot([p[0] for p in pb], [p[1] for p in pb], linestyle="none", marker=marker, markerfacecolor="none", markeredgecolor=color, markersize=4.5, alpha=0.9)
    for ax in axes:
        ax.set_xlabel("Cache Size (X% of Working Set)")
        ax.set_xscale("log")
    axes[0].set_ylabel("Miss Ratio")
    axes[1].set_ylabel("Popular Object Ratio")
    axes[1].set_ylim(0, 1.0)
    axes[0].plot([], [], linestyle="none", marker="o", markerfacecolor="none", markeredgecolor=GREY, label="hollow: paper (digitized)")
    axes[0].legend(frameon=False, loc="upper right")
    axes[1].legend(frameon=False, loc="lower right")
    caption(axes[0], "(a) Miss ratio over size")
    caption(axes[1], "(b) Popular object ratio over size")
    fig.suptitle("Figure 8 - Miss ratio and popular object ratio on a Zipfian dataset (alpha = 1.0)", fontsize=9)
    note(fig, "Ours: 10,000 objects, 10M requests, three seeds (mean). The workload size was identified by the independent SIEVEREPRODUCTION repository and re-verified here with our own generator and simulator; "
              "our earlier 1M-object runs are in fig08c. Hollow markers: paper values read from its PDF (panel a by us, b by SIEVEREPRODUCTION). Panel b averages the resident share of the C most frequent objects over snapshots every 10,000 requests; the paper's averaging is unstated.")
    fig.tight_layout()
    save(fig, "fig08_zipf_size")


def fig08c():
    old = rows("local_results/zipf8_paper_capacity_grid/figure8a_paper_vs_local.csv")
    new = rows(f"{ZSC}/figure8a_10k_objects_vs_paper.csv")
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.0), sharey=True)
    for ax, data, key, tag in ((axes[0], old, "local_mean_miss_ratio", "1,000,000 objects, 100M requests (our first design)"),
                               (axes[1], new, "mean_miss_ratio", "10,000 objects, 10M requests")):
        for pol, (color, marker, ls) in ZIPF_STYLE.items():
            pts = sorted((float(r["capacity_percent"]), float(r[key])) for r in data if r["policy"] == pol)
            ax.plot([p[0] for p in pts], [p[1] for p in pts], color=color, marker=marker, linestyle=ls, markersize=3.5, linewidth=1, label=pol)
            pp = sorted((float(r["capacity_percent"]), float(r["digitized_paper_miss_ratio" if "digitized_paper_miss_ratio" in r else "paper_digitized"])) for r in data if r["policy"] == pol)
            ax.plot([p[0] for p in pp], [p[1] for p in pp], linestyle="none", marker=marker, markerfacecolor="none", markeredgecolor=color, markersize=4.5)
        ax.set_xscale("log")
        ax.set_xlabel("Cache Size (X% of Working Set)")
        caption(ax, tag, y=-0.32)
    axes[0].set_ylabel("Miss Ratio")
    axes[0].legend(frameon=False, fontsize=6)
    fig.suptitle("Figure 8a (companion) - why the workload size matters: same cache fractions, different Zipf support", fontsize=8.5)
    note(fig, "Lines: our runs. Hollow markers: the paper's curves (read off its PDF). The paper does not state the workload size. At the 1M-object size our miss ratios are 0.1-0.27 lower than the paper's; "
              "at 10,000 objects (the size found by SIEVEREPRODUCTION) every ARC, LRU and SIEVE point is within 0.0008 of the paper's. LFU at small caches is the only series that stays seed-sensitive (0.013).")
    fig.tight_layout()
    save(fig, "fig08c_zipf_support_1M_vs_10k")


# ----------------------------------------------------------------------------- Figure 9
def fig09():
    miss, pop = rows(f"{ZSC}/figure9a_10k_objects_miss_ratio.csv"), rows(f"{ZSC}/popular_ratio_10k_objects.csv")
    pop = [r for r in pop if int(r["cache_objects"]) == 1000]
    hand = [r for r in rows(f"{ZSC}/hand_samples_thinned.csv") if r["seed"] == "42"]
    paper = rows(f"{SNAP}/fig9/fig9_paper_values.csv")
    fig = plt.figure(figsize=(9.4, 3.1))
    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 1.3])
    axes = [fig.add_subplot(gs[0]), fig.add_subplot(gs[1])]
    for ax, data, key, panel in ((axes[0], miss, "mean_miss_ratio", "a"), (axes[1], pop, "mean_popular_ratio", "b")):
        for pol, (color, marker, ls) in ZIPF_STYLE.items():
            pts = sorted((float(r["alpha"]), float(r[key])) for r in data if r["policy"] == pol)
            ax.plot([p[0] for p in pts], [p[1] for p in pts], color=color, marker=marker, linestyle=ls, markersize=3, linewidth=1, label=pol)
            pp = sorted((float(r["x"]), float(r["value"])) for r in paper if r["panel"] == panel and r["series"] == pol)
            ax.plot([p[0] for p in pp], [p[1] for p in pp], linestyle="none", marker=marker, markerfacecolor="none", markeredgecolor=color, markersize=4.5, alpha=0.9)
        ax.set_xlabel("Zipf Parameter (skewness alpha)")
    axes[0].set_ylabel("Miss Ratio")
    axes[1].set_ylabel("Popular Object Ratio")
    axes[0].legend(frameon=False, loc="upper right", fontsize=6)
    caption(axes[0], "(a) Miss ratio")
    caption(axes[1], "(b) Popular object ratio")
    sub = gs[2].subgridspec(3, 1, hspace=0.55)
    for k, (alpha, color) in enumerate(((0.8, "#d62728"), (1.0, "#1f77b4"), (1.2, "#2ca02c"))):
        axh = fig.add_subplot(sub[k])
        pts = sorted((int(r["n_req"]), float(r["hand_normalized"])) for r in hand if float(r["alpha"]) == alpha)
        axh.plot([p[0] for p in pts], [p[1] for p in pts], color=color, linewidth=0.8, label=f"Zipf {alpha} (ours)")
        pp = sorted((float(r["requests"]), float(r["value"])) for r in paper if r["panel"] == "c" and float(r["series"]) == alpha and r["requests"])
        axh.plot([p[0] for p in pp], [p[1] for p in pp], color="black", linewidth=0.5, alpha=0.55, label="paper (read off)")
        axh.set_ylim(-0.1, 1.15)
        axh.set_yticks([0, 1])
        axh.legend(frameon=False, loc="upper left", fontsize=5.5)
        axh.tick_params(axis="x", labelsize=5.5, pad=1)   # each subplot has its own time axis
        if k == 1:
            axh.set_ylabel("Hand Position from Tail")
        if k == 2:
            axh.set_xlabel("Logical Time (#requests; own axis per row)", labelpad=2)
            caption(axh, "(c) Hand movement in SIEVE", y=-0.95)
    fig.suptitle("Figure 9 - Zipfian workloads with different skewness", fontsize=9)
    note(fig, "Ours, three seeds (mean; seed 42 in c). (a, b): 10,000 objects, 10M requests, a 1,000-object cache (10%). (c): 1,000,000 objects, a 1,000-object cache, cut at the 262,144th eviction - a setup "
              "chosen after the fact by SIEVEREPRODUCTION to match the paper, then re-run here with our generator and simulator, so it shows reproducibility, not prediction. Hollow markers/grey curves: paper values read off its PDF by SIEVEREPRODUCTION (the paper prints no time axis for alpha = 1.2).")
    fig.tight_layout()
    save(fig, "fig09_zipf_skew_and_hand")


# ----------------------------------------------------------------------------- Figure 10
def fig10():
    data = rows("local_results/zipf10_original_scale/figure10_interval_results.csv")
    style = {"arc": ("ARC", ARC_C, "-"), "lru": ("LRU", LRU_C, "--"), "lfu": ("LFU", LFU_C, "-."), "sieve": ("SIEVE", SIEVE_C, "-")}
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.0))
    for pol, (label, color, ls) in style.items():
        pts = sorted((int(r["n_req"]), float(r["interval_miss_ratio"]), float(r["popular_ratio"])) for r in data if r["policy"] == pol)
        total = pts[-1][0]
        xs = [p[0] / total for p in pts]
        axes[0].plot(xs, [p[1] for p in pts], color=color, linestyle=ls, linewidth=0.9, label=label)
        axes[1].plot(xs, [p[2] for p in pts], color=color, linestyle=ls, linewidth=0.9, label=label)
    axes[0].set_ylim(0.1, 0.35)
    for ax, ylabel in ((axes[0], "Miss Ratio"), (axes[1], "Popular Objects Ratio")):
        ax.set_xlabel("Logical Time")
        ax.set_ylabel(ylabel)
        ax.axvline(0.5, color=GREY, linewidth=0.6, linestyle=":")
    axes[0].legend(frameon=False, ncol=2, loc="upper left", fontsize=6)
    axes[1].legend(frameon=False, loc="lower right", fontsize=6)
    caption(axes[0], "(a) Interval miss ratio")
    caption(axes[1], "(b) Popular object ratio over time")
    fig.suptitle("Figure 10 - Interval miss ratio and popular object ratio across a workload change (two alpha=1 Zipf workloads)", fontsize=9)
    note(fig, "Ours: two disjoint 100,000-object, 10M-request Zipf alpha 1.0 phases joined at the midpoint, 10,000-object cache, interval = 100,000 requests. The paper's population overlap and exact sizes are unrecovered "
              "(disjoint IDs is a declared assumption). The y-axis of (a) is clipped like the paper's; spikes above it are real values (LFU does not recover).")
    fig.tight_layout()
    save(fig, "fig10_workload_change")


def fig10c():
    data = [r for r in rows("local_results/zipf10_support_check/samples.csv") if r["capacity_objects"] == "3000" and r["kind"] != "switch"]
    style = {"arc": ("ARC", ARC_C, "-"), "lru": ("LRU", LRU_C, "--"), "lfu": ("LFU", LFU_C, "-."), "sieve": ("SIEVE", SIEVE_C, "-")}
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.0))
    for pol, (label, color, ls) in style.items():
        by = defaultdict(list)
        for r in data:
            if r["policy"] == pol:
                by[int(r["n_req"])].append((float(r["interval_miss_ratio"]), float(r["popular_ratio"])))
        xs = sorted(by)
        total = xs[-1]
        axes[0].plot([x / total for x in xs], [np.mean([v[0] for v in by[x]]) for x in xs], color=color, linestyle=ls, linewidth=0.9, label=label)
        axes[1].plot([x / total for x in xs], [np.mean([v[1] for v in by[x]]) for x in xs], color=color, linestyle=ls, linewidth=0.9, label=label)
    axes[0].set_ylim(0.1, 0.35)
    for ax, ylabel in ((axes[0], "Miss Ratio"), (axes[1], "Popular Objects Ratio")):
        ax.set_xlabel("Logical Time")
        ax.set_ylabel(ylabel)
        ax.axvline(0.5, color=GREY, linewidth=0.6, linestyle=":")
    axes[0].legend(frameon=False, ncol=2, loc="upper left", fontsize=6)
    axes[1].legend(frameon=False, loc="lower right", fontsize=6)
    caption(axes[0], "(a) Interval miss ratio")
    caption(axes[1], "(b) Popular object ratio over time")
    fig.suptitle("Figure 10 (companion) - the same experiment at the 10,000-object support of Figure 8", fontsize=9)
    note(fig, "Ours: two disjoint 10,000-object, 5M-request Zipf alpha 1.0 phases (seed pairs 42/43 and 44/45, mean), a 3,000-object cache, interval = 100,000 requests. The cache size is the one fitted choice (the LRU plateau, 0.175 here against about 0.188 read off the paper); "
              "the other three policies' levels, LFU's failure to recover (miss ratio 0.98, popularity 0) and SIEVE's dip to 0.70 right after the switch are not fitted. SIEVE's miss-ratio bump after the switch (0.24) is larger than the paper's (about 0.18, read by eye).")
    fig.tight_layout()
    save(fig, "fig10c_workload_change_10k_objects")


# ----------------------------------------------------------------------------- Figure 11
def fig11():
    data = rows("local_results/instructions/instructions_paper_all_summary.csv")
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.0), sharey=False)
    colors = {"lru": "#d9d9d9", "fifo": "#fbd9b5", "sieve": SIEVE_C}
    for ax, cap, tag in ((axes[0], "0.1", "(a) Large cache (10% of objects)"), (axes[1], "0.001", "(b) Small cache (0.1% of objects)")):
        for i, alpha in enumerate(("0.8", "1.0", "1.2")):
            for j, pol in enumerate(("lru", "fifo", "sieve")):
                r = [x for x in data if x["alpha"] == alpha and x["capacity_fraction"] == cap and x["policy"] == pol][0]
                v = float(r["mean_net_instructions_per_request"])
                x = i + (j - 1) * 0.27
                ax.bar(x, v, width=0.25, color=colors[pol], edgecolor="black", linewidth=0.4, label=pol.upper() if i == 0 else None)
                ax.text(x, v + 4, f"{float(r['miss_ratio']):.2f}", rotation=90, ha="center", va="bottom", fontsize=5.5)
        ax.set_xticks(range(3), ["0.8", "1.0", "1.2"])
        ax.set_xlabel("Zipf Parameter (skewness alpha)")
        ax.set_ylabel("Instructions per request")
        ax.set_ylim(0, ax.get_ylim()[1] * 1.12)
        caption(ax, tag)
    axes[0].legend(frameon=False, ncol=3, loc="upper right", fontsize=6)
    fig.suptitle("Figure 11 - Average instructions per request for LRU, FIFO and SIEVE (the number above a bar is the miss ratio)", fontsize=9)
    note(fig, "Ours: hardware instruction counts (perf) for 100M requests over 1M objects, minus a matched no-op simulator, mean of 5 runs; seeds, capacity convention and timed region of the paper are unrecovered. "
              "Capacities are 10% and 0.1% of the observed object footprint.")
    fig.tight_layout()
    save(fig, "fig11_instructions")


# ----------------------------------------------------------------------------- Figure 12
def fig12():
    data = rows("local_results/figure12_public_selected_seven/figure12_public_selected_seven.csv")
    lecar_fixed = rows("local_results/lecar_sieve_fixed_grid/per_trace.csv")
    pairs = [("SIEVE", "SIEVE", None), ("LeCaR", "LeCaR-LRU", "LeCaR-SIEVE"), ("TwoQ", "TwoQ-LRU", "TwoQ-SIEVE"), ("ARC", "ARC-LRU", "ARC-SIEVE")]
    fig = plt.figure(figsize=(9.4, 3.2))
    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 0.9])
    for k, (cap, tag) in enumerate((("0.1", "(a) Large cache"), ("0.001", "(b) Small cache"))):
        ax = fig.add_subplot(gs[k])
        for i, (name, orig, repl) in enumerate(pairs):
            for off, label, color in ((-0.2, orig, "#ff9d1c"), (0.2, repl, "#a6d5e8")):
                if label is None:
                    continue
                vals = [float(r["reduction_from_fifo"]) for r in data if r["label"] == label and r["capacity_fraction"] == cap]
                if label == "LeCaR-SIEVE":   # the first LeCaR-SIEVE had a hand wrap-to-head bug; use the corrected runs (2026-10-23)
                    vals = [float(r["lecar_sieve_corrected_reduction"]) for r in lecar_fixed if r["capacity_fraction"] == cap]
                draw_box(ax, i + off, vals, color, width=0.34)
                ax.scatter([i + off] * len(vals), vals, s=5, color="black", zorder=5, alpha=0.6)
        ax.set_xticks(range(len(pairs)), [p[0] for p in pairs])
        ax.set_ylabel("Miss Ratio Reduction from FIFO")
        ax.axhline(0, color="black", linewidth=0.5)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        caption(ax, tag)
        if k == 0:
            ax.add_patch(Rectangle((0, 0), 0, 0, facecolor="#ff9d1c", label="Original"))
            ax.add_patch(Rectangle((0, 0), 0, 0, facecolor="#a6d5e8", label="replace LRU with SIEVE"))
            ax.legend(frameon=False, ncol=2, loc="lower center", bbox_to_anchor=(0.5, 1.0), fontsize=6)
    axc = fig.add_subplot(gs[2])
    probe = rows("local_results/figure12c_pinned_meta_reag_probe/source.csv")
    for yi, (cap, name) in enumerate((("0.001", "Small cache"), ("0.1", "Large cache"))):
        base = {r["policy"]: float(r["miss_ratio"]) for r in probe if r["capacity_fraction_requested"] == cap}
        for j, (pol, label, color) in enumerate((("sieve-belady", "SIEVE-Belady", "#ff7f0e"), ("lru-belady", "LRU-Belady", "#d9d9d9"), ("fifo-belady", "FIFO-Belady", "#fbd9b5"))):
            if pol in base:
                axc.barh(yi + (1 - j) * 0.27, base[pol], height=0.25, color=color, edgecolor="black", linewidth=0.4, label=label if yi == 0 else None)
    axc.set_yticks([0, 1], ["Small\ncache", "Large\ncache"])
    axc.set_xlabel("Miss ratio on meta_reag")
    axc.legend(frameon=False, fontsize=6, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=1)
    caption(axc, "(c) With foresight: one trace (miss ratio)")
    fig.suptitle("Figure 12 - Impact of replacing LRU with SIEVE in advanced algorithms (a, b); the potential of FIFO, LRU and SIEVE with foresight (c)", fontsize=9, y=1.03)
    note(fig, "(a, b): boxes over only 7 public traces with every point drawn (the paper uses 1,559 traces); S3-FIFO was not run. TwoQ/ARC/LeCaR are the pinned simulator's, with SIEVE replacing the frequent-object LRU. "
              "(c): the paper reports the share of 1,559 traces on which each variant is best; we ran the three Belady-assisted variants on one trace (meta_reag) and show their miss ratios instead. "
              "On these 7 traces replacing LRU with SIEVE lowers the mean reduction for ARC (10%: 7.2% to 5.2%) and leaves TwoQ unchanged; for LeCaR it raises it at 10% (6.2% to 7.8%, with the hand-wrap bug of our first LeCaR-SIEVE corrected) and lowers it at 0.1% (2.7% to 1.4%). On the four CDN and Wiki traces all three substitutions are at or above their LRU originals, as in the paper; the losses come from Twitter traces (docs/figure12_promotion_protocol.md, docs/lecar_sieve_collapse_protocol.md).")
    fig.tight_layout()
    save(fig, "fig12_advanced_algorithms")


# ----------------------------------------------------------------------------- Figure 13
def fig13():
    pol_label = {"sieve": "SIEVE", "arc": "ARC", "clock": "CLOCK", "lru": "LRU", "lfu": "LFU"}
    by = defaultdict(lambda: defaultdict(list))
    for trace in ("meta_reag", "meta_rnha", "meta_rprn"):
        for r in rows(f"local_results/byte_capacity_study/six_policy_extension/traces/{trace}/six_policy_byte_source.csv"):
            if r["policy"] in pol_label:
                by[r["capacity_fraction"]][pol_label[r["policy"]]].append(float(r["reduction_from_fifo"]))
    order = ["SIEVE", "ARC", "CLOCK", "LRU", "LFU"]
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.0))
    for ax, cap, tag, color in ((axes[0], "0.1", "(a) Large cache (10% of byte footprint)", "#f5a623"), (axes[1], "0.001", "(b) Small cache (0.1% of byte footprint)", "#a7d3e8")):
        for i, algo in enumerate(order):
            vals = by[cap][algo]
            ax.bar(i, np.mean(vals), width=0.55, color=SIEVE_C if algo == "SIEVE" else color, edgecolor="black", linewidth=0.5)
            ax.scatter([i] * len(vals), vals, s=10, color="black", zorder=5)
        ax.set_xticks(range(len(order)), order, rotation=45, ha="right")
        ax.set_ylabel("Byte Miss Ratio\nReduction from FIFO")
        ax.axhline(0, color="black", linewidth=0.5)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        caption(ax, tag)
    fig.suptitle("Figure 13 - Byte miss ratio across CDN traces (3 public Meta CDN traces)", fontsize=9)
    note(fig, "Ours: bars are the mean and dots the three public Meta CDN traces (meta_reag, meta_rnha, meta_rprn); the paper's boxes cover 1,492 proprietary and public CDN traces. "
              "Capacity is a share of the byte footprint; only the six pinned-simulator policies were run in byte mode.")
    fig.tight_layout()
    save(fig, "fig13_byte_miss_ratio")


# ----------------------------------------------------------------------------- Figure 14
def fig14():
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.0))
    reason = "The LRB Wiki2018/Wiki2019 traces (author archive) exceeded the\nlocal storage budget, and LRB itself (training, features) was not built."
    unavailable(axes[0], "(a) Wiki2018 trace", reason, headline="not run")
    unavailable(axes[1], "(b) Wiki2019 trace", reason, headline="not run")
    fig.suptitle("Figure 14 - Byte miss ratios at different cache sizes on the two Wiki CDN traces used in LRB's evaluation", fontsize=9)
    note(fig, "Not reproduced. The general Wiki CDN trace we do have (wiki_2019t) is a different workload and is not substituted here; see docs/figure14_lrb_provenance_audit.md.")
    fig.tight_layout()
    save(fig, "fig14_lrb_wiki_bytes")


# ----------------------------------------------------------------------------- companions from the independent replication
IR = "local_results/independent_replication"
IR_NOTE = ("SIEVEREPRODUCTION (Urcyle/SIEVEREPRODUCTION: a separate code base and run set under the same GitHub account, imported as a labelled snapshot in external_replication/) ")


def fig03c():
    means = rows(f"{IR}/fig3_twitter_means.csv")
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 4.6), sharey=False)
    for ax, size, tag in ((axes[0], "large", "(c) Twitter, large cache (10%)"), (axes[1], "small", "(f) Twitter, small cache (0.1%)")):
        data = [r for r in means if r["size"] == size]
        x = np.arange(len(data))
        ax.plot(x - 0.2, [float(r["theirs_mean"]) for r in data], "o", color="#1f77b4", markersize=4,
                label=f"SIEVEREPRODUCTION, clusters 1-24 (n={data[0]['theirs_n']}, scaled-down traces)")
        ax.plot(x, [float(r["ours_mean"]) for r in data], "^", color="#8b1a1a", markersize=4,
                label=f"ours, complete sets (n={data[0]['ours_n']} full-size traces)")
        ax.plot(x + 0.2, [float(r["union_mean"]) for r in data], "s", color="#2ca02c", markersize=3.5,
                label=f"union (their 24 + our full-size + 17 sampled clusters, n up to {max(int(r['union_n']) for r in data)})")
        ax.plot(x + 0.4, [float(r["paper_mean"]) for r in data], "D", markerfacecolor="none", markeredgecolor=GREY, markersize=4.5,
                label="paper mean (read off its PDF)")
        ax.set_xticks(x + 0.1, [r["algo"] for r in data], rotation=45, ha="right")
        ax.set_ylabel("Mean Miss Ratio Reduction from FIFO")
        ax.axhline(0, color="black", linewidth=0.5)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        ax.set_title(tag, fontsize=8)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=2, loc="lower center", bbox_to_anchor=(0.5, 0.13), frameon=False, fontsize=6.5)
    fig.suptitle("Figure 3c / 3f (companion) - Twitter means from three trace sets against the paper", fontsize=9)
    note(fig, "Means of the 11 algorithms' reductions. " + IR_NOTE + "ran Twitter clusters 1-24 on sampled or prefix-truncated copies (sample10/sample100, first 1B requests) to fit a laptop; "
              "ours are the clusters on which we ran all 11 algorithms at full size. Rank correlation with the paper's means: 0.96 / 0.98 (theirs), 0.991 / 0.982 (union of 47 and 48 clusters; 23 of them from the authors' 10% and 1% sample files run here, docs/twitter_sampled_extension_protocol.md, twitter_sample10_extension_protocol.md and twitter_gated_extension_protocol.md). Panels a, b, d, e (CDN1, CDN2) are proprietary.")
    fig.tight_layout(rect=(0, 0.2, 1, 0.97))
    save(fig, "fig03c_twitter_means_three_sets")


def fig04c():
    theirs = rows(f"{SNAP}/fig4/fig4.csv")
    paper = defaultdict(list)
    for r in rows(f"{SNAP}/fig4/fig4_paper_values.csv"):
        paper[(r["size"], r["dataset"], r["algo"])].append(float(r["reduction"]))
    labels = [l for _, l in FIG4_ALGOS]
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.2))
    for ax, size, tag in ((axes[0], "large", "(a) Large cache"), (axes[1], "small", "(b) Small cache")):
        for j, label in enumerate(labels):
            for ds, (dlabel, color, marker) in DATASET_STYLE.items():
                for v in paper.get((size, ds, label), []):
                    ax.scatter(j + 0.14, v, marker=marker, s=14, facecolors="none", edgecolors=color, linewidths=0.6, alpha=0.7, zorder=2)
                for r in theirs:
                    if r["size"] == size and r["algo"] == label and r["dataset"] == ds:
                        ax.scatter(j - 0.14, float(r["reduction"]), marker=marker, s=22, color=color, zorder=3, edgecolors="black", linewidths=0.3)
        ax.set_xticks(range(len(labels)), labels, rotation=45, ha="right")
        ax.set_ylabel("Miss Ratio Reduction from FIFO")
        ax.axhline(0, color="black", linewidth=0.5)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        caption(ax, tag)
    handles = [plt.Line2D([], [], marker=m, color=c, linestyle="none", markersize=4, label=n) for n, c, m in DATASET_STYLE.values()]
    handles += [plt.Line2D([], [], marker="o", markerfacecolor="none", markeredgecolor=GREY, linestyle="none", label="hollow, right of tick: paper's points"),
                plt.Line2D([], [], marker="o", color=GREY, linestyle="none", label="filled, left of tick: SIEVEREPRODUCTION")]
    fig.legend(handles=handles, ncol=6, loc="lower center", bbox_to_anchor=(0.5, -0.02), frameon=False, fontsize=6.5)
    fig.suptitle("Figure 4 (companion) - all 13 public traces and 11 algorithms, from the independent replication", fontsize=9)
    note(fig, "\n" + IR_NOTE + "ran every public trace (Meta CDN 3, Meta KV 5, Wiki 3, Tencent Photo 2 on a 10% spatial sample). Our own runs agree with theirs to 0.0001 on the 96 cells both of us ran, except CACHEUS and LHD (random). "
              "Paper points: hollow, read from the PDF by SIEVEREPRODUCTION; trace identity matched by SIEVE's value (all 26 SIEVE points agree to 4 decimals).")
    fig.tight_layout()
    save(fig, "fig04c_all_public_traces_independent")


def fig05c():
    bars = rows(f"{SNAP}/fig5/fig5_bars.csv")
    order = ["Wiki", "Tencent", "Meta (CDN)", "Meta (KV)", "CDN1", "CDN2", "Twitter"]
    parts = [("SIEVE", SIEVE_C, ""), ("ARC", "#d9d9d9", "\\\\"), ("TwoQ", "#f6c28b", "//"), ("LHD", "#bfbfbf", "||"), ("Others", "white", "xxx")]
    fig, axes = plt.subplots(1, 2, figsize=(8.8, 4.2), sharey=True)
    for ax, size, tag in ((axes[0], "large", "(a) Large cache"), (axes[1], "small", "(b) Small cache")):
        for yi, name in enumerate(order):
            for off, source, label in ((0.2, "paper Figure 5", "paper"), (-0.2, "replication", "SIEVEREPRODUCTION")):
                found = [r for r in bars if r["dataset"] == name and r["size"] == size and r["source"] == source]
                if not found:
                    if source == "replication":
                        ax.text(0.5, yi - 0.2, "proprietary: not replicated" if name in ("CDN1", "CDN2") else "n/a", ha="center", va="center", fontsize=6, color="#555555")
                    continue
                r = found[0]
                left = 0
                for key, color, hatch in parts:
                    v = float(r[key])
                    if v:
                        ax.barh(yi + off, v, left=left, height=0.36, color=color, hatch=hatch, edgecolor="black", linewidth=0.4, alpha=1.0 if source == "replication" else 0.6)
                        left += v
                if source == "replication":
                    ax.text(1.02, yi - 0.2, f"n={r['traces']}", va="center", fontsize=6)
        ax.set_yticks(range(len(order)), order)
        ax.set_xlim(0, 1.12)
        ax.set_xticks([0, .2, .4, .6, .8, 1.0])
        ax.invert_yaxis()
        caption(ax, tag)
    legend = [Rectangle((0, 0), 1, 1, facecolor=c, hatch=h, edgecolor="black", label=l) for l, c, h in parts]
    fig.legend(handles=legend, ncol=5, loc="upper center", bbox_to_anchor=(0.5, 0.94), frameon=False, fontsize=6.5)
    fig.suptitle("Figure 5 (companion) - best algorithm per dataset: paper (upper, faded) against the independent replication (lower)", y=0.99, fontsize=8.5)
    note(fig, IR_NOTE + "took the best of 11 algorithms on every public trace (Twitter: 24 sampled clusters of 53). Seven of the eight public-dataset bars equal the paper's; the exception is Tencent at the large cache "
              "(SIEVE 1/2 against 1), caused by CACHEUS (random) beating SIEVE by 0.0004 on one trace. Ties on Twitter go to the first algorithm in plotting order. Paper bars read from the PDF by SIEVEREPRODUCTION.")
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    save(fig, "fig05c_best_algorithm_independent")


FIGURES = {"fig01": fig01, "fig02": fig02, "fig03": fig03, "fig03b": fig03b, "fig03c": fig03c, "fig04": fig04, "fig04c": fig04c, "fig05": fig05, "fig05b": fig05b, "fig05c": fig05c, "fig06": fig06, "fig07": fig07,
           "fig08": fig08, "fig08c": fig08c, "fig09": fig09, "fig10": fig10, "fig10c": fig10c, "fig11": fig11, "fig12": fig12, "fig13": fig13, "fig14": fig14}

if __name__ == "__main__":
    for key in (sys.argv[1:] or list(FIGURES)):
        FIGURES[key]()
