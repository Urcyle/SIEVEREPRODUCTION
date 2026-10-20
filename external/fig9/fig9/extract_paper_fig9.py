#!/usr/bin/env python3
"""Read the plotted values of the paper's Figure 9 from the PDF's vector drawing.

usage: fig9/extract_paper_fig9.py external/fig8/paper/nsdi24-sieve.pdf -o paper/fig9_paper_values.csv

Figure 9 (page 11, index 10):
  (a) miss ratio and (b) popular object ratio over the Zipf skew alpha (0.2 ... 1.6) for LRU,
      LFU, ARC, SIEVE: one 8-point polyline per algorithm and panel. Axes are calibrated by a
      least-squares line through (tick value, its grey grid line); residual reported.
  (c) SIEVE's hand position from the tail over time for alpha 0.8, 1.0, 1.2: one long polyline
      per alpha, each in its own subplot whose y ticks are "0" and "1". Each subplot has its own x
      scale (tick labels 0-300000 for alpha 0.8 and 0-500000 for alpha 1.0; the alpha 1.2
      subplot shows none), so x is given as the fraction of the subplot's x range from the curve's
      first to its last point (x_frac), and in requests where ticks exist.
Output columns: panel, algo_or_alpha, x, value, and for (c) x_frac and requests.
"""
import argparse
import re

import numpy as np
import pandas as pd
import pymupdf

ALGO = {(1.0, 0.549, 0.0): "SIEVE", (0.392, 0.584, 0.929): "LFU", (0.0, 0.0, 0.502): "ARC",
        (0.173, 0.627, 0.173): "LRU"}
HAND = {(0.839, 0.153, 0.157): "0.8", (0.122, 0.467, 0.706): "1.0", (0.173, 0.627, 0.173): "1.2"}
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
    page = pymupdf.open(a.pdf)[10]
    cap = page.search_for("Figure 9:")[0]
    top = cap.y0 - 200
    curves, hands, vgrid, hgrid = [], [], [], []
    for d in page.get_drawings():
        r = d["rect"]
        if not (top < r.y0 and r.y1 < cap.y0):
            continue
        col = tuple(round(c, 3) for c in (d.get("color") or ()))
        if d["type"] != "s":
            continue
        pts = [d["items"][0][1]] + [it[2] for it in d["items"]]
        if col in ALGO and len(d["items"]) == 7 and r.x0 < 360:
            curves.append((ALGO[col], pts))
        elif col in HAND and len(d["items"]) > 100 and r.x0 > 360:
            hands.append((HAND[col], pts))
        elif col == GRID:
            for it in d["items"]:
                p, q = it[1], it[2]
                if abs(p.x - q.x) < 0.01:
                    vgrid.append(p.x)
                elif abs(p.y - q.y) < 0.01:
                    hgrid.append((p.y, min(p.x, q.x), max(p.x, q.x)))
    labels = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                x0, y0, x1, y1 = s["bbox"]
                if not top < y0 < cap.y0:
                    continue
                # numeric labels; a span holding several numbers ("100000 150000 ...") is skipped,
                # since the position of each number in it is not exact
                toks = s["text"].split()
                if len(toks) == 1 and re.fullmatch(r"\d+(\.\d+)?", toks[0]):
                    w = (x1 - x0) / len(s["text"])
                    pos = 0
                    for t in s["text"].split(" "):
                        if t:
                            labels.append((float(t), x0 + (pos + len(t) / 2) * w, (y0 + y1) / 2, x0 + pos * w,
                                           x0 + (pos + len(t)) * w, "." in t))
                        pos += len(t) + 1

    out = []
    # (a), (b): split the 8 curves by x into the two panels
    mx = sorted(np.mean([p.x for p in pts]) for _, pts in curves)
    split = (mx[3] + mx[4]) / 2
    for panel, side in (("a", lambda x: x < split), ("b", lambda x: x >= split)):
        cur = [(al, pts) for al, pts in curves if side(np.mean([p.x for p in pts]))]
        assert len(cur) == 4, (panel, len(cur))
        x_lo = min(p.x for _, pts in cur for p in pts) - 12
        x_hi = max(p.x for _, pts in cur for p in pts) + 12
        vg = sorted({round(x, 3) for x in vgrid if x_lo < x < x_hi})
        hg = sorted({round(y, 3) for y, gx0, gx1 in hgrid if gx0 < x_hi and gx1 > x_lo})
        y_bottom = max(hg)
        xl = [(v, cx) for v, cx, cy, lx0, lx1, dec in labels if cy > y_bottom and min(vg) - 5 < cx < max(vg) + 5]
        yl = [(v, cy) for v, cx, cy, lx0, lx1, dec in labels if min(vg) - 25 < lx1 < min(vg) and cy <= y_bottom + 4]
        fx, rx = fit([(v, min(vg, key=lambda g: abs(g - cx))) for v, cx in xl])
        fy, ry = fit([(v, min(hg, key=lambda g: abs(g - cy))) for v, cy in yl])
        for al, pts in cur:
            for p in pts:
                out.append(dict(panel=panel, series=al, x=round(fx(p.x), 3), value=round(fy(p.y), 4),
                                calib_resid=round(max(rx, ry), 6)))
    # (c): y from each subplot's "0" and "1" labels; x as fraction, and requests from ticks
    ticks_x = {"0.8": [], "1.0": []}
    for al, pts in sorted(hands, key=lambda h: np.mean([p.y for p in h[1]])):
        ys = [p.y for p in pts]
        y_lo, y_hi = min(ys) - 5, max(ys) + 5
        yl = [(v, cy) for v, cx, cy, lx0, lx1, dec in labels
              if v in (0.0, 1.0) and 355 < lx0 and lx1 < 368 and y_lo < cy < y_hi]
        fy, ry = fit(yl)
        x = np.array([p.x for p in pts])
        frac = (x - x.min()) / (x.max() - x.min())
        # x tick labels of this subplot: just below its bottom frame
        xt = [(v, cx) for v, cx, cy, *_ in labels if cx > 370 and y_hi - 4 < cy < y_hi + 6 and v >= 0]
        req = None
        if len(xt) >= 2:
            fx, rx = fit(xt)
            req = fx(x)
        for i, p in enumerate(pts):
            out.append(dict(panel="c", series=al, x=round(frac[i], 5), value=round(fy(p.y), 4),
                            requests=round(float(req[i])) if req is not None else np.nan, calib_resid=round(ry, 6)))
    df = pd.DataFrame(out)
    df.to_csv(a.out, index=False)
    ab = df[df.panel != "c"]
    print(ab.pivot_table(index=["panel", "x"], columns="series", values="value").to_string())
    c = df[df.panel == "c"]
    for al, g in c.groupby("series"):
        v = g.value.to_numpy()
        wr = np.flatnonzero(v[1:] < v[:-1] - 0.5) + 1
        print(f"(c) alpha {al}: {len(g)} points, last requests {g.requests.iloc[-1]}, wraps at x_frac {g.x.iloc[wr].round(3).tolist()}")
    print("max calibration residual", df.calib_resid.max())


if __name__ == "__main__":
    main()
