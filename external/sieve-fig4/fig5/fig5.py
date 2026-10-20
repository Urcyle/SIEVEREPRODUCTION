#!/usr/bin/env python3
"""Figure 5: the fraction of each dataset's traces on which each algorithm is the best.

usage: fig5/fig5.py   (from the repository root, after scripts/parse_logs.py and scripts/compare_fig4.py;
       writes fig5/ and results/fig5_*.csv)

Inputs
  results/fig4.csv                      Meta KV, Meta CDN, Tencent, Wiki (this repository)
  results/fig5_inputs/twitter_fig3.csv  Twitter clusters 1-24 (copy from sieve-fig3)
  paper/fig4_paper_values.csv           the paper's Figure 4 dots (for the paper's own per-trace best)
  paper/fig5_paper_values.csv           the paper's Figure 5 bars (fig5/extract_paper_fig5.py)
Best algorithm of a trace at a cache size = the largest miss ratio reduction from FIFO among the
11 algorithms (the same as the lowest miss ratio). Categories as in the paper: SIEVE, ARC, TwoQ,
LHD, Others (any other algorithm).
Ties: cachesim prints miss ratios with 4 decimals (also in its result files), so on some Twitter
traces several algorithms have the same miss ratio (none on the other four datasets). The figure
gives a tied trace to the first tied algorithm in the paper's plotting order (SIEVE, ARC,
TinyLFU, TwoQ, LIRS, LHD, CACHEUS, Hyperbolic, CLOCK, LRU, B-LRU), which is what a "first
maximum" in a plotting script does (the paper does not say). Ties are listed in
results/fig5_best.csv (column "tied").
Outputs
  results/fig5_best.csv        best algorithm per trace and size (ours, and the paper's own Figure
                               4 dots for the four public datasets)
  results/fig5_bars.csv        bar fractions: ours, from the paper's Figure 4 dots, and the paper's
                               Figure 5
  fig5/fig5.png, fig5/fig5_side_by_side.png
"""
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CATS = ["SIEVE", "ARC", "TwoQ", "LHD", "Others"]
ORDER = ["SIEVE", "ARC", "TinyLFU", "TwoQ", "LIRS", "LHD", "CACHEUS", "Hyperbolic", "CLOCK", "LRU",
         "B-LRU"]  # the paper's plotting order (x axis of Figures 3 and 4)
STYLE = {"SIEVE": ("#ff8c00", ""), "ARC": ("#fda861", "///"), "TwoQ": ("#fdd9b3", "\\\\\\"),
         "LHD": ("#fff5eb", "|||"), "Others": ("#dcdcdc", "xxx")}
ROWS = ["Wiki", "Tencent", "Meta (CDN)", "Meta (KV)", "CDN1", "CDN2", "Twitter"]  # top to bottom
DS = {"wiki": "Wiki", "tencentPhoto": "Tencent", "metaCDN": "Meta (CDN)", "metaKV": "Meta (KV)",
      "twitter": "Twitter"}


def cat(a):
    return a if a in CATS else "Others"


def best(df, value, higher=True):
    """one row per (dataset, trace, size): the best algorithm (ties: the first tied algorithm in
    ORDER; the others are listed in "tied") and its category"""
    rows = []
    for (ds, t, z), g in df.groupby(["dataset", "trace", "size"]):
        top = g[value].max() if higher else g[value].min()
        win = sorted(g[g[value] == top].algo, key=ORDER.index)
        share = {c: float(cat(win[0]) == c) for c in CATS}
        rows.append(dict(dataset=DS[ds], trace=t, size=z, best=win[0], tied=" ".join(win[1:]),
                         **share))
    return pd.DataFrame(rows)


def bars(b):
    out = b.groupby(["dataset", "size"])[CATS].mean()
    out["traces"] = b.groupby(["dataset", "size"]).size()
    return out.reset_index()


def draw(ax, frac, title):
    for i, ds in enumerate(ROWS):
        r = frac[frac.dataset == ds]
        if r.empty:
            ax.text(0.5, i, "not public", ha="center", va="center", fontsize=7, color="0.4")
            continue
        left = 0.0
        for c in CATS:
            v = float(r[c].iloc[0])
            col, h = STYLE[c]
            ax.barh(i, v, left=left, color=col, hatch=h, edgecolor="0.25", linewidth=0.3, height=0.8)
            left += v
    ax.set_yticks(range(len(ROWS)))
    ax.set_yticklabels(ROWS)
    ax.set_ylim(len(ROWS) - 0.5, -0.5)  # first row on top (set, not inverted: axes share y)
    ax.set_xlim(0, 1)
    ax.set_title(title, fontsize=9)


