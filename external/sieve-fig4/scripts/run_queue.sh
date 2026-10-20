#!/bin/bash
# Run every trace of a manifest with scripts/run_trace.sh, one after another. Finished passes
# are skipped, so the queue can be restarted at any time.
#
# usage: scripts/run_queue.sh manifests/fig4.tsv
# manifest columns (tab-separated, '#' = comment):
#   dataset  trace_file  [run_suffix (- or empty = none)  [env assignments for run_trace.sh,
#   space-separated]]
# e.g.  tencentPhoto  data/tencentPhoto/tencent_photo1.oracleGeneral.zst  .s10  SAMPLE=0.1 SIZES=large
# The run goes to results/raw/<dataset>/<trace><run_suffix>/.
# A trace file that is not there yet (still downloading/converting, no .ok) is waited for, and
# its stats (results/stats/<trace>.tsv) are computed first if missing. Large-cache groups are
# planned from the stats (scripts/plan_groups.py; for a sampled run, on the sampled size).
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
{
# fields are split with awk on single tabs ("read" with IFS=tab would merge empty columns)
grep -v '^#' "$1" | awk -F'\t' '{print $1 "|" $2 "|" ($3 == "" ? "-" : $3) "|" $4}' \
	| while IFS='|' read -r ds trace suffix envs; do
	[[ $suffix == - ]] && suffix=
	name=$(basename "$trace" .oracleGeneral.zst)
	if [[ ! -f results/stats/$name.tsv ]]; then
		echo "$(date +%T) == $ds/$name: waiting for the trace file"
		until [[ -f $trace.ok || ( -L $trace && -f $(readlink -f "$trace").ok ) ]]; do sleep 60; done
		echo "$(date +%T) == $ds/$name: computing stats"
		.venv/bin/python -I scripts/trace_stats.py "$trace" > "results/stats/$name.tsv.part" 2> /dev/null \
			&& mv "results/stats/$name.tsv.part" "results/stats/$name.tsv"
	fi
	read -r _ _ _ _ _ _ _ large < "results/stats/$name.tsv"
	ratio=$(grep -oP 'SAMPLE=\K\S+' <<< "$envs" || echo 1)
	groups=$(.venv/bin/python -I scripts/plan_groups.py "$(.venv/bin/python -c "print(int($large * $ratio))")")
	echo "$(date +%T) == $ds/$name$suffix: ${envs:-whole trace, both sizes}; large groups $groups"
	env $envs scripts/run_trace.sh "$trace" "results/raw/$ds/$name$suffix" "$groups" < /dev/null \
		|| echo "$(date +%T) == $ds/$name$suffix FAILED"
done
echo "$(date +%T) queue finished"
exit
}
