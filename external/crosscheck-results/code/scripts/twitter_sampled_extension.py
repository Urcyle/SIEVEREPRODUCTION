#!/usr/bin/env python3
"""Twitter sample100 extension (protocol: docs/twitter_sampled_extension_protocol.md).

  python3 -B scripts/twitter_sampled_extension.py fetch     # download + identity + exact unique count
  python3 -B scripts/twitter_sampled_extension.py run       # resumable; two workers, one root each
  python3 -B scripts/twitter_sampled_extension.py summarize # tables from saved counters only
  python3 -B scripts/twitter_sampled_extension.py ghost     # variant Amendment 6: ghost0.5 / ghost1.0 on the held-out-2 files
  python3 -B scripts/twitter_sampled_extension.py ghost-summary
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sieve_repro.baseline_run import run_baseline
from sieve_repro.run import GIB, file_sha256, run_one
from sieve_repro.trace import validate_oracle_file

# Batch 1 (sample100) is the default; batch 2 (sample10) is selected with TWITTER_EXT_CONFIG=config/twitter_sample10_extension.json
CONFIG_PATH = ROOT / os.environ.get("TWITTER_EXT_CONFIG", "config/twitter_sampled_extension.json")
CONFIG = json.loads(CONFIG_PATH.read_text())
OUT = ROOT / CONFIG.get("out_dir", "local_results/twitter_sampled_extension")
DATA = ROOT / CONFIG.get("data_dir", "data/twitter_sample100")
SUMMARY_CSV = CONFIG.get("summary_csv", "sample100_extension.csv")


def kind(n: int) -> str:
    return CONFIG.get("kinds", {}).get(str(n), "sample100")
COUNTER_BINARY = ROOT / "build/counter-sim/bin/cachesim"
SEEDED_BINARY = ROOT / "build/seeded-baselines/bin/cachesim"
LABELS = {"fifo": "FIFO", "lru": "LRU", "clock": "CLOCK", "sieve": "SIEVE", "arc": "ARC", "twoq": "TwoQ", "lirs": "LIRS",
          "tinylfu_snapshot": "TinyLFU", "blru": "B-LRU", "hyperbolic": "Hyperbolic", "lhd": "LHD", "cacheus": "CACHEUS"}


def label(n: int) -> str:
    if "labels" in CONFIG:           # explicit names (the Wiki files)
        return CONFIG["labels"][str(n)]
    return f"{CONFIG['label_prefix']}{n}" if "label_prefix" in CONFIG else f"twitter_cluster{n}_{kind(n)}"


def trace_path(n: int) -> Path:
    if "local_files" in CONFIG:      # files made locally (the Meta KV split), nothing to download
        return ROOT / CONFIG["local_files"][str(n)]
    return DATA / f"cluster{n}.oracleGeneral.{kind(n)}.zst"


def identity_path(n: int) -> Path:
    return OUT / (f"{label(n)}_identity.json" if "local_files" in CONFIG else f"cluster{n}_{kind(n)}_identity.json")


def fast_validate(path: Path) -> dict:
    """Same fields as validate_oracle_file(count_unique=True), computed with NumPy blocks (24-byte <IQIq records)."""
    import hashlib
    import numpy as np
    dtype = np.dtype([("time", "<u4"), ("id", "<u8"), ("size", "<u4"), ("next", "<i8")])
    stored = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 24), b""):
            stored.update(block)
    stream_hash = hashlib.sha256()
    proc = subprocess.Popen(["zstd", "-dc", "--", str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    n = zeros = 0
    seen = np.empty(0, dtype=np.uint64)
    pending, pending_size = [], 0
    carry = b""
    while block := proc.stdout.read(24 * (1 << 21)):
        block = carry + block
        usable = len(block) // 24 * 24
        carry = block[usable:]
        data = block[:usable]
        stream_hash.update(data)
        rows = np.frombuffer(data, dtype=dtype)
        n += len(rows)
        nonzero = rows["size"] != 0
        zeros += int((~nonzero).sum())
        pending.append(np.unique(rows["id"][nonzero]))
        pending_size += len(pending[-1])
        if pending_size > 20_000_000:
            seen = np.unique(np.concatenate([seen] + pending))
            pending, pending_size = [], 0
    stderr = proc.stderr.read().decode(errors="replace")
    if carry or proc.wait() != 0:
        raise ValueError(f"alignment or zstd failure: {stderr[-300:]}")
    seen = np.unique(np.concatenate([seen] + pending))
    return {"record_count": n, "zero_size_count": zeros, "sha256": stored.hexdigest(), "stream_sha256": stream_hash.hexdigest(),
            "stored_bytes": path.stat().st_size, "compressed_bytes": path.stat().st_size, "unique_objects": int(len(seen))}


def fetch() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    for n in CONFIG["clusters"]:
        if identity_path(n).exists():
            continue
        path = trace_path(n)
        if "local_files" in CONFIG and str(n) not in CONFIG.get("urls", {}):
            url, size = "local file made by scripts/split_metakv_202206.py", path.stat().st_size
        else:
            url = CONFIG["urls"][str(n)] if "urls" in CONFIG else f"{CONFIG['base_url']}/twitter/{kind(n)}/cluster{n}.oracleGeneral.{kind(n)}.zst"
            head = urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60)
            size = int(head.headers["Content-Length"])
            for attempt in range(5):
                if path.exists() and path.stat().st_size == size:
                    break
                subprocess.run(["curl", "-sS", "-f", "-L", "-C", "-", "--retry", "5", "-o", str(path), url], check=False)
            if path.stat().st_size != size:
                raise SystemExit(f"cluster{n}: downloaded {path.stat().st_size} of {size} bytes")
        subprocess.run(["zstd", "-q", "-t", str(path)], check=True)
        started = time.monotonic()
        meta = fast_validate(path)
        meta.update({"label": label(n), "url": url, "head_content_length": size,
                     "scan_seconds": time.monotonic() - started})
        identity_path(n).write_text(json.dumps(meta, indent=1, sort_keys=True) + "\n")
        print(f"cluster{n}: {meta['record_count']:,} requests, {meta['unique_objects']:,} objects, {size / 1e9:.2f} GB", flush=True)


def exact_capacity(meta: dict, fraction: float) -> int | None:
    """floor(exact unique objects x fraction), as the protocol requires; cachesim's own estimate is only a diagnostic.
    Batch 1 files are under 1 GiB (the estimate is exact there) and keep their original run identities (None)."""
    return int(meta["unique_objects"] * fraction) if CONFIG.get("exact_capacity_objects") else None


HEAVY = {"twoq", "lirs", "tinylfu_snapshot", "blru"}


def estimate(meta: dict, policy: str | None = None) -> int:
    if policy == "cacheus" and os.environ.get("TWITTER_EXT_CACHEUS_PER_OBJECT"):
        # docs/metakv_split_protocol.md, amendment 2: a try with a lower CACHEUS estimate; the live 12 GiB / 4 GiB-available guard still stops the run
        return GIB // 2 + int(os.environ["TWITTER_EXT_CACHEUS_PER_OBJECT"]) * meta["unique_objects"]
    if os.environ.get("TWITTER_EXT_MEASURED_ESTIMATE") and policy is not None and policy != "cacheus":
        # docs/wiki_full_extension_protocol.md, amendment 1: peak RSS measured on the 37.2 M-object wiki_2016u (12-53 B/object) replaces the older per-object bytes
        return GIB // 4 + (60 if policy in HEAVY else 30) * meta["unique_objects"]
    if CONFIG.get("policy_specific_estimate") and policy is not None:
        # measured peak RSS of 400+ completed runs (0.14-0.95 GiB at 5.8-7.1 M objects for every policy but CACHEUS, 1-3.2 GiB for CACHEUS,
        # which also had one run above 9 GiB): CACHEUS 0.5 GiB + 600 B/object, TwoQ/LIRS/TinyLFU/B-LRU 0.25 GiB + 150 B, the rest 0.25 GiB + 80 B
        per, base = (600, GIB // 2) if policy == "cacheus" else (150, GIB // 4) if policy in HEAVY else (80, GIB // 4)
        return base + per * meta["unique_objects"]
    if CONFIG.get("exact_capacity_objects"):   # batch 2, amendment 2: 1 GiB + 100 bytes per object
        return 1 * GIB + 100 * meta["unique_objects"]
    return 1 * GIB + 250 * meta["unique_objects"]   # batch 1, amendment 1 of the protocol


def work(worker: int, clusters: list[int]) -> None:
    root = OUT / f"worker{worker}"
    root.mkdir(parents=True, exist_ok=True)
    manifest_hash = file_sha256(CONFIG_PATH)
    omitted = root / "omitted.csv"
    for n in clusters:
        meta = json.loads(identity_path(n).read_text())
        # the simulator's working-set estimate may be sampled on large files; the exact scan is bound by its record hash
        for fraction in CONFIG["capacity_fractions"]:
            for policy in CONFIG["worker_policies"][worker] if "worker_policies" in CONFIG else CONFIG["core_policies"] + CONFIG["extra_policies"]:
                if os.environ.get("TWITTER_EXT_ONLY_POLICIES") and policy not in os.environ["TWITTER_EXT_ONLY_POLICIES"].split(","):
                    continue
                try:
                    if policy in CONFIG["core_policies"] and not CONFIG.get("exact_capacity_objects"):
                        record = run_one(trace=trace_path(n), trace_meta=meta, policy=policy, fraction=fraction,
                                         binary=COUNTER_BINARY, output_root=root, estimated_peak_bytes=estimate(meta, policy),
                                         workload_label=meta["label"], capacity_objects=exact_capacity(meta, fraction))
                    else:
                        record = run_baseline(trace=trace_path(n), metadata=meta, policy=policy, fraction=fraction,
                                              seed=CONFIG["rng_seed"], binary=SEEDED_BINARY, output_root=root,
                                              manifest_hash=manifest_hash, estimated_peak_bytes=estimate(meta, policy),
                                              capacity_objects=exact_capacity(meta, fraction))
                    print(f"w{worker} cluster{n} {fraction} {policy}: {record['n_miss']:,}/{record['n_req']:,} "
                          f"{record['elapsed_seconds']:.0f}s rss={record.get('peak_rss_kib', 0):,}KiB", flush=True)
                except (MemoryError, Exception) as error:  # noqa: BLE001 - recorded, not hidden
                    with omitted.open("a", newline="") as stream:
                        writer = csv.writer(stream)
                        if stream.tell() == 0:
                            writer.writerow(["cluster", "fraction", "policy", "reason"])
                        writer.writerow([n, fraction, policy, str(error)[:300]])
                    print(f"w{worker} cluster{n} {fraction} {policy}: OMITTED {str(error)[:120]}", flush=True)


def run() -> None:
    missing = [n for n in CONFIG["clusters"] if not identity_path(n).exists()]
    if missing:
        raise SystemExit(f"run `fetch` first; missing identity for {missing}")
    only = {int(x) for x in os.environ.get("TWITTER_EXT_WORKERS", "").split(",") if x}   # run a subset of workers (memory)
    threads = [threading.Thread(target=work, args=(i, part)) for i, part in enumerate(CONFIG["worker_partition"])
               if not only or i in only]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def summarize() -> None:
    records = {}
    for path in OUT.glob("worker*/runs/*/complete.json"):
        r = json.loads(path.read_text())
        spec = r["spec"]
        label = spec.get("trace_label") or spec.get("workload_label")
        policy = spec.get("policy_label") or spec["policy"]
        fraction = spec.get("capacity_fraction")
        if fraction is None:
            continue
        records[(label, fraction, policy)] = r
    rows = []
    for (label, fraction, policy), r in sorted(records.items()):
        fifo = records.get((label, fraction, "fifo"))
        if fifo is None or policy not in LABELS:
            continue
        f, a = fifo["n_miss"] / fifo["n_req"], r["n_miss"] / r["n_req"]
        reduction = 0.0 if max(f, a) == 0 else (f - a) / max(f, a)
        rows.append({"trace": label, "capacity_fraction": fraction, "policy": policy, "algo": LABELS[policy],
                     "requests": r["n_req"], "misses": r["n_miss"], "miss_ratio": f"{a:.6f}",
                     "reduction_from_fifo": f"{reduction:.6f}", "cache_objects": r["cache_size"],
                     "run_id": r["run_id"], "peak_rss_kib": r.get("peak_rss_kib", "")})
    with (OUT / SUMMARY_CSV).open("w", newline="") as stream:
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


HELDOUT2 = (37, 40, 43, 46, 52, 54)          # fixed in docs/variant_protocol.md, Amendment 6 (32 joins only if its baseline ran)
HELDOUT3 = tuple(CONFIG["clusters"]) if "kinds" in CONFIG else ()   # Amendment 7: every batch-2 file
GHOST_CONFIGS = ("ghost0.5", "ghost1.0")
GHOST_OUT = ROOT / ("local_results/variants_heldout3" if "kinds" in CONFIG else "local_results/variants_heldout2")


def sieve_baselines() -> dict:
    found = {}
    for path in OUT.glob("worker*/runs/*/complete.json"):
        r = json.loads(path.read_text())
        spec = r["spec"]
        policy = spec.get("policy") or spec.get("policy_label")      # first-slice runner vs seeded-baselines runner
        label = spec.get("workload_label") or spec.get("trace_label")
        if policy == "sieve" and "capacity_fraction" in spec:
            found[(label, spec["capacity_fraction"])] = r
    return found


def ghost() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import sieve_variants as sv
    GHOST_OUT.mkdir(parents=True, exist_ok=True)
    base = sieve_baselines()
    clusters = list(HELDOUT3 or HELDOUT2) + ([32] if not HELDOUT3 and (f"twitter_cluster32_sample100", 0.001) in base else [])
    shard, shards = (int(x) for x in os.environ.get("TWITTER_EXT_SHARD", "0/1").split("/"))
    for position, n in enumerate(clusters):
        if position % shards != shard:
            continue
        meta = json.loads(identity_path(n).read_text())
        for fraction in CONFIG["capacity_fractions"]:
            ref = base.get((meta["label"], fraction))
            if ref is None:
                print(f"cluster{n} {fraction}: no SIEVE baseline, skipped")
                continue
            names = list(GHOST_CONFIGS) + (["base"] if n == (HELDOUT3[0] if HELDOUT3 else 54) else [])   # base equality check on one file per capacity
            for name in names:
                try:
                    r = sv.run_config(name, binary=sv.BINARY, trace=trace_path(n), trace_sha256=meta["sha256"],
                                      workload_label=meta["label"], capacity_objects=ref["cache_size"],
                                      capacity_label=sv.FRACTION_LABELS[fraction], unique_objects=meta["unique_objects"],
                                      expected_requests=ref["n_req"], baseline_run_id=ref["run_id"],
                                      baseline_peak_kib=ref.get("peak_rss_kib"), output_root=GHOST_OUT)
                    print(f"cluster{n} {fraction} {name}: {r['n_miss']:,} (SIEVE {ref['n_miss']:,})", flush=True)
                except Exception as error:  # noqa: BLE001 - reported, not hidden
                    print(f"cluster{n} {fraction} {name}: OMITTED {str(error)[:150]}", flush=True)


def ghost_summary() -> None:
    import statistics
    from sieve_repro.variants import config_name
    base = sieve_baselines()
    recs = {}
    for path in GHOST_OUT.glob("runs/*/complete.json"):
        r = json.loads(path.read_text())
        spec = r["spec"]
        recs[(spec["workload_label"], r["cache_size"], config_name(spec))] = r
    rows, verdict = [], []
    for fraction in CONFIG["capacity_fractions"]:
        for config in GHOST_CONFIGS:
            gains = []
            for n in (HELDOUT3 or HELDOUT2 + (32,)):
                label = f"twitter_cluster{n}_{kind(n)}"
                ref = base.get((label, fraction))
                if ref is None:
                    continue
                match = [r for (lab, cap, name), r in recs.items() if lab == label and cap == ref["cache_size"] and name == config]
                if not match:
                    continue
                g = match[0]["n_miss"]
                gain = (ref["n_miss"] - g) / ref["n_miss"]
                gains.append(gain)
                rows.append({"trace": label, "capacity_fraction": fraction, "config": config, "sieve_misses": ref["n_miss"],
                             "ghost_misses": g, "reduction_vs_sieve": f"{gain:.6f}"})
            if gains:
                lost = sum(x < 0 for x in gains)
                verdict.append({"capacity_fraction": fraction, "config": config, "n": len(gains),
                                "mean": f"{statistics.fmean(gains):.6f}", "median": f"{statistics.median(gains):.6f}",
                                "wins": sum(x > 0 for x in gains), "ties": sum(x == 0 for x in gains), "losses": lost,
                                "passes_rule": statistics.fmean(gains) > 0 and statistics.median(gains) >= 0 and lost * 4 <= len(gains)})
    tag = "heldout3" if HELDOUT3 else "heldout2"
    for name, table in ((f"ghost_{tag}_per_trace.csv", rows), (f"ghost_{tag}_verdict.csv", verdict)):
        with (GHOST_OUT / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, tuple(table[0]))
            writer.writeheader()
            writer.writerows(table)
    for v in verdict:
        print(v)
    if HELDOUT3:   # Amendment 7 (b): pooled with held-out-2
        earlier = list(csv.DictReader((ROOT / "local_results/variants_heldout2/ghost_heldout2_per_trace.csv").open(newline="")))
        pooled = []
        for fraction in CONFIG["capacity_fractions"]:
            for config in GHOST_CONFIGS:
                gains = [float(r["reduction_vs_sieve"]) for r in rows + earlier
                         if float(r["capacity_fraction"]) == fraction and r["config"] == config]
                if gains:
                    lost = sum(x < 0 for x in gains)
                    pooled.append({"capacity_fraction": fraction, "config": config, "n": len(gains),
                                   "mean": f"{statistics.fmean(gains):.6f}", "median": f"{statistics.median(gains):.6f}",
                                   "wins": sum(x > 0 for x in gains), "ties": sum(x == 0 for x in gains), "losses": lost,
                                   "passes_rule": statistics.fmean(gains) > 0 and statistics.median(gains) >= 0 and lost * 4 <= len(gains)})
        with (GHOST_OUT / "ghost_heldout2_plus_3_verdict.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, tuple(pooled[0]))
            writer.writeheader()
            writer.writerows(pooled)
        print("pooled:")
        for v in pooled:
            print(v)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"fetch", "run", "summarize", "ghost", "ghost-summary"}:
        raise SystemExit(__doc__)
    {"fetch": fetch, "run": run, "summarize": summarize, "ghost": ghost, "ghost-summary": ghost_summary}[sys.argv[1]]()
