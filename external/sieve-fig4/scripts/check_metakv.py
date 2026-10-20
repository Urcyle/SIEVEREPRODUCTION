#!/usr/bin/env python3
"""Check that our 5 converted Meta KV traces, one after another, are exactly the CMU mirror's
merged file (same object ids, sizes and times, record by record). next_access_vtime is not
compared: in the merged file it points across trace boundaries.

usage: check_metakv.py data/metaKV/202206_kv_traces_all.csv.oracleGeneral.zst \
           data/metaKV/kvcache_traces_{1..5}.oracleGeneral.zst
"""
import subprocess
import sys

import numpy as np

REC = np.dtype([("t", "<u4"), ("id", "<u8"), ("sz", "<u4"), ("next", "<i8")])
CHUNK = 10_000_000


def stream(path):
    p = subprocess.Popen(["zstd", "-dc", "--", path], stdout=subprocess.PIPE, bufsize=1 << 24)
    while buf := p.stdout.read(CHUNK * REC.itemsize):
        yield np.frombuffer(buf, dtype=REC)
    assert p.wait() == 0, path


def ours(paths):
    for p in paths:
        n = 0
        for r in stream(p):
            n += len(r)
            yield r
        print(f"  {p}: {n:,} records", flush=True)


def main():
    merged, parts = sys.argv[1], sys.argv[2:]
    a_it, b_it = stream(merged), ours(parts)
    a = b = np.empty(0, REC)
    total = 0
    while True:
        if len(a) == 0:
            a = next(a_it, None)
        if len(b) == 0:
            b = next(b_it, None)
        if a is None or b is None:
            break
        n = min(len(a), len(b))
        for f in ("t", "id", "sz"):
            bad = np.flatnonzero(a[f][:n] != b[f][:n])
            if len(bad):
                sys.exit(f"MISMATCH at record {total + bad[0]:,} field {f}")
        total += n
        a, b = a[n:], b[n:]
    rest_a = (0 if a is None else len(a)) + sum(len(x) for x in a_it)
    rest_b = (0 if b is None else len(b)) + sum(len(x) for x in b_it)
    if rest_a or rest_b:
        sys.exit(f"MISMATCH: equal for {total:,} records, then {rest_a:,} left in merged, "
                 f"{rest_b:,} left in ours")
    print(f"IDENTICAL: {total:,} records (time, obj_id, size)")


if __name__ == "__main__":
    main()
