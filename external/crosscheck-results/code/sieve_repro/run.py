"""One-config-at-a-time simulator runs with exact counters and durable records."""

from datetime import datetime, timezone
from hashlib import sha256
import csv
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time

from .core import capacity_for, parse_counters
from .observer import parse_observer_output


GIB = 1024 ** 3
WSS = re.compile(r"working set size:\s*(\d+) object")
POLICIES = {"fifo": "FIFO", "lru": "LRU", "clock": "Clock", "sieve": "Sieve",
            "lfu": "LFU", "arc": "ARC", "twoq": "TwoQ", "lecar": "LeCaR",
            "arc_sieve": "ARC-SIEVE", "twoq_sieve": "TwoQ-SIEVE",
            "lecar_sieve": "LeCaR-SIEVE"}
SIMULATOR_ALGORITHMS = {"arc_sieve": "arc", "twoq_sieve": "twoq",
                        "lecar_sieve": "lecar"}
REQUIRED_VARIANT_PARAMS = {"arc_sieve": "T2-type=SIEVE", "twoq_sieve": "Am-type=SIEVE",
                           "lecar_sieve": "lru-type=SIEVE"}


def build_simulator_command(*, binary: Path, trace: Path, policy: str,
                            fraction: float | None, capacity_objects: int | None,
                            eviction_params: str | None = None) -> list[str]:
    if policy not in POLICIES:
        raise ValueError("unsupported policy")
    required = REQUIRED_VARIANT_PARAMS.get(policy)
    if required is not None and eviction_params != required:
        raise ValueError(f"{policy} requires eviction parameters {required}")
    if policy in {"arc", "arc_sieve"} and eviction_params not in (None, "T2-type=LRU", "T2-type=SIEVE"):
        raise ValueError("ARC accepts only T2-type=LRU or T2-type=SIEVE")
    if policy in {"twoq", "twoq_sieve"} and eviction_params not in (None, "Am-type=LRU", "Am-type=SIEVE"):
        raise ValueError("TwoQ accepts only Am-type=LRU or Am-type=SIEVE")
    if policy in {"lecar", "lecar_sieve"} and eviction_params not in (
            None, "lru-type=LRU", "lru-type=SIEVE"):
        raise ValueError("LeCaR accepts only lru-type=LRU or lru-type=SIEVE")
    if policy == "arc" and eviction_params == "T2-type=SIEVE":
        raise ValueError("use policy=arc_sieve for the SIEVE T2 variant")
    if policy == "twoq" and eviction_params == "Am-type=SIEVE":
        raise ValueError("use policy=twoq_sieve for the SIEVE Am variant")
    if policy == "lecar" and eviction_params == "lru-type=SIEVE":
        raise ValueError("use policy=lecar_sieve for the SIEVE LRU-expert variant")
    size = fraction if capacity_objects is None else capacity_objects
    if size is None:
        raise ValueError("choose a fractional or absolute object capacity")
    command = [str(binary), str(trace), "oracleGeneral",
               SIMULATOR_ALGORITHMS.get(policy, policy), str(size),
               "--ignore-obj-size", "1", "--num-thread", "1", "--warmup-sec", "-1"]
    if eviction_params is not None:
        command.extend(["--eviction-params", eviction_params])
    return command


def mem_available_bytes() -> int:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    raise RuntimeError("MemAvailable not found")


def process_tree_rss_bytes(pid: int) -> int:
    """Sample a Linux process and its current children, independent of parent high-water RSS."""
    total = 0
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                total += int(line.split()[1]) * 1024
                break
        children = Path(f"/proc/{pid}/task/{pid}/children").read_text().split()
        total += sum(process_tree_rss_bytes(int(child)) for child in children)
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        pass
    return total


def check_memory(available_bytes: int, estimated_peak_bytes: int,
                 *, headroom_bytes: int = 4 * GIB) -> None:
    if estimated_peak_bytes <= 0 or estimated_peak_bytes > 12 * GIB:
        raise ValueError("estimate exceeds the 12 GiB soft experiment budget")
    if available_bytes - estimated_peak_bytes < headroom_bytes:
        raise MemoryError(
            f"need {(estimated_peak_bytes + headroom_bytes) / GIB:.2f} GiB available; "
            f"have {available_bytes / GIB:.2f} GiB"
        )


