#!/usr/bin/env python3
"""Draw Figure 3 panels: miss ratio reduction from FIFO, one box per algorithm.

usage: plot_fig3.py <dataset.csv> --size large|small --title "..." -o fig.png [--stats out.csv]

Style follows the paper's Figure 3: the box spans P25-P75, whiskers reach P10 and P90, the
line is the median, the triangle is the mean, and no outliers are drawn. Large cache boxes are
orange and small cache boxes are light blue. Algorithms appear in the paper's order.
--stats writes the plotted numbers (P10, P25, median, P75, P90, mean, n) per algorithm.
"""
import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ORDER = ["SIEVE", "ARC", "TinyLFU", "TwoQ", "LIRS", "LHD", "CACHEUS", "Hyperbolic", "CLOCK",
         "LRU", "B-LRU"]
FILL = {"large": "#FFA500", "small": "#ADD8E6"}


def stats(df):
    out = []
    for algo in ORDER:
        v = df.loc[df.algo == algo, "reduction"].to_numpy()
        p10, p25, p50, p75, p90 = np.percentile(v, [10, 25, 50, 75, 90])
        out.append(dict(algo=algo, n=len(v), p10=p10, p25=p25, median=p50, p75=p75, p90=p90,
                        mean=v.mean()))
    return pd.DataFrame(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--size", choices=["large", "small"], required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--stats")
    a = ap.parse_args()

    df = pd.read_csv(a.csv)
    df = df[df["size"] == a.size]
    st = stats(df)
    if a.stats:
        st.round(4).to_csv(a.stats, index=False)

    fig, ax = plt.subplots(figsize=(4.2, 3.2), dpi=200)
    bxp = [dict(label=r.algo, whislo=r.p10, q1=r.p25, med=r.median, q3=r.p75, whishi=r.p90,
                mean=r.mean, fliers=[]) for r in st.itertuples()]
    ax.bxp(bxp, showmeans=True, showfliers=False, patch_artist=True, widths=0.6,
           boxprops=dict(facecolor=FILL[a.size], edgecolor="#333333", linewidth=0.8),
           medianprops=dict(color="#333333", linewidth=0.8),
           whiskerprops=dict(color="#333333", linewidth=0.8),
           capprops=dict(color="#333333", linewidth=0.8),
           meanprops=dict(marker="v", markerfacecolor="#2E7D32", markeredgecolor="#C62828",
                          markersize=6))
    ax.set_ylabel("Miss Ratio Reduction\nfrom FIFO", fontsize=9)
    ax.set_xticklabels(ORDER, rotation=45, ha="right", fontsize=8)
    ax.tick_params(axis="y", labelsize=8)
    ax.grid(axis="y", color="#DDDDDD", linewidth=0.6)
    ax.grid(axis="x", color="#EEEEEE", linewidth=0.6)
    ax.set_axisbelow(True)
    n = int(st.n.iloc[0])
    ax.set_title(f"{a.title}, {a.size} cache, {n} traces", fontsize=9)
    fig.tight_layout()
    fig.savefig(a.out)


if __name__ == "__main__":
    main()
