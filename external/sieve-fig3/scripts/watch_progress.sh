#!/bin/bash
# Show the progress of the Twitter run queue (scripts/run_queue.sh) once a minute until it
# exits, and commit each finished Twitter log as soon as it appears.
#
# usage: scripts/watch_progress.sh          # report and commit
#        NO_COMMIT=1 scripts/watch_progress.sh   # report only
#
# Keep this running in an open WSL terminal: WSL shuts the Linux VM down when no terminal is
# attached, and that also kills the detached queue.
ROOT=$(cd "$(dirname "$0")/.." && pwd)
last=""

commit_new() {
	[[ -n ${NO_COMMIT:-} ]] && return
	local new names
	new=$(git -C "$ROOT" ls-files --others --exclude-standard -- 'results/raw/twitter/*.log')
	[[ -z $new ]] && return
	names=$(echo "$new" | xargs -n1 basename | sed 's/\.log$//' | paste -sd, -)
	git -C "$ROOT" add -- $new
	git -C "$ROOT" commit -q -m "Add Twitter run results: $names" -- $new \
		&& echo "$(date +%H:%M) committed $names ($(git -C "$ROOT" rev-parse --short HEAD))"
}

while pgrep -f 'scripts/run_queue.sh' > /dev/null; do
	commit_new
	n=$(ls "$ROOT"/results/raw/twitter/*.log 2>/dev/null | wc -l)
	cur=$(ps -eo args | grep -v grep | grep -m1 'bin/cachesim /' | grep -oE 'cluster[0-9]+' | head -n 1)
	s="Twitter done $n/54, running: ${cur:-none}"
	[[ $s != "$last" ]] && echo "$(date +%H:%M) $s" && last=$s
	sleep 60
done
commit_new
n=$(ls "$ROOT"/results/raw/twitter/*.log | wc -l)
echo "$(date +%H:%M) queue exited. Twitter done $n/54"
[[ $n -eq 54 ]] || echo "WARNING: queue stopped before all Twitter traces in the manifest finished"
