#!/usr/bin/env bash
# Build an isolated TwoQ-SIEVE diagnostic from the pinned artifact source copy.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
artifact="$root/external/NSDI24-SIEVE"
source="$root/build/figure12c-compat-source/libCacheSim"
build="$root/build/figure12a-twoq-sieve"
patch_file="$root/patches/figure12a-twoq-sieve.patch"
expected=0861f8261c37b8286a70449a1defb5a4749c72d2
actual=$(git -C "$artifact" rev-parse HEAD)
[[ "$actual" == "$expected" ]] || { echo "artifact commit mismatch: $actual" >&2; exit 1; }
[[ -z $(git -C "$artifact" status --porcelain) ]] || { echo 'artifact checkout is dirty' >&2; exit 1; }
[[ -d "$source" ]] || { echo 'build the pinned compatibility source copy first' >&2; exit 1; }
[[ ! -e "$build" ]] || { echo 'build output already exists; preserving it' >&2; exit 1; }
if ! rg -q 'Am-type=LRU' "$source/libCacheSim/cache/eviction/TwoQ.c"; then
  patch --forward --batch -d "$source" -p1 < "$patch_file"
fi
rg -q 'TwoQ-SIEVE' "$source/libCacheSim/cache/eviction/TwoQ.c" || { echo 'TwoQ-SIEVE source patch missing' >&2; exit 1; }

python3 - "$root" <<'PY'
import shutil, subprocess, sys
from pathlib import Path
root=Path(sys.argv[1])
cap=10*1024**3
paths=['build','data','docs','external/NSDI24-SIEVE','local_results','paper_reference']
used=sum(int(subprocess.check_output(['du','-sb',str(root/p)],text=True).split()[0])
         for p in paths if (root/p).exists())
remaining=cap-used
available_kib=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                       if line.startswith('MemAvailable:')))
if remaining < 20_000_000:
    raise SystemExit(f'need 20 MB aggregate headroom; only {remaining} bytes remain')
if available_kib < 5*1024*1024:
    raise SystemExit(f'need 5 GiB available RAM; only {available_kib} KiB available')
if shutil.disk_usage(root).free < 2*1024**3:
    raise SystemExit('need 2 GiB free filesystem space before build')
print(f'preflight aggregate_remaining={remaining} bytes MemAvailable={available_kib*1024} bytes disk_free={shutil.disk_usage(root).free} bytes')
PY

cmake -S "$source" -B "$build" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DENABLE_TESTS=OFF -DUSE_HUGEPAGE=OFF \
  -DOPT_SUPPORT_ZSTD_TRACE=ON
cmake --build "$build" --target cachesim --parallel 1
sha256sum "$build/bin/cachesim"
