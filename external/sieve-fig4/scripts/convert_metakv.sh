#!/bin/bash
# Convert Meta's 5 KV traces (data/metaKV/csv/kvcache_traces_<i>.csv) to oracleGeneral with
# libCacheSim's own traceConv, the same way the CMU mirror's merged file
# (metaKV/202206_kv_traces_all.csv.oracleGeneral.zst) was made:
#   obj_id = key, size = size, each row repeated op_count times (cnt-col), rows with size 0
#   dropped by the reader (GETs that missed and DELETEs), time 0 (the CSV has no time column;
#   set by scripts/zero_time.py).
# scripts/check_metakv.py verifies the result against the mirror's merged file.
#
# usage: scripts/convert_metakv.sh      (waits for each download's .ok file)
# output: data/metaKV/kvcache_traces_<i>.oracleGeneral.zst
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
CONV=$ROOT/external/NSDI24-SIEVE/libCacheSim/_build/bin/traceConv
[[ -x $CONV ]] || (cd "$ROOT/external/NSDI24-SIEVE/libCacheSim/_build" && make -j4 traceConv > /dev/null)
cd "$ROOT/data/metaKV"
for i in 1 2 3 4 5; do
	out=kvcache_traces_$i.oracleGeneral.zst
	[[ -f $out.ok ]] && { echo "have $out"; continue; }
	until [[ -f csv/kvcache_traces_$i.csv.ok ]]; do sleep 30; done
	echo "$(date -Iseconds) convert trace $i"
	"$CONV" "csv/kvcache_traces_$i.csv" csv -o "kvcache_traces_$i.oracleGeneral" \
		-t "obj-id-col=1,obj-size-col=3,cnt-col=4,has-header=true,delimiter=,,obj-id-is-num=true" 2>&1 \
		| grep -E "finished|ERROR" | sed 's/\x1b\[[0-9;]*m//g'
	zstd -q -T4 -12 --rm -f "kvcache_traces_$i.oracleGeneral" -o "$out"
	rm -f "kvcache_traces_$i.oracleGeneral.reverse"
	# traceConv leaves time at 0xFFFFFFFF without a time column; the mirror's file has 0
	"$ROOT/.venv/bin/python" -I "$ROOT/scripts/zero_time.py" "$out"
	touch "$out.ok"
	echo "$(date -Iseconds) ok  $out ($(du -h "$out" | cut -f1))"
done
