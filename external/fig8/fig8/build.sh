#!/bin/bash
# Build cachesim and the libCacheSim library from the pinned simulator submodule (the authors'
# artifact, Urcyle/NSDI24-SIEVE @ 0346336) and set up the Python venv.
# usage: fig8/build.sh
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
# SIEVEREPRODUCTION: the shared simulator (external/NSDI24-SIEVE here is a link to it)
"$ROOT/../../scripts/setup_simulator.sh"
mkdir -p results/tmp external/NSDI24-SIEVE/libCacheSim/_build
cd external/NSDI24-SIEVE/libCacheSim/_build
cmake -DCMAKE_BUILD_TYPE=Release .. > "$ROOT/results/tmp/build.log" 2>&1
make -j"$(nproc)" >> "$ROOT/results/tmp/build.log" 2>&1
cd "$ROOT"
ls -la external/NSDI24-SIEVE/libCacheSim/_build/bin/cachesim
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
echo "build ok"
# fig8/popular_ratio: linked against the same libCacheSim libraries as cachesim
B=external/NSDI24-SIEVE/libCacheSim/_build/libCacheSim
cc -O3 -DNDEBUG -DOS_LINUX -DSUPPORT_ZSTD_TRACE=1 -DUSE_HUGEPAGE=1 -c fig8/popular_ratio.c -o results/tmp/popular_ratio.o \
	-Iexternal/NSDI24-SIEVE/libCacheSim/libCacheSim/include $(pkg-config --cflags glib-2.0)
c++ -O3 results/tmp/popular_ratio.o -o fig8/popular_ratio \
	$B/cache/libcachelib.a $B/cache/eviction/libevictionC.a $B/cache/eviction/libevictionCPP.a \
	$B/traceReader/libtraceReader.a $B/profiler/libprofiler.a $B/dataStructure/libdataStructure.a \
	$B/dataStructure/hash/libds_hash.a $B/utils/libutils.a $B/cache/admission/libadmissionC.a \
	$B/cache/admission/libadmissionCpp.a $B/cache/prefetch/libprefetchC.a $B/cache/libcachelib.a \
	$B/dataStructure/libdataStructure.a $B/traceReader/libtraceReader.a $B/utils/libutils.a \
	$(pkg-config --libs glib-2.0) -ltcmalloc_minimal -lzstd -lpthread -lm
echo "popular_ratio ok"
