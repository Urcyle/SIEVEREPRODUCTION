#!/bin/bash
# Simulate the 12 algorithms of SIEVE Figure 3 on one trace at the two cache sizes of the
# figure (0.1% and 10% of the trace footprint), ignoring object size as in paper §4.2.
#
# usage: scripts/run_trace.sh <trace.oracleGeneral[.sampleN].zst> <log> [sample_ratio] [max_req]
#
#   sample_ratio (optional, <= 0.5): spatial sampling done inside cachesim (-s). This is
#   used only for traces whose footprint is too large for 11 GB of RAM. The footprint and
#   the cache sizes are then computed on the sampled trace.
#   max_req (optional): simulate only the first max_req requests (cachesim -n); the footprint
#   and the cache sizes are then computed on that prefix. -1 = whole trace.
#
# Two cachesim passes, both appended to <log>:
#   pass "main": fifo,lru,clock,arc,twoq,lirs,lhd,cacheus,hyperbolic,tinyLFU,sieve
#   pass "blru": lru with bloom-filter admission (admits an object on its 2nd request) = B-LRU
# Each pass is followed by the /usr/bin/time line (wall seconds, peak RSS).
# The log is written to <log>.part and renamed only when both passes succeed, so a log that
# exists is always complete.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
CACHESIM=$ROOT/external/NSDI24-SIEVE/libCacheSim/_build/bin/cachesim
ALGOS=fifo,lru,clock,arc,twoq,lirs,lhd,cacheus,hyperbolic,tinyLFU,sieve
SIZES=0.001,0.1
THREADS=${THREADS:-8}

trace=$(realpath "$1")
log=$2
ratio=${3:-1}
max_req=${4:--1}
[[ -f $log ]] && { echo "exists: $log"; exit 0; }

# One simulation at a time machine-wide (each needs 6-8 GB of the 11 GB), even when several
# queues run in parallel. After getting the lock, check again whether another queue already
# produced this log.
exec 9> "$ROOT/results/.cachesim.lock"
flock 9
[[ -f $log ]] && { echo "exists: $log"; exit 0; }
mkdir -p "$(dirname "$log")"
log=$(realpath -m "$log")

samp=()
[[ $ratio != 1 ]] && samp=(-s "$ratio")
[[ $max_req != -1 ]] && samp+=(-n "$max_req")

# cachesim also writes result/<trace> in its working directory; keep that out of the repo
work=$ROOT/results/tmp/work.$$
mkdir -p "$work"
trap 'rm -rf "$work"' EXIT
cd "$work"

{
	echo "# trace $trace"
	echo "# sample_ratio $ratio"
	echo "# max_req $max_req"
	echo "# cachesim $(git -C "$ROOT/external/NSDI24-SIEVE" rev-parse --short HEAD)"
	echo "# started $(date -Iseconds) on $(hostname), $THREADS threads"
	echo "# pass main"
} > "$log.part"
/usr/bin/time -f "# time wall_s=%e maxrss_kb=%M" "$CACHESIM" "$trace" oracleGeneral "$ALGOS" "$SIZES" \
	--ignore-obj-size 1 --num-thread "$THREADS" "${samp[@]}" >> "$log.part" 2>> "$log.part.err"
grep "^# time" "$log.part.err" | tail -n 1 >> "$log.part"

echo "# pass blru" >> "$log.part"
/usr/bin/time -f "# time wall_s=%e maxrss_kb=%M" "$CACHESIM" "$trace" oracleGeneral lru "$SIZES" \
	-a bloom-filter --ignore-obj-size 1 --num-thread "$THREADS" "${samp[@]}" >> "$log.part" 2>> "$log.part.err"
grep "^# time" "$log.part.err" | tail -n 1 >> "$log.part"
echo "# finished $(date -Iseconds)" >> "$log.part"

n=$(grep -c "miss ratio" "$log.part" || true)
if [[ $n -ne 24 ]]; then
	echo "expected 24 miss-ratio lines, got $n; see $log.part and $log.part.err" >&2
	exit 1
fi
mv "$log.part" "$log"
rm -f "$log.part.err"
