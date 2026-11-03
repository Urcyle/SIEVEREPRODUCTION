"""Strict validation of periodic observations from a separate simulator build."""

import json


FIELDS = {"kind", "n_req", "n_miss", "interval_req", "interval_miss", "cache_size",
          "occupancy", "hot_count", "phase", "hand_rank_from_tail", "hand_pointer_null"}


def parse_observer_output(output: str, *, n_req: int, n_miss: int, cache_size: int,
                          interval: int, policy: str, has_hotset: bool,
                          hand_interval: int | None = None,
                          switch_after: int | None = None) -> list[dict]:
    if interval <= 0 or cache_size <= 0 or n_req <= 0:
        raise ValueError("invalid observation configuration")
    if hand_interval is not None and (hand_interval <= 0 or policy != "sieve"):
        raise ValueError("hand sampling requires SIEVE and a positive interval")
    if switch_after is not None and not (0 < switch_after < n_req):
        raise ValueError("phase boundary must lie inside the trace")
    endpoints = set(range(interval, n_req + 1, interval)) | {n_req}
    if switch_after is not None:
        endpoints.add(switch_after)
    expected = {(t, "final" if t == n_req and t % interval else "sample")
                for t in endpoints}
    if switch_after is not None:
        expected.add((switch_after, "switch"))
    if hand_interval is not None:
        expected |= {(t, "hand") for t in range(hand_interval, n_req, hand_interval)
                     if t not in endpoints}

    rows = []
    observed = set()
    last_n = last_miss = sample_n = sample_miss = phase = 0
    for text in output.splitlines():
        if not text.startswith("SIEVE_OBSERVE "):
            if text.startswith("SIEVE_OBSERVE") or "SIEVE_OBSERVE " in text:
                raise ValueError("malformed observation prefix/framing")
            continue
        try:
            row = json.loads(text.removeprefix("SIEVE_OBSERVE "))
        except json.JSONDecodeError as error:
            raise ValueError("malformed observation JSON") from error
        if not isinstance(row, dict) or set(row) != FIELDS:
            raise ValueError("observation schema mismatch")
        for key in ("n_req", "n_miss", "interval_req", "interval_miss", "cache_size",
                    "occupancy", "phase"):
            if type(row[key]) is not int or row[key] < 0:
                raise ValueError(f"invalid integer observation field: {key}")
        t, misses, kind = row["n_req"], row["n_miss"], row["kind"]
        key = (t, kind)
        if key not in expected or key in observed:
            raise ValueError("unexpected or duplicate observation time/kind")
        if t < last_n or misses < last_miss or misses > t or misses - last_miss > t - last_n:
            raise ValueError("observation counters are inconsistent")
        if t == last_n and (kind != "switch" or misses != last_miss):
            raise ValueError("only the phase-switch snapshot may repeat a request index")
        if row["cache_size"] != cache_size or row["occupancy"] > cache_size:
            raise ValueError("observation capacity/occupancy mismatch")
        if kind == "switch":
            if t != switch_after or phase != 0 or sample_n != t:
                raise ValueError("invalid phase-switch snapshot")
            phase = 1
        if row["phase"] != phase:
            raise ValueError("incorrect observation hot-set phase")
        if kind in ("sample", "final"):
            if row["interval_req"] != t - sample_n or row["interval_miss"] != misses - sample_miss:
                raise ValueError("interval counters do not match cumulative differences")
            sample_n, sample_miss = t, misses
        elif row["interval_req"] != 0 or row["interval_miss"] != 0:
            raise ValueError("hand/switch records must not reset interval counters")
        if row["interval_miss"] > row["interval_req"]:
            raise ValueError("interval misses exceed requests")
        hot = row["hot_count"]
        if has_hotset and kind != "hand":
            if type(hot) is not int or not (0 <= hot <= row["occupancy"]):
                raise ValueError("invalid resident hot-object count")
        elif hot is not None:
            raise ValueError("unexpected hot count on an observation without hot-set sampling")
        rank, pointer_null = row["hand_rank_from_tail"], row["hand_pointer_null"]
        if policy == "sieve":
            if type(pointer_null) is not bool:
                raise ValueError("SIEVE pointer-null field must be boolean")
            if row["occupancy"] == 0:
                if rank is not None:
                    raise ValueError("empty SIEVE cache has no hand rank")
            elif type(rank) is not int or not (0 <= rank < row["occupancy"]):
                raise ValueError("SIEVE hand rank is outside the resident queue")
            if pointer_null and rank not in (0, None):
                raise ValueError("a null SIEVE pointer means the effective tail")
        elif rank is not None or pointer_null is not None:
            raise ValueError("hand fields are only defined for SIEVE")
        row["popular_ratio"] = hot / cache_size if hot is not None else None
        row["hand_normalized"] = (rank / (row["occupancy"] - 1)
                                   if rank is not None and row["occupancy"] > 1
                                   else 0.0 if rank is not None else None)
        row["interval_miss_ratio"] = (row["interval_miss"] / row["interval_req"]
                                       if row["interval_req"] else None)
        rows.append(row)
        observed.add(key)
        last_n, last_miss = t, misses
    if observed != expected or sample_n != n_req or sample_miss != n_miss:
        raise ValueError("missing observations or mismatched final counters")
    return rows