def main():
    f4 = pd.read_csv(ROOT / "results/fig4.csv")[["dataset", "trace", "size", "algo", "miss_ratio"]]
    tw = pd.read_csv(ROOT / "results/fig5_inputs/twitter_fig3.csv")
    tw = tw[tw.algo != "FIFO"].assign(dataset="twitter")[["dataset", "trace", "size", "algo", "miss_ratio"]]
    ours = pd.concat([f4, tw])
    b_ours = best(ours, "miss_ratio", higher=False).assign(source="replication")

    # the paper's own Figure 4 dots -> best per trace (public datasets only)
    p4 = pd.read_csv(ROOT / "paper/fig4_paper_values.csv")
    p4 = p4.assign(trace="dot" + p4.trace_idx.astype(str))[["dataset", "trace", "size", "algo", "reduction"]]
    b_p4 = best(p4, "reduction", higher=True).assign(source="paper Figure 4 dots")
    # name the paper's dots by our trace names (assignment from fig4/comparison.csv)
    m = pd.read_csv(ROOT / "fig4/comparison.csv")[["dataset", "trace", "trace_idx"]].drop_duplicates()
    name = {(DS[d], "dot" + str(i)): t for d, t, i in m.itertuples(index=False)}
    b_p4["trace"] = [name.get((d, t), t) for d, t in zip(b_p4.dataset, b_p4.trace)]
    allb = pd.concat([b_ours, b_p4])
    allb.to_csv(ROOT / "results/fig5_best.csv", index=False)

    p5 = pd.read_csv(ROOT / "paper/fig5_paper_values.csv")
    p5 = p5.assign(source="paper Figure 5", traces=pd.NA)[["dataset", "size"] + CATS + ["traces", "source"]]
    fr = pd.concat([bars(b_ours).assign(source="replication"),
                    bars(b_p4).assign(source="paper Figure 4 dots"), p5])
    fr[CATS] = fr[CATS].astype(float).round(4)
    fr.to_csv(ROOT / "results/fig5_bars.csv", index=False)

    out = ROOT / "fig5"
    out.mkdir(exist_ok=True)
    rep = fr[fr.source == "replication"]
    fig, axes = plt.subplots(1, 2, figsize=(8, 2.8), sharey=True)
    for ax, (z, p) in zip(axes, [("large", "a"), ("small", "b")]):
        draw(ax, rep[rep["size"] == z], f"({p}) {z.capitalize()} cache (replication)")
    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=STYLE[c][0], hatch=STYLE[c][1], edgecolor="0.25") for c in CATS]
    fig.legend(handles, CATS, ncol=5, loc="upper center", fontsize=8, frameon=False)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(out / "fig5.png", dpi=170)
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(8, 5.2), sharey=True)
    pp = fr[fr.source == "paper Figure 5"]
    for col, (z, p) in enumerate([("large", "a"), ("small", "b")]):
        draw(axes[0, col], pp[pp["size"] == z], f"({p}) {z} cache: paper (bars from its PDF)")
        draw(axes[1, col], rep[rep["size"] == z], f"({p}) {z} cache: this replication")
    fig.legend(handles, CATS, ncol=5, loc="upper center", fontsize=8, frameon=False)
    fig.text(0.5, 0.01, "Replication's Twitter bar: clusters 1-24 of the paper's 53, scaled down "
             "(Figure 3 runs); a tie goes to the first tied algorithm in the paper's order.",
             ha="center", fontsize=7, color="0.3")
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig.savefig(out / "fig5_side_by_side.png", dpi=170)
    plt.close(fig)

    show = fr.pivot_table(index=["size", "dataset"], columns="source", values="SIEVE")
    print("SIEVE fraction:\n" + show.round(3).to_string())
    t = allb[allb.tied != ""]
    print(f"\n{len(t)} tied (trace, size):\n" + t[["source", "dataset", "trace", "size", "best", "tied"]].to_string(index=False))


if __name__ == "__main__":
    main()
