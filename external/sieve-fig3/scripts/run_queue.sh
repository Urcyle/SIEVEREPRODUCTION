#!/bin/bash
# Run every trace listed in a manifest, one at a time (one cachesim run needs ~6-9 GB of the
# 11 GB RAM, so runs are never in parallel). Resumable: traces whose log exists are skipped.
#
# usage: scripts/run_queue.sh <manifest.tsv>
#   manifest columns (tab separated, '#' lines ignored):
#     dataset   trace_file   sample_ratio   max_req   log_file
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

grep -v '^#' "$1" | while IFS=$'\t' read -r ds trace ratio maxreq log; do
	[[ -z $ds ]] && continue
	if [[ -f $log ]]; then
		continue
	fi
	if [[ ! -f $trace ]]; then
		echo "$(date -Iseconds) SKIP $ds $trace (not downloaded/split yet)"
		continue
	fi
	echo "$(date -Iseconds) start $ds $(basename "$trace") ratio=$ratio max_req=$maxreq"
	if scripts/run_trace.sh "$trace" "$log" "$ratio" "$maxreq" < /dev/null; then
		echo "$(date -Iseconds) done  $ds $(basename "$trace") $(grep '^# time' "$log" | head -n 1)"
	else
		echo "$(date -Iseconds) FAIL  $ds $(basename "$trace")"
	fi
done
