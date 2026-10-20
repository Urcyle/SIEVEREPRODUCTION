#!/bin/bash
# Run scripts/trace_stats.py on the given traces, 3 at a time, one output file per trace:
# results/stats/<trace>.tsv (skipped if it exists).
# usage: scripts/stats_all.sh <trace.zst> [...]
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
for t in "$@"; do
	out=results/stats/$(basename "$t" .oracleGeneral.zst).tsv
	[[ -f $out ]] && { echo "have $out"; continue; }
	echo "$t $out"
done | grep -v '^have' | xargs -P 3 -L 1 sh -c '.venv/bin/python -I scripts/trace_stats.py "$0" > "$1.part" && mv "$1.part" "$1" && echo "$(date -Iseconds) done $1: $(cat "$1")"'
