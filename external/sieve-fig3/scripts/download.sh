#!/bin/bash
# Download trace files from the public CMU PDL mirror of the libCacheSim trace collection.
#
# usage: scripts/download.sh <remote path> [<remote path> ...]
#   remote path is relative to the dataset root, e.g.
#     metaCDN/meta_reag.oracleGeneral.zst
#     twitter/sample100/cluster7.oracleGeneral.sample100.zst
#
# Files land in data/<remote path>. Downloads resume if interrupted (curl -C -), and every file
# is checked with `zstd -t` before it is marked complete (a .ok file is written next to it).
set -uo pipefail

BASE=https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets
ROOT=$(cd "$(dirname "$0")/.." && pwd)

for rel in "$@"; do
	dst=$ROOT/data/$rel
	if [[ -f $dst.ok ]]; then
		echo "have $rel"
		continue
	fi
	mkdir -p "$(dirname "$dst")"
	echo "$(date -Iseconds) get $rel"
	for attempt in 1 2 3 4 5; do
		curl -sS -f -L -C - --retry 5 --retry-delay 10 -o "$dst" "$BASE/$rel" && break
		echo "  attempt $attempt failed, retrying" >&2
		sleep 30
	done
	if zstd -q -t "$dst"; then
		touch "$dst.ok"
		echo "$(date -Iseconds) ok  $rel ($(du -h "$dst" | cut -f1))"
	else
		echo "$(date -Iseconds) BAD $rel (zstd -t failed; delete it and rerun)" >&2
	fi
done
