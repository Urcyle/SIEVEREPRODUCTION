#!/usr/bin/env bash
# Build an isolated exact-counter variant with a recoverable MMIX seed lifecycle.
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source_dir="$root/external/NSDI24-SIEVE"
expected=0861f8261c37b8286a70449a1defb5a4749c72d2
[[ $(git -C "$source_dir" rev-parse HEAD) == "$expected" ]] || { echo 'artifact pin mismatch' >&2; exit 1; }
[[ -z $(git -C "$source_dir" status --porcelain) ]] || { echo 'artifact checkout dirty' >&2; exit 1; }
available_kib=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
(( available_kib >= 5 * 1024 * 1024 )) || { echo 'need at least 5 GiB available before one-job build' >&2; exit 1; }
scratch_limit=$((10 * 1024 * 1024 * 1024))
scratch_before=$(du -sb "$root" | awk '{print $1}')
reserve_bytes=$((256 * 1024 * 1024))
(( scratch_before + reserve_bytes <= scratch_limit )) || { echo 'workspace scratch plus 256 MiB build reserve exceeds 10 GiB' >&2; exit 1; }
printf 'SIEVE_BUILD_RESOURCES stage=before mem_available_kib=%s scratch_bytes=%s reserve_bytes=%s\n' \
  "$available_kib" "$scratch_before" "$reserve_bytes"
seeded_source="$root/build/seeded-source"
rm -rf "$seeded_source"
mkdir -p "$seeded_source"
git -C "$source_dir" archive HEAD libCacheSim | tar -xf - -C "$seeded_source"
patch --forward --batch -d "$seeded_source" -p1 < "$root/patches/exact-counters.patch"
patch --forward --batch -d "$seeded_source" -p1 < "$root/patches/controlled-seed.patch"
cmake -S "$seeded_source/libCacheSim" -B "$root/build/seeded-baselines" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DENABLE_TESTS=OFF -DUSE_HUGEPAGE=OFF \
  -DOPT_SUPPORT_ZSTD_TRACE=ON
cmake --build "$root/build/seeded-baselines" --target cachesim --parallel 1
scratch_after=$(du -sb "$root" | awk '{print $1}')
(( scratch_after <= scratch_limit )) || { echo 'workspace scratch exceeds 10 GiB after build' >&2; exit 1; }
printf 'SIEVE_BUILD_RESOURCES stage=after scratch_bytes=%s\n' "$scratch_after"
sha256sum "$root/build/seeded-baselines/bin/cachesim"
