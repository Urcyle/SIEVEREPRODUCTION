#!/usr/bin/env python3
"""Plot Figure 8 and compare it with the paper.

usage: fig8/plot_fig8.py   (after fig8/run.sh and fig8/extract_paper_fig8.py)

Plots seed 1 of results/fig8_raw.tsv in the paper's style: (a) miss ratio and (b) popular
object ratio (mean over the whole trace) over cache size. Writes
  fig8/fig8.png                 the replication
  fig8/fig8_side_by_side.png    paper (redrawn from its PDF values) | replication
  results/fig8_comparison.csv   every point: paper, seed 1, and the range over seeds 1-5
"""
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# the paper's colours, markers and line styles (from its PDF), legend order per panel
STYLE = {"LRU": ("#2ca02c", "s", "--"), "ARC": ("#000080", "o", "-"), "LFU": ("#6495ed", "v", "-."),
         "SIEVE": ("#ff8c00", "X", "-")}
ORDER = {"a": ["LRU", "ARC", "LFU", "SIEVE"], "b": ["SIEVE", "LFU", "ARC", "LRU"]}
YLABEL = {"a": "Miss Ratio", "b": "Popular Object Ratio"}
TITLE = {"a": "(a) Miss ratio", "b": "(b) Popular object ratio"}


def panel(ax, d, p, title):
    for algo in ORDER[p]:
        g = d[d.algo == algo].sort_values("pct")
        col, mk, ls = STYLE[algo]
        ax.plot(g.pct, g.value, color=col, marker=mk, linestyle=ls, markersize=5, label=algo)
    ax.set_xlabel("Cache Size (X% of Working Set)")
    ax.set_ylabel(YLABEL[p])
    ax.set_ylim(0, 0.9 if p == "a" else 1.05)
    ax.grid(alpha=0.5)
    ax.legend(fontsize=8, loc="upper right" if p == "a" else "lower right")
    ax.set_title(title, fontsize=9)


def main():
    r = pd.read_csv(ROOT / "results/fig8_raw.tsv", sep="\t")
    r["pct"] = r.cache_pct.round(1)
    long = pd.concat([r.assign(panel="a", value=r.miss_ratio), r.assign(panel="b", value=r.popular_mean)])
    paper = pd.read_csv(ROOT / "paper/fig8_paper_values.csv")
    paper["pct"] = paper.cache_pct.round(1)

    s1 = long[long.seed == 1]
    rng = long.groupby(["panel", "algo", "pct"]).value.agg(seeds_min="min", seeds_max="max").reset_index()
    cmp_ = (paper[["panel", "algo", "pct", "value"]].rename(columns={"value": "paper"})
            .merge(s1[["panel", "algo", "pct", "value"]].rename(columns={"value": "seed1"}), on=["panel", "algo", "pct"])
            .merge(rng, on=["panel", "algo", "pct"]))
    cmp_["diff_seed1"] = (cmp_.seed1 - cmp_.paper).round(4)
    cmp_["paper_in_seed_range"] = (cmp_.paper >= cmp_.seeds_min - 5e-5) & (cmp_.paper <= cmp_.seeds_max + 5e-5)
    cmp_["metric"] = cmp_.panel.map({"a": "miss_ratio", "b": "popular_ratio_mean"})
    cmp_ = cmp_.round(4).sort_values(["panel", "algo", "pct"])
    cmp_.to_csv(ROOT / "results/fig8_comparison.csv", index=False)

    out = ROOT / "fig8"
    fig, axes = plt.subplots(1, 2, figsize=(8, 3))
    for ax, p in zip(axes, "ab"):
        panel(ax, s1[s1.panel == p], p, TITLE[p] + " (replication)")
    fig.tight_layout()
    fig.savefig(out / "fig8.png", dpi=170)
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(8, 6))
    for col, p in enumerate("ab"):
        panel(axes[0, col], paper[paper.panel == p], p, TITLE[p] + ": paper (from its PDF)")
        panel(axes[1, col], s1[s1.panel == p], p, TITLE[p] + ": replication")
    fig.text(0.5, 0.005, "Replication: Zipf alpha = 1.0, 10,000 objects, 10 M requests, seed 1; "
             "popular object ratio = mean over the trace (sampled every 10,000 requests).",
             ha="center", fontsize=7, color="0.3")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(out / "fig8_side_by_side.png", dpi=170)
    plt.close(fig)

    for p in "ab":
        c = cmp_[cmp_.panel == p]
        print(f"panel {p}: mean |seed1 - paper| {c.diff_seed1.abs().mean():.4f}, max {c.diff_seed1.abs().max():.4f}, "
              f"paper inside 5-seed range {int(c.paper_in_seed_range.sum())}/{len(c)}")


if __name__ == "__main__":
    main()
