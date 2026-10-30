#!/usr/bin/env python3
"""Phase 5: parse the held-out and Figure 4 runs, apply the pre-registered verdict, draw the
figures.

usage: scripts/analyze.py   (from external/sieve-g, after the queues of manifests/heldout.tsv
                            and manifests/fig4check.tsv)

Writes
  results/heldout.csv, results/fig4_check.csv   parsed runs (scripts/parse_logs.py)
  results/verdict.md                            the pre-registered verdict (PREREGISTRATION.md),
                                                both cache sizes, primary (29 clusters, without
                                                cluster 49) and secondary (all 30)
  results/fig4_check.md                         every Figure 4 trace: SIEVE vs Figure 4, SIEVE-G
  figures/fig_dev_failures.png                  dev clusters, FIFO / SIEVE / SIEVE-G at 0.1%
  figures/fig_heldout_box.png                   reduction from FIFO, SIEVE vs SIEVE-G, clusters
                                                25-54 (primary set), both sizes (Figure 3 style)
  figures/fig_heldout_scatter.png               per cluster: SIEVE vs SIEVE-G miss ratio
  figures/fig4_check.png                        per Figure 4 trace: SIEVE-G - SIEVE miss ratio
"""
import subprocess
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

G = Path(__file__).resolve().parent.parent
RATIO = "0.25"                       # frozen (PREREGISTRATION.md)
SG = f"SIEVE-G {RATIO}"
EQ = 0.0001                          # "worse/better by > 0.0001 in miss ratio"
FILL = {"large": "#FFA500", "small": "#ADD8E6"}   # Figure 3 style
SIZE = {"small": "0.1%", "large": "10%"}
PY = sys.executable


def parse(logs, dataset, out):
    logs = sorted(str(p) for p in logs)
    if not logs:
        return None
    subprocess.run([PY, "-I", str(G / "scripts/parse_logs.py"), *logs, "--dataset", dataset, "-o", str(out)],
                   check=True)
    return pd.read_csv(out)


def wide(df):
    w = df.pivot_table(index=["trace", "size"], columns="algo", values="miss_ratio").reset_index()
    w["diff"] = w[SG] - w["SIEVE"]                                  # > 0: SIEVE-G worse
    w["rel"] = [(s - g) / (s if g <= s else g) if not (s == 0 and g == 0) else 0.0
                for s, g in zip(w["SIEVE"], w[SG])]                 # relative reduction vs SIEVE
    w["outcome"] = np.where(w["diff"] > EQ + 1e-9, "worse", np.where(w["diff"] < -EQ - 1e-9, "better", "equal"))
    return w


def verdict(w, label):
    rows = []
    for z in ("small", "large"):
        g = w[w["size"] == z]
        n = len(g)
        worse = int((g.outcome == "worse").sum())
        ok_mean, ok_med, ok_worse = g.rel.mean() > 0, g.rel.median() >= 0, worse <= 0.25 * n
        rows.append({"set": label, "cache": SIZE[z], "clusters": n,
                     "mean rel. reduction": f"{g.rel.mean():+.4f}", "median": f"{g.rel.median():+.4f}",
                     "better": int((g.outcome == "better").sum()), "equal": int((g.outcome == "equal").sum()),
                     "worse": worse, "worse share": f"{worse / n:.0%}",
                     "mean > 0": "yes" if ok_mean else "no", "median ≥ 0": "yes" if ok_med else "no",
                     "worse ≤ 25%": "yes" if ok_worse else "no",
                     "verdict": "PASS" if ok_mean and ok_med and ok_worse else "FAIL"})
    return rows


