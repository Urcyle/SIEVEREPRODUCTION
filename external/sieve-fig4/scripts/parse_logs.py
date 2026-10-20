#!/usr/bin/env python3
"""Collect the miss ratios of all finished traces into one table.

usage: parse_logs.py results/raw -o results/fig4.csv

Each run directory results/raw/<dataset>/<run>/ holds the pass logs of scripts/run_trace.sh.
<run> is the trace name, plus a suffix such as ".s10" for a run on a 10% spatial sample (-s 0.1).
A (run, size) is complete when all 12 algorithms have a result at that size; only complete ones
are written. For each (trace, size) the whole-trace run is used if complete, else the sampled
run; for Tencent Photo the 10% sample is preferred (the paper's Tencent values are the sample's).
Output, one row per (trace, size, algorithm):
  dataset, trace, run, sample_ratio, size (small/large), cache_size, requests, algo,
  miss_ratio, fifo_miss_ratio, reduction
Rows of incomplete runs (e.g. whole-trace validation runs of a few algorithms) go to
<out>.partial.csv.
reduction = (mr_FIFO - mr) / mr_FIFO, or (mr_FIFO - mr) / mr when the algorithm is worse than
FIFO, so it stays in [-1, 1] (as for Figure 3).
"""
import argparse
import re
from pathlib import Path

import pandas as pd

NAMES = {"FIFO": "FIFO", "LRU": "LRU", "Clock": "CLOCK", "ARC": "ARC", "TwoQ": "TwoQ",
         "LIRS": "LIRS", "LHD": "LHD", "Cacheus": "CACHEUS", "Hyperbolic": "Hyperbolic",
         "WTinyLFU-w0.01-SLRU": "TinyLFU", "Sieve": "SIEVE"}
# Result lines: "result/<trace> <algo> cache size <n>, <r> req, miss ratio <m>, ..." when cachesim
# runs several caches; "<trace path> <algo> cache size 5MiB, <r> req, miss ratio <m>, ..." (size
# rounded) when it runs one cache, which also prints INFO progress lines (not matched: they
# start with an escape code). For a one-cache log the size is taken from the header's args.
LINE = re.compile(r"^(?:result/|/)\S*\s+(\S+) cache size\s+(\S+),\s+(\d+) req, miss ratio ([\d.]+)")


def parse_run(d):
    rows = []
    for log in sorted(d.glob("*.log")):
        text = re.sub(r"\x1b\[[0-9;]*m", "", log.read_text())  # cachesim's colour codes
        m = re.search(r"# sample_ratio (\S+)", text)
        ratio = float(m.group(1)) if m else 1.0
        m = re.search(r"# sizes (\S+)", text)
        sizes = m.group(1) if m else "both"
        res = [LINE.match(x).groups() for x in text.splitlines() if LINE.match(x)]
        if len(res) == 1 and not res[0][1].isdigit():
            size_arg = re.search(r"# cachesim \S+ args: \S+ (\S+)", text).group(1)
            if "." in size_arg:  # a fraction (sampled run): of the footprint cachesim logged
                wss = int(re.search(r"working set size: (\d+) object", text).group(1))
                size_arg = str(int(wss * float(size_arg)))
            res = [(res[0][0], size_arg, res[0][2], res[0][3])]
        # size label: from the pass; B-LRU with both sizes: the smaller cache is "small"
        if log.stem == "small":
            label = {cs: "small" for _, cs, _, _ in res}
        elif log.stem.startswith("large"):
            label = {cs: "large" for _, cs, _, _ in res}
        elif sizes in ("small", "large"):
            label = {cs: sizes for _, cs, _, _ in res}
        else:
            cs_sorted = sorted({int(cs) for _, cs, _, _ in res})
            label = {str(c): lab for c, lab in zip(cs_sorted, ["small", "large"])}
        for name, cs, req, mr in res:
            algo = "B-LRU" if log.stem == "blru" else NAMES[name]
            rows.append(dict(dataset=d.parent.name, trace=d.name.split(".")[0], run=d.name,
                             sample_ratio=ratio, size=label[cs], cache_size=int(cs),
                             requests=int(req), algo=algo, miss_ratio=float(mr)))
    return rows


def reduction(df):
    fifo = df[df.algo == "FIFO"].set_index(["run", "size"]).miss_ratio
    df = df[df.set_index(["run", "size"]).index.isin(fifo.index)].copy()
    df["fifo_miss_ratio"] = [fifo[(r, s)] for r, s in zip(df.run, df["size"])]
    worse = df.miss_ratio > df.fifo_miss_ratio
    df["reduction"] = (df.fifo_miss_ratio - df.miss_ratio) / df.fifo_miss_ratio
    df.loc[worse, "reduction"] = (df.fifo_miss_ratio - df.miss_ratio)[worse] / df.miss_ratio[worse]
    return df[df.algo != "FIFO"].round({"reduction": 4})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    rows = []
    for d in sorted(p for p in Path(a.raw).glob("*/*") if p.is_dir()):
        rows += parse_run(d)
    df = pd.DataFrame(rows)
    assert not df.duplicated(["run", "size", "algo"]).any()
    n = df.groupby(["run", "size"]).algo.transform("nunique")
    full, part = df[n == 12], df[n < 12]
    # per (trace, size): whole-trace run if complete, else the sampled one; except Tencent, where
    # the 10% sample is preferred for both sizes: the paper's Tencent values are those of the 10%
    # sample (fig4/README.md), and the whole-trace runs are kept as a check
    pref = full.sample_ratio.where(full.dataset != "tencentPhoto", -full.sample_ratio)
    full = full.assign(_pref=pref).sort_values("_pref", ascending=False).drop(columns="_pref")
    keep = full.groupby(["trace", "size"]).run.transform("first")
    full = reduction(full[full.run == keep])
    full.to_csv(a.out, index=False)
    reduction(part).to_csv(a.out.replace(".csv", ".partial.csv"), index=False)
    print(f"{full.trace.nunique()} traces, {len(full)} rows -> {a.out}")
    print(full.groupby(["dataset", "size"]).run.unique().to_string())


if __name__ == "__main__":
    main()
