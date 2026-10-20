#!/usr/bin/env python3
"""Generate a Zipfian trace with the authors' generator, reproducibly.

usage: fig8/gen_trace.py -m <objects> -n <requests> --alpha 1.0 --seed 1 -o data/zipf_....oracleGeneral

Uses gen_zipf() of the artifact's libCacheSim/scripts/data_gen.py unchanged (inverse-CDF sampling
of a Zipf distribution over m objects) and writes the same binary format as its --bin-output:
oracleGeneral records (uint32 time, uint64 obj_id, uint32 size 4000, int64 next access -2),
time spread over 7 days. The only addition is a fixed numpy seed (data_gen.py has none), so the
trace can be regenerated exactly; requests are drawn in batches of 1 M as in data_gen.py.
"""
import argparse
import importlib.util
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "data_gen", ROOT / "external/NSDI24-SIEVE/libCacheSim/scripts/data_gen.py")
data_gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(data_gen)

REC = np.dtype([("t", "<u4"), ("id", "<u8"), ("sz", "<u4"), ("next", "<i8")])

ap = argparse.ArgumentParser()
ap.add_argument("-m", type=int, required=True)
ap.add_argument("-n", type=int, required=True)
ap.add_argument("--alpha", type=float, default=1.0)
ap.add_argument("--seed", type=int, default=1)
ap.add_argument("--obj-size", type=int, default=4000)
ap.add_argument("--time-span", type=int, default=86400 * 7)
ap.add_argument("-o", "--out", required=True)
a = ap.parse_args()

np.random.seed(a.seed)
batch = 1_000_000
done = 0
with open(a.out, "wb") as f:
    while done < a.n:
        k = min(batch, a.n - done)
        rec = np.empty(k, REC)
        rec["id"] = data_gen.gen_zipf(a.m, a.alpha, k)
        rec["t"] = (np.arange(done + 1, done + k + 1, dtype=np.int64) * a.time_span // a.n).astype(np.uint32)
        rec["sz"] = a.obj_size
        rec["next"] = -2
        rec.tofile(f)
        done += k
print(f"{a.out}: {a.n:,} requests, {a.m:,} objects, alpha {a.alpha}, seed {a.seed}", file=sys.stderr)
