#!/bin/bash
# CACHEUS draws its learning rate (0.001 + (next_rand() % 1000) / 1000) when the cache is created.
# cachesim creates the caches in its main thread, algorithm by algorithm and size by size, from a
# random state that starts at 0, so the rate depends on how many caches drew before it in the
# same process. In a run of all algorithms at the sizes 0.001,0.1 (as the paper's figure needs),
# CACHEUS small gets draw 1 and CACHEUS large draw 2; in this replication's large-cache passes
# CACHEUS was created first (draw 1). This runs CACHEUS at 0.001,0.1 in one process (large = draw
# 2) to see whether that reproduces the paper's CACHEUS values.
# Result (2026-10-10): no. The miss ratios are identical to the replication's (draw 1) runs to 4
# decimals (tencent_photo2 10% large 0.2447; kvcache_traces_1 0.3117 / 0.0778), so the learning
# rate draw does not explain CACHEUS's differences from the paper.
# usage: scripts/cacheus_draw.sh   -> results/validation/cacheus_draw/<trace>.log
ROOT=$(cd "$(dirname "$0")/.." && pwd)
CACHESIM=$ROOT/external/NSDI24-SIEVE/libCacheSim/_build/bin/cachesim
out=$ROOT/results/validation/cacheus_draw
mkdir -p "$out" "$ROOT/results/tmp/cacheus_draw"
cd "$ROOT/results/tmp/cacheus_draw" || exit 1
run() {  # <name> <trace> [extra cachesim args]
	local name=$1 trace=$2; shift 2
	[[ -f $out/$name.log ]] && return
	{ echo "# trace $trace"; echo "# args: cacheus 0.001,0.1 --ignore-obj-size 1 $*"; } > "$out/$name.log.part"
	/usr/bin/time -f "# time wall_s=%e maxrss_kb=%M" "$CACHESIM" "$ROOT/$trace" oracleGeneral cacheus 0.001,0.1 \
		--ignore-obj-size 1 --num-thread 2 "$@" 2>&1 | grep -E "cache size|^# time|working set size" >> "$out/$name.log.part" \
		&& mv "$out/$name.log.part" "$out/$name.log"
}
run tencent_photo2.s10 data/tencentPhoto/tencent_photo2.oracleGeneral.zst -s 0.1 &
run kvcache_traces_1 data/metaKV/kvcache_traces_1.oracleGeneral.zst &
wait
cat "$out"/*.log
