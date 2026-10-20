#!/usr/bin/env python3
"""Read the plotted values of the paper's Figure 3 straight from the PDF's vector drawings.

usage: extract_paper_fig3.py paper/nsdi24-sieve.pdf -o paper/fig3_paper_values.csv

Figure 3 is a vector graphic on page 7 (index 6). Each panel has 11 filled boxes (orange =
large cache, light blue = small cache) and 11 mean markers (green triangles with a red edge).
Medians and whiskers are black lines. Per panel:
  * y axis calibration: a least-squares line through (tick label text, label y-centre) for
    the numeric labels just left of the panel; the residual is reported
  * box top/bottom -> P75/P25; black horizontal line inside the box -> median
  * black vertical line above/below the box at its centre -> whisker end (P90/P10)
  * triangle bounding-box centre -> mean
Boxes are matched to algorithms by left-to-right order (paper order).
Panels are numbered a-f by position: top row a b c, bottom row d e f.
The PDF stores the drawing unclipped, so values the printed figure hides past the axis edge are
still recovered; the column beyond_axis names them. A whisker with no line (zero length)
equals its box edge.
"""
import argparse
import re

import numpy as np
import pandas as pd
import pymupdf

ORDER = ["SIEVE", "ARC", "TinyLFU", "TwoQ", "LIRS", "LHD", "CACHEUS", "Hyperbolic", "CLOCK",
         "LRU", "B-LRU"]
ORANGE, BLUE = (1.0, 0.65, 0.0), (0.68, 0.85, 0.9)
MEAN_FILL = (0.0, 0.5, 0.0)


