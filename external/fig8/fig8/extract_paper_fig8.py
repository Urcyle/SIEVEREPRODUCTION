#!/usr/bin/env python3
"""Read the plotted points of the paper's Figure 8 from the PDF's vector drawing.

usage: fig8/extract_paper_fig8.py paper/nsdi24-sieve.pdf -o paper/fig8_paper_values.csv

Figure 8 (page 10, index 9) has two panels: (a) miss ratio and (b) popular object ratio over
cache size (% of the working set), for LRU, LFU, ARC and SIEVE on a Zipfian (alpha = 1) trace.
Each curve is one polyline of 8 points in the algorithm's colour (the legend has a short
2-point line per algorithm, which is skipped). Both axes are calibrated per panel by a
least-squares line through (tick value, position of its grey grid line); each grid line takes the
value of the nearest tick label (x ticks: whole numbers below the panel; y ticks: decimals left of
it). The residual is reported.
"""
import argparse
import re

import numpy as np
import pandas as pd
import pymupdf

COLORS = {(1.0, 0.549, 0.0): "SIEVE", (0.392, 0.584, 0.929): "LFU", (0.0, 0.0, 0.502): "ARC",
          (0.173, 0.627, 0.173): "LRU"}
GRID = (0.69, 0.69, 0.69)


def fit(pairs):
    v = np.array([p[0] for p in pairs])
    pos = np.array([p[1] for p in pairs])
    A = np.vstack([pos, np.ones_like(pos)]).T
    (m, k), *_ = np.linalg.lstsq(A, v, rcond=None)
    return (lambda x: m * x + k), float(np.max(np.abs(A @ np.array([m, k]) - v)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    page = pymupdf.open(a.pdf)[9]
    cap = page.search_for("Figure 8:")[0]
    top = cap.y0 - 200
    lines, vgrid, hgrid = [], [], []
    for d in page.get_drawings():
        r = d["rect"]
        if not (top < r.y0 and r.y1 < cap.y0):
            continue
        col = tuple(round(c, 3) for c in (d.get("color") or ()))
        if d["type"] == "s" and col in COLORS and len(d["items"]) == 7:
            pts = [d["items"][0][1]] + [it[2] for it in d["items"]]
            lines.append((COLORS[col], pts))
        if d["type"] == "s" and col == GRID:
            for it in d["items"]:
                p, q = it[1], it[2]
                if abs(p.x - q.x) < 0.01:
                    vgrid.append((p.x, min(p.y, q.y), max(p.y, q.y)))
                elif abs(p.y - q.y) < 0.01:
                    hgrid.append((p.y, min(p.x, q.x), max(p.x, q.x)))
    labels = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                t = s["text"].strip()
                x0, y0, x1, y1 = s["bbox"]
                if re.fullmatch(r"\d+(\.\d+)?", t) and top < y0 < cap.y0:
                    labels.append((float(t), (x0 + x1) / 2, (y0 + y1) / 2, x0, x1, "." in t))

    # panels: split the curves by x (panel a is left)
    xs = sorted(np.mean([p.x for p in pts]) for _, pts in lines)
    split = (xs[len(xs) // 2 - 1] + xs[len(xs) // 2]) / 2
    out = []
    for panel, side in (("a", lambda x: x < split), ("b", lambda x: x >= split)):
        cur = [(alg, pts) for alg, pts in lines if side(np.mean([p.x for p in pts]))]
        assert len(cur) == 4, (panel, len(cur))
        x_lo = min(p.x for _, pts in cur for p in pts) - 15
        x_hi = max(p.x for _, pts in cur for p in pts) + 15
        vg = sorted({round(x, 3) for x, *_ in vgrid if x_lo < x < x_hi})
        hg = sorted({round(y, 3) for y, x0, x1 in hgrid if x0 < x_hi and x1 > x_lo})
        # x tick labels: below the plot; y tick labels: left of it
        y_bottom = max(hg)
        # x ticks are whole numbers below the plot, under this panel's vertical grid lines;
        # y ticks have a decimal point and end just left of this panel's first grid line
        xl = [(v, cx) for v, cx, cy, lx0, lx1, dec in labels
              if not dec and cy > y_bottom and min(vg) - 5 < cx < max(vg) + 5]
        yl = [(v, cy) for v, cx, cy, lx0, lx1, dec in labels
              if dec and min(vg) - 20 < lx1 < min(vg) and cy <= y_bottom + 4]
        fx, rx = fit([(v, min(vg, key=lambda g: abs(g - cx))) for v, cx in xl])
        fy, ry = fit([(v, min(hg, key=lambda g: abs(g - cy))) for v, cy in yl])
        for alg, pts in cur:
            for i, p in enumerate(pts):
                out.append(dict(panel=panel, metric="miss_ratio" if panel == "a" else "popular_ratio",
                                algo=alg, point=i, cache_pct=round(fx(p.x), 3), value=round(fy(p.y), 4),
                                calib_resid_x=round(rx, 6), calib_resid_y=round(ry, 6)))
    df = pd.DataFrame(out).sort_values(["panel", "algo", "point"])
    df.to_csv(a.out, index=False)
    print(df.pivot_table(index=["panel", "point"], columns="algo", values="value").to_string())
    print("cache % per point:", sorted(df.cache_pct.round(2).unique()))
    print("max residual x/y:", df.calib_resid_x.max(), df.calib_resid_y.max())


if __name__ == "__main__":
    main()
