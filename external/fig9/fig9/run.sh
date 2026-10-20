#!/bin/bash
# Run Figure 9 (after fig9/build.sh). Seeds 1-5; seed 1 is the figure, seeds 2-5 show how much a
# different random trace moves each result.
#
# (a), (b): Zipf alpha 0.2, 0.4, ..., 1.6; 10,000 objects, 10 M requests (the Figure 8 workload:
#   the paper's alpha = 1.0 points are its Figure 8 values at 10%); LRU, LFU, ARC, SIEVE at the
#   large cache, 10% = 1,000 objects; external/fig8/fig8/popular_ratio
#   -> results/fig9ab_raw.tsv
# (c): Zipf alpha 0.8, 1.0, 1.2; the generator's default population of 1,000,000 objects; the small
#   cache, 0.1% = 1,000 objects; SIEVE's hand recorded for 2^18 = 262,144 evictions (the paper's
#   curves end after that many evictions); fig9/sieve_hand. The traces have 2,000,000 requests
#   (the last eviction needed comes at 1.4 M requests at most); the generator draws requests in
#   batches of 1 M from the seeded stream, so these are the first 2 M requests of the generator's
#   default 100 M-request trace.
#   -> data/hand/ (one line per eviction), condensed by fig9/hand_summary.py into results/
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
PY=external/fig8/.venv/bin/python
GEN=external/fig8/fig8/gen_trace.py
mkdir -p data/hand results
gen() {  # alpha m n seed -> path
	local t=data/zipf_$1_m$2_n$3_s$4.oracleGeneral
	[[ -f $t ]] || $PY -I $GEN -m "$2" -n "$3" --alpha "$1" --seed "$4" -o "$t" 2> /dev/null
	echo "$t"
}

# (a), (b)
for s in 1 2 3 4 5; do for a in 0.2 0.4 0.6 0.8 1.0 1.2 1.4 1.6; do gen $a 10000 10000000 $s > /dev/null; done; done
{
	printf 'seed\talpha\talgo\tcache_size\tn_req\tmiss_ratio\tpopular_at_end\tpopular_mean\tpopular_mean_2nd_half\tH_in_true_top\n'
	for s in 1 2 3 4 5; do for a in 0.2 0.4 0.6 0.8 1.0 1.2 1.4 1.6; do for al in lru lfu arc sieve; do
		echo "$s $a $al"
	done; done; done | xargs -P "$(nproc)" -L 1 sh -c \
		'external/fig8/fig8/popular_ratio data/zipf_$1_m10000_n10000000_s$0.oracleGeneral $2 1000 \
		 | awk -v s=$0 -v a=$1 '\''{printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n", s, a, toupper($1), $2, $3, $4, $5, $6, $7, $8}'\''' \
		| sort -t$'\t' -k1,1n -k2,2n -k3,3
} > results/fig9ab_raw.tsv
echo "(a), (b): $(($(wc -l < results/fig9ab_raw.tsv) - 1)) runs -> results/fig9ab_raw.tsv"

# (c)
for s in 1 2 3 4 5; do for a in 0.8 1.0 1.2; do
	t=$(gen $a 1000000 2000000 $s)
	fig9/sieve_hand "$t" 1000 262144 > data/hand/hand_a${a}_s$s.txt &
done; wait; done
$PY -I fig9/hand_summary.py data/hand results
