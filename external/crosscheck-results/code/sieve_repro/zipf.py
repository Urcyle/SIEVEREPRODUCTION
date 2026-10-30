"""Seeded finite-support Zipf generator using the artifact's packed record layout."""

from pathlib import Path
import hashlib
import os
import math
import subprocess
import threading

import numpy as np


RECORD_DTYPE = np.dtype([("time", "<u4"), ("id", "<u8"), ("size", "<u4"), ("next", "<i8")])


def generate_zipf(path: Path, *, objects: int, requests: int, alpha: float,
                  seed: int, batch_size: int = 1_000_000) -> None:
    if objects <= 0 or requests <= 0 or batch_size <= 0 or alpha < 0:
        raise ValueError("invalid Zipf parameters")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ranks = np.arange(1, objects + 1, dtype=np.float64)
    weights = np.power(ranks, -alpha)
    cdf = np.cumsum(weights)
    cdf /= cdf[-1]
    rng = np.random.Generator(np.random.PCG64(seed))
    temp = path.with_name(path.name + ".part")
    try:
        with temp.open("wb") as output:
            for start in range(0, requests, batch_size):
                count = min(batch_size, requests - start)
                rows = np.empty(count, dtype=RECORD_DTYPE)
                rows["id"] = np.searchsorted(cdf, rng.random(count), side="left")
                rows["time"] = ((np.arange(start + 1, start + count + 1, dtype=np.uint64) *
                                  604800) // requests).astype(np.uint32)
                rows["size"] = 4000
                rows["next"] = -2
                rows.tofile(output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def frequency_counts(path: Path, *, objects: int, start: int = 0,
                     requests: int | None = None, id_offset: int = 0) -> np.ndarray:
    """Stream a bounded synthetic ID namespace; never truncate uint64 IDs to floats."""
    path = Path(path)
    if objects <= 0 or start < 0 or id_offset < 0 or id_offset + objects > 2**64:
        raise ValueError("invalid frequency-scan namespace")
    size = path.stat().st_size
    if size % RECORD_DTYPE.itemsize:
        raise ValueError("partial packed synthetic record")
    available = size // RECORD_DTYPE.itemsize - start
    requests = available if requests is None else requests
    if requests <= 0 or requests > available:
        raise ValueError("frequency scan range is outside the trace")
    counts = np.zeros(objects, dtype=np.int64)
    with path.open("rb") as stream:
        stream.seek(start * RECORD_DTYPE.itemsize)
        remaining = requests
        while remaining:
            rows = np.fromfile(stream, dtype=RECORD_DTYPE, count=min(remaining, 1_000_000))
            if len(rows) == 0 or np.any(rows["size"] == 0) or np.any(rows["next"] != -2):
                raise ValueError("unexpected synthetic record semantics")
            ids = rows["id"]
            if np.any(ids < id_offset) or np.any(ids >= id_offset + objects):
                raise ValueError("synthetic ID is outside its defined phase namespace")
            counts += np.bincount((ids - np.uint64(id_offset)).astype(np.int64),
                                  minlength=objects)
            remaining -= len(rows)
    return counts


def phase_change_frequency_counts(path: Path, *, objects: int,
                                 requests_per_phase: int) -> list[np.ndarray]:
    """Count each phase while streaming a packed raw or zstd trace in bounded chunks."""
    if objects <= 0 or requests_per_phase <= 0:
        raise ValueError("invalid phase frequency scan parameters")
    path = Path(path)
    counts = [np.zeros(objects, dtype=np.int64), np.zeros(objects, dtype=np.int64)]
    proc = None
    stream = path.open("rb")
    if path.suffix == ".zst":
        stream.close()
        proc = subprocess.Popen(["zstd", "-dc", "--", str(path)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stream = proc.stdout
    carry = b""
    index = 0
    try:
        while block := stream.read(RECORD_DTYPE.itemsize * 65536):
            block = carry + block
            usable = len(block) // RECORD_DTYPE.itemsize * RECORD_DTYPE.itemsize
            rows = np.frombuffer(block[:usable], dtype=RECORD_DTYPE)
            carry = block[usable:]
            cursor = 0
            while cursor < len(rows):
                phase = index // requests_per_phase
                if phase not in (0, 1):
                    raise ValueError("phase frequency scan found too many records")
                take = min(len(rows) - cursor, requests_per_phase - index % requests_per_phase)
                part = rows[cursor:cursor + take]
                offset = phase * objects
                ids = part["id"]
                if (np.any(ids < offset) or np.any(ids >= offset + objects) or
                        np.any(part["size"] == 0) or np.any(part["next"] != -2)):
                    raise ValueError("phase record semantics or namespace mismatch")
                counts[phase] += np.bincount((ids - np.uint64(offset)).astype(np.int64),
                                              minlength=objects)
                cursor += take
                index += take
        if carry:
            raise ValueError("partial packed record at end of phase trace")
    finally:
        stream.close()
        if proc is not None:
            stderr = proc.stderr.read().decode(errors="replace")
            proc.stderr.close()
            if proc.wait() != 0:
                raise ValueError(f"zstd decompression failed: {stderr[-300:]}")
    if index != 2 * requests_per_phase:
        raise ValueError(f"phase trace has {index} records, expected {2 * requests_per_phase}")
    return counts


def phase_change_expected_digest(*, objects: int, requests_per_phase: int,
                                alpha: float, seeds: tuple[int, int],
                                batch_size: int = 1_000_000) -> dict:
    """Recreate the logical stream digest and phase counts without writing trace bytes."""
    if (objects <= 0 or requests_per_phase <= 0 or batch_size <= 0 or len(seeds) != 2 or
            not math.isfinite(alpha) or alpha < 0 or 2 * objects > 2**64):
        raise ValueError("invalid phase-change digest recipe")
    cdf = np.cumsum(np.power(np.arange(1, objects + 1, dtype=np.float64), -alpha))
    cdf /= cdf[-1]
    total = 2 * requests_per_phase
    digest = hashlib.sha256()
    phase_counts = [np.zeros(objects, dtype=np.int64), np.zeros(objects, dtype=np.int64)]
    for phase, seed in enumerate(seeds):
        rng = np.random.Generator(np.random.PCG64(seed))
        for start in range(0, requests_per_phase, batch_size):
            count = min(batch_size, requests_per_phase - start)
            rows = np.empty(count, dtype=RECORD_DTYPE)
            ids = np.searchsorted(cdf, rng.random(count), side="left")
            rows["id"] = ids + phase * objects
            global_start = phase * requests_per_phase + start
            rows["time"] = ((np.arange(global_start + 1, global_start + count + 1,
                                        dtype=np.uint64) * 604800) // total).astype(np.uint32)
            rows["size"] = 4000
            rows["next"] = -2
            digest.update(rows.tobytes())
            phase_counts[phase] += np.bincount(ids.astype(np.int64), minlength=objects)
    return {"stream_sha256": digest.hexdigest(),
            "record_count": total, "raw_bytes": total * RECORD_DTYPE.itemsize,
            "unique_objects_per_phase": [int(np.count_nonzero(c)) for c in phase_counts]}


def top_ids(counts: np.ndarray, capacity: int, *, id_offset: int = 0) -> np.ndarray:
    """Empirical frequency descending; exact ties use numeric ID ascending."""
    if not (0 < capacity <= len(counts)) or np.any(counts < 0):
        raise ValueError("invalid empirical hot-set capacity/counts")
    if id_offset < 0 or id_offset + len(counts) > 2**64:
        raise ValueError("hot-set IDs exceed uint64")
    ids = np.arange(len(counts), dtype=np.uint64) + np.uint64(id_offset)
    return ids[np.lexsort((ids, -counts.astype(np.int64)))[:capacity]]


def generate_phase_change(path: Path, *, objects: int, requests_per_phase: int,
                          alpha: float, seeds: tuple[int, int],
                          batch_size: int = 1_000_000) -> None:
    """Two seeded finite-support streams in disjoint namespaces, one chronological file."""
    if objects <= 0 or requests_per_phase <= 0 or batch_size <= 0 or len(seeds) != 2:
        raise ValueError("invalid phase-change recipe")
    if not math.isfinite(alpha) or alpha < 0 or 2 * objects > 2**64:
        raise ValueError("invalid phase-change support/skew")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cdf = np.cumsum(np.power(np.arange(1, objects + 1, dtype=np.float64), -alpha))
    cdf /= cdf[-1]
    total = 2 * requests_per_phase
    temp = path.with_name(path.name + ".part")
    try:
        with temp.open("wb") as output:
            for phase, seed in enumerate(seeds):
                rng = np.random.Generator(np.random.PCG64(seed))
                for start in range(0, requests_per_phase, batch_size):
                    count = min(batch_size, requests_per_phase - start)
                    rows = np.empty(count, dtype=RECORD_DTYPE)
                    rows["id"] = (np.searchsorted(cdf, rng.random(count), side="left") +
                                  phase * objects)
                    global_start = phase * requests_per_phase + start
                    rows["time"] = ((np.arange(global_start + 1, global_start + count + 1,
                                                dtype=np.uint64) * 604800) // total).astype(np.uint32)
                    rows["size"] = 4000
                    rows["next"] = -2
                    rows.tofile(output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def generate_phase_change_zstd(path: Path, *, objects: int, requests_per_phase: int,
                               alpha: float, seeds: tuple[int, int],
                               batch_size: int = 1_000_000,
                               compression_level: int = 3,
                               max_output_bytes: int | None = None) -> dict:
    """Generate two disjoint phases directly into a zstd stream, with no raw-file scratch."""
    if (objects <= 0 or requests_per_phase <= 0 or batch_size <= 0 or len(seeds) != 2 or
            not math.isfinite(alpha) or alpha < 0 or 2 * objects > 2**64 or
            not 1 <= compression_level <= 19 or
            (max_output_bytes is not None and max_output_bytes <= 0)):
        raise ValueError("invalid compressed phase-change recipe")
    path = Path(path)
    if path.suffix != ".zst":
        raise ValueError("compressed phase-change output must end in .zst")
    if path.exists():
        raise FileExistsError(f"refusing to replace existing synthetic input: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".part")
    cdf = np.cumsum(np.power(np.arange(1, objects + 1, dtype=np.float64), -alpha))
    cdf /= cdf[-1]
    total = 2 * requests_per_phase
    stream_hash = hashlib.sha256()
    phase_counts = [np.zeros(objects, dtype=np.int64), np.zeros(objects, dtype=np.int64)]
    output_size = [0]
    size_limit_hit = [False]
    try:
        with temp.open("wb") as compressed:
            proc = subprocess.Popen(
                ["zstd", "-q", f"-{compression_level}", "-T1", "-c"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            def drain_compressed():
                while True:
                    block = proc.stdout.read(1024 * 1024)
                    if not block:
                        break
                    if (max_output_bytes is not None and
                            output_size[0] + len(block) > max_output_bytes):
                        size_limit_hit[0] = True
                        proc.terminate()
                        break
                    compressed.write(block)
                    output_size[0] += len(block)
                proc.stdout.close()
            reader = threading.Thread(target=drain_compressed, daemon=True)
            reader.start()
            try:
                for phase, seed in enumerate(seeds):
                    rng = np.random.Generator(np.random.PCG64(seed))
                    for start in range(0, requests_per_phase, batch_size):
                        count = min(batch_size, requests_per_phase - start)
                        rows = np.empty(count, dtype=RECORD_DTYPE)
                        ids = np.searchsorted(cdf, rng.random(count), side="left")
                        rows["id"] = ids + phase * objects
                        global_start = phase * requests_per_phase + start
                        rows["time"] = ((np.arange(global_start + 1,
                                                    global_start + count + 1,
                                                    dtype=np.uint64) * 604800) // total).astype(np.uint32)
                        rows["size"] = 4000
                        rows["next"] = -2
                        payload = rows.tobytes()
                        stream_hash.update(payload)
                        phase_counts[phase] += np.bincount(ids.astype(np.int64), minlength=objects)
                        proc.stdin.write(payload)
                proc.stdin.close()
            except BaseException as error:
                if proc.stdin and not proc.stdin.closed:
                    proc.stdin.close()
                if proc.poll() is None:
                    proc.terminate()
                proc.wait()
                reader.join()
                if size_limit_hit[0]:
                    raise RuntimeError(
                        f"compressed output exceeded {max_output_bytes} bytes; partial file discarded") from error
                raise
            stderr = proc.stderr.read().decode(errors="replace")
            proc.stderr.close()
            exit_code = proc.wait()
            reader.join()
            if size_limit_hit[0]:
                raise RuntimeError(f"compressed output exceeded {max_output_bytes} bytes; partial file discarded")
            if exit_code:
                raise RuntimeError(f"zstd compression failed ({exit_code}): {stderr}")
            compressed.flush()
            os.fsync(compressed.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return {
        "path": str(path), "raw_sha256": stream_hash.hexdigest(),
        "stored_sha256": digest.hexdigest(), "record_count": total,
        "raw_bytes": total * RECORD_DTYPE.itemsize, "stored_bytes": path.stat().st_size,
        "maximum_output_bytes": max_output_bytes,
        "unique_objects_per_phase": [int(np.count_nonzero(c)) for c in phase_counts],
        "compression_level": compression_level, "exit_code": 0,
    }
