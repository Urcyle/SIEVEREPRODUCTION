#!/usr/bin/env python3
"""Read the bar values of the paper's Figure 5 from the PDF's vector drawing.

usage: fig5/extract_paper_fig5.py paper/nsdi24-sieve.pdf -o paper/fig5_paper_values.csv

Figure 5 (page 7, index 6, right of Figure 4) has two panels, (a) large and (b) small cache,
each with 7 horizontal stacked bars (datasets), segments SIEVE, ARC, TwoQ, LHD, Others = the
fraction of the dataset's traces on which that algorithm is the best.
  * SIEVE segments are plain filled rectangles (dark orange).
  * The hatched segments (ARC, TwoQ, LHD, Others) are pattern tiles clipped to the segment, so
    their extent is the clip rectangle. Clips come in stacking order: per panel 7 ARC clips
    (one per bar), then 7 TwoQ, 7 LHD, 7 Others. Zero-width clips are segments of width 0.
  * x scale: a bar starts at the axis origin (x of value 0) and the bars that are full end at
    the x of value 1.0; both are taken from the bars (min start, max end) and checked against
    the "0.0" and "1.0" tick labels.
  * Rows are named by the dataset label at the same y.
"""
import argparse

import numpy as np
import pandas as pd
import pymupdf

SIEVE_FILL = (1.0, 0.549, 0.0)
CATS = ["SIEVE", "ARC", "TwoQ", "LHD", "Others"]
PANELS = {"a": (300, 440), "b": (440, 600)}
Y_RANGE = (374, 430)  # the bars (legend above, axis labels below)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    page = pymupdf.open(a.pdf)[6]
    sieve, clips = [], []
    for d in page.get_drawings(extended=True):
        if d["type"] == "clip":
            r = d.get("scissor")
            if r is not None and Y_RANGE[0] < r.y0 < Y_RANGE[1] and r.y1 - r.y0 < 8 and r.x0 > 300:
                clips.append(r)
        elif d["type"] == "f" and d["fill"] and tuple(round(c, 3) for c in d["fill"]) == SIEVE_FILL:
            r = d["rect"]
            if r.x0 > 300 and Y_RANGE[0] < r.y0 < Y_RANGE[1] and r.y1 - r.y0 > 5:
                sieve.append(r)
    labels = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                t = s["text"].strip()
                x0, y0, x1, y1 = s["bbox"]
                if x0 > 300 and Y_RANGE[0] < y0 < Y_RANGE[1]:
                    labels.append((t, x0, x1, (y0 + y1) / 2))

    out = []
    for panel, (xlo, xhi) in PANELS.items():
        sv = sorted([r for r in sieve if xlo < r.x0 < xhi], key=lambda r: r.y0)
        cl = [r for r in clips if xlo < r.x0 <= xhi + 1]
        assert len(sv) == 7 and len(cl) == 28, (panel, len(sv), len(cl))
        x0 = min(r.x0 for r in sv)
        x1 = max(max(r.x1 for r in sv), max(r.x1 for r in cl))
        ticks = {t: (lx0 + lx1) / 2 for t, lx0, lx1, _ in
                 [(t, lx0, lx1, y) for t, lx0, lx1, y in labels if xlo < lx0 < xhi]
                 if t in ("0.0", "1.0")}
        w = x1 - x0
        rows = sorted(sv, key=lambda r: r.y0)
        for i, rs in enumerate(rows):
            yc = (rs.y0 + rs.y1) / 2
            name = min((l for l in labels if xlo - 40 < l[2] < x0 and l[0] not in ("0.0", "1.0")),
                       key=lambda l: abs(l[3] - yc))[0]
            vals = {"SIEVE": (rs.x1 - rs.x0) / w}
            # clips of this row, in drawing order -> ARC, TwoQ, LHD, Others
            row_clips = [r for r in cl if abs((r.y0 + r.y1) / 2 - yc) < 1]
            assert len(row_clips) == 4, (panel, name, len(row_clips))
            for cat, r in zip(CATS[1:], row_clips):
                vals[cat] = (r.x1 - r.x0) / w
            total = sum(vals.values())
            out.append(dict(panel=panel, size="large" if panel == "a" else "small", dataset=name,
                            **{c: round(v, 4) for c, v in vals.items()}, total=round(total, 4),
                            x_origin=round(x0, 2), x_one=round(x1, 2),
                            tick_0=round(ticks.get("0.0", np.nan), 2), tick_1=round(ticks.get("1.0", np.nan), 2)))
    df = pd.DataFrame(out)
    df.to_csv(a.out, index=False)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
