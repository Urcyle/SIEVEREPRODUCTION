#!/usr/bin/env python3
"""Per-request check of LeCaR-SIEVE (corrected wrap rule) against the corrected independent model, with a mutation control.

Three small unit-size fixtures (Zipf-like, loop plus scan, bursty) are replayed with the debug state log and the controlled seed
by (a) the corrected build, which must agree with the model after every request, and (b) the original build, which must DISAGREE on
at least one fixture (otherwise the fixtures could not have detected the bug).

  python3 -B scripts/verify_lecar_sieve_fixed.py
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from verify_lecar_sieve_model import LeCaRSieveModel, parse_snapshots
from sieve_repro.run import file_sha256
from sieve_repro.zipf import RECORD_DTYPE

FIXED = ROOT / "build/figure12-lecar-fixed/bin/cachesim"
ORIGINAL = ROOT / "build/figure12-lecar-sieve/bin/cachesim"
RECEIPT = ROOT / "local_results/verification/lecar_sieve_wrap_fix_model_check.json"
CACHE, SEED = 8, 42


def fixtures() -> dict:
    rng = np.random.default_rng(7)
    zipf = rng.zipf(1.3, 3000) % 60
    loop = np.concatenate([np.tile(np.arange(12), 60), np.arange(100, 400), np.tile(np.arange(6), 100)])
    burst = np.concatenate([rng.integers(0, 20, 400), rng.integers(0, 4, 400), rng.integers(30, 45, 400), rng.integers(0, 20, 400)])
    return {"zipf": zipf, "loop_scan": loop, "burst": burst}


def write(path: Path, ids) -> None:
    rows = np.zeros(len(ids), dtype=RECORD_DTYPE)
    rows["time"] = np.arange(len(ids))
    rows["id"] = ids
    rows["size"] = 1
    rows["next"] = -2
    rows.tofile(path)


def replay(binary: Path, trace: Path) -> list:
    env = dict(os.environ, SIEVE_RNG_SEED=str(SEED), LIBCACHESIM_DEBUG_LECAR_SIEVE="1")
    command = [str(binary), str(trace), "oracleGeneral", "lecar", str(CACHE), "--ignore-obj-size", "1", "--num-thread", "1",
               "--warmup-sec", "-1", "--eviction-params", "lru-type=SIEVE"]
    out = subprocess.run(command, env=env, capture_output=True, text=True, check=True, cwd=trace.parent).stdout
    return parse_snapshots(out)


def agrees(observed: list, ids) -> int:
    model = LeCaRSieveModel(CACHE, SEED)
    for index, obj in enumerate(ids, 1):
        model.request(int(obj), index)
    if len(observed) != len(model.snapshots):
        return 0
    for index, (got, expected) in enumerate(zip(observed, model.snapshots), 1):
        if any(got[k] != expected[k] for k in ("req", "hit", "hand", "q", "lfu", "ghost_lru", "ghost_lfu")) or not math.isclose(
                got["weight"], expected["weight"], rel_tol=0.0, abs_tol=2e-12):
            return -index
    return len(observed)


def main() -> None:
    receipt = {"cache": CACHE, "seed": SEED, "fixed_binary_sha256": file_sha256(FIXED), "original_binary_sha256": file_sha256(ORIGINAL), "fixtures": {}}
    with tempfile.TemporaryDirectory() as tmp:
        for name, ids in fixtures().items():
            trace = Path(tmp) / f"{name}.oracleGeneral"
            write(trace, ids)
            fixed, original = agrees(replay(FIXED, trace), ids), agrees(replay(ORIGINAL, trace), ids)
            receipt["fixtures"][name] = {"requests": int(len(ids)), "fixed_build_compared_requests": fixed,
                                         "original_build_first_mismatch_or_count": original}
    ok_fixed = all(v["fixed_build_compared_requests"] == v["requests"] for v in receipt["fixtures"].values())
    detects = any(v["original_build_first_mismatch_or_count"] < 0 for v in receipt["fixtures"].values())
    receipt["corrected_build_matches_model_everywhere"] = ok_fixed
    receipt["original_build_mismatches_corrected_model_somewhere"] = detects
    RECEIPT.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n")
    print(json.dumps(receipt, indent=1, sort_keys=True))
    if not (ok_fixed and detects):
        raise SystemExit("verification failed")


if __name__ == "__main__":
    main()
