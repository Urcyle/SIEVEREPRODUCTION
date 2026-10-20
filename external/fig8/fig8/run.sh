#!/bin/bash
# Run Figure 8: generate the Zipf traces and simulate LRU, LFU, ARC, SIEVE at the paper's 8 cache
# sizes (cachesim's default list: 0.1, 0.3, 1, 3, 10, 20, 40, 80 % of the 10,000 objects).
#
# usage: fig8/run.sh   (after fig8/build.sh)   -> results/fig8_raw.tsv
#
# Workload: Zipf alpha = 1.0, 10,000 objects, 10,000,000 requests (the paper does not state its
# size; this one reproduces its miss ratios, see fig8/README.md), seeds 1-5. Seed 1 is the figure;
# seeds 2-5 show how much a different random trace moves each point.
# Each (seed, algorithm, size) is one fig8/popular_ratio run: miss ratio (identical to cachesim's)
# and the popular object ratio at the end of the trace, averaged over the whole trace, and
# averaged over its second half (sampled every 10,000 requests).
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
M=10000 N=10000000 ALPHA=1.0
SIZES="10 30 100 300 1000 2000 4000 8000"
mkdir -p data results
for s in 1 2 3 4 5; do
	t=data/zipf_${ALPHA}_m${M}_n${N}_s$s.oracleGeneral
	[[ -f $t ]] || .venv/bin/python -I fig8/gen_trace.py -m $M -n $N --alpha $ALPHA --seed $s -o "$t"
done
{
	printf 'seed\talgo\tcache_size\tcache_pct\tn_req\tmiss_ratio\tpopular_at_end\tpopular_mean\tpopular_mean_2nd_half\tH_in_true_top\n'
	for s in 1 2 3 4 5; do
		for a in lru lfu arc sieve; do
			for c in $SIZES; do echo "$s $a $c"; done
		done
	done | xargs -P "$(nproc)" -L 1 sh -c \
		'fig8/popular_ratio data/zipf_'$ALPHA'_m'$M'_n'$N'_s$0.oracleGeneral $1 $2 | awk -v s=$0 -v m='$M' '\''{printf "%s\t%s\t%s\t%g\t%s\t%s\t%s\t%s\t%s\t%s\n", s, toupper($1), $2, 100*$2/m, $3, $4, $5, $6, $7, $8}'\''' \
		| sort -t$'\t' -k1,1n -k2,2 -k3,3n
} > results/fig8_raw.tsv
echo "$(($(wc -l < results/fig8_raw.tsv) - 1)) runs -> results/fig8_raw.tsv"
