#!/bin/bash
# Correctness gates of SIEVE-G (plan, Phase 2). Run from anywhere, after scripts/setup_simulator.sh
# and a cachesim build. One gate per call; logs go to tests/<gate>/.
#
#   tests/gates.sh g1   no ghost equals SIEVE: Zipf alpha 0.8/1.0/1.2 (10,000 objects, 10 M
#                       requests, seed 1; external/fig8's generator), sieve,sieveg-0 at
#                       0.001,0.01,0.1: every miss ratio must be identical
#   tests/gates.sh g2   the mechanism: every object requested twice, the second request <gap>
#                       requests after the first (gap 10/50/200/800), 1 M requests, cache 1,000
#                       objects; fifo,clock,sieve,sieveg-0.5
#   tests/gates.sh g4   baseline unchanged: cluster 13 (Figure 3 manifest row), fifo,sieve at
#                       0.001,0.1, must equal results/phase0 (and the Figure 3 logs)
# (G3, the 6-request unit check, used a temporary debug print and is described in tests/g3/.)
set -euo pipefail
G=$(cd "$(dirname "$0")/.." && pwd)            # external/sieve-g
ROOT=$(cd "$G/../.." && pwd)                   # the repository
CACHESIM=$ROOT/external/NSDI24-SIEVE/libCacheSim/_build/bin/cachesim
PY=$G/.venv/bin/python
work=$G/results/tmp/gates.$$
mkdir -p "$work"
trap 'rm -rf "$work"' EXIT

sim() {  # <log> <trace> <algos> <sizes> -> appends the result lines to <log>
	local log=$1 trace=$2 algos=$3 sizes=$4
	{ echo "# trace $(basename "$trace")"; echo "# cachesim args: $algos $sizes --ignore-obj-size 1"; } >> "$log"
	(cd "$work" && "$CACHESIM" "$trace" oracleGeneral "$algos" "$sizes" --ignore-obj-size 1 \
		--num-thread "$(nproc)" 2> /dev/null) | grep "miss ratio" | sed 's/  */ /g' >> "$log"
}

case ${1:-} in
g1)
	mkdir -p "$G/tests/g1" "$G/tests/data"
	log=$G/tests/g1/g1.log
	: > "$log"
	for a in 0.8 1.0 1.2; do
		t=$G/tests/data/zipf_${a}_m10000_n10000000_s1.oracleGeneral
		[[ -f $t ]] || $PY -I "$ROOT/external/fig8/fig8/gen_trace.py" -m 10000 -n 10000000 --alpha $a --seed 1 -o "$t"
		sim "$log" "$t" sieve,sieveg-0 0.001,0.01,0.1
	done
	$PY -I - "$log" <<'EOF'
import re, sys
trace = None
res = {}
for line in open(sys.argv[1]):
    if line.startswith("# trace"):
        trace = line.split()[2]
    m = re.search(r"(\S+) cache size (\d+), \d+ req, miss ratio ([\d.]+)", line)
    if m:
        res.setdefault((trace, int(m.group(2))), {})[m.group(1)] = m.group(3)
bad = 0
print(f"{'trace':42s} {'cache':>6s} {'SIEVE':>7s} {'SieveG-0':>9s}")
for (t, c), v in sorted(res.items()):
    same = v.get("Sieve") == v.get("SieveG-0.00")
    bad += not same
    print(f"{t:42s} {c:6d} {v.get('Sieve'):>7s} {v.get('SieveG-0.00'):>9s} {'' if same else 'DIFFERENT'}")
print(f"G1 {'PASS' if bad == 0 and len(res) == 9 else 'FAIL'}: {len(res) - bad} of {len(res)} identical")
EOF
	;;
g2)
	mkdir -p "$G/tests/g2" "$G/tests/data"
	log=$G/tests/g2/g2.log
	: > "$log"
	for gap in 10 50 200 800; do
		t=$G/tests/data/twice_gap${gap}_n1000000.oracleGeneral
		[[ -f $t ]] || $PY -I "$G/scripts/gen_twice.py" --gap $gap -n 1000000 -o "$t"
		sim "$log" "$t" fifo,clock,sieve,sieveg-0.5 1000
	done
	cat "$log"
	;;
g4)
	mkdir -p "$G/tests/g4"
	log=$G/tests/g4/g4.log
	: > "$log"
	sim "$log" "$G/data/twitter/sample100/cluster13.oracleGeneral.sample100.zst" fifo,sieve 0.001,0.1
	cat "$log"
	diff <(grep "miss ratio" "$log") <(grep "miss ratio" "$G/results/phase0/cluster13_fifo_sieve.log" | sed 's/  */ /g') \
		&& echo "G4 PASS: identical to phase 0" || echo "G4 FAIL"
	;;
*)
	echo "usage: $0 g1|g2|g4" >&2
	exit 2
	;;
esac