def md(df):
    cols = list(df.columns)
    return "\n".join(["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] +
                     ["| " + " | ".join(str(v) for v in r) + " |" for r in df.itertuples(index=False)])


def box(ax, df, size, algos):
    st = []
    for a in algos:
        v = df[(df.algo == a) & (df["size"] == size)].reduction.to_numpy()
        p10, p25, p50, p75, p90 = np.percentile(v, [10, 25, 50, 75, 90])
        st.append(dict(label=a, whislo=p10, q1=p25, med=p50, q3=p75, whishi=p90, mean=v.mean(), fliers=[]))
    ax.bxp(st, showmeans=True, showfliers=False, patch_artist=True, widths=0.6,
           boxprops=dict(facecolor=FILL[size], edgecolor="#333333", linewidth=0.8),
           medianprops=dict(color="#333333", linewidth=0.8), whiskerprops=dict(color="#333333", linewidth=0.8),
           capprops=dict(color="#333333", linewidth=0.8),
           meanprops=dict(marker="v", markerfacecolor="#2E7D32", markeredgecolor="#C62828", markersize=6))
    ax.axhline(0, color="#999999", linewidth=0.6)
    ax.grid(axis="y", color="#DDDDDD", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=8)
    ax.set_ylabel("Miss Ratio Reduction\nfrom FIFO", fontsize=9)
    return st


def main():
    (G / "figures").mkdir(exist_ok=True)
    out = []

    # development set (the frozen ratio only)
    dev = pd.read_csv(G / "results/dev.csv")
    dev["cluster"] = dev.trace.str.extract(r"(cluster\d+)")[0]
    order = ["cluster8", "cluster1", "cluster12", "cluster13", "cluster23", "cluster49"]
    d = dev[(dev["size"] == "small") & dev.algo.isin(["FIFO", "SIEVE", SG])]
    fig, ax = plt.subplots(figsize=(6.4, 3), dpi=200)
    x = np.arange(len(order))
    for i, (a, col) in enumerate([("FIFO", "#9E9E9E"), ("SIEVE", "#FFA500"), (SG, "#1565C0")]):
        v = [d[(d.cluster == c) & (d.algo == a)].miss_ratio.iloc[0] for c in order]
        ax.bar(x + (i - 1) * 0.27, v, 0.27, color=col, edgecolor="#333333", linewidth=0.5, label=a)
    ax.set_xticks(x)
    ax.set_xticklabels([c.replace("cluster", "cluster ") for c in order], fontsize=8)
    ax.set_ylabel("Miss ratio (0.1% cache)", fontsize=9)
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=7, ncol=3, loc="upper right")
    ax.grid(axis="y", color="#DDDDDD", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_title("Development set: the clusters where SIEVE lost to FIFO (Figure 3)", fontsize=9)
    fig.tight_layout()
    fig.savefig(G / "figures/fig_dev_failures.png")
    plt.close(fig)

    # held-out
    ho = parse((G / "results/heldout").glob("*.log"), "twitter-heldout", G / "results/heldout.csv")
    if ho is not None:
        ho["cluster"] = ho.trace.str.extract(r"(cluster\d+)")[0]
        w = wide(ho)
        w["cluster"] = w.trace.str.extract(r"(cluster\d+)")[0]
        prim = w[w.cluster != "cluster49"]
        v = pd.DataFrame(verdict(prim, "primary: 25-54 without 49") + verdict(w, "secondary: all of 25-54"))
        per = w.sort_values(["size", "cluster"], key=lambda s: s.str.extract(r"(\d+)")[0].astype(float)
                            if s.name == "cluster" else s)[["cluster", "size", "FIFO", "SIEVE", SG, "diff", "rel", "outcome"]]
        per["diff"] = per["diff"].round(4)
        per["rel"] = per["rel"].round(4)
        text = ["# Held-out verdict (pre-registered, PREREGISTRATION.md)", "",
                f"SIEVE-G with the frozen ghost ratio {RATIO}, Twitter clusters 25-54, "
                f"{ho.cluster.nunique()} of 30 run. Relative reduction of SIEVE-G over SIEVE; "
                f"better / equal / worse by more than {EQ} in miss ratio.", "", md(v), "",
                "## Per cluster (miss ratio)", "", md(per)]
        (G / "results/verdict.md").write_text("\n".join(text) + "\n")
        print(md(v))

        p = ho[ho.cluster != "cluster49"]
        fig, axes = plt.subplots(1, 2, figsize=(6.4, 3.2), dpi=200, sharey=False)
        for ax, z in zip(axes, ("large", "small")):
            box(ax, p, z, ["SIEVE", SG])
            ax.set_title(f"{z} cache ({SIZE[z]}), {p.cluster.nunique()} clusters", fontsize=9)
        fig.suptitle("Held-out Twitter clusters 25-54 (without 49)", fontsize=9)
        fig.tight_layout()
        fig.savefig(G / "figures/fig_heldout_box.png")
        plt.close(fig)

        fig, axes = plt.subplots(1, 2, figsize=(6.4, 3.3), dpi=200)
        for ax, z in zip(axes, ("large", "small")):
            g = w[w["size"] == z]
            col = g.outcome.map({"better": "#1565C0", "equal": "#9E9E9E", "worse": "#C62828"})
            ax.scatter(g["SIEVE"], g[SG], c=col, s=16, edgecolor="#333333", linewidth=0.3, zorder=3)
            lim = [0, max(g["SIEVE"].max(), g[SG].max()) * 1.05]
            ax.plot(lim, lim, color="#666666", linewidth=0.7, zorder=2)
            ax.set_xlim(lim)
            ax.set_ylim(lim)
            ax.set_xlabel("SIEVE miss ratio", fontsize=8)
            ax.set_ylabel(f"{SG} miss ratio", fontsize=8)
            ax.tick_params(labelsize=7)
            ax.grid(color="#EEEEEE", linewidth=0.6)
            n = g.outcome.value_counts()
            ax.set_title(f"{SIZE[z]} cache: {n.get('better', 0)} better, {n.get('equal', 0)} equal, "
                         f"{n.get('worse', 0)} worse", fontsize=8)
        fig.suptitle("Held-out clusters 25-54: below the line = SIEVE-G better", fontsize=9)
        fig.tight_layout()
        fig.savefig(G / "figures/fig_heldout_scatter.png")
        plt.close(fig)

    # Figure 4 check
    f4 = parse((G / "results/fig4check").glob("*.log"), "fig4", G / "results/fig4_check.csv")
    if f4 is not None:
        ref = pd.read_csv(G.parent / "sieve-fig4/results/fig4.csv")
        ref = ref[ref.algo == "SIEVE"][["trace", "size", "cache_size", "miss_ratio"]].rename(
            columns={"miss_ratio": "sieve_fig4", "cache_size": "cache_fig4"})
        w = wide(f4).merge(ref, on=["trace", "size"], how="left")
        cs = f4[f4.algo == "SIEVE"][["trace", "size", "cache_size_obj"]]
        w = w.merge(cs, on=["trace", "size"])
        w["sieve_equals_fig4"] = (w["SIEVE"] - w["sieve_fig4"]).abs() < 1e-9
        w["flag_loss_gt_0.005"] = w["diff"] > 0.005
        t = w[["trace", "size", "cache_size_obj", "cache_fig4", "SIEVE", "sieve_fig4", "sieve_equals_fig4",
               SG, "diff", "flag_loss_gt_0.005"]].copy()
        t["diff"] = t["diff"].round(4)
        (G / "results/fig4_check.md").write_text(
            "# Figure 4 check: SIEVE-G vs SIEVE on the 13 Figure 4 traces\n\n"
            "diff = SIEVE-G − SIEVE miss ratio (> 0: SIEVE-G worse); flagged if > 0.005.\n\n" + md(t) + "\n")
        print(md(t))
        fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.4), dpi=200, sharey=True)
        for ax, z in zip(axes, ("large", "small")):
            g = w[w["size"] == z].sort_values("trace")
            col = np.where(g["diff"] > 0, "#C62828", "#1565C0")
            ax.barh(g.trace, g["diff"], color=col, edgecolor="#333333", linewidth=0.4)
            ax.axvline(0, color="#333333", linewidth=0.6)
            for lim in (-0.005, 0.005):
                ax.axvline(lim, color="#999999", linewidth=0.6, linestyle="--")
            ax.set_title(f"{SIZE[z]} cache", fontsize=9)
            ax.set_xlabel(f"{SG} − SIEVE miss ratio", fontsize=8)
            ax.tick_params(labelsize=7)
            ax.grid(axis="x", color="#EEEEEE", linewidth=0.6)
        fig.suptitle("Figure 4 traces: right of 0 = SIEVE-G worse (dashed: ±0.005)", fontsize=9)
        fig.tight_layout()
        fig.savefig(G / "figures/fig4_check.png")
        plt.close(fig)


if __name__ == "__main__":
    main()
