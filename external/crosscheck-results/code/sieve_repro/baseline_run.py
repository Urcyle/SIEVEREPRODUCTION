"""Separately identified seeded online-baseline replays.

The earlier observer runner remains frozen. This family records admission,
policy defaults and the RNG lifecycle, and checks cached logs before reuse.
"""
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time

from .core import capacity_for
from .run import GIB, _atomic_record, check_memory, file_sha256, mem_available_bytes, parse_sim_output, run_id

COMMIT = "0861f8261c37b8286a70449a1defb5a4749c72d2"
LIFECYCLE = "seed-before-initialization;continue-into-single-cache-replay"
POLICIES = {
    "twoq": {"cli": "2q", "output": "TwoQ", "eviction_params": "Ain-size-ratio=0.25,Aout-size-ratio=0.5"},
    "lirs": {"cli": "lirs", "output": "LIRS", "source_defaults": {"hirs_ratio": 0.01}},
    "tinylfu_snapshot": {"cli": "wtinylfu", "output": "WTinyLFU-w0.01-SLRU", "eviction_params": "main-cache=SLRU,window-size=0.01"},
    "blru": {"cli": "lru", "output": "LRU", "admission": "bloom-filter", "admission_implementation": "growing GLib seen-ID hash table"},
    "hyperbolic": {"cli": "hyperbolic", "output": "Hyperbolic", "eviction_params": "n-sample=64"},
    "lhd": {"cli": "lhd", "output": "LHD", "source_defaults": {"associativity": 32, "admissions": 8, "explorer_fraction": 0.01, "explore_inverse_probability": 32}},
    "cacheus": {"cli": "cacheus", "output": "Cacheus", "source_defaults": {"ghost_factor": 1, "starting_weights": [0.5, 0.5], "update_interval": "C", "starting_learning_rate": "0.001 + (next_rand()%1000)/1000"}},
    "sieve_anchor": {"cli": "sieve", "output": "Sieve"},
    # Core policies, available through this runner so that large sampled-WSS files can use an explicit exact capacity
    # (twitter sample10 extension, docs/twitter_sample10_extension_protocol.md, amendment 1).
    "fifo": {"cli": "fifo", "output": "FIFO"},
    "lru": {"cli": "lru", "output": "LRU"},
    "clock": {"cli": "clock", "output": "Clock"},
    "sieve": {"cli": "sieve", "output": "Sieve"},
    "arc": {"cli": "arc", "output": "ARC"},
}


def parse_rng(output, seed):
    lines = [line for line in output.splitlines() if line.startswith("SIEVE_RNG")]
    if len(lines) != 1 or not lines[0].startswith("SIEVE_RNG "):
        raise ValueError("missing, duplicate, or malformed RNG identity")
    record = json.loads(lines[0][len("SIEVE_RNG "):])
    expected = {"seed", "state_before_replay", "lifecycle", "rng", "source_commit"}
    if (set(record) != expected or type(record["seed"]) is not int or record["seed"] != seed or
            type(record["state_before_replay"]) is not int or not 0 <= record["state_before_replay"] < 2**64 or
            record["lifecycle"] != LIFECYCLE or record["rng"] != "MMIX-LCG64" or record["source_commit"] != COMMIT):
        raise ValueError("RNG seed/lifecycle/source mismatch")
    return record


def parse_baseline_output(output, expected_policy, fraction, *, capacity_objects=None,
                          expected_unique_objects=None, allow_sampled_wss_mismatch=False):
    # The frozen first-slice regex excludes dots. Verify the exact raw policy
    # token, then reuse its counter/capacity checks with an internal placeholder.
    # The saved raw log and returned policy retain the actual artifact name.
    prefix = f"SIEVE_COUNTERS policy={expected_policy} "
    normalized = []
    for line in output.splitlines():
        if line.startswith("SIEVE_COUNTERS"):
            if not line.startswith(prefix):
                raise ValueError("unexpected exact-counter policy name or framing")
            line = "SIEVE_COUNTERS policy=SeededBaseline " + line[len(prefix):]
        normalized.append(line)
    result = parse_sim_output("\n".join(normalized), "SeededBaseline", fraction,
                              capacity_objects=capacity_objects,
                              expected_unique_objects=expected_unique_objects,
                              allow_sampled_wss_mismatch=allow_sampled_wss_mismatch)
    result["policy"] = expected_policy
    return result