def near(c, ref, tol=0.02):
    return c is not None and len(c) == 3 and all(abs(a - b) < tol for a, b in zip(c, ref))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    page = pymupdf.open(a.pdf)[6]
    dr = page.get_drawings()

    boxes = [d["rect"] for d in dr if d["type"] == "f" and
             (near(d["fill"], ORANGE) or near(d["fill"], BLUE)) and len(d["items"]) == 4]
    fills = {id(d["rect"]): ("large" if near(d["fill"], ORANGE) else "small")
             for d in dr if d["type"] == "f" and len(d["items"]) == 4 and
             (near(d["fill"], ORANGE) or near(d["fill"], BLUE))}
    means = [d["rect"] for d in dr if d["type"] == "fs" and near(d["fill"], MEAN_FILL)]
    blk = []  # black line segments
    for d in dr:
        if d["type"] == "s" and near(d.get("color"), (0, 0, 0)):
            for it in d["items"]:
                if it[0] == "l":
                    blk.append((it[1].x, it[1].y, it[2].x, it[2].y))
    blk = np.array(blk)

    # numeric text spans (tick labels)
    labels = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                t = s["text"].strip().replace("−", "-")
                if re.fullmatch(r"-?\d+\.\d+", t):
                    x0, y0, x1, y1 = s["bbox"]
                    labels.append((float(t), x1, (y0 + y1) / 2))

    # group boxes into panels: by row (y) then column (x)
    bx = sorted(boxes, key=lambda r: r.x0)
    cy = np.array([(r.y0 + r.y1) / 2 for r in boxes])
    split_y = (cy.min() + cy.max()) / 2
    out = []
    for row_i, row in enumerate([[r for r in bx if (r.y0 + r.y1) / 2 < split_y],
                                 [r for r in bx if (r.y0 + r.y1) / 2 >= split_y]]):
        # columns: gaps between consecutive boxes much larger than the box spacing
        xs = [r.x0 for r in row]
        gaps = np.diff(xs)
        cuts = np.argsort(gaps)[-2:]
        groups, start = [], 0
        for c in sorted(cuts):
            groups.append(row[start:c + 1])
            start = c + 1
        groups.append(row[start:])
        for col_i, g in enumerate(groups):
            panel = "abcdef"[row_i * 3 + col_i]
            assert len(g) == 11, (panel, len(g))
            # axes frame: the long horizontal black spines spanning all 11 boxes
            span = (g[0].x0, g[-1].x1)
            hs = blk[(np.abs(blk[:, 1] - blk[:, 3]) < 0.01) &
                     (np.minimum(blk[:, 0], blk[:, 2]) <= span[0]) &
                     (np.maximum(blk[:, 0], blk[:, 2]) >= span[1])]
            mid = np.median([(r.y0 + r.y1) / 2 for r in g])
            top = hs[hs[:, 1] < mid, 1].max()
            bot = hs[hs[:, 1] > mid, 1].min()
            left = np.minimum(hs[:, 0], hs[:, 2]).max()
            # tick labels: right edge just left of the y axis, vertically inside the frame
            cand = [(v, y) for v, x1, y in labels if left - 25 < x1 < left and top - 3 < y < bot + 3]
            vals = np.array([v for v, _ in cand])
            yy = np.array([y for _, y in cand])
            A = np.vstack([yy, np.ones_like(yy)]).T
            (m, k), res, *_ = np.linalg.lstsq(A, vals, rcond=None)
            resid = float(np.max(np.abs(A @ np.array([m, k]) - vals)))
            f = lambda y: m * y + k  # noqa: E731
            size = fills[id(g[0])]
            for algo, r in zip(ORDER, g):
                xc = (r.x0 + r.x1) / 2
                # median: horizontal black line spanning the box
                hm = blk[(np.abs(blk[:, 1] - blk[:, 3]) < 0.01) &
                         (np.minimum(blk[:, 0], blk[:, 2]) >= r.x0 - 0.5) &
                         (np.maximum(blk[:, 0], blk[:, 2]) <= r.x1 + 0.5) &
                         (np.abs(blk[:, 2] - blk[:, 0]) > 0.8 * (r.x1 - r.x0)) &
                         (blk[:, 1] >= r.y0 - 0.3) & (blk[:, 1] <= r.y1 + 0.3)]
                med = f(hm[0, 1]) if len(hm) else np.nan
                # Whiskers attach to the box edge: the upper one ends at the box top (r.y0), the
                # lower one starts at the box bottom (r.y1). PDF y grows downward. The drawing is
                # not clipped in the file, so values past the axis edge are still recoverable.
                vall = blk[(np.abs(blk[:, 0] - blk[:, 2]) < 0.01) & (np.abs(blk[:, 0] - xc) < 0.3)]
                hi_end = np.maximum(vall[:, 1], vall[:, 3])
                lo_end = np.minimum(vall[:, 1], vall[:, 3])
                up = vall[np.abs(hi_end - r.y0) < 0.5]
                lo = vall[np.abs(lo_end - r.y1) < 0.5]
                p90 = f(np.minimum(up[:, 1], up[:, 3]).min()) if len(up) else f(r.y0)
                p10 = f(np.maximum(lo[:, 1], lo[:, 3]).max()) if len(lo) else f(r.y1)
                # mean marker: same column, nearest to the box
                mk = [mr for mr in means if r.x0 <= (mr.x0 + mr.x1) / 2 <= r.x1]
                ymid = (r.y0 + r.y1) / 2
                mk.sort(key=lambda mr: abs((mr.y0 + mr.y1) / 2 - ymid))
                mean = f((mk[0].y0 + mk[0].y1) / 2) if mk else np.nan
                # values drawn outside the visible axis range (hidden in the printed figure)
                vals = dict(p10=p10, p25=f(r.y1), median=med, p75=f(r.y0), p90=p90, mean=mean)
                lo_lim, hi_lim = f(bot), f(top)
                clipped = [k for k, v in vals.items() if not np.isnan(v) and not lo_lim <= v <= hi_lim]
                out.append(dict(panel=panel, size=size, algo=algo, **vals,
                                axis_min=f(bot), axis_max=f(top),
                                beyond_axis=" ".join(clipped), calib_max_resid=resid,
                                n_ticks=len(cand)))
    df = pd.DataFrame(out).round(4)
    df.to_csv(a.out, index=False)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
