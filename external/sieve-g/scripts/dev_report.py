#!/usr/bin/env python3
"""Phase 3: check the development runs against the Figure 3 logs, tabulate them, and apply the
plan's rule for freezing the ghost ratio.

usage: dev_report.py   (after scripts/parse_logs.py results/dev/*.log --dataset dev -o results/dev.csv)

1. Check: FIFO and SIEVE in results/dev.csv must equal the Figure 3 replication to 4 decimals
   (external/sieve-fig3/results/twitter.csv; cluster 49 from its results/validation/
   cluster49.s10.log). Exits with an error otherwise.
2. Table (results/dev_table.md): per cluster and size, the miss ratio and the reduction from FIFO
   of FIFO, SIEVE and each SIEVE-G ratio.
3. Rule: among the ratios that are not worse than SIEVE (miss ratio) on any dev cluster at the
   10% cache, the one with the highest mean reduction vs FIFO at the 0.1% cache; ties -> the
   smaller ratio. Printed, and written to results/dev_choice.txt.
   "Worse" is the plan's own definition from its pass rule: a miss ratio higher than SIEVE's by
   more than 0.0001 (the resolution of cachesim's 4-decimal output). With strictly "higher", no
   ratio qualified (all are 0.0001-0.0003 above SIEVE on cluster 1 at 10%); see
   PREREGISTRATION.md.
"""
import re
import sys
from pathlib import Path

import pandas as pd

G = Path(__file__).resolve().parent.parent
F3 = G.parent / "sieve-fig3"
LINE = re.compile(r"^result/\S+\s+(\S+) cache size\s+(\d+), (\d+) req, miss ratio ([0-9.]+)")

dev = pd.read_csv(G / "results/dev.csv")
dev["cluster"] = dev.trace.str.extract(r"(cluster\d+)")[0]

# 1. check against the Figure 3 logs
orig = pd.read_csv(F3 / "results/twitter.csv")
orig = orig[orig.algo.isin(["FIFO", "SIEVE"])][["trace", "size", "algo", "miss_ratio"]].rename(columns={"trace": "cluster"})
rows = []
for line in open(F3 / "results/validation/cluster49.s10.log"):
    m = LINE.match(re.sub(r"\x1b\[[0-9;]*m", "", line))
    if m and m.group(1) in ("FIFO", "Sieve"):
        rows.append((m.group(1), int(m.group(2)), float(m.group(4))))
cs = sorted({r[1] for r in rows})
orig = pd.concat([orig, pd.DataFrame([dict(cluster="cluster49", size="small" if c == cs[0] else "large",
                                           algo="SIEVE" if a == "Sieve" else "FIFO", miss_ratio=mr)
                                      for a, c, mr in rows])])
chk = dev[dev.algo.isin(["FIFO", "SIEVE"])].merge(orig, on=["cluster", "size", "algo"], suffixes=("", "_fig3"))
chk["same"] = (chk.miss_ratio - chk.miss_ratio_fig3).abs() < 1e-9
print(chk[["cluster", "size", "algo", "miss_ratio", "miss_ratio_fig3", "same"]].to_string(index=False))
n_expected = dev.cluster.nunique() * 2 * 2
if len(chk) != n_expected or not chk.same.all():
    sys.exit(f"CHECK FAILED: {int(chk.same.sum())} of {n_expected} FIFO/SIEVE values equal the Figure 3 logs")
print(f"check: all {n_expected} FIFO/SIEVE miss ratios equal the Figure 3 logs\n")

# 2. table
ratios = sorted(a for a in dev.algo.unique() if a.startswith("SIEVE-G"))
algos = ["FIFO", "SIEVE"] + ratios
order = ["cluster8", "cluster1", "cluster12", "cluster13", "cluster23", "cluster49"]
lines = ["| cluster | cache | " + " | ".join(algos) + " |", "|---|---|" + "---|" * len(algos)]
for c in order:
    for z in ("small", "large"):
        g = dev[(dev.cluster == c) & (dev["size"] == z)].set_index("algo")
        if g.empty:
            continue
        cells = [f"{g.miss_ratio[a]:.4f} ({g.reduction[a]:+.3f})" for a in algos]
        lines.append(f"| {c} | {'0.1%' if z == 'small' else '10%'} ({int(g.cache_size_obj.iloc[0]):,}) | " + " | ".join(cells) + " |")
table = "\n".join(lines)
(G / "results/dev_table.md").write_text(
    "# Development set: miss ratio (reduction from FIFO)\n\n" + table + "\n")
print(table)

# 3. the rule
out = []
for a in ratios:
    big = dev[dev["size"] == "large"].pivot_table(index="cluster", columns="algo", values="miss_ratio")
    worse = (big[a] - big["SIEVE"] > 0.0001 + 1e-9)  # the plan's "worse by > 0.0001"
    small = dev[(dev["size"] == "small") & (dev.algo == a)]
    strictly = (big[a] > big["SIEVE"] + 1e-12)
    out.append(dict(algo=a, ratio=float(a.split()[1]), worse_than_sieve_at_10pct=int(worse.sum()),
                    strictly_higher_at_10pct=int(strictly.sum()),
                    clusters_worse=" ".join(big.index[worse]), mean_reduction_small=small.reduction.mean()))
o = pd.DataFrame(out)
sieve_small = dev[(dev["size"] == "small") & (dev.algo == "SIEVE")].reduction.mean()
print(f"\nSIEVE mean reduction at 0.1%: {sieve_small:.4f}")
print(o.to_string(index=False))
ok = o[o.worse_than_sieve_at_10pct == 0]
if ok.empty:
    choice = "none: every ratio is worse than SIEVE on some dev cluster at the 10% cache"
else:
    best = ok.mean_reduction_small.max()
    pick = ok[(ok.mean_reduction_small - best).abs() < 1e-12].sort_values("ratio").iloc[0]
    choice = f"{pick.ratio:.2f}"
print("\nfrozen ghost ratio:", choice)
(G / "results/dev_choice.txt").write_text(o.to_string(index=False) + f"\n\nSIEVE mean reduction at 0.1%: {sieve_small:.4f}\nfrozen ghost ratio: {choice}\n")
