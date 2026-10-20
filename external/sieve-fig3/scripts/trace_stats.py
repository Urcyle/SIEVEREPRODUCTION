#!/usr/bin/env python3
"""Exact request count, footprint (# unique objects) and duration of oracleGeneral traces.

usage: trace_stats.py <trace.zst> [...]   ->  TSV on stdout:
    file  n_req  n_obj  duration_h
Requests with object size 0 are skipped, as cachesim does (ignore_size_zero_req).
"""
import subprocess
import sys

import numpy as np

REC = np.dtype([("ts", "<u4"), ("id", "<u8"), ("sz", "<u4"), ("nxt", "<i8")])
CHUNK = 4_000_000


def stats(path):
    src = subprocess.Popen(["zstd", "-dc", "-q", path], stdout=subprocess.PIPE, bufsize=1 << 24)
    n_req, uniq, pending, n_pending = 0, np.empty(0, np.uint64), [], 0
    t0 = t1 = None
    tail = b""
    while True:
        buf = src.stdout.read(CHUNK * REC.itemsize)
        if not buf:
            break
        buf = tail + buf
        n = len(buf) // REC.itemsize
        tail = buf[n * REC.itemsize:]
        r = np.frombuffer(buf[:n * REC.itemsize], dtype=REC)
        if t0 is None:
            t0 = int(r["ts"][0])
        t1 = int(r["ts"][-1])
        r = r[r["sz"] != 0]
        n_req += len(r)
        ids = np.unique(r["id"])
        pending.append(ids)
        n_pending += len(ids)
        if n_pending > 50_000_000:
            uniq = np.unique(np.concatenate([uniq] + pending))
            pending, n_pending = [], 0
    src.wait()
    uniq = np.unique(np.concatenate([uniq] + pending))
    return n_req, len(uniq), (t1 - t0) / 3600 if t0 is not None else 0


if __name__ == "__main__":
    for p in sys.argv[1:]:
        n_req, n_obj, h = stats(p)
        print(f"{p}\t{n_req}\t{n_obj}\t{h:.1f}", flush=True)
