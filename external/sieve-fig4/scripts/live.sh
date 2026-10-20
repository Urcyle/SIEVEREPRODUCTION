#!/bin/bash
# Live view of the Figure 4 replication in tmux session "fig4":
#   window "live": status (refreshed every 10 s) | auto-committer | top
#   other windows: one per long job (download, stats, runs), started with scripts/job.sh
# Keep the terminal with this session open: WSL stops the Linux VM, and with it every job,
# when no terminal is attached.
#
# usage: scripts/live.sh        (creates the session if needed, then attaches)
ROOT=$(cd "$(dirname "$0")/.." && pwd)
if ! tmux has-session -t fig4 2>/dev/null; then
	tmux new-session -d -s fig4 -n live -c "$ROOT" -x 200 -y 50 "watch -t -n 10 scripts/status.sh"
	tmux split-window -t fig4:live -v -l 30% -c "$ROOT" "scripts/autocommit.sh 2>&1 | tee -a logs/autocommit.log; bash"
	tmux split-window -t fig4:live.1 -h -c "$ROOT" "top -o %MEM"
	tmux select-pane -t fig4:live.0
	tmux set -t fig4 -g mouse on
	tmux set -t fig4 -g status-right "#(cd $ROOT && find results/raw -name '*.log' | wc -l) runs done | %H:%M"
fi
[[ -n ${NO_ATTACH:-} ]] || exec tmux attach -t fig4
