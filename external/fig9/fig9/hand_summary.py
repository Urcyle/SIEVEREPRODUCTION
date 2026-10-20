#!/usr/bin/env python3
"""Condense the hand logs of fig9/sieve_hand (one line per eviction) for Figure 9c.

usage: fig9/hand_summary.py data/hand results

Writes
  results/fig9c_hand_s1.tsv    seed 1, per alpha: every 256th eviction plus the points just before
                               and at each wrap (the hand going back to the tail), for plotting
  results/fig9c_summary.tsv    per seed and alpha: requests until the 262,144th eviction, misses,
                               number of wraps and their times, and when the hand first passes 0.9
A wrap is a drop of the position by more than 0.5 from one eviction to the next.
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

src, out = Path(sys.argv[1]), Path(sys.argv[2])
rows, curves = [], []
for f in sorted(src.glob("hand_a*_s*.txt")):
    alpha, seed = re.match(r"hand_a([\d.]+)_s(\d+)\.txt", f.name).groups()
    text = f.read_text()
    m = re.search(r"# misses (\d+) evictions (\d+) requests (\d+)", text)
    d = np.loadtxt(f, comments="#")
    t, p = d[:, 0].astype(np.int64), d[:, 1]
    wr = np.flatnonzero(p[1:] < p[:-1] - 0.5) + 1
    above = np.flatnonzero(p > 0.9)
    rows.append(dict(seed=int(seed), alpha=alpha, requests=int(m.group(3)), misses=int(m.group(1)),
                     evictions=int(m.group(2)), n_wraps=len(wr),
                     wraps_at_requests=" ".join(map(str, t[wr])),
                     first_above_0_9=int(t[above[0]]) if len(above) else -1))
    if seed == "1":
        keep = np.zeros(len(t), bool)
        keep[::256] = True
        keep[-1] = keep[0] = True
        keep[wr] = keep[wr - 1] = True
        curves.append(pd.DataFrame(dict(alpha=alpha, request=t[keep], position=p[keep].round(4))))
pd.DataFrame(rows).sort_values(["alpha", "seed"]).to_csv(out / "fig9c_summary.tsv", sep="\t", index=False)
pd.concat(curves).to_csv(out / "fig9c_hand_s1.tsv", sep="\t", index=False)
print(pd.DataFrame(rows).sort_values(["alpha", "seed"]).drop(columns="wraps_at_requests").to_string(index=False))
