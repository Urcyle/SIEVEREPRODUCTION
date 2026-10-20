#!/bin/bash
# Two extra Tencent experiments that explain the remaining differences from the paper
# (see fig4/README.md):
#  1. CACHEUS spread: CACHEUS draws its learning rate at random when the cache is created; when
#     cachesim runs one cache, the seed is the time, so each run draws a new rate. Three more
#     run of CACHEUS alone on photo2's 10% sample (large cache) shows how much that moves it
#     (FIFO runs in its own process for the reduction).
#  2. Small cache on the 10% sample: whether the paper's Tencent small-cache values match the
#     sample (as its large-cache values do) better than the whole trace.
# usage: scripts/extra_tencent.sh   (resumable; uses the normal slots)
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
T=data/tencentPhoto
# Result of run 1 (2026-10-10): the same miss ratio as the first run (0.2447), so the time seed
# does not change CACHEUS here; runs 2-3 were dropped (see scripts/cacheus_draw.sh).
for i in 1; do
	SAMPLE=0.1 SIZES=large NO_BLRU=1 scripts/run_trace.sh $T/tencent_photo2.oracleGeneral.zst \
		results/raw/tencentPhoto/tencent_photo2.s10_cacheus$i "fifo;cacheus"
done
for t in tencent_photo1 tencent_photo2; do
	SAMPLE=0.1 SIZES=small scripts/run_trace.sh $T/$t.oracleGeneral.zst results/raw/tencentPhoto/$t.s10small
done
