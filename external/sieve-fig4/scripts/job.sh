#!/bin/bash
# Start a long job in its own window of the tmux session "fig4" (see scripts/live.sh), with
# its output in logs/<name>.log. The window stays open after the job ends.
#
# usage: scripts/job.sh <name> <command...>
ROOT=$(cd "$(dirname "$0")/.." && pwd)
name=$1; shift
mkdir -p "$ROOT/logs"
cmd=$(printf '%q ' "$@")
tmux new-window -d -t fig4 -n "$name" -c "$ROOT" \
	"echo \"\$(date -Iseconds) start: $cmd\" >> logs/$name.log; $cmd 2>&1 | tee -a logs/$name.log; echo \"\$(date -Iseconds) exit \${PIPESTATUS[0]}\" | tee -a logs/$name.log; bash"