def validate_record(record, expected_spec):
    if record.get("status") != "complete" or record.get("exit_code") != 0 or record.get("spec") != expected_spec:
        raise ValueError("stale or unsuccessful seeded baseline record")
    path = Path(record["log"])
    if file_sha256(path) != record["log_sha256"]:
        raise ValueError("seeded baseline raw log changed")
    output = path.read_text()
    rng = parse_rng(output, expected_spec["rng_seed"])
    if rng != record["rng_identity"]:
        raise ValueError("saved RNG identity differs from raw output")
    exact_capacity = expected_spec.get("capacity_objects")
    exact = parse_baseline_output(
        output, expected_spec["policy_configuration"]["output"],
        expected_spec["capacity_fraction"], capacity_objects=exact_capacity,
        expected_unique_objects=expected_spec["expected_unique_objects"] if exact_capacity is not None else None,
        allow_sampled_wss_mismatch=exact_capacity is not None)
    if any(record.get(k) != v for k, v in exact.items()):
        raise ValueError("saved counters differ from raw output")
    expected_capacity = (exact_capacity if exact_capacity is not None else
                         capacity_for(record["unique_objects"], expected_spec["capacity_fraction"]))
    if (record["unique_objects"] != expected_spec["expected_unique_objects"] or
            record["n_req"] != expected_spec["expected_requests"] or
            record["cache_size"] != expected_capacity):
        raise ValueError("seeded baseline input count/footprint/capacity mismatch")
    if any(record.get(k) != v for k, v in expected_spec.get("expected_counters", {}).items()):
        raise ValueError("seeded anchor differs from its original production reference")
    if (record["available_before_bytes"] - record["estimated_peak_bytes"] < 4 * GIB or
            record["peak_rss_kib"] * 1024 > 12 * GIB):
        raise ValueError("seeded baseline resource gate violated")


def process_tree_rss(pid):
    """Best-effort live RSS sum; exact Linux peak comes from os.wait4."""
    total = 0
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                total = int(line.split()[1]) * 1024
        children = Path(f"/proc/{pid}/task/{pid}/children").read_text().split()
        total += sum(process_tree_rss(int(child)) for child in children)
    except (FileNotFoundError, ProcessLookupError):
        pass
    return total


