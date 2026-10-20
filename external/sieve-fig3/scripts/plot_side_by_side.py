#!/usr/bin/env python3
"""Paper vs replication, side by side, for Figure 3c (large cache) and 3f (small cache).

usage: plot_side_by_side.py -o fig3cf_side_by_side.png

Left column: the paper's boxes, redrawn from paper/fig3_paper_values.csv (read from the PDF).
Right column: ours, from results/raw/twitter/*.log. Each row shares one y axis, so heights
can be compared directly. Also prints the rank of every algorithm by mean in both.
"""
import argparse
import glob
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from make_figures import draw  # noqa: E402
from parse_logs import parse  # noqa: E402
from plot_fig3 import ORDER, stats  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    paper = pd.read_csv("paper/fig3_paper_values.csv")
    ours = pd.DataFrame([r for p in glob.glob("results/raw/twitter/*.log") for r in parse(p)])
    n = ours.trace.nunique()

    fig, axes = plt.subplots(2, 2, figsize=(10, 7.4), dpi=200)
    for row, (pn, size, label) in enumerate((("c", "large", "large cache (10%)"),
                                             ("f", "small", "small cache (0.1%)"))):
        p = paper[paper.panel == pn].set_index("algo").reindex(ORDER).reset_index()
        o = stats(ours[ours["size"] == size])
        draw(axes[row][0], p, size, f"Paper Fig. 3{pn}: Twitter, {label}, 54 traces")
        draw(axes[row][1], o, size, f"Ours: Twitter, {label}, {n} traces")
        lo = min(p.p10.min(), o.p10.min())
        hi = max(p.p90.max(), o.p90.max())
        pad = 0.05 * (hi - lo)
        for ax in axes[row]:
            ax.set_ylim(lo - pad, hi + pad)
            ax.axhline(0, color="#999999", linewidth=0.6, zorder=0)

        rp = p.set_index("algo")["mean"].rank(ascending=False).astype(int)
        ro = o.set_index("algo")["mean"].rank(ascending=False).astype(int)
        print(f"\nFig. 3{pn} ({label}) rank by mean: paper vs ours")
        for algo in ORDER:
            print(f"  {algo:10s} {rp[algo]:2d} {ro[algo]:2d}")
    fig.tight_layout()
    fig.savefig(a.out)


if __name__ == "__main__":
    main()
