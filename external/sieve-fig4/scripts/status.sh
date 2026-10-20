#!/bin/bash
# One screen of progress for the Figure 4 runs: downloads, the running simulation, finished
# logs, memory, and the latest commits. Used by scripts/live.sh (refreshed by `watch`).
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
echo "== $(date '+%F %T')   load $(cut -d' ' -f1-3 /proc/loadavg)   $(free -h | awk '/Mem/{print "mem used "$3" / "$2}')"
echo
echo "== jobs (logs/*.log, last line each)"
for f in $(ls -t logs/*.log 2>/dev/null | head -8); do
	printf '%-28s %s\n' "$(basename "$f" .log)" "$(tail -n 1 "$f" | cut -c1-110)"
done
echo
echo "== downloads in progress"
for f in $(find data -name '*.zst' -o -name '*.csv' 2>/dev/null); do
	[[ -L $f || -f $f.ok ]] && continue
	printf '  %-55s %s\n' "$f" "$(du -h "$f" | cut -f1)"
done
echo
echo "== simulator processes (progress = bytes read / (trace size x caches), each cache reads the trace)"
for p in $(pgrep -x cachesim) $(pgrep -x traceConv); do
	read -ra a < <(tr '\0' ' ' < /proc/$p/cmdline)
	f=${a[1]}; [[ $f = /* ]] || f=$(readlink -f /proc/$p/cwd)/$f
	rchar=$(awk '/^rchar/{print $2}' /proc/$p/io 2>/dev/null)
	rss=$(awk '/VmRSS/{printf "%.1f", $2/1048576}' /proc/$p/status)
	up=$(ps -o etime= -p $p | tr -d ' ')
	if [[ ${a[0]} == *cachesim ]]; then
		n=$(( $(tr ',' '\n' <<< "${a[3]}" | wc -l) * $(tr ',' '\n' <<< "${a[4]}" | wc -l) ))
		pct=$(awk -v r="$rchar" -v s="$(stat -L -c %s "$f")" -v n=$n 'BEGIN{printf "%.0f%%", 100*r/(s*n)}')
		printf '  %-34s %-46s %s caches  %5s  up %-9s rss %s GB\n' "$(basename "$f" .oracleGeneral.zst)" "$(cut -c1-46 <<< "${a[3]}")" "$n" "$pct" "$up" "$rss"
	else
		# traceConv reads the CSV several times (count, then backward), so no percentage
		printf '  %-34s %-46s %5s  up %-9s rss %s GB\n' "$(basename "$f")" "traceConv (converting)" "-" "$up" "$rss"
	fi
done
echo
echo "== finished runs: $(find results/raw -name '*.log' 2>/dev/null | wc -l)"
find results/raw -name '*.log' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -5 | cut -d' ' -f2 | sed 's/^/  /'
echo
echo "== last commits"
git log --format='  %h %ar  %s' -5
