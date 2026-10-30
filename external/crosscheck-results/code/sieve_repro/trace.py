"""Bounded-memory oracleGeneral reader and structural validation."""

from hashlib import sha256
from array import array
import heapq
from pathlib import Path
import struct
import sys
import subprocess
import tempfile


RECORD = struct.Struct("<IQIq")
OBJECT_SIZE_PAIR = struct.Struct("<QI")
UINT64_MAX = (1 << 64) - 1
ELIAS_FANO_MAGIC = b"SIEVE-EF"
ELIAS_FANO_HEADER = struct.Struct("<8sQBQ")


def read_records(path: Path):
    path = Path(path)
    if path.suffix == ".zst":
        proc = subprocess.Popen(["zstd", "-dc", "--", str(path)], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        stream = proc.stdout
    else:
        proc = None
        stream = path.open("rb")
    try:
        carry = b""
        while block := stream.read(24 * 65536):
            block = carry + block
            usable = len(block) // RECORD.size * RECORD.size
            for row in RECORD.iter_unpack(block[:usable]):
                yield row
            carry = block[usable:]
        if carry:
            raise ValueError("oracleGeneral record alignment error")
    finally:
        stream.close()
        if proc is not None:
            stderr = proc.stderr.read().decode(errors="replace")
            proc.stderr.close()
            if proc.wait() != 0:
                raise ValueError(f"zstd decompression failed: {stderr[-300:]}")


def validate_oracle_file(path: Path, *, count_unique: bool = False) -> dict[str, int | str]:
    path = Path(path)
    digest = sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    stream_digest = sha256()
    n = zeros = 0
    unique = set() if count_unique else None
    for row in read_records(path):
        stream_digest.update(RECORD.pack(*row))
        _, obj_id, size, _ = row
        n += 1
        zeros += size == 0
        if unique is not None and size != 0:
            unique.add(obj_id)
    if n == 0:
        raise ValueError("empty trace")
    result = {"record_count": n, "zero_size_count": zeros, "sha256": digest.hexdigest(),
              "stream_sha256": stream_digest.hexdigest(), "stored_bytes": path.stat().st_size}
    if path.suffix == ".zst":
        result["compressed_bytes"] = result["stored_bytes"]
    if unique is not None:
        result["unique_objects"] = len(unique)
    return result


def _iter_u64_file(path: Path):
    with Path(path).open("rb") as stream:
        while block := stream.read(64 * 1024):
            usable = len(block) // 8 * 8
            if usable != len(block):
                raise ValueError("external unique-count chunk alignment error")
            for (value,) in struct.iter_unpack("<Q", block):
                yield value


def _sort_and_compact_u64(values: array) -> int:
    """Sort a native uint64 buffer in place and compact adjacent duplicates."""
    import numpy as np

    ids = np.frombuffer(values, dtype=np.uint64)
    if not len(ids):
        return 0
    ids.sort(kind="quicksort")
    write_index = 0
    previous = None
    block_records = 2_000_000
    for start in range(0, len(ids), block_records):
        stop = min(start + block_records, len(ids))
        block = ids[start:stop]
        unique = np.empty(len(block), dtype=np.bool_)
        unique[0] = previous is None or block[0] != previous
        np.not_equal(block[1:], block[:-1], out=unique[1:])
        positions = np.flatnonzero(unique)
        count = len(positions)
        last_value = int(block[-1])
        ids[write_index:write_index + count] = block[positions]
        write_index += count
        previous = last_value
    return write_index


def _elias_fano_payload_size(count: int, maximum: int) -> int:
    if count == 0:
        return 0
    low_bits = ((maximum + 1) // count).bit_length() - 1
    low_payload = (count * low_bits + 7) // 8
    high_bit_length = (maximum >> low_bits) + count
    high_payload = (high_bit_length + 7) // 8
    return low_payload + high_payload


def elias_fano_payload_bytes(sorted_unique_ids: array) -> int:
    """Return lower-bit and unary upper-bit storage for sorted uint64 IDs."""
    if not isinstance(sorted_unique_ids, array) or sorted_unique_ids.typecode != "Q":
        raise TypeError("IDs must be stored in an array('Q')")
    if sorted_unique_ids.itemsize != 8:
        raise ValueError("array('Q') must contain 64-bit values")
    count = len(sorted_unique_ids)
    if count == 0:
        return 0

    previous = -1
    for value in sorted_unique_ids:
        if value <= previous:
            raise ValueError("Elias-Fano IDs must be strictly increasing")
        previous = value

    return _elias_fano_payload_size(count, sorted_unique_ids[-1])


def write_elias_fano_chunk(path: Path, sorted_unique_ids: array) -> int:
    """Write a sorted uint64 chunk in a bounded-memory Elias-Fano encoding."""
    if not isinstance(sorted_unique_ids, array) or sorted_unique_ids.typecode != "Q":
        raise TypeError("IDs must be stored in an array('Q')")
    if sorted_unique_ids.itemsize != 8 or sys.byteorder != "little":
        raise ValueError("Elias-Fano chunk writer requires little-endian 64-bit IDs")
    count = len(sorted_unique_ids)
    if count == 0:
        raise ValueError("cannot encode an empty Elias-Fano chunk")

    import numpy as np

    ids = np.frombuffer(sorted_unique_ids, dtype=np.uint64)
    maximum = int(ids[-1])
    low_bits = ((maximum + 1) // count).bit_length() - 1
    low_mask = (1 << low_bits) - 1
    low_bytes_expected = (count * low_bits + 7) // 8
    high_bit_length = (maximum >> low_bits) + count
    high_bytes = bytearray((high_bit_length + 7) // 8)
    high = np.frombuffer(high_bytes, dtype=np.uint8)
    block_records = 1_000_000

    path = Path(path)
    with path.open("wb") as stream:
        stream.write(ELIAS_FANO_HEADER.pack(ELIAS_FANO_MAGIC, count, low_bits, maximum))
        if low_bits:
            low_written = 0
            for start in range(0, count, block_records):
                stop = min(start + block_records, count)
                low = np.bitwise_and(ids[start:stop], low_mask)
                bits = np.unpackbits(low.view(np.uint8), bitorder="little")
                bits = bits.reshape(-1, 64)[:, :low_bits]
                packed = np.packbits(bits.reshape(-1), bitorder="little")
                stream.write(packed.tobytes())
                low_written += len(packed)
            if low_written != low_bytes_expected:
                raise ValueError("Elias-Fano lower-bit payload length mismatch")

        for start in range(0, count, block_records):
            stop = min(start + block_records, count)
            values = ids[start:stop]
            high_values = values >> low_bits if low_bits < 64 else np.zeros(len(values), dtype=np.uint64)
            ranks = np.arange(start, stop, dtype=np.uint64)
            positions = high_values + ranks
            byte_indices = (positions >> 3).astype(np.intp)
            bit_masks = np.left_shift(np.uint8(1), (positions & 7).astype(np.uint8))
            np.bitwise_or.at(high, byte_indices, bit_masks)
        stream.write(high_bytes)
    return path.stat().st_size


def iter_elias_fano_blocks(path: Path, *, block_records: int = 1_000_000):
    """Decode a sorted uint64 Elias-Fano chunk as bounded NumPy blocks."""
    import numpy as np

    if type(block_records) is not int or block_records <= 0 or block_records % 8:
        raise ValueError("Elias-Fano decode block size must be a positive multiple of eight")
    path = Path(path)
    with path.open("rb") as stream:
        header = stream.read(ELIAS_FANO_HEADER.size)
        if len(header) != ELIAS_FANO_HEADER.size:
            raise ValueError("truncated Elias-Fano chunk header")
        magic, count, low_bits, maximum = ELIAS_FANO_HEADER.unpack(header)
        if magic != ELIAS_FANO_MAGIC or count == 0 or low_bits > 64:
            raise ValueError("invalid Elias-Fano chunk header")
        low_bytes_count = (count * low_bits + 7) // 8
        high_bit_length = (maximum >> low_bits) + count
        high_bytes_count = (high_bit_length + 7) // 8
        expected_size = ELIAS_FANO_HEADER.size + low_bytes_count + high_bytes_count
        if path.stat().st_size != expected_size:
            raise ValueError("Elias-Fano chunk size does not match its header")
        low_start = stream.tell()
        stream.seek(low_bytes_count, 1)
        high_bytes = stream.read(high_bytes_count)
        if len(high_bytes) != high_bytes_count:
            raise ValueError("truncated Elias-Fano upper-bit payload")

    low_bits_per_value = low_bits
    high_position_buffer = np.empty(0, dtype=np.int64)
    high_read_offset = 0
    rank_start = 0
    low_mask = (1 << low_bits_per_value) - 1 if low_bits_per_value < 64 else UINT64_MAX
    low_weights = np.left_shift(np.uint64(1), np.arange(low_bits_per_value, dtype=np.uint64))
    previous = None
    decoded_maximum = None
    stream = path.open("rb")
    stream.seek(low_start)
    try:
        while rank_start < count:
            block_count = min(block_records, count - rank_start)
            if low_bits_per_value:
                low_byte_count = (block_count * low_bits_per_value + 7) // 8
                low_payload = stream.read(low_byte_count)
                if len(low_payload) != low_byte_count:
                    raise ValueError("truncated Elias-Fano lower-bit payload")
                unpacked = np.unpackbits(np.frombuffer(low_payload, dtype=np.uint8),
                                         bitorder="little")[:block_count * low_bits_per_value]
                low_matrix = unpacked.reshape(block_count, low_bits_per_value)
                low_values = low_matrix.astype(np.uint64) @ low_weights
                low_values &= low_mask
            else:
                low_values = np.zeros(block_count, dtype=np.uint64)

            while len(high_position_buffer) < block_count:
                end = min(high_read_offset + 1_048_576, high_bytes_count)
                if end <= high_read_offset:
                    raise ValueError("Elias-Fano upper-bit payload has too few set bits")
                raw = np.frombuffer(high_bytes[high_read_offset:end], dtype=np.uint8)
                bits = np.unpackbits(raw, bitorder="little")
                positions = np.flatnonzero(bits).astype(np.int64) + high_read_offset * 8
                high_position_buffer = np.concatenate((high_position_buffer, positions))
                high_read_offset = end
            high_positions = high_position_buffer[:block_count]
            high_position_buffer = high_position_buffer[block_count:]
            ranks = np.arange(rank_start, rank_start + block_count, dtype=np.int64)
            high_values = (high_positions - ranks).astype(np.uint64)
            if low_bits_per_value < 64:
                values = (high_values << low_bits_per_value) | low_values
            else:
                values = low_values
            if (values.size > 1 and np.any(values[1:] <= values[:-1])):
                raise ValueError("Elias-Fano decoded IDs are not strictly increasing")
            if previous is not None and int(values[0]) <= previous:
                raise ValueError("Elias-Fano decoded IDs are not strictly increasing")
            previous = int(values[-1])
            decoded_maximum = previous
            rank_start += block_count
            yield values
        if high_position_buffer.size:
            raise ValueError("Elias-Fano upper-bit payload has extra set bits")
        if high_read_offset < high_bytes_count:
            tail = high_bytes[high_read_offset:]
            if any(tail):
                raise ValueError("Elias-Fano upper-bit payload has extra set bits")
        if decoded_maximum != maximum:
            raise ValueError("Elias-Fano maximum does not match its header")
    finally:
        stream.close()


def iter_elias_fano_chunk(path: Path):
    """Decode one sorted uint64 Elias-Fano chunk as Python integers."""
    for block in iter_elias_fano_blocks(path):
        for value in block:
            yield int(value)


def _count_sorted_elias_fano_union(chunk_paths, *, block_records: int,
                                   max_buffer_records: int) -> tuple[int, str, int]:
    """Count a multiway sorted union with bounded vectorized blocks and fallback."""
    import numpy as np

    per_run_budget = max(8, (max_buffer_records // max(1, len(chunk_paths)) // 8) * 8)
    block_records = min(block_records, per_run_budget)
    iterators = [iter_elias_fano_blocks(path, block_records=block_records)
                 for path in chunk_paths]
    exhausted = [False] * len(iterators)
    buffers = [np.empty(0, dtype=np.uint64) for _ in iterators]
    carry = np.empty(0, dtype=np.uint64)
    unique_count = 0
    previous = None

    def count_segment(values):
        nonlocal unique_count, previous
        if not values.size:
            return
        distinct = 1 + int(np.count_nonzero(values[1:] != values[:-1]))
        if previous is not None and int(values[0]) == previous:
            distinct -= 1
        unique_count += distinct
        previous = int(values[-1])

    while True:
        for index, iterator in enumerate(iterators):
            if exhausted[index]:
                continue
            try:
                buffers[index] = next(iterator)
            except StopIteration:
                exhausted[index] = True
                buffers[index] = np.empty(0, dtype=np.uint64)

        pieces = [carry]
        pieces.extend(buffer for buffer in buffers if buffer.size)
        if not pieces or not any(piece.size for piece in pieces):
            break
        combined = np.concatenate(pieces) if len(pieces) > 1 else pieces[0].copy()
        combined.sort(kind="quicksort")

        active_tails = [int(buffers[index][-1]) for index in range(len(buffers))
                        if not exhausted[index] and buffers[index].size]
        if not active_tails:
            count_segment(combined)
            return unique_count, "blockwise sorted-run union", block_records

        watermark = min(active_tails)
        cutoff = int(np.searchsorted(combined, np.uint64(watermark), side="left"))
        count_segment(combined[:cutoff])
        carry = combined[cutoff:].copy()
        if carry.size > max_buffer_records:
            def flatten_blocks(iterator):
                for block in iterator:
                    for value in block:
                        yield int(value)

            iterators_to_merge = [iter(carry)]
            iterators_to_merge.extend(
                flatten_blocks(iterator)
                for index, iterator in enumerate(iterators) if not exhausted[index])
            for value in heapq.merge(*iterators_to_merge):
                if previous is None or value != previous:
                    unique_count += 1
                    previous = value
            return (unique_count, "blockwise union with bounded streaming fallback",
                    block_records)

    return unique_count, "blockwise sorted-run union", block_records


def estimate_unique_temporary_bytes(path: Path, *, expected_record_count: int,
                                    expected_zero_size_count: int,
                                    chunk_records: int = 1_000_000,
                                    include_zero_size_ids: bool = False) -> dict[str, int | bool | str]:
    """Measure the exact chunk-run footprint without creating scratch files."""
    values = (expected_record_count, expected_zero_size_count, chunk_records)
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError("external unique-count estimate limits must be nonnegative integers")
    if (expected_record_count <= 0 or expected_zero_size_count > expected_record_count or
            chunk_records <= 0):
        raise ValueError("invalid expected trace counts or chunk size")

    import numpy as np

    seen_records = seen_zero = nonzero_records = chunk_count = temporary_bytes_estimate = 0
    buffer = array("Q")

    def measure_chunk():
        nonlocal chunk_count, temporary_bytes_estimate, buffer
        if not buffer:
            return
        unique_count = _sort_and_compact_u64(buffer)
        chunk_count += 1
        temporary_bytes_estimate += unique_count * 8
        buffer = array("Q")

    for _, obj_id, size, _ in read_records(path):
        seen_records += 1
        if size == 0:
            seen_zero += 1
            if not include_zero_size_ids:
                continue
        else:
            nonzero_records += 1
        buffer.append(obj_id)
        if len(buffer) >= chunk_records:
            measure_chunk()
    measure_chunk()
    if (seen_records != expected_record_count or
            seen_zero != expected_zero_size_count):
        raise ValueError("external unique estimate differs from validated trace schema")
    return {"record_count": seen_records, "zero_size_count": seen_zero,
            "nonzero_records": nonzero_records, "chunk_records": chunk_records,
            "include_zero_size_ids": include_zero_size_ids,
            "working_set_id_scope": ("all request IDs" if include_zero_size_ids else
                                     "IDs on nonzero-size requests"),
            "chunk_count": chunk_count,
            "temporary_bytes_estimate": temporary_bytes_estimate}


def estimate_unique_elias_fano_temporary_bytes(
        path: Path, *, expected_record_count: int,
        expected_zero_size_count: int,
        chunk_records: int = 1_000_000,
        include_zero_size_ids: bool = False) -> dict[str, int | str | bool]:
    """Estimate a sorted Elias-Fano run per compacted chunk without writing files."""
    values = (expected_record_count, expected_zero_size_count, chunk_records)
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError("external unique estimate limits must be nonnegative integers")
    if (expected_record_count <= 0 or expected_zero_size_count > expected_record_count or
            chunk_records <= 0):
        raise ValueError("invalid expected trace counts or chunk size")

    seen_records = seen_zero = nonzero_records = chunk_count = 0
    temporary_bytes_estimate = 0
    buffer = array("Q")

    def measure_chunk():
        nonlocal chunk_count, temporary_bytes_estimate, buffer
        if not buffer:
            return
        unique_count = _sort_and_compact_u64(buffer)
        temporary_bytes_estimate += (ELIAS_FANO_HEADER.size +
                                     _elias_fano_payload_size(
                                         unique_count, buffer[unique_count - 1]))
        chunk_count += 1
        buffer = array("Q")

    for _, obj_id, size, _ in read_records(path):
        seen_records += 1
        if size == 0:
            seen_zero += 1
            if not include_zero_size_ids:
                continue
        else:
            nonzero_records += 1
        buffer.append(obj_id)
        if len(buffer) >= chunk_records:
            measure_chunk()
    measure_chunk()
    if (seen_records != expected_record_count or
            seen_zero != expected_zero_size_count):
        raise ValueError("external unique estimate differs from validated trace schema")
    return {"record_count": seen_records, "zero_size_count": seen_zero,
            "nonzero_records": nonzero_records, "chunk_records": chunk_records,
            "include_zero_size_ids": include_zero_size_ids,
            "working_set_id_scope": ("all request IDs" if include_zero_size_ids else
                                     "IDs on nonzero-size requests"),
            "chunk_count": chunk_count,
            "encoding": "elias_fano_with_chunk_header",
            "temporary_bytes_estimate": temporary_bytes_estimate}


def count_unique_objects_external(path: Path, *, scratch_dir: Path,
                                  expected_record_count: int,
                                  expected_zero_size_count: int,
                                  max_temporary_bytes: int,
                                  chunk_records: int = 1_000_000,
                                  max_chunks: int = 512,
                                  scratch_encoding: str = "u64",
                                  merge_block_records: int = 1_000_000,
                                  max_merge_buffer_records: int = 8_000_000,
                                  include_zero_size_ids: bool = False) -> dict[str, int | str | bool]:
    """Count exact request IDs by sorting bounded chunks and merging them.

    The caller can use ``estimate_unique_temporary_bytes`` for a no-write preflight
    and pass that exact chunk-run footprint as the scratch ceiling. All chunk files
    are removed before return, including on failure. By default, zero-size rows are
    excluded for compatibility; pass ``include_zero_size_ids=True`` only when the
    target replay reader processes zero-size requests and those IDs count toward WSS.
    """
    values = (expected_record_count, expected_zero_size_count,
              max_temporary_bytes, chunk_records, max_chunks, merge_block_records,
              max_merge_buffer_records)
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError("external unique-count limits must be nonnegative integers")
    if expected_record_count <= 0 or expected_zero_size_count > expected_record_count:
        raise ValueError("invalid expected trace counts")
    if (chunk_records <= 0 or max_chunks <= 0 or merge_block_records <= 0 or
            max_merge_buffer_records <= 0):
        raise ValueError("chunk limits must be positive")
    if scratch_encoding == "elias_fano" and merge_block_records % 8:
        raise ValueError("Elias-Fano merge block size must be divisible by eight")
    if scratch_encoding not in ("u64", "elias_fano"):
        raise ValueError("scratch encoding must be 'u64' or 'elias_fano'")
    indexed_expected = (expected_record_count if include_zero_size_ids else
                        expected_record_count - expected_zero_size_count)
    temporary_upper_bound = indexed_expected * 8
    if scratch_encoding == "u64" and max_temporary_bytes > temporary_upper_bound:
        raise ValueError("temporary-file ceiling exceeds the conservative record bound")

    import numpy as np

    scratch_dir = Path(scratch_dir)
    scratch_dir.mkdir(parents=True, exist_ok=True)
    seen_records = 0
    seen_zero = 0
    nonzero_records = 0
    temporary_bytes_written = 0
    chunk_paths = []
    buffer = array("Q")

    def flush_chunk(directory):
        nonlocal temporary_bytes_written, buffer
        if not buffer:
            return
        unique_count = _sort_and_compact_u64(buffer)
        if len(chunk_paths) >= max_chunks:
            raise OSError("external unique scan exceeded its configured merge fan-in")
        suffix = "ef" if scratch_encoding == "elias_fano" else "bin"
        chunk_path = Path(directory) / f"ids-{len(chunk_paths):06d}.{suffix}"
        if scratch_encoding == "elias_fano":
            encoded_bytes = write_elias_fano_chunk(chunk_path, buffer[:unique_count])
            expected_bytes = (ELIAS_FANO_HEADER.size +
                              _elias_fano_payload_size(
                                  unique_count, int(buffer[unique_count - 1])))
            if encoded_bytes != expected_bytes:
                raise ValueError("Elias-Fano chunk size differs from its exact preflight")
            temporary_bytes_written += encoded_bytes
        else:
            sorted_ids = np.frombuffer(buffer, dtype=np.uint64)[:unique_count]
            sorted_ids.astype("<u8", copy=False).tofile(chunk_path)
            del sorted_ids
            temporary_bytes_written += unique_count * 8
        if temporary_bytes_written > max_temporary_bytes:
            raise OSError("external unique scan exceeded its temporary-file budget")
        chunk_paths.append(chunk_path)
        buffer = array("Q")

    with tempfile.TemporaryDirectory(prefix="sieve-wss-", dir=scratch_dir) as temp_name:
        for _, obj_id, size, _ in read_records(path):
            seen_records += 1
            if size == 0:
                seen_zero += 1
                if not include_zero_size_ids:
                    continue
            else:
                nonzero_records += 1
            buffer.append(obj_id)
            if len(buffer) >= chunk_records:
                flush_chunk(temp_name)
        flush_chunk(temp_name)
        if (seen_records != expected_record_count or
                seen_zero != expected_zero_size_count):
            raise ValueError("external unique scan counts differ from the validated trace schema")
        if scratch_encoding == "elias_fano":
            if chunk_paths:
                unique_objects, merge_method, effective_merge_block_records = _count_sorted_elias_fano_union(
                    chunk_paths, block_records=merge_block_records,
                    max_buffer_records=max_merge_buffer_records)
            else:
                unique_objects, merge_method = 0, "blockwise sorted-run union"
                effective_merge_block_records = merge_block_records
        else:
            unique_objects = 0
            previous = None
            has_previous = False
            if chunk_paths:
                iterators = (_iter_u64_file(chunk) for chunk in chunk_paths)
                for obj_id in heapq.merge(*iterators):
                    if not has_previous or obj_id != previous:
                        unique_objects += 1
                        previous = obj_id
                        has_previous = True
            merge_method = "heapq sorted-run merge"
            effective_merge_block_records = merge_block_records

    method = ("bounded NumPy unique chunks with Elias-Fano runs"
              if scratch_encoding == "elias_fano" else
              "bounded NumPy unique chunks with heap-merged little-endian uint64 runs")
    return {"method": method, "scratch_encoding": scratch_encoding,
            "include_zero_size_ids": include_zero_size_ids,
            "working_set_id_scope": ("all request IDs" if include_zero_size_ids else
                                     "IDs on nonzero-size requests"),
            "merge_method": merge_method,
            "merge_block_records": effective_merge_block_records,
            "merge_block_records_requested": merge_block_records,
            "max_merge_buffer_records": max_merge_buffer_records,
            "record_count": seen_records, "zero_size_count": seen_zero,
            "nonzero_records": nonzero_records, "unique_objects": unique_objects,
            "chunk_records": chunk_records, "chunk_count": len(chunk_paths),
            "temporary_bytes_upper_bound": temporary_upper_bound,
            "temporary_bytes_written": temporary_bytes_written,
            "max_temporary_bytes": max_temporary_bytes}


def _iter_object_size_file(path: Path):
    with Path(path).open("rb") as stream:
        carry = b""
        while block := stream.read(64 * 1024):
            block = carry + block
            usable = len(block) // OBJECT_SIZE_PAIR.size * OBJECT_SIZE_PAIR.size
            yield from OBJECT_SIZE_PAIR.iter_unpack(block[:usable])
            carry = block[usable:]
        if carry:
            raise ValueError("external object-size chunk alignment error")


def _checked_u64_add(total: int, value: int, label: str) -> int:
    result = total + value
    if result > UINT64_MAX:
        raise OverflowError(f"{label} exceeds the simulator's uint64 byte counter")
    return result


def estimate_unique_object_size_scratch_bytes(
        path: Path, *, expected_record_count: int, expected_zero_size_count: int,
        chunk_records: int = 1_000_000) -> dict[str, int]:
    """Measure exact external-sort space for distinct (object ID, byte size) pairs."""
    values = (expected_record_count, expected_zero_size_count, chunk_records)
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError("object-size scan limits must be nonnegative integers")
    if (expected_record_count <= 0 or expected_zero_size_count > expected_record_count or
            chunk_records <= 0):
        raise ValueError("invalid expected trace counts or chunk size")

    import numpy as np

    dtype = np.dtype([("obj_id", "<u8"), ("size", "<u4")])
    seen_records = seen_zero = chunk_count = temporary_bytes_estimate = 0
    buffer = []

    def measure_chunk():
        nonlocal chunk_count, temporary_bytes_estimate
        if not buffer:
            return
        pairs = np.unique(np.asarray(buffer, dtype=dtype))
        chunk_count += 1
        temporary_bytes_estimate += int(pairs.size) * OBJECT_SIZE_PAIR.size
        buffer.clear()

    for _, obj_id, size, _ in read_records(path):
        seen_records += 1
        seen_zero += size == 0
        buffer.append((obj_id, size))
        if len(buffer) >= chunk_records:
            measure_chunk()
    measure_chunk()
    if (seen_records != expected_record_count or
            seen_zero != expected_zero_size_count):
        raise ValueError("object-size estimate differs from validated trace schema")
    return {"record_count": seen_records, "zero_size_count": seen_zero,
            "chunk_records": chunk_records, "chunk_count": chunk_count,
            "pair_record_bytes": OBJECT_SIZE_PAIR.size,
            "temporary_bytes_estimate": temporary_bytes_estimate,
            "temporary_bytes_upper_bound": expected_record_count * OBJECT_SIZE_PAIR.size}


def count_unique_object_sizes_external(
        path: Path, *, scratch_dir: Path, expected_record_count: int,
        expected_zero_size_count: int, max_temporary_bytes: int,
        chunk_records: int = 1_000_000, max_chunks: int = 512) -> dict[str, int | bool | None | str]:
    """Count exact IDs and sum stable object sizes using bounded external sorting.

    All observed sizes are kept in the sorted runs. If one ID has multiple sizes,
    its byte footprint is ambiguous and ``unique_object_bytes`` is returned as
    ``None``. Temporary runs are removed on success and failure.
    """
    values = (expected_record_count, expected_zero_size_count,
              max_temporary_bytes, chunk_records, max_chunks)
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError("object-size scan limits must be nonnegative integers")
    if (expected_record_count <= 0 or expected_zero_size_count > expected_record_count or
            chunk_records <= 0 or max_chunks <= 0):
        raise ValueError("invalid object-size scan limits")
    temporary_upper_bound = expected_record_count * OBJECT_SIZE_PAIR.size
    if max_temporary_bytes > temporary_upper_bound:
        raise ValueError("temporary-file ceiling exceeds the conservative record bound")

    import numpy as np

    dtype = np.dtype([("obj_id", "<u8"), ("size", "<u4")])
    scratch_dir = Path(scratch_dir)
    scratch_dir.mkdir(parents=True, exist_ok=True)
    seen_records = seen_zero = 0
    request_bytes = 0
    stream_digest = sha256()
    temporary_bytes_written = 0
    chunk_paths = []
    buffer = []

    def flush_chunk(directory):
        nonlocal temporary_bytes_written
        if not buffer:
            return
        pairs = np.unique(np.asarray(buffer, dtype=dtype))
        if len(chunk_paths) >= max_chunks:
            raise OSError("external object-size scan exceeded its configured merge fan-in")
        chunk_path = Path(directory) / f"object-sizes-{len(chunk_paths):06d}.bin"
        pairs.tofile(chunk_path)
        temporary_bytes_written += int(pairs.size) * OBJECT_SIZE_PAIR.size
        if temporary_bytes_written > max_temporary_bytes:
            raise OSError("external object-size scan exceeded its temporary-file budget")
        chunk_paths.append(chunk_path)
        buffer.clear()

    with tempfile.TemporaryDirectory(prefix="sieve-byte-wss-", dir=scratch_dir) as temp_name:
        for row in read_records(path):
            stream_digest.update(RECORD.pack(*row))
            _, obj_id, size, _ = row
            seen_records += 1
            seen_zero += size == 0
            request_bytes = _checked_u64_add(request_bytes, size, "requested bytes")
            buffer.append((obj_id, size))
            if len(buffer) >= chunk_records:
                flush_chunk(temp_name)
        flush_chunk(temp_name)
        if (seen_records != expected_record_count or
                seen_zero != expected_zero_size_count):
            raise ValueError("object-size scan counts differ from validated trace schema")

        unique_objects = 0
        size_conflicts = 0
        unique_object_bytes = 0
        current_id = current_size = None
        current_conflicts = False
        for obj_id, size in heapq.merge(*(_iter_object_size_file(chunk)
                                          for chunk in chunk_paths)):
            if current_id is None or obj_id != current_id:
                if current_id is not None:
                    if current_conflicts:
                        size_conflicts += 1
                    else:
                        unique_object_bytes = _checked_u64_add(
                            unique_object_bytes, current_size, "unique-object byte footprint")
                unique_objects += 1
                current_id, current_size = obj_id, size
                current_conflicts = False
            elif size != current_size:
                current_conflicts = True
        if current_id is not None:
            if current_conflicts:
                size_conflicts += 1
            else:
                unique_object_bytes = _checked_u64_add(
                    unique_object_bytes, current_size, "unique-object byte footprint")

    return {"method": "bounded NumPy unique (object ID, size) chunks with heap merge",
            "record_count": seen_records, "zero_size_count": seen_zero,
            "stream_sha256": stream_digest.hexdigest(),
            "request_bytes": request_bytes, "unique_objects": unique_objects,
            "size_conflicting_objects": size_conflicts,
            "size_consistent": size_conflicts == 0,
            "unique_object_bytes": unique_object_bytes if size_conflicts == 0 else None,
            "chunk_records": chunk_records, "chunk_count": len(chunk_paths),
            "pair_record_bytes": OBJECT_SIZE_PAIR.size,
            "temporary_bytes_upper_bound": temporary_upper_bound,
            "temporary_bytes_written": temporary_bytes_written,
            "max_temporary_bytes": max_temporary_bytes}
