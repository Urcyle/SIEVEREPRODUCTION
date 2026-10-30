#!/usr/bin/env python3
"""Split the merged Meta KV 202206 file into the paper's five traces without downloading them again.

The merged file (`data/metakv_2022/202206_kv_traces_all...`) is the five Meta KV traces concatenated; zero-size records
(GET misses and DELETEs, which every reader skips) are dropped here. The boundaries are the per-trace request counts that
SIEVEREPRODUCTION measured from Meta's own per-trace CSV files (results/stats/kvcache_traces_N.tsv); the counts add up
exactly to the merged file's valid-request count (1,644,762,386). Checks: trace 1 must equal our separately downloaded
trace-1 file record for record in (object id, size) (hash of the valid-record stream; the time and next-access fields differ
between the two sources and are not used by the policies, so the split writes time 0 and next -2), and every part's exact distinct-object count must be within 0.1% of the
other repository's working-set figure.

  python3 -B scripts/split_metakv_202206.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MERGED = ROOT / "data/metakv_2022/202206_kv_traces_all.csv.oracleGeneral.zst"
TRACE1 = ROOT / "data/metakv_candidate/meta_kvcache_traces_1.oracleGeneral.bin.zst"
OUT = ROOT / "data/metakv_split"
RECEIPT = ROOT / "local_results/metakv_split_receipt.json"
COUNTS = [335_173_084, 328_002_954, 318_815_605, 329_914_873, 332_855_870]      # valid requests per trace
OBJECTS = [16_982_130, 16_542_009, 16_168_504, 16_236_011, 16_661_458]          # SIEVEREPRODUCTION's working-set figure per trace (the simulator's sampled estimate)
DTYPE = np.dtype([("time", "<u4"), ("id", "<u8"), ("size", "<u4"), ("next", "<i8")])


def valid_blocks(path: Path):
    proc = subprocess.Popen(["zstd", "-dc", "--", str(path)], stdout=subprocess.PIPE)
    carry = b""
    while block := proc.stdout.read(24 * (1 << 21)):
        block = carry + block
        usable = len(block) // 24 * 24
        carry = block[usable:]
        rows = np.frombuffer(block[:usable], dtype=DTYPE)
        yield rows[rows["size"] != 0]
    if carry or proc.wait() != 0:
        raise SystemExit("alignment or zstd failure")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    receipt = {"merged_sha256": None, "parts": []}
    parts = []
    sinks = []
    for i in range(5):
        path = OUT / f"kvcache_traces_{i + 1}.valid.oracleGeneral.zst"
        sink = subprocess.Popen(["zstd", "-q", "-T4", "-3", "-f", "-o", str(path)], stdin=subprocess.PIPE)
        sinks.append(sink)
        parts.append({"path": str(path.relative_to(ROOT)), "records": 0, "hash": hashlib.sha256(), "pair_hash": hashlib.sha256(), "seen": [], "pending": 0, "unique": np.empty(0, dtype=np.uint64)})
    index = 0
    for rows in valid_blocks(MERGED):
        start = 0
        while start < len(rows):
            part = parts[index]
            take = min(len(rows) - start, COUNTS[index] - part["records"])
            chunk = rows[start:start + take].copy()
            chunk["time"] = 0          # the merged file's time field is not per-trace
            chunk["next"] = -2         # next-access times of the merged stream are meaningless inside one trace (unused by these policies)
            data = chunk.tobytes()
            sinks[index].stdin.write(data)
            part["hash"].update(data)
            pairs = np.empty(len(chunk), dtype=[("id", "<u8"), ("size", "<u4")])
            pairs["id"], pairs["size"] = chunk["id"], chunk["size"]
            part["pair_hash"].update(pairs.tobytes())
            part["seen"].append(np.unique(chunk["id"]))
            part["pending"] += len(part["seen"][-1])
            if part["pending"] > 20_000_000:
                part["unique"] = np.unique(np.concatenate([part["unique"]] + part["seen"]))
                part["seen"], part["pending"] = [], 0
            part["records"] += take
            start += take
            if part["records"] == COUNTS[index]:
                sinks[index].stdin.close()
                sinks[index].wait()
                part["unique"] = np.unique(np.concatenate([part["unique"]] + part["seen"]))
                part["seen"] = []
                index += 1
                if index == 5:
                    break
        if index == 5:
            break
    if index != 5:
        raise SystemExit("merged file ended before the five counts were reached")
    for i, part in enumerate(parts):
        record = {"trace": i + 1, "path": part["path"], "valid_records": part["records"], "unique_objects": int(len(part["unique"])),
                  "valid_stream_sha256": part["hash"].hexdigest(), "id_size_sha256": part["pair_hash"].hexdigest(), "stored_bytes": (ROOT / part["path"]).stat().st_size}
        assert abs(record["unique_objects"] - OBJECTS[i]) <= 0.001 * OBJECTS[i], (i + 1, record["unique_objects"], OBJECTS[i])   # exact count within 0.1% of the sampled estimate
        receipt["parts"].append(record)
    # trace 1 against the separately downloaded file
    digest = hashlib.sha256()
    n = 0
    for rows in valid_blocks(TRACE1):
        pairs = np.empty(len(rows), dtype=[("id", "<u8"), ("size", "<u4")])
        pairs["id"], pairs["size"] = rows["id"], rows["size"]
        digest.update(pairs.tobytes())
        n += len(rows)
    receipt["trace1_check"] = {"valid_records": n, "id_size_sha256": digest.hexdigest(),
                               "equal_to_split_part_1": digest.hexdigest() == receipt["parts"][0]["id_size_sha256"]}
    if not receipt["trace1_check"]["equal_to_split_part_1"]:
        raise SystemExit("trace 1 differs from the separately downloaded file")
    RECEIPT.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n")
    print(json.dumps(receipt["trace1_check"]), [p["unique_objects"] for p in receipt["parts"]])


if __name__ == "__main__":
    main()
