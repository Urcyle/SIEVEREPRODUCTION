"""Statistics of oracleGeneral traces, and the cache sizes cachesim would use for them.

usage: python -I scripts/trace_stats.py <trace.oracleGeneral.zst> [...] >> results/stats/traces.tsv

For each trace, prints one tab-separated line:
  trace  file_bytes  requests  objects  wss_scaling  wss_obj  size_0.001  size_0.1

* requests / objects: exact counts over the requests cachesim reads. Like cachesim's reader
  (ignore_size_zero_req = true), requests with object size 0 are skipped.
* wss_obj: the footprint exactly as cachesim's cal_working_set_size() computes it when cache
  sizes are given as fractions: for a trace file > 5 GiB it counts only objects with
  obj_id % 101 == 0 and multiplies by 101 (> 1 GiB: % 11, x 11). wss_scaling is that factor.
* size_0.001 / size_0.1: (uint64)(wss_obj * fraction), the cache sizes (in objects, since object
  size is ignored) cachesim would use. scripts/run_trace.sh passes these as absolute sizes, so
  runs that are split into several cachesim processes all get the paper's cache sizes without
  each process scanning the trace again.

oracleGeneral record (24 bytes): uint32 time, uint64 obj_id, uint32 obj_size, int64 next_access_vtime.
"""
import os
import subprocess
import sys

import numpy as np

REC = np.dtype([("t", "<u4"), ("id", "<u8"), ("sz", "<u4"), ("next", "<i8")])
CHUNK = 20_000_000  # records per read (480 MB)
GiB = 1 << 30


def stats(path):
    file_bytes = os.stat(path).st_size  # cachesim uses the size of the file it is given
    scaling = 101 if file_bytes > 5 * GiB else 11 if file_bytes > GiB else 1
    p = subprocess.Popen(["zstd", "-dc", "--", os.path.realpath(path)], stdout=subprocess.PIPE, bufsize=1 << 24)
    n_req = n_obj = 0
    sampled = []  # unique sampled object ids per chunk
    while True:
        buf = p.stdout.read(CHUNK * REC.itemsize)
        if not buf:
            break
        r = np.frombuffer(buf, dtype=REC)
        r = r[r["sz"] > 0]
        n_req += len(r)
        n_obj += int(np.count_nonzero(r["next"] == -1))  # last request of each object
        ids = r["id"] if scaling == 1 else r["id"][r["id"] % scaling == 0]
        sampled.append(np.unique(ids))
        if len(sampled) >= 16:
            sampled = [np.unique(np.concatenate(sampled))]
        print(f"  {os.path.basename(path)}: {n_req / 1e6:,.0f} M requests read", file=sys.stderr, flush=True)
    if p.wait() != 0:
        sys.exit(f"zstd failed on {path}")
    wss = len(np.unique(np.concatenate(sampled))) * scaling if sampled else 0
    return [os.path.basename(path), file_bytes, n_req, n_obj, scaling, wss, int(wss * 0.001), int(wss * 0.1)]


if __name__ == "__main__":
    for path in sys.argv[1:]:
        print("\t".join(map(str, stats(path))), flush=True)
