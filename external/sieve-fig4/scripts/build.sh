#!/bin/bash
# Build cachesim from the pinned simulator submodule (Urcyle/NSDI24-SIEVE @ 0346336 =
# the authors' artifact plus a build fix for newer toolchains) and set up the Python venv.
#
# usage: scripts/build.sh
# needs: cmake, a C/C++ compiler, glib2 dev headers, libzstd dev headers, python3 (venv)
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
# SIEVEREPRODUCTION: the shared simulator (external/NSDI24-SIEVE here is a link to it)
"$ROOT/../../scripts/setup_simulator.sh"
mkdir -p logs external/NSDI24-SIEVE/libCacheSim/_build
cd external/NSDI24-SIEVE/libCacheSim/_build
cmake -DCMAKE_BUILD_TYPE=Release .. > "$ROOT/logs/build.log" 2>&1
make -j"$(nproc)" cachesim >> "$ROOT/logs/build.log" 2>&1
make -j"$(nproc)" traceConv >> "$ROOT/logs/build.log" 2>&1
cd "$ROOT"
cc -O2 -Wall -o tools/blru_bitmap tools/blru_bitmap.c
ls -la external/NSDI24-SIEVE/libCacheSim/_build/bin/cachesim
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
echo "build ok"
