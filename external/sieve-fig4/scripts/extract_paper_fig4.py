#!/usr/bin/env python3
"""Read the plotted values of the paper's Figure 4 straight from the PDF's vector drawing.

usage: extract_paper_fig4.py paper/nsdi24-sieve.pdf -o paper/fig4_paper_values.csv

Figure 4 is a vector graphic on page 7 (index 6), next to Figure 3. Each dot is one trace:
  Meta KV   orange circle    opacity 1.0 / 0.8 / 0.6 / 0.4 / 0.2   (5 traces)
  Meta CDN  red diamond      opacity 1.0 / 0.67 / 0.33             (3 traces)
  Tencent   blue triangle    opacity 1.0 / 0.5                     (2 traces)
  Wiki      green square     opacity 1.0 / 0.67 / 0.33             (3 traces)
The opacity says which trace of a dataset a dot belongs to (trace_idx 1 = most opaque), but not
which trace file it is; that is matched later from the values.
Per panel (a = left, b = right):
  * y axis: least-squares line through (tick value, y of its grey horizontal grid line); each
    grid line takes the value of the nearest tick label. (Calibrating on the labels' text
    centres instead puts every value 0.18 pt off, i.e. -0.0017 in (a) and -0.0008 in (b).)
    The residual is reported.
  * algorithm: the dot's x column, left to right in the paper's order
  * legend dots (not on an algorithm column) are skipped
The PDF stores the drawing unclipped, so dots the printed figure hides below the axis
("Some negative results are not shown") are still recovered; column beyond_axis marks them.
"""
import argparse
import re

import numpy as np
import pandas as pd
import pymupdf

ORDER = ["SIEVE", "ARC", "TinyLFU", "TwoQ", "LIRS", "LHD", "CACHEUS", "Hyperbolic", "CLOCK",
         "LRU", "B-LRU"]
DATASETS = {(1.0, 0.549, 0.0): ("metaKV", [1.0, 0.8, 0.6, 0.4, 0.2]),
            (0.863, 0.078, 0.235): ("metaCDN", [1.0, 0.67, 0.33]),
            (0.392, 0.584, 0.929): ("tencentPhoto", [1.0, 0.5]),
            (0.235, 0.702, 0.443): ("wiki", [1.0, 0.67, 0.33])}
# x ranges of the two panels on the page (Figure 3/5 elements lie outside them)
PANELS = {"a": (60, 175), "b": (178, 295)}
Y_RANGE = (330, 480)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    page = pymupdf.open(a.pdf)[6]

    dots = []
    for d in page.get_drawings():
        if d["type"] != "fs" or not d["fill"]:
            continue
        key = tuple(round(x, 3) for x in d["fill"])
        if key not in DATASETS:
            continue
        r = d["rect"]
        x, y = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
        if not Y_RANGE[0] < y < Y_RANGE[1]:
            continue
        ds, opac = DATASETS[key]
        op = d.get("fill_opacity") or 1.0
        idx = int(np.argmin([abs(op - o) for o in opac])) + 1
        dots.append((x, y, ds, idx))

    # grey horizontal grid lines of the two panels
    grid_y, grid_x0 = [], {}
    for d in page.get_drawings():
        if d["type"] == "s" and d.get("color") and all(abs(c - 0.69) < 0.01 for c in d["color"]):
            for it in d["items"]:
                if it[0] == "l" and abs(it[1].y - it[2].y) < 0.01 and Y_RANGE[0] < it[1].y < Y_RANGE[1]:
                    grid_y.append(it[1].y)
                    grid_x0[round(it[1].y, 3)] = min(it[1].x, it[2].x) + 1
    grid_y = [round(y, 3) for y in grid_y]

    labels = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                t = s["text"].strip().replace("−", "-")
                if re.fullmatch(r"-?\d+\.\d+", t):
                    x0, y0, x1, y1 = s["bbox"]
                    labels.append((float(t), x1, (y0 + y1) / 2))

    out = []
    for panel, (xlo, xhi) in PANELS.items():
        pd_ = [p for p in dots if xlo < p[0] < xhi]
        # algorithm columns: x positions shared by many dots (legend dots stand alone)
        xs = np.round([p[0] for p in pd_], 1)
        vals, counts = np.unique(xs, return_counts=True)
        cols = sorted(v for v, c in zip(vals, counts) if c >= 5)
        assert len(cols) == 11, (panel, cols)
        left = min(cols)
        cand = [(v, y) for v, x1, y in labels
                if left - 15 < x1 < left - 1 and Y_RANGE[0] < y < Y_RANGE[1]]
        grid = sorted({round(y, 3) for y in grid_y if xlo < grid_x0[y] < xhi})
        v = np.array([c[0] for c in cand])
        # each tick label -> the y of the nearest grid line
        yy = np.array([min(grid, key=lambda g: abs(g - c[1])) for c in cand])
        assert np.max(np.abs(yy - np.array([c[1] for c in cand]))) < 1.0, "grid/label mismatch"
        A = np.vstack([yy, np.ones_like(yy)]).T
        (m, k), *_ = np.linalg.lstsq(A, v, rcond=None)
        resid = float(np.max(np.abs(A @ np.array([m, k]) - v)))
        f = lambda y: m * y + k  # noqa: E731
        # visible axis bottom: the lowest tick minus the plot's margin is not stored as a
        # line, so flag dots below the lowest tick label's value minus half a tick step
        step = np.min(np.diff(np.sort(v)))
        for x, y, ds, idx in pd_:
            j = int(np.argmin([abs(x - c) for c in cols]))
            if abs(x - cols[j]) > 1.0:
                continue  # legend
            val = f(y)
            out.append(dict(panel=panel, size="large" if panel == "a" else "small",
                            dataset=ds, trace_idx=idx, algo=ORDER[j], reduction=round(val, 4),
                            beyond_axis=bool(val < v.min() - step / 2),
                            calib_max_resid=round(resid, 6), n_ticks=len(cand)))
    df = pd.DataFrame(out).sort_values(["panel", "dataset", "trace_idx", "algo"],
                                       key=lambda s: s.map({k: i for i, k in enumerate(ORDER)})
                                       if s.name == "algo" else s)
    df.to_csv(a.out, index=False)
    n = df.groupby(["panel", "dataset"]).size()
    print(n.to_string())
    print(df.pivot_table(index=["dataset", "trace_idx"], columns=["panel", "algo"],
                         values="reduction").reindex(columns=ORDER, level=1).round(3).to_string())


if __name__ == "__main__":
    main()
