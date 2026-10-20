#!/bin/bash
# Simulate the 12 algorithms of SIEVE Figure 4 on one whole trace at the figure's two cache
# sizes (0.1% and 10% of the trace footprint), ignoring object size as in paper §4.2.
#
# usage: scripts/run_trace.sh <trace.oracleGeneral.zst> <out_dir> [large_groups]
#
# Cache sizes come from results/stats/<trace>.tsv (scripts/trace_stats.py): the same sizes
# cachesim computes itself from the fractions 0.001 and 0.1, passed as absolute object counts
# so that a trace can be split over several cachesim processes.
#
# To fit whole traces in 11 GB, the work is split into passes, each a separate cachesim run:
#   small       all 11 algorithms at the small size (tiny caches: little memory)
#   large.<i>   one group of algorithms at the large size; groups come from large_groups,
#               ';'-separated, e.g. "fifo,lru,clock,sieve;arc,lhd;cacheus"
#               (default: all 11 in one group)
#   blru        LRU with bloom-filter admission (admits an object on its 2nd request) = B-LRU,
#               both sizes
# Environment:
#   SIZES=small|large|both (default both): which cache sizes to run (B-LRU follows it)
#   SAMPLE=<ratio>: spatial sampling inside cachesim (-s; keeps objects with
#               hash(obj_id) % (1/ratio) == 0, and every request to them). Cache sizes are then
#               given as fractions, so cachesim computes the footprint on the sampled trace.
#   ALGOS_LARGE: run only these algorithms (comma list) at the large size, one per group
#   BLRU_TOOL=1: run the B-LRU pass with tools/blru_bitmap instead of cachesim's
#               "lru -a bloom-filter", whose table of all objects ever seen does not fit in
#               11 GB for Tencent (529 M objects); same results (see the tool's header)
#   NO_BLRU=1:  skip the B-LRU pass (implied by ALGOS_LARGE: such runs are only validation)
# Each pass writes <out_dir>/<pass>.log (via .part, renamed only on success), and a pass whose
# log exists is skipped, so an interrupted trace resumes at the next unfinished pass.
set -euo pipefail
# The body is one { } block so bash reads all of it before running: editing this file while
# a run is in progress cannot change the running script.
{

ROOT=$(cd "$(dirname "$0")/.." && pwd)
CACHESIM=$ROOT/external/NSDI24-SIEVE/libCacheSim/_build/bin/cachesim
ALGOS=fifo,lru,clock,arc,twoq,lirs,lhd,cacheus,hyperbolic,tinyLFU,sieve
THREADS=${THREADS:-8}

trace=$(realpath "$1")
out=$(realpath -m "$2")
groups=${3:-$ALGOS}
name=$(basename "$1" .oracleGeneral.zst)
stats=$ROOT/results/stats/$name.tsv
[[ -f $stats ]] || { echo "no $stats; run scripts/trace_stats.py first" >&2; exit 1; }
read -r _ _ n_req _ _ wss small large < "$stats"
SIZES=${SIZES:-both}
SAMPLE=${SAMPLE:-1}
samp=()
if [[ $SAMPLE != 1 ]]; then
	samp=(-s "$SAMPLE")
	small=0.001 large=0.1
fi
[[ -n ${ALGOS_LARGE:-} ]] && groups=${ALGOS_LARGE//,/;}
mkdir -p "$out"

# At most 2 simulations at a time machine-wide (each pass is planned to need
# well under half of the 11 GB, see scripts/plan_groups.py). A pass also holds its own lock,
# so two queues never run the same pass.
# tools/blru_bitmap passes (1 core, < 1 GB) may also use a third slot. The SLOTS variable of
# older manifests is ignored.
take_slot() {  # <number of slots this pass may use>
	while true; do
		for ((k = 0; k < $1; k++)); do
			exec {slot}> "$ROOT/results/.cachesim.slot$k"
			flock -n $slot && return
			exec {slot}>&-
		done
		sleep 10
	done
}

# cachesim also writes result/<trace> in its working directory; keep that out of the repo
work=$ROOT/results/tmp/work.$$
mkdir -p "$work"
trap 'rm -rf "$work"' EXIT
cd "$work"

run_pass() {  # <pass name> <expected miss-ratio lines> <cachesim args...>
	local pass=$1 want=$2; shift 2
	local log=$out/$pass.log
	[[ -f $log ]] && { echo "$(date +%T) $name $pass: done before, skipping"; return; }
	exec {plock}> "$log.lock"
	flock -n $plock || { echo "$(date +%T) $name $pass: another queue is running it, skipping"; exec {plock}>&-; return; }
	# whole-trace validation passes (ALGOS_LARGE; ~53 M-object caches, 4-5 GB each) run one at a
	# time: two of them could push the machine into swap thrashing
	if [[ $1 == blru_bitmap ]]; then take_slot 3
	elif [[ -n ${ALGOS_LARGE:-} ]]; then take_slot 1
	else take_slot 2; fi
	if [[ -f $log ]]; then
		echo "$(date +%T) $name $pass: done meanwhile, skipping"
		exec {slot}>&- {plock}>&-; rm -f "$log.lock"; return
	fi
	echo "$(date +%T) $name $pass: start ($*)"
	{
		echo "# trace $trace"
		echo "# requests $n_req wss_obj $wss small $small large $large"
		echo "# sample_ratio $SAMPLE"
		echo "# pass $pass"
		echo "# sizes $SIZES"
		echo "# cachesim $(git -C "$ROOT/external/NSDI24-SIEVE" rev-parse --short HEAD) args: $*"
		echo "# started $(date -Iseconds) on $(hostname), $THREADS threads"
	} > "$log.part"
	if [[ $1 == blru_bitmap ]]; then
		# shellcheck disable=SC2016
		/usr/bin/time -f "# time wall_s=%e maxrss_kb=%M" bash -c 'zstd -dc < "$1" | "$2" "$3" "$4"' _ \
			"$trace" "$ROOT/tools/blru_bitmap" "$name" "$2" >> "$log.part" 2> "$log.part.err"
	else
		/usr/bin/time -f "# time wall_s=%e maxrss_kb=%M" "$CACHESIM" "$trace" oracleGeneral "$@" \
			--ignore-obj-size 1 --num-thread "$THREADS" "${samp[@]}" >> "$log.part" 2> "$log.part.err"
	fi || {
		echo "$(date +%T) $name $pass: cachesim FAILED, see $log.part.err" >&2; exec {slot}>&- {plock}>&-; return 1; }
	grep "^# time" "$log.part.err" | tail -n 1 >> "$log.part"
	echo "# finished $(date -Iseconds)" >> "$log.part"
	exec {slot}>&-
	local n
	# result lines only: "result/<trace> ..." (several caches) or "<trace path> ..." (one cache;
	# cachesim then also prints INFO progress lines per simulated day, and the result line starts
	# with the escape code that ends the last INFO line, so colour codes are stripped first)
	n=$(sed 's/\x1b\[[0-9;]*m//g' "$log.part" | grep -cE '^(result/|/)\S* +\S+ cache size .* req, miss ratio' || true)
	if [[ $n -ne $want ]]; then
		echo "$(date +%T) $name $pass: expected $want miss-ratio lines, got $n; see $log.part.err" >&2
		exec {plock}>&-
		return 1
	fi
	mv "$log.part" "$log"
	rm -f "$log.part.err" "$log.lock"
	exec {plock}>&-
	echo "$(date +%T) $name $pass: ok, $(grep '^# time' "$log")"
}

[[ $SIZES != large ]] && run_pass small 11 "$ALGOS" "$small"
if [[ $SIZES != small ]]; then
	# Algorithms that already have a finished large pass in this run (possibly from an earlier
	# grouping) are left out; new passes get the next free numbers.
	done_algos=$(sed -n 's/^# cachesim .* args: \([^ ]*\) .*/\1/p' "$out"/large.*.log 2>/dev/null | tr ',' '\n' | sort -u || true)
	i=$(find "$out" -maxdepth 1 -name "large.*.log" | wc -l)
	IFS=';' read -ra G <<< "$groups"
	for g in "${G[@]}"; do
		g=$(tr "," "\n" <<< "$g" | { grep -vxF -f <(echo "$done_algos"; echo __none__) || true; } | paste -sd, -)
		[[ -z $g ]] && continue
		i=$((i + 1))
		run_pass "large.$i" "$(tr ',' '\n' <<< "$g" | wc -l)" "$g" "$large"
	done
fi
[[ -n ${NO_BLRU:-}${ALGOS_LARGE:-} ]] && SIZES=none
if [[ -n ${BLRU_TOOL:-} && $SIZES != none ]]; then
	case $SIZES in
		small) run_pass blru 1 blru_bitmap "$small" ;;
		large) run_pass blru 1 blru_bitmap "$large" ;;
		*) run_pass blru 2 blru_bitmap "$small,$large" ;;
	esac
	SIZES=none
fi
case $SIZES in
	none) ;;
	small) run_pass blru 1 lru "$small" -a bloom-filter ;;
	large) run_pass blru 1 lru "$large" -a bloom-filter ;;
	*) run_pass blru 2 lru "$small,$large" -a bloom-filter ;;
esac
echo "$(date +%T) $name: this queue's passes done (passes another queue was running are not waited for)"
exit
}
