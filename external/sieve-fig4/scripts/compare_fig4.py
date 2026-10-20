#!/usr/bin/env python3
"""Compare this replication's Figure 4 with the paper's, and draw both.

usage: compare_fig4.py results/fig4.csv paper/fig4_paper_values.csv -o fig4

Matching traces to the paper's dots: the paper shows each trace of a dataset only by opacity
(trace_idx), not by name. Within each dataset, every assignment of our traces to the paper's
trace_idx values is tried, and the one with the smallest total |difference| over all 22 values
(11 algorithms x 2 sizes) is used. Datasets where not all traces are finished yet are matched
on the finished ones.

Writes:
  <out>/comparison.csv     one row per (panel, trace, algorithm): paper vs replication
  <out>/sieve_ranks.csv    per panel and trace: SIEVE's rank among the 11 algorithms, both
  <out>/fig4a.png, fig4b.png             the replication in the paper's style
  <out>/fig4_side_by_side.png            paper (redrawn from its PDF values) | replication
and prints a summary.
"""
import argparse
import itertools
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ORDER = ["SIEVE", "ARC", "TinyLFU", "TwoQ", "LIRS", "LHD", "CACHEUS", "Hyperbolic", "CLOCK",
         "LRU", "B-LRU"]
STYLE = {  # paper's colours, markers and per-trace opacities (from the PDF)
    "metaKV": ("Meta (KV)", "#ff8c00", "o", [1.0, 0.8, 0.6, 0.4, 0.2]),
    "metaCDN": ("Meta (CDN)", "#dc143c", "D", [1.0, 0.67, 0.33]),
    "tencentPhoto": ("Tencent", "#6495ed", ">", [1.0, 0.5]),
    "wiki": ("Wiki", "#3cb371", "s", [1.0, 0.67, 0.33]),
}
PANEL = {"large": "a", "small": "b"}


def match(ours, paper):
    rows = []
    for ds, g in ours.groupby("dataset"):
        p = paper[paper.dataset == ds]
        traces = sorted(g.trace.unique())
        idxs = sorted(p.trace_idx.unique())
        best = None
        for perm in itertools.permutations(idxs, len(traces)):
            cost = 0.0
            for t, i in zip(traces, perm):
                a = g[g.trace == t].set_index(["size", "algo"]).reduction
                b = p[p.trace_idx == i].set_index(["size", "algo"]).reduction
                cost += (a - b.reindex(a.index)).abs().sum()
            if best is None or cost < best[0]:
                best = (cost, perm)
        rows += [dict(dataset=ds, trace=t, trace_idx=i) for t, i in zip(traces, best[1])]
    return pd.DataFrame(rows)


def ranks(df, key):
    out = []
    for k, g in df.groupby(key + ["size"]):
        r = g.set_index("algo").reduction.rank(ascending=False, method="min")
        out.append(dict(zip(key + ["size"], k), sieve_rank=int(r["SIEVE"]),
                        best=g.loc[g.reduction.idxmax(), "algo"]))
    return pd.DataFrame(out)


def draw(ax, df, title):
    for ds, (label, color, marker, alphas) in STYLE.items():
        g = df[df.dataset == ds]
        for i, alpha in enumerate(alphas, start=1):
            gi = g[g.trace_idx == i].set_index("algo").reindex(ORDER)
            ax.scatter(range(len(ORDER)), gi.reduction, color=color, marker=marker, s=28,
                       alpha=alpha, label=label if i == 1 else None, zorder=3)
    ax.set_xticks(range(len(ORDER)))
    ax.set_xticklabels(ORDER, rotation=45, ha="right")
    ax.set_ylabel("Miss Ratio Reduction from FIFO")
    ax.grid(alpha=0.4, zorder=0)
    ax.set_title(title, fontsize=10)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ours")
    ap.add_argument("paper")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    ours = pd.read_csv(a.ours)
    paper = pd.read_csv(a.paper)

    m = match(ours, paper)
    ours = ours.merge(m, on=["dataset", "trace"])
    cmp_ = ours.merge(paper[["size", "dataset", "trace_idx", "algo", "reduction"]],
                      on=["size", "dataset", "trace_idx", "algo"], suffixes=("", "_paper"))
    cmp_["panel"] = cmp_["size"].map(PANEL)
    cmp_["diff"] = (cmp_.reduction - cmp_.reduction_paper).round(4)
    cmp_ = cmp_[["panel", "dataset", "trace", "trace_idx", "algo", "miss_ratio",
                 "reduction", "reduction_paper", "diff"]]
    cmp_.to_csv(out / "comparison.csv", index=False)

    key = ["dataset", "trace", "trace_idx"]
    ro = ranks(ours, key)
    rp = ranks(paper.merge(m, on=["dataset", "trace_idx"]), key)
    rk = ro.merge(rp, on=key + ["size"], suffixes=("", "_paper"))
    rk.insert(0, "panel", rk.pop("size").map(PANEL))
    rk = rk.sort_values(["panel", "dataset", "trace_idx"])
    rk.to_csv(out / "sieve_ranks.csv", index=False)

    for size, panel in PANEL.items():
        fig, ax = plt.subplots(figsize=(4.2, 3.2))
        draw(ax, ours[ours["size"] == size], f"({panel}) {size.capitalize()} cache (replication)")
        ax.legend(fontsize=7, ncol=2, loc="upper right")
        fig.tight_layout()
        fig.savefig(out / f"fig4{panel}.png", dpi=160)
        plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(9, 7), sharey="row")
    pm = paper.copy()
    for r, (size, panel) in enumerate(PANEL.items()):
        draw(axes[r, 0], pm[pm["size"] == size], f"({panel}) {size} cache: paper (values from its PDF)")
        draw(axes[r, 1], ours[ours["size"] == size], f"({panel}) {size} cache: this replication")
    axes[0, 0].legend(fontsize=7, ncol=2, loc="upper right")
    fig.tight_layout()
    fig.savefig(out / "fig4_side_by_side.png", dpi=160)
    plt.close(fig)

    print("trace matching:\n" + m.to_string(index=False))
    print("\nSIEVE rank per trace (1 = best of 11):\n" + rk.to_string(index=False))
    d = cmp_.groupby(["panel", "dataset"])["diff"].agg(lambda s: s.abs().mean()).round(4)
    print("\nmean |reduction - paper|:\n" + d.to_string())
    s = cmp_[cmp_.algo == "SIEVE"]
    print("\nSIEVE values:\n" + s[["panel", "dataset", "trace", "reduction", "reduction_paper",
                                    "diff"]].to_string(index=False))


if __name__ == "__main__":
    main()
