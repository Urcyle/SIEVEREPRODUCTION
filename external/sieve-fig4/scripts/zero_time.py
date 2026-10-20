#!/usr/bin/env python3
"""Set the time field of an oracleGeneral trace to 0 (in place, via a temporary file).

usage: zero_time.py <trace.oracleGeneral.zst> [...]

traceConv leaves the time of every request at 0xFFFFFFFF when the CSV has no time column (Meta's
KV traces have none). The CMU mirror's conversion of the same traces has time 0, so this makes
our files identical to it (scripts/check_metakv.py). Object ids, sizes and next-access fields
are not touched.
"""
import os
import subprocess
import sys

import numpy as np

REC = np.dtype([("t", "<u4"), ("id", "<u8"), ("sz", "<u4"), ("next", "<i8")])
CHUNK = 10_000_000

for path in sys.argv[1:]:
    tmp = path + ".tmp"
    src = subprocess.Popen(["zstd", "-dc", "--", path], stdout=subprocess.PIPE, bufsize=1 << 24)
    dst = subprocess.Popen(["zstd", "-q", "-T4", "-12", "-f", "-o", tmp], stdin=subprocess.PIPE)
    n = 0
    while buf := src.stdout.read(CHUNK * REC.itemsize):
        r = np.frombuffer(buf, dtype=REC).copy()
        r["t"] = 0
        dst.stdin.write(r.tobytes())
        n += len(r)
    dst.stdin.close()
    assert src.wait() == 0 and dst.wait() == 0, path
    os.replace(tmp, path)
    print(f"{path}: {n:,} records, time set to 0", flush=True)
