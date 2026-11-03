#!/usr/bin/env bash
# Build the Figure 12 promotion-variant simulator (docs/figure12_promotion_protocol.md).
# Starts from the already patched Figure 12 source copy (scripts/build_figure12_advanced.sh must have been run).
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
base="$root/build/figure12c-compat-source/libCacheSim"
source="$root/build/figure12-promote-source/libCacheSim"
build="$root/build/figure12-promote"
rg -q 'T2_sieve_pointer' "$base/libCacheSim/cache/eviction/ARC.c" || { echo 'run scripts/build_figure12_advanced.sh first' >&2; exit 1; }
rm -rf "$root/build/figure12-promote-source"
mkdir -p "$root/build/figure12-promote-source"
cp -r "$base" "$source"
patch --forward --batch -d "$source" -p1 < "$root/patches/figure12-promote-visited.patch"
cmake -S "$source" -B "$build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DENABLE_TESTS=OFF -DUSE_HUGEPAGE=OFF -DOPT_SUPPORT_ZSTD_TRACE=ON
cmake --build "$build" --target cachesim --parallel 2
sha256sum "$build/bin/cachesim"
