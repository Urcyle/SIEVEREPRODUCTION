#!/bin/bash
# Run every row of a manifest with scripts/run_sieveg.sh, one after another (ALGOS / SIZES from the
# environment). Finished logs are skipped, so the queue can be restarted at any time.
# usage: scripts/run_queue.sh manifests/<name>.tsv
# manifest columns (tab-separated, '#' = comment): name  trace_file  sample_ratio  max_req  log_file
# (trace_file and log_file relative to external/sieve-g)
G=$(cd "$(dirname "$0")/.." && pwd)
cd "$G"
grep -v '^#' "$1" | while IFS=$'\t' read -r name trace ratio max_req log; do
	echo "$(date +%T) == $name ($trace, sample_ratio $ratio, max_req $max_req)"
	scripts/run_sieveg.sh "$trace" "$log" "$ratio" "$max_req" < /dev/null || echo "$(date +%T) == $name FAILED"
done
echo "$(date +%T) queue finished: $1"
