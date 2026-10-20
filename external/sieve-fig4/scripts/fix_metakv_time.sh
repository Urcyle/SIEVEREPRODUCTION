#!/bin/bash
# One-off repair of the first conversion (before zero_time.py was part of convert_metakv.sh):
# set time 0 in the 5 converted Meta KV traces, verify them against the mirror, mark complete.
cd ~/sieve-fig4/data/metaKV || exit 1
~/sieve-fig4/.venv/bin/python -I ~/sieve-fig4/scripts/zero_time.py kvcache_traces_{1,2,3,4,5}.oracleGeneral.zst || exit 1
cd ~/sieve-fig4 && .venv/bin/python -I scripts/check_metakv.py data/metaKV/202206_kv_traces_all.csv.oracleGeneral.zst data/metaKV/kvcache_traces_{1,2,3,4,5}.oracleGeneral.zst \
	&& for i in 1 2 3 4 5; do touch data/metaKV/kvcache_traces_$i.oracleGeneral.zst.ok; done
