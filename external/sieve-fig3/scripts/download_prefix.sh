#!/bin/bash
# Download only the first N requests of a trace: stream it, decompress, keep the first N
# 24-byte records, and recompress. This is for full Twitter clusters where only a prefix is
# simulated (see choose_twitter.py). It avoids downloading e.g. all 27 GB of cluster1.
#
# usage: scripts/download_prefix.sh <remote path> <n_req>
#   writes data/<remote path minus .zst>.first<n_req>.zst  (+ .ok when verified)
set -uo pipefail

BASE=https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets
ROOT=$(cd "$(dirname "$0")/.." && pwd)
rel=$1
n=$2
dst=$ROOT/data/${rel%.zst}.first$n.zst
[[ -f $dst.ok ]] && { echo "have $dst"; exit 0; }
mkdir -p "$(dirname "$dst")"
echo "$(date -Iseconds) get first $n req of $rel"
# head closes the pipe after n records; curl/zstd then exit with SIGPIPE, which is expected
curl -sS -f -L "$BASE/$rel" | zstd -dc -q 2>/dev/null | head -c $((n * 24)) | zstd -q -T4 -3 -f -o "$dst"
got=$(( $(zstd -dc -q "$dst" | wc -c) / 24 ))
if [[ $got -eq $n ]]; then
	touch "$dst.ok"
	echo "$(date -Iseconds) ok  $dst ($got req, $(du -h "$dst" | cut -f1))"
else
	echo "$(date -Iseconds) BAD $dst: $got of $n req (trace shorter than n, or download failed)" >&2
	exit 1
fi