def run_id(spec: dict) -> str:
    return sha256(json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def parse_sim_output(output: str, expected_policy: str, fraction: float | None,
                     capacity_objects: int | None = None,
                     expected_unique_objects: int | None = None,
                     allow_sampled_wss_mismatch: bool = False) -> dict:
    records = [parse_counters(line) for line in output.splitlines()
               if line.startswith("SIEVE_COUNTERS")]
    if len(records) != 1 or records[0]["policy"] != expected_policy:
        raise ValueError("simulator did not emit exactly one matching exact-counter record")
    record = records[0]
    if record["n_req"] <= 0 or record["cache_size"] <= 0:
        raise ValueError("empty run or zero cache capacity")
    matches = WSS.findall(output)
    if len(matches) > 1:
        raise ValueError("working-set footprint is ambiguous")
    reported_footprint = int(matches[0]) if matches else None
    if capacity_objects is None:
        if reported_footprint is None:
            raise ValueError("working-set footprint missing or ambiguous")
        footprint = reported_footprint
        expected_size = capacity_for(footprint, fraction)
    else:
        if expected_unique_objects is None or expected_unique_objects <= 0:
            raise ValueError("absolute-capacity run needs an independent unique-object count")
        footprint = expected_unique_objects
        if (reported_footprint is not None and reported_footprint != footprint and
                not allow_sampled_wss_mismatch):
            raise ValueError("simulator and independent unique-object counts differ")
        expected_size = capacity_objects
    if record["cache_size"] != expected_size:
        raise ValueError("simulator capacity differs from configured object capacity")
    record["unique_objects"] = footprint
    if allow_sampled_wss_mismatch and reported_footprint is not None:
        record["artifact_reported_unique_objects"] = reported_footprint
    return record


def _atomic_record(path: Path, record: dict) -> None:
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w") as output:
        json.dump(record, output, indent=2, sort_keys=True)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    os.replace(temp, path)


def file_sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as input_file:
        while block := input_file.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def validate_sampled_wss_spec(spec: dict, unique_objects: int, result_root: Path) -> bool:
    """Permit artifact WSS mismatch only for a run bound to its exact saved scan."""
    marker = spec.get("artifact_reported_wss")
    special_fields = {"exact_wss_method", "exact_wss_scan_record_sha256",
                      "artifact_reported_wss"}
    if marker is None:
        if special_fields.intersection(spec):
            raise ValueError("partial sampled-WSS identity in run specification")
        return False
    scan_hash = spec.get("exact_wss_scan_record_sha256")
    workload = spec.get("workload_label")
    sampled_workloads = {
        "wiki_2019t": ("wiki_2019t_external_unique_scan.json", "wiki_2019t_trace.json"),
        "twitter_cluster50": ("twitter_cluster50_external_unique_scan.json",
                              "twitter_cluster50_trace.json"),
        "twitter_cluster53": ("twitter_cluster53_external_unique_scan.json",
                              "twitter_cluster53_trace.json"),
        "twitter_cluster45": ("twitter_cluster45_external_unique_scan.json",
                              "twitter_cluster45_trace.json"),
        "twitter_cluster3": ("twitter_cluster3_external_unique_scan.json",
                             "twitter_cluster3_trace.json"),
        "twitter_cluster49": ("twitter_cluster49_external_unique_scan.json",
                              "twitter_cluster49_trace.json"),
        "twitter_cluster35": ("twitter_cluster35_external_unique_scan.json",
                              "twitter_cluster35_trace.json"),
        "twitter_cluster7": ("twitter_cluster7_external_unique_scan.json",
                              "twitter_cluster7_trace.json"),
        "twitter_cluster13": ("twitter_cluster13_external_unique_scan.json",
                              "twitter_cluster13_trace.json"),
        "twitter_cluster8": ("twitter_cluster8_external_unique_scan.json",
                             "twitter_cluster8_trace.json"),
        "twitter_cluster31": ("twitter_cluster31_elias_fano_unique_scan.json",
                              "twitter_cluster31_trace.json"),
        "twitter_cluster39": ("twitter_cluster39_elias_fano_unique_scan.json",
                              "twitter_cluster39_trace.json"),
        "twitter_cluster48": ("twitter_cluster48_elias_fano_unique_scan.json",
                              "twitter_cluster48_trace.json"),
        "twitter_cluster38": ("twitter_cluster38_elias_fano_unique_scan.json",
                              "twitter_cluster38_trace.json"),
        "twitter_cluster21": ("twitter_cluster21_elias_fano_unique_scan.json",
                              "twitter_cluster21_trace.json"),
        "metakv_trace1_candidate": ("metakv_trace1_candidate_unique_scan.json",
                                     "metakv_trace1_candidate_trace.json"),
        "metakv_202210": ("metakv_202210_elias_fano_unique_scan.json",
                           "metakv_202210_trace.json"),
        "metakv_202206": ("metakv_202206_elias_fano_unique_scan.json",
                           "metakv_202206_trace.json")}
    if (marker != "diagnostic_only" or workload not in sampled_workloads or
            spec.get("exact_wss_method") != "bounded_external_scan" or
            "capacity_objects" not in spec or type(unique_objects) is not int or unique_objects <= 0 or
            not isinstance(scan_hash, str) or len(scan_hash) != 64 or
            any(char not in "0123456789abcdef" for char in scan_hash)):
        raise ValueError("sampled artifact WSS is not bound to an externally scanned run")
    result_root = Path(result_root)
    scan_name, trace_name = sampled_workloads[workload]
    scan_path = result_root / "verification" / scan_name
    trace_path = result_root / trace_name
    if scan_path.is_file() and file_sha256(scan_path) == scan_hash:
        pass
    else:
        # Keep runs verifiable when a later acquisition/storage refresh replaces
        # the current scan metadata. Historical pairs are immutable and keyed by
        # the scan hash already embedded in the run specification.
        archive = result_root / "verification/historical_scan_records"
        archived_scan = archive / f"{scan_hash}.scan.json"
        archived_trace = archive / f"{scan_hash}.trace.json"
        if (not archived_scan.is_file() or not archived_trace.is_file() or
                file_sha256(archived_scan) != scan_hash):
            raise ValueError("exact-WSS scan record is missing or has changed")
        scan_path, trace_path = archived_scan, archived_trace
    if not trace_path.is_file():
        raise ValueError("exact-WSS scan record is missing or has changed")
    scan = json.loads(scan_path.read_text())
    trace = json.loads(trace_path.read_text())
    if (scan.get("status") != "passed" or
            scan.get("trace_stored_sha256") != spec.get("trace_sha256") or
            scan.get("trace_stream_sha256") != trace.get("stream_sha256") or
            trace.get("sha256") != spec.get("trace_sha256") or
            scan.get("schema_scan_record_sha256") != file_sha256(trace_path) or
            scan.get("working_set", {}).get("unique_objects") != unique_objects or
            scan.get("trace_schema", {}).get("record_count") != trace.get("record_count") or
            scan.get("trace_schema", {}).get("zero_size_count") != trace.get("zero_size_count")):
        raise ValueError("exact-WSS scan does not match the validated trace record")
    return True


def run_one(*, trace: Path, trace_meta: dict, policy: str, fraction: float | None,
            binary: Path, output_root: Path, estimated_peak_bytes: int,
            workload_label: str, capacity_objects: int | None = None,
            eviction_params: str | None = None, rng_seed: int | None = None,
            policy_state_debug: bool = False,
            observer: dict | None = None,
            expected_counters: dict | None = None) -> dict:
    if policy not in POLICIES:
        raise ValueError("unsupported policy")
    if fraction is None and capacity_objects is None:
        raise ValueError("choose a fractional or absolute object capacity")
    if capacity_objects is not None and capacity_objects <= 0:
        raise ValueError("absolute object capacity must be positive")
    if fraction is not None and not 0 < fraction <= 1:
        raise ValueError("capacity fraction must be in (0, 1]")
    if rng_seed is not None and (type(rng_seed) is not int or not 0 <= rng_seed < 2**64):
        raise ValueError("RNG seed must be a uint64 integer")
    if type(policy_state_debug) is not bool or (policy_state_debug and policy != "lecar_sieve"):
        raise ValueError("policy-state debug is available only for LeCaR-SIEVE")
    if capacity_objects is not None and fraction is not None:
        unique_objects = trace_meta.get("unique_objects")
        if (type(unique_objects) is not int or unique_objects <= 0 or
                capacity_objects != capacity_for(unique_objects, fraction)):
            raise ValueError("absolute capacity does not match the labeled fraction of exact unique objects")
    trace, binary, output_root = Path(trace).resolve(), Path(binary).resolve(), Path(output_root)
    if not trace.is_file() or not binary.is_file():
        raise FileNotFoundError("trace or simulator binary missing")
    trace_digest = trace_meta["sha256"]
    binary_digest = file_sha256(binary)
    spec = {"artifact_commit": "0861f8261c37b8286a70449a1defb5a4749c72d2",
            "binary_sha256": binary_digest, "trace_sha256": trace_digest,
            "policy": policy,
            "workload_label": workload_label, "warmup_seconds": -1,
            "ignore_object_size": True, "threads": 1}
    if eviction_params is not None:
        spec["eviction_params"] = eviction_params
    if rng_seed is not None:
        spec["rng_seed"] = rng_seed
    if policy_state_debug:
        spec["policy_state_debug"] = True
    # Validate command/policy compatibility before creating a run directory.
    build_simulator_command(binary=binary, trace=trace, policy=policy,
                            fraction=fraction, capacity_objects=capacity_objects,
                            eviction_params=eviction_params)
    allow_sampled_wss_mismatch = trace_meta.get("artifact_wss_may_be_sampled") is True
    if allow_sampled_wss_mismatch:
        scan_hash = trace_meta.get("unique_scan_record_sha256")
        if (workload_label not in {"wiki_2019t", "twitter_cluster50", "twitter_cluster53",
                                   "twitter_cluster45", "twitter_cluster3",
                                   "twitter_cluster49", "twitter_cluster35",
                                   "twitter_cluster7", "twitter_cluster13", "twitter_cluster8",
                                   "twitter_cluster31",
                                   "twitter_cluster39",
                                   "twitter_cluster48",
                                   "twitter_cluster38", "twitter_cluster21",
                                   "metakv_trace1_candidate", "metakv_202210",
                                   "metakv_202206"} or
                capacity_objects is None or
                type(trace_meta.get("unique_objects")) is not int or
                not isinstance(scan_hash, str) or len(scan_hash) != 64 or
                any(char not in "0123456789abcdef" for char in scan_hash)):
            raise ValueError("sampled artifact WSS is permitted only for an externally scanned run")
        spec["exact_wss_method"] = "bounded_external_scan"
        spec["exact_wss_scan_record_sha256"] = scan_hash
        spec["artifact_reported_wss"] = "diagnostic_only"
    if capacity_objects is not None:
        spec["capacity_objects"] = capacity_objects
    if fraction is not None:
        spec["capacity_fraction"] = fraction
    allow_sampled_wss_mismatch = validate_sampled_wss_spec(
        spec, trace_meta.get("unique_objects"), output_root)
    observer_env = {}
    if observer is not None:
        allowed = {"interval", "hand_interval", "hotset_path", "hotset_next_path",
                   "switch_after", "baseline_run_id", "hotset_definition"}
        if set(observer) - allowed or type(observer.get("interval")) is not int or observer["interval"] <= 0:
            raise ValueError("invalid observer configuration")
        observer_spec = {"interval": observer["interval"],
                         "runner_sha256": file_sha256(Path(__file__)),
                         "validator_sha256": file_sha256(Path(__file__).with_name("observer.py")),
                         "patch_sha256": file_sha256(Path(__file__).resolve().parents[1] /
                                                      "patches/periodic-observer.patch")}
        observer_env["SIEVE_OBSERVER_INTERVAL"] = str(observer["interval"])
        for key, variable in (("hand_interval", "SIEVE_OBSERVER_HAND_INTERVAL"),
                              ("switch_after", "SIEVE_OBSERVER_SWITCH_AFTER")):
            if key in observer:
                if type(observer[key]) is not int or observer[key] <= 0:
                    raise ValueError(f"invalid observer {key}")
                observer_spec[key] = observer[key]
                observer_env[variable] = str(observer[key])
        if "hand_interval" in observer and policy != "sieve":
            raise ValueError("hand observation is SIEVE-specific")
        if ("hotset_next_path" in observer) != ("switch_after" in observer):
            raise ValueError("phase switch needs both the next hot set and a boundary")
        for key, variable, identity_key in (
                ("hotset_path", "SIEVE_OBSERVER_HOTSET", "hotset_sha256"),
                ("hotset_next_path", "SIEVE_OBSERVER_HOTSET_NEXT", "hotset_next_sha256")):
            if key in observer:
                path = Path(observer[key]).resolve()
                observer_spec[identity_key] = file_sha256(path)
                observer_env[variable] = str(path)
        for key in ("baseline_run_id", "hotset_definition"):
            if key in observer:
                observer_spec[key] = observer[key]
        spec["observer"] = observer_spec
    if expected_counters is not None:
        if set(expected_counters) != {"cache_size", "n_req", "n_miss", "n_req_byte", "n_miss_byte"}:
            raise ValueError("reference comparison needs all five exact counters")
        spec["expected_counters"] = expected_counters
    identity = run_id(spec)
    run_dir = output_root / "runs" / identity
    run_dir.mkdir(parents=True, exist_ok=True)
    complete = run_dir / "complete.json"
    if complete.exists():
        record = json.loads(complete.read_text())
        if record.get("spec") != spec or record.get("status") != "complete":
            raise ValueError("stale or mismatched completed run")
        if record.get("exit_code") != 0:
            raise ValueError("cached completion has no successful exit")
        if expected_counters is not None and any(record.get(k) != v for k, v in expected_counters.items()):
            raise ValueError("cached exact counters differ from their reference")
        raw_log = Path(record.get("log", ""))
        if not raw_log.is_file():
            raise ValueError("cached raw log is missing")
        recorded_log_hash = record.get("log_sha256")
        if recorded_log_hash is not None and file_sha256(raw_log) != recorded_log_hash:
            raise ValueError("cached raw log hash differs from completion record")
        output = raw_log.read_text(errors="replace")
        exact = parse_sim_output(output, POLICIES[policy], fraction, capacity_objects,
                                 trace_meta.get("unique_objects"),
                                 allow_sampled_wss_mismatch=allow_sampled_wss_mismatch)
        if any(record.get(k) != v for k, v in exact.items()):
            raise ValueError("cached counters differ from their raw log")
        if observer is not None:
            saved = Path(record.get("observations_path", ""))
            if not saved.is_file() or file_sha256(saved) != record.get("observations_sha256"):
                raise ValueError("saved observation file missing or changed")
            if recorded_log_hash is None:
                raise ValueError("saved raw observation log missing or changed")
            output = raw_log.read_text(errors="strict")
            observations = parse_observer_output(
                output, n_req=exact["n_req"], n_miss=exact["n_miss"], cache_size=exact["cache_size"],
                interval=observer["interval"], hand_interval=observer.get("hand_interval"),
                switch_after=observer.get("switch_after"), policy=policy,
                has_hotset="hotset_path" in observer)
            with saved.open(newline="") as input_file:
                saved_rows = list(csv.DictReader(input_file))
            expected_rows = [{k: "" if v is None else str(v) for k, v in row.items()}
                             for row in observations]
            if saved_rows != expected_rows or len(observations) != record.get("observation_count"):
                raise ValueError("cached CSV differs from its validated raw observations")
        return record

    check_memory(mem_available_bytes(), estimated_peak_bytes)

    attempt = 1
    while (run_dir / f"attempt-{attempt:04d}.json").exists():
        attempt += 1
    log_path = run_dir / f"attempt-{attempt:04d}.log"
    command = build_simulator_command(binary=binary, trace=trace, policy=policy,
                                      fraction=fraction, capacity_objects=capacity_objects,
                                      eviction_params=eviction_params)
    record = {"run_id": identity, "attempt": attempt, "spec": spec,
              "command": command, "log": str(log_path.resolve()),
              "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "status": "running", "available_before_bytes": mem_available_bytes(),
              "estimated_peak_bytes": estimated_peak_bytes,
              "raw_record_count": trace_meta["record_count"],
              "zero_size_count": trace_meta["zero_size_count"],
              "trace_storage": {"path": str(trace),
                                "sha256": trace_meta.get("stored_sha256", file_sha256(trace)),
                                "stream_sha256": trace_meta.get("stream_sha256", trace_digest),
                                "stored_bytes": trace.stat().st_size,
                                "format": trace_meta.get("storage_format",
                                                          "zstd" if trace.suffix == ".zst" else "raw")}}
    if observer is not None:
        record["observer_environment"] = observer_env
    _atomic_record(run_dir / f"attempt-{attempt:04d}.json", record)
    proc = None
    sampled_peak_rss_bytes = 0
    wait4_peak_rss_kib = None
    start = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix="sieve-run-") as cwd:
            with log_path.open("w") as log:
                environment = {k: v for k, v in os.environ.items()
                               if not k.startswith("SIEVE_OBSERVER_") and
                               k not in {"SIEVE_FIXTURE_STATE", "SIEVE_RNG_SEED",
                                         "LIBCACHESIM_DEBUG_LECAR_SIEVE"}}
                environment.update(observer_env)
                if rng_seed is not None:
                    environment["SIEVE_RNG_SEED"] = str(rng_seed)
                if policy_state_debug:
                    environment["LIBCACHESIM_DEBUG_LECAR_SIEVE"] = "1"
                proc = subprocess.Popen(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                        env=environment, start_new_session=True)
                while True:
                    sampled_peak_rss_bytes = max(sampled_peak_rss_bytes,
                                                 process_tree_rss_bytes(proc.pid))
                    finished, status, usage = os.wait4(proc.pid, os.WNOHANG)
                    if finished:
                        proc.returncode = os.waitstatus_to_exitcode(status)
                        wait4_peak_rss_kib = usage.ru_maxrss
                        break
                    if sampled_peak_rss_bytes > 12 * GIB:
                        raise MemoryError("live process-tree RSS crossed the 12 GiB soft experiment limit")
                    if mem_available_bytes() < 4 * GIB:
                        raise MemoryError("live MemAvailable crossed the 4 GiB experiment headroom")
                    time.sleep(0.1)
    except BaseException as error:
        if proc is not None and proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=5)
            except ProcessLookupError:
                proc.wait()
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
        record.update({"status": "failed", "error": str(error),
                       "exit_code": proc.returncode if proc is not None else None,
                       "elapsed_seconds": time.monotonic() - start,
                       "sampled_peak_rss_kib": (sampled_peak_rss_bytes + 1023) // 1024,
                       "finished_at_utc": datetime.now(timezone.utc).isoformat()})
        _atomic_record(run_dir / f"attempt-{attempt:04d}.json", record)
        raise
    elapsed = time.monotonic() - start
    record.update({"exit_code": proc.returncode, "elapsed_seconds": elapsed,
                   "peak_rss_kib": ((sampled_peak_rss_bytes + 1023) // 1024
                                    if sampled_peak_rss_bytes else wait4_peak_rss_kib),
                   "wait4_reported_peak_rss_kib": wait4_peak_rss_kib,
                   "resource_measurement_method":
                       "Linux /proc process-tree RSS sampled every 0.1s; wait4 ru_maxrss retained separately",
                   "finished_at_utc": datetime.now(timezone.utc).isoformat()})
    record["log_sha256"] = file_sha256(log_path)
    try:
        if proc.returncode != 0:
            raise RuntimeError(f"simulator exit {proc.returncode}")
        output = log_path.read_text(errors="replace")
        exact = parse_sim_output(output, POLICIES[policy],
                                 fraction, capacity_objects,
                                 trace_meta.get("unique_objects"),
                                 allow_sampled_wss_mismatch=allow_sampled_wss_mismatch)
        if exact["n_req"] != trace_meta["record_count"] - trace_meta["zero_size_count"]:
            raise ValueError("simulated request count differs from validated reader semantics")
        if expected_counters is not None and any(exact[k] != v for k, v in expected_counters.items()):
            raise ValueError("observation build changed the reference exact counters")
        if observer is not None:
            observations = parse_observer_output(
                output, n_req=exact["n_req"], n_miss=exact["n_miss"],
                cache_size=exact["cache_size"], interval=observer["interval"],
                hand_interval=observer.get("hand_interval"),
                switch_after=observer.get("switch_after"), policy=policy,
                has_hotset="hotset_path" in observer)
            samples_path = run_dir / f"attempt-{attempt:04d}.csv"
            temporary = samples_path.with_suffix(".csv.tmp")
            with temporary.open("w", newline="") as output_file:
                writer = csv.DictWriter(output_file, fieldnames=list(observations[0]),
                                        lineterminator="\n")
                writer.writeheader()
                writer.writerows(observations)
                output_file.flush()
                os.fsync(output_file.fileno())
            os.replace(temporary, samples_path)
            record.update({"observations_path": str(samples_path.resolve()),
                           "observations_sha256": file_sha256(samples_path),
                           "observation_count": len(observations)})
        record.update(exact)
        record["status"] = "complete"
        _atomic_record(complete, record)
    except Exception as error:
        record["status"] = "failed"
        record["error"] = str(error)
        _atomic_record(run_dir / f"attempt-{attempt:04d}.json", record)
        raise
    _atomic_record(run_dir / f"attempt-{attempt:04d}.json", record)
    return record
