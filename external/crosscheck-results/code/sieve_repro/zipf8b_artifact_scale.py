"""Validation helpers for the seeded artifact-scale Figure 8b extension."""

from __future__ import annotations

import math


REQUESTS = 100_000_000
WORKLOAD_LABEL = "figure8a_artifact_sampler_seed42"


def capacity_grid(unique_objects: int, fractions: tuple[float, ...]) -> list[tuple[float, int]]:
    """Floor the paper's capacity fractions against the exact full-trace WSS."""
    if type(unique_objects) is not int or unique_objects <= 0 or not fractions:
        raise ValueError("invalid unique-object count or empty capacity grid")
    result = []
    seen = set()
    for fraction in fractions:
        if (type(fraction) not in (float, int) or not math.isfinite(fraction) or
                not 0 < fraction <= 1):
            raise ValueError("capacity fractions must be finite and in (0, 1]")
        fraction = float(fraction)
        capacity = math.floor(unique_objects * fraction)
        if capacity <= 0 or capacity in seen:
            raise ValueError("capacity grid contains zero or duplicate integer capacities")
        result.append((fraction, capacity))
        seen.add(capacity)
    return result


def validate_reference(record: dict, *, trace_sha256: str, binary_sha256: str,
                       policy: str, fraction: float, capacity: int,
                       unique_objects: int, workload_label: str = WORKLOAD_LABEL,
                       requests: int = REQUESTS) -> None:
    """Bind a completed exact-counter run to the precise trace/configuration."""
    spec = record.get("spec", {})
    if (record.get("status") != "complete" or record.get("exit_code") != 0 or
            record.get("n_req") != requests or record.get("cache_size") != capacity or
            record.get("unique_objects") != unique_objects or
            type(record.get("n_miss")) is not int or
            not 0 <= record["n_miss"] <= requests or
            spec.get("trace_sha256") != trace_sha256 or
            spec.get("binary_sha256") != binary_sha256 or
            spec.get("workload_label") != workload_label or
            spec.get("policy") != policy or spec.get("capacity_fraction") != fraction or
            spec.get("capacity_objects") != capacity):
        raise ValueError("counter reference is incomplete or does not match the declared run")


def summarize_observations(observations: list[dict]) -> dict:
    """Summarize saved sample/final snapshots, including the last endpoint."""
    snapshots = [row for row in observations if row.get("kind") in ("sample", "final")]
    if not snapshots or any(type(row.get("popular_ratio")) not in (float, int) or
                            not math.isfinite(row["popular_ratio"]) or
                            not 0 <= row["popular_ratio"] <= 1 for row in snapshots):
        raise ValueError("observations have no valid popular-object snapshots")
    final = [row for row in snapshots if row["kind"] == "final"]
    if len(final) > 1 or (final and final[0] is not snapshots[-1]):
        raise ValueError("final observation must be the last unique snapshot")
    return {"snapshot_count": len(snapshots),
            "mean_popular_ratio": sum(row["popular_ratio"] for row in snapshots) / len(snapshots),
            "final_popular_ratio": snapshots[-1]["popular_ratio"]}
