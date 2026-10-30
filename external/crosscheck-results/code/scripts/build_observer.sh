#!/usr/bin/env bash
# Build a separate periodic, read-only observer of the pinned author artifact.
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source_dir="$root/external/NSDI24-SIEVE"
expected=0861f8261c37b8286a70449a1defb5a4749c72d2
[[ $(git -C "$source_dir" rev-parse HEAD) == "$expected" ]] || { echo 'artifact pin mismatch' >&2; exit 1; }
[[ -z $(git -C "$source_dir" status --porcelain) ]] || { echo 'artifact checkout dirty' >&2; exit 1; }
available_kib=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
(( available_kib >= 5 * 1024 * 1024 )) || { echo 'need at least 5 GiB available before one-job build' >&2; exit 1; }
observer_source="$root/build/observer-source"
rm -rf "$observer_source"
mkdir -p "$observer_source"
git -C "$source_dir" archive HEAD libCacheSim | tar -xf - -C "$observer_source"
patch --forward --batch -d "$observer_source" -p1 < "$root/patches/exact-counters.patch"
patch --forward --batch -d "$observer_source" -p1 < "$root/patches/periodic-observer.patch"
cmake -S "$observer_source/libCacheSim" -B "$root/build/observer-sim" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DENABLE_TESTS=OFF -DUSE_HUGEPAGE=OFF \
  -DOPT_SUPPORT_ZSTD_TRACE=ON
cmake --build "$root/build/observer-sim" --target cachesim --parallel 1
sha256sum "$root/build/observer-sim/bin/cachesim"