def stop_process(process):
    """Reap even if a child exits between status check and termination."""
    if process is None or process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def run_baseline(*, trace, metadata, policy, fraction, seed, binary, output_root, manifest_hash,
                 expected_counters=None, estimated_peak_bytes=3 * GIB, capacity_objects=None):
    if policy not in POLICIES or type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError("unsupported policy or RNG seed")
    trace, binary, output_root = Path(trace).resolve(), Path(binary).resolve(), Path(output_root)
    if file_sha256(trace) != metadata["sha256"]:
        raise ValueError("public input changed since its validated manifest")
    if (capacity_objects is not None and
            (type(capacity_objects) is not int or capacity_objects <= 0 or
             capacity_objects != capacity_for(metadata["unique_objects"], fraction))):
        raise ValueError("explicit object capacity must equal floor(unique_objects × fraction)")
    config = POLICIES[policy]
    spec = {"family": "seeded-online-baselines", "artifact_commit": COMMIT,
            "binary_sha256": file_sha256(binary), "trace_sha256": metadata["sha256"],
            "trace_label": metadata["label"], "policy_label": policy, "policy_configuration": config,
            "capacity_fraction": fraction, "ignore_object_size": True, "warmup_seconds": -1,
            "threads": 1, "rng_seed": seed, "rng_lifecycle": LIFECYCLE,
            "expected_requests": metadata["record_count"] - metadata["zero_size_count"],
            "expected_unique_objects": metadata["unique_objects"],
            "runner_sha256": file_sha256(Path(__file__)), "configuration_manifest_sha256": manifest_hash,
            "seed_patch_sha256": file_sha256(Path(__file__).resolve().parents[1] / "patches/controlled-seed.patch")}
    if capacity_objects is not None:
        spec["capacity_objects"] = capacity_objects
    if metadata.get("unique_wss_reference_run_ids"):
        spec["unique_wss_reference_run_ids"] = sorted(metadata["unique_wss_reference_run_ids"])
    if expected_counters:
        spec["expected_counters"] = expected_counters
    identity = run_id(spec)
    folder = output_root / "runs" / identity
    folder.mkdir(parents=True, exist_ok=True)
    with (output_root / ".simulation.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        completed = folder / "complete.json"
        if completed.exists():
            record = json.loads(completed.read_text())
            validate_record(record, spec)
            return record
        available = mem_available_bytes()
        configured_capacity = str(fraction if capacity_objects is None else capacity_objects)
        command = [str(binary), str(trace), "oracleGeneral", config["cli"], configured_capacity,
                   "--ignore-obj-size", "1", "--num-thread", "1", "--warmup-sec", "-1"]
        if "eviction_params" in config:
            command += ["--eviction-params", config["eviction_params"]]
        if "admission" in config:
            command += ["--admission", config["admission"]]
        attempt = 1
        while (folder / f"attempt-{attempt:04d}.json").exists():
            attempt += 1
        prefix = folder / f"attempt-{attempt:04d}"
        log = prefix.with_suffix(".log")
        env = {k: v for k, v in os.environ.items() if not k.startswith("SIEVE_OBSERVER_") and k != "SIEVE_FIXTURE_STATE"}
        env["SIEVE_RNG_SEED"] = str(seed)
        record = {"run_id": identity, "spec": spec, "attempt": attempt, "command": command,
                  "environment": {"SIEVE_RNG_SEED": str(seed)}, "available_before_bytes": available,
                  "estimated_peak_bytes": estimated_peak_bytes, "log": str(log),
                  "resource_measurement_method": "Linux os.wait4 ru_maxrss; live proc-tree RSS sampled every 0.25s",
                  "started_at_utc": datetime.now(timezone.utc).isoformat(), "status": "running"}
        _atomic_record(prefix.with_suffix(".json"), record)
        start = time.monotonic()
        process = None
        observed_peak = 0
        last_mem_available = None
        live_guard_reason = None
        try:
            # Shared guard prevents concurrent jobs in this experiment family.
            with (log.open("w") as output,
                  tempfile.TemporaryDirectory(prefix="sieve-baselines-", dir=output_root) as scratch):
                record["available_before_bytes"] = mem_available_bytes()
                check_memory(record["available_before_bytes"], estimated_peak_bytes)
                process = subprocess.Popen(command, cwd=scratch, stdout=output,
                                           stderr=subprocess.STDOUT, env=env, start_new_session=True)
                while True:
                    finished, status, usage = os.wait4(process.pid, os.WNOHANG)
                    if finished:
                        process.returncode = os.waitstatus_to_exitcode(status)
                        record["peak_rss_kib"] = usage.ru_maxrss
                        break
                    observed_peak = max(observed_peak, process_tree_rss(process.pid))
                    last_mem_available = mem_available_bytes()
                    if observed_peak > 12 * GIB:
                        live_guard_reason = "process-tree RSS exceeded 12 GiB"
                    elif last_mem_available < 4 * GIB:
                        live_guard_reason = "available system RAM fell below 4 GiB"
                    if live_guard_reason is not None:
                        raise MemoryError("live RSS/headroom gate crossed; preserving failed attempt")
                    time.sleep(0.25)
                record.update(exit_code=process.returncode, elapsed_seconds=time.monotonic() - start,
                              sampled_process_tree_peak_bytes=observed_peak)
            if record["exit_code"] != 0:
                raise RuntimeError(f"simulator exited {record['exit_code']}")
            output = log.read_text()
            exact = parse_baseline_output(
                output, config["output"], fraction, capacity_objects=capacity_objects,
                expected_unique_objects=metadata["unique_objects"] if capacity_objects is not None else None,
                allow_sampled_wss_mismatch=capacity_objects is not None)
            record.update(exact, rng_identity=parse_rng(output, seed), log_sha256=file_sha256(log),
                          status="complete", finished_at_utc=datetime.now(timezone.utc).isoformat())
            validate_record(record, spec)
        except BaseException as error:
            stop_process(process)
            record.update(status="failed", error=f"{type(error).__name__}: {error}",
                          elapsed_seconds=time.monotonic() - start, exit_code=process.returncode if process else None,
                          finished_at_utc=datetime.now(timezone.utc).isoformat())
            if observed_peak:
                record["sampled_process_tree_peak_bytes"] = observed_peak
            if last_mem_available is not None:
                record["mem_available_at_last_live_check_bytes"] = last_mem_available
            if live_guard_reason is not None:
                record["live_guard_reason"] = live_guard_reason
            _atomic_record(prefix.with_suffix(".json"), record)
            raise
        _atomic_record(prefix.with_suffix(".json"), record)
        _atomic_record(completed, record)
        return record
