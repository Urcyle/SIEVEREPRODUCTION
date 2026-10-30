#!/usr/bin/env python3
"""Trace for gate G2: every object is requested exactly twice, the second request exactly <gap>
requests after the first.

usage: gen_twice.py --gap <g> -n <requests> -o <trace.oracleGeneral>

The trace is a sequence of blocks of 2*gap requests: gap new objects, then the same gap objects
again in the same order. So each object's second request comes exactly gap requests after its
first, no object appears in two blocks, and half of all requests are second requests. n must be a
multiple of 2*gap. Written as oracleGeneral records (time = request index, size 1, next access
-2), like the artifact's generator.
"""
import argparse

import numpy as np

REC = np.dtype([("t", "<u4"), ("id", "<u8"), ("sz", "<u4"), ("next", "<i8")])

ap = argparse.ArgumentParser()
ap.add_argument("--gap", type=int, required=True)
ap.add_argument("-n", type=int, required=True)
ap.add_argument("-o", "--out", required=True)
a = ap.parse_args()
assert a.n % (2 * a.gap) == 0, "n must be a multiple of 2*gap"

blocks = a.n // (2 * a.gap)
first = np.arange(blocks * a.gap, dtype=np.uint64).reshape(blocks, a.gap)
ids = np.concatenate([first, first], axis=1).reshape(-1)  # block: g new ids, then the same g
rec = np.empty(a.n, REC)
rec["t"] = np.arange(a.n, dtype=np.uint32)
rec["id"] = ids + 1  # ids from 1
rec["sz"] = 1
rec["next"] = -2
rec.tofile(a.out)

# check the property
pos = {}
for i, o in enumerate(rec["id"][: 4 * a.gap].tolist()):
    pos.setdefault(o, []).append(i)
assert all(len(p) == 2 and p[1] - p[0] == a.gap for p in pos.values())
print(f"{a.out}: {a.n:,} requests, {a.n // 2:,} objects, each requested twice, gap {a.gap}")
