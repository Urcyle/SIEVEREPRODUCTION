"""Independent model of the opt-in SIEVE variants (docs/variant_protocol.md, section 2).

Written from the protocol text, not from the C patch. Defaults (max_freq=1,
ghost_ratio=0, age_mult=0) are baseline SIEVE.
"""


class SieveVariantReference:
    """Object-capacity model; ``queue`` is ordered head (newest) to tail (oldest)."""

    def __init__(self, capacity: int, max_freq: int = 1, ghost_ratio: float = 0.0,
                 age_mult: int = 0, door_ratio: float = 0.0):
        if (capacity < 1 or not 1 <= max_freq <= 255 or ghost_ratio < 0 or age_mult < 0
                or door_ratio < 0):
            raise ValueError("invalid variant parameters")
        self.capacity = capacity
        self.max_freq = max_freq
        self.ghost_cap = max(1, int(ghost_ratio * capacity)) if ghost_ratio > 0 else 0
        self.door_cap = max(1, int(door_ratio * capacity)) if door_ratio > 0 else 0
        self.door: list[int] = []  # oldest first
        self.period = max(1, age_mult * capacity) if age_mult > 0 else 0
        self.queue: list[int] = []
        self.freq: dict[int, int] = {}
        self.stamp: dict[int, int] = {}
        self.hand: int | None = None
        self.ghost: list[int] = []  # oldest first
        self.n = 0

    def _epoch(self) -> int:
        return self.n // self.period if self.period else 0

    def access(self, key: int) -> bool:
        epoch = self._epoch()
        if epoch > 2**32 - 1:
            raise OverflowError("epoch exceeds 32 bits")
        self.n += 1
        ghost_hit = False
        if self.ghost_cap and key in self.ghost:
            self.ghost.remove(key)
            ghost_hit = True
        if key in self.freq:
            self.freq[key] = min(self.freq[key] + 1, self.max_freq)
            if self.period:
                self.stamp[key] = epoch
            return True
        if self.door_cap:
            if key in self.door:
                self.door.remove(key)
            else:  # first recent miss: remember the ID, do not cache the object
                self.door.append(key)
                while len(self.door) > self.door_cap:
                    self.door.pop(0)
                return False
        if len(self.queue) == self.capacity:
            self._evict(epoch)
        self.queue.insert(0, key)
        self.freq[key] = 1 if ghost_hit else 0
        self.stamp[key] = epoch if self.period else 0
        return False

    def _valid(self, key: int, epoch: int) -> bool:
        return self.freq[key] > 0 and (not self.period or self.stamp[key] == epoch)

    def _evict(self, epoch: int) -> None:
        victim = self.hand if self.hand is not None else self.queue[-1]
        while self._valid(victim, epoch):
            self.freq[victim] -= 1
            pos = self.queue.index(victim)
            victim = self.queue[pos - 1] if pos > 0 else self.queue[-1]
        pos = self.queue.index(victim)
        self.hand = self.queue[pos - 1] if pos > 0 else None
        self.queue.pop(pos)
        del self.freq[victim], self.stamp[victim]
        if self.ghost_cap:
            self.ghost.append(victim)
            while len(self.ghost) > self.ghost_cap:
                self.ghost.pop(0)

    def state_line(self, hit: bool) -> str:
        """The exact text the state-instrumented build prints after each request."""
        hand = "none" if self.hand is None else str(self.hand)
        queue = ",".join(f"{k}:{self.freq[k]}:{self.stamp[k]}" for k in self.queue)
        ghost = ",".join(str(k) for k in self.ghost)
        line = f"SIEVE_STATE hit={int(hit)} hand={hand} queue={queue} ghost={ghost}"
        if self.door_cap:
            line += " door=" + ",".join(str(k) for k in self.door)
        return line


def eviction_params(max_freq: int = 1, ghost_ratio: float = 0.0, age_mult: int = 0,
                    door_ratio: float = 0.0) -> str | None:
    """Parameter string for ``--eviction-params``; None means baseline SIEVE."""
    parts = []
    if max_freq != 1:
        parts.append(f"max-freq={max_freq}")
    if ghost_ratio:
        parts.append(f"ghost-ratio={ghost_ratio}")
    if age_mult:
        parts.append(f"age-period-x={age_mult}")
    if door_ratio:
        parts.append(f"door-ratio={door_ratio}")
    return ",".join(parts) or None


# Frozen grid (docs/variant_protocol.md, section 2). Order within a family is the
# "smaller parameter first" order used to break exact selection ties.
FAMILIES = {
    "ctr": [("ctr3", {"max_freq": 3}), ("ctr7", {"max_freq": 7})],
    "ghost": [("ghost0.5", {"ghost_ratio": 0.5}), ("ghost1.0", {"ghost_ratio": 1.0})],
    "age": [("age1", {"age_mult": 1}), ("age2", {"age_mult": 2}),
            ("age4", {"age_mult": 4}), ("age8", {"age_mult": 8})],
    "bloom": [("bloom", {"admission": "bloom-filter"})],
    # Added in round 2 (protocol amendment 2).
    "door": [("door1", {"door_ratio": 1.0}), ("door2", {"door_ratio": 2.0}),
             ("door4", {"door_ratio": 4.0})],
}
CONFIGS = {name: spec for members in FAMILIES.values() for name, spec in members}


def run_arguments(name: str) -> tuple[str | None, str | None]:
    """(eviction_params, admission) for a configuration name; 'base' is baseline SIEVE."""
    if name == "base":
        return None, None
    spec = dict(CONFIGS[name])
    admission = spec.pop("admission", None)
    return eviction_params(**spec), admission


def config_name(spec: dict) -> str:
    """Frozen configuration name for a variant run specification."""
    if spec["policy"] == "fifo":
        return "fifo"
    pair = (spec.get("eviction_params"), spec.get("admission"))
    for name in ["base"] + list(CONFIGS):
        if run_arguments(name) == pair:
            return name
    raise ValueError(f"run matches no frozen configuration: {pair}")
