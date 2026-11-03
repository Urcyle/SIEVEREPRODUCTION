"""Small independent SIEVE model and exact-count metrics."""

from decimal import Decimal, ROUND_FLOOR
import re


class SieveReference:
    """Object-capacity Algorithm 1 model; queue is ordered head to tail."""

    def __init__(self, capacity: int):
        if capacity < 0:
            raise ValueError("capacity must be nonnegative")
        self.capacity = capacity
        self.queue: list[int] = []
        self.visited: dict[int, int] = {}
        self.hand: int | None = None

    def access(self, key: int) -> bool:
        if key in self.visited:
            self.visited[key] = 1
            return True
        if self.capacity == 0:
            return False
        if len(self.queue) == self.capacity:
            victim = self.hand if self.hand is not None else self.queue[-1]
            while self.visited[victim]:
                self.visited[victim] = 0
                pos = self.queue.index(victim)
                victim = self.queue[pos - 1] if pos > 0 else self.queue[-1]
            pos = self.queue.index(victim)
            self.hand = self.queue[pos - 1] if pos > 0 else None
            self.queue.pop(pos)
            del self.visited[victim]
        self.queue.insert(0, key)
        self.visited[key] = 0
        return False

    def snapshot(self) -> tuple[tuple[tuple[int, int], ...], int | None]:
        return tuple((key, self.visited[key]) for key in self.queue), self.hand


def capacity_for(unique_objects: int, fraction: float) -> int:
    if unique_objects < 0 or not (0 <= fraction <= 1):
        raise ValueError("invalid footprint or fraction")
    return int((Decimal(unique_objects) * Decimal(str(fraction))).to_integral_value(rounding=ROUND_FLOOR))


def reduction(fifo_misses: int, requests: int, policy_misses: int) -> float:
    if requests <= 0 or min(fifo_misses, policy_misses) < 0 or max(fifo_misses, policy_misses) > requests:
        raise ValueError("invalid counts")
    denominator = max(fifo_misses, policy_misses)
    return (fifo_misses - policy_misses) / denominator if denominator else 0.0


COUNTERS = re.compile(
    r"^SIEVE_COUNTERS policy=([A-Za-z0-9_-]+) cache_size=(\d+) "
    r"n_req=(\d+) n_miss=(\d+) n_req_byte=(\d+) n_miss_byte=(\d+)$"
)


def parse_counters(line: str) -> dict[str, int | str]:
    match = COUNTERS.fullmatch(line.strip())
    if not match:
        raise ValueError("missing exact SIEVE_COUNTERS record")
    policy, *counts = match.groups()
    result = dict(zip(("cache_size", "n_req", "n_miss", "n_req_byte", "n_miss_byte"), map(int, counts)))
    result["policy"] = policy
    if result["n_miss"] > result["n_req"] or result["n_miss_byte"] > result["n_req_byte"]:
        raise ValueError("invalid counter relationship")
    return result
