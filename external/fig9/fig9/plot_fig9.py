#!/usr/bin/env python3
"""Plot Figure 9 and compare it with the paper.

usage: fig9/plot_fig9.py   (after fig9/run.sh and fig9/extract_paper_fig9.py)

Writes
  fig9/fig9.png                 the replication (seed 1), three panels like the paper
  fig9/fig9_side_by_side.png    paper (redrawn from its PDF values) above, replication below
  results/fig9_comparison.csv   (a), (b): every point, paper vs seed 1 and the range over seeds 1-5
(b) is the popular object ratio averaged over the trace, as for Figure 8. In (c) each subplot has
its own x range, as in the paper (the curves end after 2^18 evictions); the paper's (c) curves are
drawn over their own x range in requests where the paper gives ticks (alpha 0.8, 1.0) and, for
alpha 1.2, over this replication's range for seed 1.
"""
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STYLE = {"LRU": ("#2ca02c", "s", "--"), "ARC": ("#000080", "o", "-"), "LFU": ("#6495ed", "v", "-."),
         "SIEVE": ("#ff8c00", "X", "-")}
ORDER = {"a": ["LRU", "ARC", "LFU", "SIEVE"], "b": ["SIEVE", "LFU", "ARC", "LRU"]}
HAND = {"0.8": "#d62728", "1.0": "#1f77b4", "1.2": "#2ca02c"}


def ab(ax, d, p, title):
    for algo in ORDER[p]:
        g = d[d.series == algo].sort_values("x")
        col, mk, ls = STYLE[algo]
        ax.plot(g.x, g.value, color=col, marker=mk, linestyle=ls, markersize=4, label=algo)
    ax.set_xticks([0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6])
    ax.set_xlabel("Zipf Parameter (skewness α)")
    ax.set_ylabel("Miss Ratio" if p == "a" else "Popular Object Ratio")
    ax.grid(alpha=0.5)
    ax.legend(fontsize=7, loc="upper right" if p == "a" else "lower right")
    ax.set_title(title, fontsize=8)


def hand(fig, spec, curves, title):
    sub = spec.subgridspec(3, 1, hspace=0.45)  # each subplot shows its own x range
    axes = []
    for i, a in enumerate(["0.8", "1.0", "1.2"]):
        ax = fig.add_subplot(sub[i])
        g = curves[curves.alpha == a]
        ax.plot(g.x, g.position, color=HAND[a], linewidth=1.2, label=f"Zipf {a}")
        ax.set_ylim(-0.1, 1.15)
        ax.set_yticks([0, 1])
        ax.set_xlim(0, g.x.max() * 1.03)
        ax.tick_params(axis="x", labelsize=6)
        ax.ticklabel_format(axis="x", style="plain")
        axes.append(ax)
    axes[0].set_title(title, fontsize=8)
    axes[1].set_ylabel("Hand Position from Tail")
    axes[2].set_xlabel("Logical Time (#requests)")
    h = [plt.Line2D([], [], color=HAND[a], label=f"Zipf {a}") for a in HAND]
    axes[0].legend(handles=h, ncol=3, fontsize=6, loc="lower right")


def main():
    r = pd.read_csv(ROOT / "results/fig9ab_raw.tsv", sep="\t")
    long = pd.concat([r.assign(panel="a", value=r.miss_ratio), r.assign(panel="b", value=r.popular_mean)])
    long = long.rename(columns={"algo": "series", "alpha": "x"})
    paper = pd.read_csv(ROOT / "paper/fig9_paper_values.csv")
    pab = paper[paper.panel != "c"].copy()
    pab["x"] = pab.x.round(1)
    s1 = long[long.seed == 1]
    rng = long.groupby(["panel", "series", "x"]).value.agg(seeds_min="min", seeds_max="max").reset_index()
    cmp_ = (pab[["panel", "series", "x", "value"]].rename(columns={"value": "paper"})
            .merge(s1[["panel", "series", "x", "value"]].rename(columns={"value": "seed1"}), on=["panel", "series", "x"])
            .merge(rng, on=["panel", "series", "x"]))
    cmp_["diff_seed1"] = cmp_.seed1 - cmp_.paper
    cmp_["paper_in_seed_range"] = (cmp_.paper >= cmp_.seeds_min - 5e-5) & (cmp_.paper <= cmp_.seeds_max + 5e-5)
    cmp_ = cmp_.rename(columns={"series": "algo", "x": "alpha"}).round(4).sort_values(["panel", "algo", "alpha"])
    cmp_.to_csv(ROOT / "results/fig9_comparison.csv", index=False)

    ours_c = pd.read_csv(ROOT / "results/fig9c_hand_s1.tsv", sep="\t", dtype={"alpha": str})
    ours_c = ours_c.rename(columns={"request": "x"})
    pc = paper[paper.panel == "c"].rename(columns={"series": "alpha", "value": "position"}).copy()
    pc["alpha"] = pc.alpha.map(lambda v: f"{float(v):.1f}")
    end12 = ours_c[ours_c.alpha == "1.2"].x.max()
    pc["x"] = pc.requests.where(pc.alpha != "1.2", pc.x * end12)

    out = ROOT / "fig9"
    fig = plt.figure(figsize=(11, 3))
    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 1.6])
    ab(fig.add_subplot(gs[0]), s1[s1.panel == "a"], "a", "(a) Miss ratio")
    ab(fig.add_subplot(gs[1]), s1[s1.panel == "b"], "b", "(b) Popular object ratio")
    hand(fig, gs[2], ours_c, "(c) Hand movement in SIEVE")
    fig.tight_layout()
    fig.savefig(out / "fig9.png", dpi=170)
    plt.close(fig)

    fig = plt.figure(figsize=(11, 6.2))
    gs = fig.add_gridspec(2, 3, width_ratios=[1, 1, 1.6], hspace=0.45)
    ab(fig.add_subplot(gs[0, 0]), pab[pab.panel == "a"], "a", "(a) Miss ratio: paper")
    ab(fig.add_subplot(gs[0, 1]), pab[pab.panel == "b"], "b", "(b) Popular object ratio: paper")
    hand(fig, gs[0, 2], pc, "(c) Hand movement: paper (alpha 1.2 x range: replication's)")
    ab(fig.add_subplot(gs[1, 0]), s1[s1.panel == "a"], "a", "(a) Miss ratio: replication")
    ab(fig.add_subplot(gs[1, 1]), s1[s1.panel == "b"], "b", "(b) Popular object ratio: replication")
    hand(fig, gs[1, 2], ours_c, "(c) Hand movement: replication")
    fig.text(0.5, 0.005, "Replication, seed 1. (a), (b): 10,000 objects, 10 M requests, cache 10% (1,000 objects). "
             "(c): 1,000,000 objects, cache 0.1% (1,000 objects), 2^18 evictions.", ha="center", fontsize=7, color="0.3")
    fig.savefig(out / "fig9_side_by_side.png", dpi=170, bbox_inches="tight")
    plt.close(fig)

    for p in "ab":
        c = cmp_[cmp_.panel == p]
        print(f"panel {p}: mean |seed1 - paper| {c.diff_seed1.abs().mean():.4f}, max {c.diff_seed1.abs().max():.4f}, "
              f"paper inside 5-seed range {int(c.paper_in_seed_range.sum())}/{len(c)}")


if __name__ == "__main__":
    main()
