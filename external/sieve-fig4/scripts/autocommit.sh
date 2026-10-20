#!/bin/bash
# Commit new result files as soon as they appear (finished run logs, trace statistics,
# validation logs). Checks once a minute; runs until stopped. Used by scripts/live.sh.
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
while true; do
	new=$(git ls-files --others --exclude-standard -- 'results/raw/*.log' 'results/raw/**/*.log' 'results/stats/*' 'results/validation/*')
	if [[ -n $new ]]; then
		names=$(echo "$new" | sed -E 's#^results/(raw|stats|validation)/##; s#\.(log|tsv)$##' | paste -sd, - | sed 's/,/, /g' | cut -c1-150)
		git add -- $new && git commit -q -m "Add results: $names" -- $new \
			&& echo "$(date +%H:%M) committed $names ($(git rev-parse --short HEAD))"
	fi
	sleep 60
done
