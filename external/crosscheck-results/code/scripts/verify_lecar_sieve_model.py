#!/usr/bin/env python3
"""Compare LeCaR-SIEVE per-request state to an independent seeded reference."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
import re
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sieve_repro.run import file_sha256
from sieve_repro.trace import read_records

STATE = re.compile(r"LECAR_SIEVE_STATE req=(\d+) hit=(\d+) weight=([^ ]+) hand=(-?\d+) "
                   r"q=\[(.*?)\] lfu=\[(.*?)\] ghost_lru=\[(.*?)\] ghost_lfu=\[(.*?)\]")


class LeCaRSieveModel:
    def __init__(self, capacity: int, seed: int):
        self.capacity = capacity
        self.state = seed
        self.queue = []                 # newest to oldest, insertion-order SIEVE list
        self.visited = {}
        self.hand = None
        self.freq = defaultdict(list)   # each list is oldest to newest
        self.ghost_lru = []             # newest to oldest: (id, time)
        self.ghost_lfu = []
        self.weight_lru = 0.5
        self.weight_lfu = 0.5
        self.dr = 0.005 ** (1.0 / capacity)
        self.snapshots = []
        self.hits = []
        self.evictions = []

    def next_rand(self):
        self.state = (6364136223846793005 * self.state + 1442695040888963407) & ((1 << 64) - 1)
        return self.state

    def lfu_candidate(self):
        return self.freq[min(self.freq)][0]

    def sieve_candidate(self, mutate):
        if not self.queue:
            return None
        start = self.queue.index(self.hand) if self.hand in self.queue else len(self.queue) - 1
        for offset in range(len(self.queue) * 2):
            index = start - offset
            index %= len(self.queue)
            obj = self.queue[index]
            if self.visited[obj]:
                if mutate:
                    self.visited[obj] = False
                elif offset >= len(self.queue) and index == start:
                    # The real pass cleared the first cycle before wrapping.
                    return obj
                continue
            return obj
        if mutate:
            for obj in self.queue:
                self.visited[obj] = False
        return self.queue[start]

    def update_weight(self, age, expert):
        reward = self.dr ** age
        if expert == "lru":
            self.weight_lru = self.weight_lru * math.exp(-0.45 * reward) + 1e-10
            total = self.weight_lru + self.weight_lfu + 2e-10
            self.weight_lru /= total
            self.weight_lfu = (self.weight_lfu + 1e-10) / total
        else:
            self.weight_lfu = self.weight_lfu * math.exp(-0.45 * reward) + 1e-10
            total = self.weight_lfu + self.weight_lru + 2e-10
            self.weight_lfu /= total
            self.weight_lru = (self.weight_lru + 1e-10) / total

    def _drop_ghost(self, ghosts, obj):
        for index, (ghost_id, _time) in enumerate(ghosts):
            if ghost_id == obj:
                del ghosts[index]
                return True
        return False

    def _cap_ghosts(self, ghosts):
        while len(ghosts) > self.capacity // 2:
            ghosts.pop()

    def request(self, obj, now):
        hit = obj in self.visited
        if hit:
            self.visited[obj] = True
            old_freq = next(freq for freq, values in self.freq.items() if obj in values)
            self.freq[old_freq].remove(obj)
            if not self.freq[old_freq]:
                del self.freq[old_freq]
            self.freq[old_freq + 1].append(obj)
        else:
            lru_ghost = next((v for v in self.ghost_lru if v[0] == obj), None)
            lfu_ghost = next((v for v in self.ghost_lfu if v[0] == obj), None)
            if lru_ghost is not None:
                self.update_weight(now - lru_ghost[1], "lru")
                self._drop_ghost(self.ghost_lru, obj)
            elif lfu_ghost is not None:
                self.update_weight(now - lfu_ghost[1], "lfu")
                self._drop_ghost(self.ghost_lfu, obj)

            if len(self.queue) >= self.capacity:
                lru = self.sieve_candidate(mutate=False)
                lfu = self.lfu_candidate()
                draw = None
                if lru == lfu:
                    victim, expert = self.sieve_candidate(mutate=True), "both"
                else:
                    draw = self.next_rand() % 100
                    if draw / 100.0 < self.weight_lru:
                        victim, expert = self.sieve_candidate(mutate=True), "lru"
                    else:
                        victim, expert = lfu, "lfu"
                self.evictions.append({"req": now, "lru_candidate": lru,
                                       "lfu_candidate": lfu, "draw": draw,
                                       "expert": expert, "victim": victim,
                                       "hand_before": self.hand})
                if expert == "lru":
                    self._drop_ghost(self.ghost_lru, victim)
                    self.ghost_lru.insert(0, (victim, now))
                    self._cap_ghosts(self.ghost_lru)
                elif expert == "lfu":
                    self.ghost_lfu.insert(0, (victim, now))
                    self._cap_ghosts(self.ghost_lfu)

                index = self.queue.index(victim)
                previous = self.queue[index - 1] if index > 0 else None
                del self.queue[index]
                del self.visited[victim]
                for values in self.freq.values():
                    if victim in values:
                        values.remove(victim)
                        break
                self.freq = defaultdict(list, {f: v for f, v in self.freq.items() if v})
                if victim == self.hand or expert in ("lru", "both"):
                    # SIEVE semantics (artifact Sieve.c): a NULL hand means the next scan starts at the tail.
                    # The first version restarted at the head (self.queue[0]); that was the bug found on 2026-10-23.
                    self.hand = previous if previous in self.queue else None

            self.queue.insert(0, obj)
            self.visited[obj] = False
            self.freq[1].append(obj)

        self.hits.append(hit)
        lfu_order = [[item, frequency] for frequency in sorted(self.freq)
                     for item in self.freq[frequency]]
        self.snapshots.append({"req": now, "hit": hit, "weight": self.weight_lru,
                               "hand": self.hand,
                               "q": [[item, self.visited[item]] for item in self.queue],
                               "lfu": lfu_order,
                               "ghost_lru": [item for item, _ in self.ghost_lru],
                               "ghost_lfu": [item for item, _ in self.ghost_lfu]})


def parse_snapshots(log: str):
    snapshots = []
    for line in log.splitlines():
        match = STATE.search(line)
        if not match:
            continue
        req, hit, weight, hand, q, lfu, ghost_lru, ghost_lfu = match.groups()
        def pairs(value):
            return [] if not value else [[int(row.split(":")[0]), int(row.split(":")[1])]
                                         for row in value.split(",")]
        def ids(value):
            return [] if not value else [int(row) for row in value.split(",")]
        snapshots.append({"req": int(req), "hit": bool(int(hit)), "weight": float(weight),
                          "hand": None if int(hand) < 0 else int(hand),
                          "q": [[obj, bool(visited)] for obj, visited in pairs(q)],
                          "lfu": pairs(lfu), "ghost_lru": ids(ghost_lru),
                          "ghost_lfu": ids(ghost_lfu)})
    return snapshots


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True, help="completed.json for the debug replay")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run = json.loads(args.run.read_text())
    if (run.get("status") != "complete" or run.get("exit_code") != 0 or
            run.get("spec", {}).get("policy") != "lecar_sieve" or
            run.get("spec", {}).get("policy_state_debug") is not True):
        raise SystemExit("run is not a completed LeCaR-SIEVE state-debug replay")
    raw = args.trace.read_bytes()
    if hashlib.sha256(raw).hexdigest() != run["spec"]["trace_sha256"]:
        raise SystemExit("fixture hash differs from the run identity")
    records = list(read_records(args.trace))
    if any(row[2] != 1 for row in records):
        raise SystemExit("reference fixture requires unit-size requests")
    model = LeCaRSieveModel(run["cache_size"], run["spec"]["rng_seed"])
    for index, (_time, obj, _size, _next) in enumerate(records, 1):
        model.request(obj, index)
    observed = parse_snapshots(Path(run["log"]).read_text())
    if len(observed) != len(model.snapshots):
        raise SystemExit(f"snapshot count mismatch: simulator {len(observed)} model {len(model.snapshots)}")
    for index, (got, expected) in enumerate(zip(observed, model.snapshots), 1):
        if any(got[key] != expected[key] for key in ("req", "hit", "hand", "q", "lfu", "ghost_lru", "ghost_lfu")) or not math.isclose(
                got["weight"], expected["weight"], rel_tol=0.0, abs_tol=2e-12):
            raise SystemExit(f"state mismatch at request {index}: simulator={got} model={expected}")
    output = {"verified": True, "requests": len(records), "misses": model.hits.count(False),
              "state_snapshots_compared": len(observed),
              "state_log_sha256": file_sha256(Path(run["log"])),
              "model_snapshots_sha256": hashlib.sha256(json.dumps(
                  model.snapshots, separators=(",", ":")).encode()).hexdigest(),
              "trace_sha256": run["spec"]["trace_sha256"], "rng_seed": run["spec"]["rng_seed"]}
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
