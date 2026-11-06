#!/usr/bin/env python3
"""Tencent Photo runs of docs/tencent_full_protocol.md: S (10% spatial sample), F (full size) and C (CACHEUS seed spread).

  python3 -B scripts/tencent_full_run.py fetch           # identity of both files (hashes, record count, exact distinct count)
  python3 -B scripts/tencent_full_run.py run [S|F|C...]  # run the listed families (default all), phases in the protocol's order
  python3 -B scripts/tencent_full_run.py summarize
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ.setdefault("TWITTER_EXT_CONFIG", "config/tencent_full_extension.json")

import twitter_sampled_extension as ext
from sieve_repro.baseline_run import run_baseline
from sieve_repro.run import GIB, file_sha256, mem_available_bytes

CONFIG = ext.CONFIG
OUT = ROOT / CONFIG["out_dir"]
BINARY = ROOT / "build/seeded-baselines/bin/cachesim"
FRACTIONS = (0.001, 0.1)
SAMPLE = 0.1
POLICIES = ("fifo", "lru", "clock", "sieve", "arc", "twoq", "lirs", "tinylfu_snapshot", "hyperbolic", "lhd", "cacheus", "blru")
# bytes per cached object (protocol, "Memory gate"); B-LRU adds 60 bytes per object of the file it runs on
BYTES = {"fifo": 90, "lru": 90, "clock": 90, "sieve": 90, "hyperbolic": 90, "arc": 160, "lhd": 250, "tinylfu_snapshot": 350,
         "twoq": 440, "lirs": 560, "cacheus": 1300, "blru": 90}
# full size at 10%: only these fit this machine (FIFO-type about 5 GB, ARC about 9 GB); the others are not attempted (protocol, family F)
FULL_LARGE = ("fifo", "lru", "clock", "sieve", "arc", "lhd")      # amendment 1: LHD joins, gated; the heavier policies stay on the sample
FULL_SMALL = tuple(p for p in POLICIES if p != "blru")
SPREAD_SEEDS = tuple(range(1, 9))
MAX_WAIT_ROUNDS = 90          # a job that fails only the pre-run memory gate waits up to 90 x 120 s


def metadata(n: int) -> dict:
    return json.loads(ext.identity_path(n).read_text())


def jobs(families: set[str]) -> list[dict]:
    """Phase order: S, C (cheap), F small, F large."""
    out = []
    for fam in ("S", "C", "F"):
        if fam not in families:
            continue
        for n in (2, 1):
            if fam == "S":
                out += [{"fam": "S", "n": n, "policy": p, "fraction": f, "seed": 42, "sample": SAMPLE} for f in FRACTIONS for p in POLICIES]
            elif fam == "C" and n == 2:
                out += [{"fam": "C", "n": n, "policy": "cacheus", "fraction": f, "seed": s, "sample": SAMPLE} for f in FRACTIONS for s in SPREAD_SEEDS]
            elif fam == "F":
                out += [{"fam": "F", "n": n, "policy": p, "fraction": 0.001, "seed": 42, "sample": None} for p in FULL_SMALL]
    if "F" in families:
        out += [{"fam": "F", "n": n, "policy": p, "fraction": 0.1, "seed": 42, "sample": None} for n in (2, 1) for p in FULL_LARGE]
    return out


def estimate(job: dict) -> int:
    meta = metadata(job["n"])
    objects = meta["unique_objects"] * (job["sample"] or 1)
    est = GIB * 3 // 10 + BYTES[job["policy"]] * int(objects * job["fraction"])
    if job["policy"] == "blru":
        est += 60 * int(objects)
    return est


def execute(job: dict, root: Path) -> None:
    meta = metadata(job["n"])
    manifest = ext.file_sha256(ext.CONFIG_PATH)
    kwargs = dict(trace=ext.trace_path(job["n"]), metadata=meta, policy=job["policy"], fraction=job["fraction"], seed=job["seed"],
                  binary=BINARY, output_root=root, manifest_hash=manifest, estimated_peak_bytes=estimate(job))
    if job["sample"]:
        kwargs["sample_ratio"] = job["sample"]
    else:
        kwargs["capacity_objects"] = int(meta["unique_objects"] * job["fraction"])
    need = estimate(job) + 4 * GIB + GIB // 16        # the runner's gate (estimate + 4 GiB headroom) with a small margin
    waited = 0
    while mem_available_bytes() < need and waited < MAX_WAIT_ROUNDS:   # wait for RAM before calling the runner: same allowance, no failed attempts
        time.sleep(120)
        waited += 1
    try:
        record = run_baseline(**kwargs)
        print(f"{job['fam']} photo{job['n']} {job['fraction']} {job['policy']} seed{job['seed']}: {record['n_miss']:,}/{record['n_req']:,} "
              f"{record['elapsed_seconds']:.0f}s rss={record.get('peak_rss_kib', 0):,}KiB", flush=True)
        return
    except Exception as error:  # noqa: BLE001 - recorded, not hidden
        reason = f"{type(error).__name__}: {error}"
        with (root / "omitted.csv").open("a", newline="") as stream:
            writer = csv.writer(stream)
            if stream.tell() == 0:
                writer.writerow(["family", "trace", "fraction", "policy", "seed", "reason"])
            writer.writerow([job["fam"], job["n"], job["fraction"], job["policy"], job["seed"], reason[:300]])
        print(f"{job['fam']} photo{job['n']} {job['fraction']} {job['policy']} seed{job['seed']}: OMITTED {reason[:140]}", flush=True)
        return


def run(families: set[str]) -> None:
    missing = [n for n in CONFIG["clusters"] if not ext.identity_path(n).exists()]
    if missing:
        raise SystemExit(f"run `fetch` first; missing identity for {missing}")
    todo = jobs(families)
    # cheap jobs (estimate <= 3 GiB) three at a time, staggered; the rest one at a time after them
    cheap = [j for j in todo if estimate(j) <= 3 * GIB]
    heavy = [j for j in todo if estimate(j) > 3 * GIB]
    for batch, workers in ((cheap, 3), (heavy, 1)):
        queue, lock = list(batch), threading.Lock()

        def worker(i: int) -> None:
            root = OUT / f"worker{i}"
            root.mkdir(parents=True, exist_ok=True)
            time.sleep(60 * i)
            while True:
                with lock:
                    if not queue:
                        return
                    job = queue.pop(0)
                execute(job, root)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()


def records() -> list[dict]:
    out = []
    for path in OUT.glob("worker*/runs/*/complete.json"):
        r = json.loads(path.read_text())
        spec = r["spec"]
        out.append({"trace": spec["trace_label"], "family": "sample" if spec.get("sample_ratio") else "full",
                    "fraction": spec["capacity_fraction"], "policy": spec["policy_label"], "seed": spec["rng_seed"], "requests": r["n_req"],
                    "misses": r["n_miss"], "cache_objects": r["cache_size"], "footprint_objects": r["unique_objects"],
                    "run_id": r["run_id"], "peak_rss_kib": r.get("peak_rss_kib", ""), "elapsed_seconds": round(r["elapsed_seconds"])})
    return out


def summarize() -> None:
    recs = records()
    base = {(r["trace"], r["family"], r["fraction"]): r for r in recs if r["policy"] == "fifo" and r["seed"] == 42}
    rows = []
    for r in sorted(recs, key=lambda r: (r["trace"], r["family"], r["fraction"], r["policy"], r["seed"])):
        fifo = base.get((r["trace"], r["family"], r["fraction"]))
        f, a = (fifo["misses"] / fifo["requests"], r["misses"] / r["requests"]) if fifo else (None, r["misses"] / r["requests"])
        red = "" if f is None else f"{0.0 if max(f, a) == 0 else (f - a) / max(f, a):.6f}"
        rows.append({**r, "miss_ratio": f"{a:.6f}", "reduction_from_fifo": red})
    if rows:
        with (OUT / CONFIG["summary_csv"]).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, tuple(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    omitted = [row for p in sorted(OUT.glob("worker*/omitted.csv")) for row in csv.DictReader(p.open(newline=""))]
    if omitted:
        with (OUT / "omitted.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, tuple(omitted[0]))
            writer.writeheader()
            writer.writerows(omitted)
    print(f"{len(rows)} rows, {len(omitted)} omitted")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "fetch":
        ext.fetch()
    elif cmd == "run":
        run(set(sys.argv[2:]) or {"S", "C", "F"})
    elif cmd == "summarize":
        summarize()
    else:
        raise SystemExit(__doc__)
