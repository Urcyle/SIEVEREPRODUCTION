#!/bin/bash
# Download Meta's KV cache traces (CacheLib, 202206: 5 traces, kvcache_traces_{1..5}.csv) from
# Meta's public S3 bucket. These are the 5 "Meta KV, 2022" traces of the paper's Table 1; the
# CMU mirror has them only merged into one file (metaKV/202206_kv_traces_all...).
#
# usage: scripts/download_metakv.sh
# Files land in data/metaKV/csv/. Downloads resume (curl -C -), and each file is marked complete
# (.ok) only when its size equals the size S3 reports.
set -uo pipefail
BASE=https://cachelib-workload-sharing.s3.amazonaws.com/pub/kvcache/202206
ROOT=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$ROOT/data/metaKV/csv"
for i in 1 2 3 4 5; do
	f=kvcache_traces_$i.csv
	dst=$ROOT/data/metaKV/csv/$f
	[[ -f $dst.ok ]] && { echo "have $f"; continue; }
	want=$(curl -sI "$BASE/$f" | tr -d '\r' | awk 'tolower($1)=="content-length:"{print $2}')
	echo "$(date -Iseconds) get $f ($want bytes)"
	for attempt in 1 2 3 4 5; do
		curl -sS -f -C - --retry 5 --retry-delay 10 -o "$dst" "$BASE/$f" && break
		sleep 30
	done
	have=$(stat -c %s "$dst")
	if [[ $have == "$want" ]]; then
		touch "$dst.ok"; echo "$(date -Iseconds) ok  $f"
	else
		echo "$(date -Iseconds) BAD $f: $have of $want bytes" >&2
	fi
done
