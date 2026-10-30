#!/bin/bash
# Simulate SIEVE-G next to FIFO and SIEVE on one trace at the cache sizes of Figure 3 (0.1% and
# 10% of the trace footprint), object size ignored. Made from external/sieve-fig3/scripts/
# run_trace.sh: the same arguments, lock and log format, but one cachesim pass only (no B-LRU).
#
# usage: scripts/run_sieveg.sh <trace.oracleGeneral[.sampleN].zst> <log> [sample_ratio] [max_req]
#   sample_ratio, max_req: as in run_trace.sh (cachesim -s / -n; 1 / -1 = whole trace)
# environment:
#   ALGOS  algorithms (default fifo,sieve,sieveg-0.25,sieveg-0.5,sieveg-1.0: the dev set)
#   SIZES  cache sizes (default 0.001,0.1)
# The log must contain one miss-ratio line per algorithm and size (10 with the defaults). It is
# written to <log>.part and renamed only when complete, so a log that exists is complete, and an
# existing log is not run again.
set -euo pipefail

G=$(cd "$(dirname "$0")/.." && pwd)            # external/sieve-g
ROOT=$(cd "$G/../.." && pwd)                   # the repository
CACHESIM=$ROOT/external/NSDI24-SIEVE/libCacheSim/_build/bin/cachesim
ALGOS=${ALGOS:-fifo,sieve,sieveg-0.25,sieveg-0.5,sieveg-1.0}
SIZES=${SIZES:-0.001,0.1}
THREADS=${THREADS:-8}
want=$(( $(tr ',' '\n' <<< "$ALGOS" | wc -l) * $(tr ',' '\n' <<< "$SIZES" | wc -l) ))

trace=$(realpath "$1")
log=$2
ratio=${3:-1}
max_req=${4:--1}
[[ -f $log ]] && { echo "exists: $log"; exit 0; }

# One simulation at a time machine-wide (11 GB RAM). After getting the lock, check again whether
# another queue already produced this log.
mkdir -p "$G/results"
exec 9> "$G/results/.cachesim.lock"
flock 9
[[ -f $log ]] && { echo "exists: $log"; exit 0; }
mkdir -p "$(dirname "$log")"
log=$(realpath -m "$log")

samp=()
[[ $ratio != 1 ]] && samp=(-s "$ratio")
[[ $max_req != -1 ]] && samp+=(-n "$max_req")

# cachesim also writes result/<trace> in its working directory; keep that out of the repo
work=$G/results/tmp/work.$$
mkdir -p "$work"
trap 'rm -rf "$work"' EXIT
cd "$work"

{
	echo "# trace $trace"
	echo "# sample_ratio $ratio"
	echo "# max_req $max_req"
	echo "# cachesim $(git -C "$ROOT/external/NSDI24-SIEVE" rev-parse --short HEAD) + patches/NSDI24-SIEVE-build-fix.patch + patches/SIEVE-G.patch"
	echo "# algos $ALGOS"
	echo "# sizes $SIZES"
	echo "# started $(date -Iseconds) on $(hostname), $THREADS threads"
	echo "# pass main"
} > "$log.part"
/usr/bin/time -f "# time wall_s=%e maxrss_kb=%M" "$CACHESIM" "$trace" oracleGeneral "$ALGOS" "$SIZES" \
	--ignore-obj-size 1 --num-thread "$THREADS" "${samp[@]}" >> "$log.part" 2>> "$log.part.err"
grep "^# time" "$log.part.err" | tail -n 1 >> "$log.part"
echo "# finished $(date -Iseconds)" >> "$log.part"

n=$(grep -c "miss ratio" "$log.part" || true)
if [[ $n -ne $want ]]; then
	echo "expected $want miss-ratio lines, got $n; see $log.part and $log.part.err" >&2
	exit 1
fi
mv "$log.part" "$log"
rm -f "$log.part.err"
echo "$(date +%T) ok $(basename "$log"): $(grep '^# time' "$log")"
