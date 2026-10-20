#!/bin/bash
# Download the Twitter files chosen by choose_twitter.py.
#
# usage: scripts/download_twitter.sh manifests/twitter_choice.tsv
#   sample100 files: all 54 are fetched first (needed for trace_stats.py), not here
#   sample10 / full whole trace: scripts/download.sh
#   full with a request cap: scripts/download_prefix.sh (streams just the first max_req requests)
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)

tail -n +2 "$1" | while IFS=$'\t' read -r c version extra cap _; do
	case $version in
	sample10) "$ROOT/scripts/download.sh" "twitter/sample10/$c.oracleGeneral.sample10.zst" ;;
	full)
		if [[ $cap == -1 ]]; then
			"$ROOT/scripts/download.sh" "twitter/$c.oracleGeneral.zst"
		fi
		;;
	esac
done
# prefixes last: they are the largest transfers
tail -n +2 "$1" | while IFS=$'\t' read -r c version extra cap _; do
	if [[ $version == full && $cap != -1 ]]; then
		"$ROOT/scripts/download_prefix.sh" "twitter/$c.oracleGeneral.zst" "$cap"
	fi
done
