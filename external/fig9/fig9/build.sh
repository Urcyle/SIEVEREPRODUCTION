#!/bin/bash
# Build everything Figure 9 needs. The simulator, the Zipf trace generator and the popular-object-
# ratio tool come from the Figure 8 replication (submodule external/fig8, which itself pins the
# authors' artifact); they are built there by its own build script, and not copied here. This
# repository adds fig9/sieve_hand, linked against the same libCacheSim build.
# usage: fig9/build.sh
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
# SIEVEREPRODUCTION: external/fig8 is a link to ../../fig8 (the copy of the Figure 8 repository)
external/fig8/fig8/build.sh
F8=external/fig8
B=$F8/external/NSDI24-SIEVE/libCacheSim/_build/libCacheSim
mkdir -p results/tmp
cc -O3 -DNDEBUG -DOS_LINUX -DSUPPORT_ZSTD_TRACE=1 -DUSE_HUGEPAGE=1 -c fig9/sieve_hand.c -o results/tmp/sieve_hand.o \
	-I$F8/external/NSDI24-SIEVE/libCacheSim/libCacheSim/include $(pkg-config --cflags glib-2.0)
c++ -O3 results/tmp/sieve_hand.o -o fig9/sieve_hand \
	$B/cache/libcachelib.a $B/cache/eviction/libevictionC.a $B/cache/eviction/libevictionCPP.a \
	$B/traceReader/libtraceReader.a $B/profiler/libprofiler.a $B/dataStructure/libdataStructure.a \
	$B/dataStructure/hash/libds_hash.a $B/utils/libutils.a $B/cache/admission/libadmissionC.a \
	$B/cache/admission/libadmissionCpp.a $B/cache/prefetch/libprefetchC.a $B/cache/libcachelib.a \
	$B/dataStructure/libdataStructure.a $B/traceReader/libtraceReader.a $B/utils/libutils.a \
	$(pkg-config --libs glib-2.0) -ltcmalloc_minimal -lzstd -lpthread -lm
echo "fig9 build ok"
