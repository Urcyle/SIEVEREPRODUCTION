#!/usr/bin/env bash
# Build the LeCaR-SIEVE variant from the pinned paper artifact plus local patches.
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
artifact="$root/external/NSDI24-SIEVE"
source="$root/build/figure12c-compat-source/libCacheSim"
build="$root/build/figure12-lecar-sieve"
expected=0861f8261c37b8286a70449a1defb5a4749c72d2
actual=$(git -C "$artifact" rev-parse HEAD)
[[ "$actual" == "$expected" ]] || { echo "artifact commit mismatch: $actual" >&2; exit 1; }
[[ -z $(git -C "$artifact" status --porcelain) ]] || { echo 'artifact checkout is dirty' >&2; exit 1; }
[[ -d "$source" ]] || { echo 'create the compatibility source copy first' >&2; exit 1; }

lecar="$source/libCacheSim/cache/eviction/LeCaR.c"
main="$source/libCacheSim/bin/cachesim/main.c"
if ! rg -q 'LeCaR_sieve_candidate' "$lecar"; then
  patch --forward --batch -d "$source" -p1 < "$root/patches/figure12c-lecar-sieve.patch"
fi
if ! rg -q 'SIEVE_RNG_SEED' "$main"; then
  patch --forward --batch -d "$source" -p1 < "$root/patches/controlled-seed.patch"
fi

python3 - "$root" <<'PY'
import shutil, subprocess, sys
from pathlib import Path
root=Path(sys.argv[1]); cap=10*1024**3
paths=['build','data','docs','external/NSDI24-SIEVE','local_results','paper_reference']
used=sum(int(subprocess.check_output(['du','-sb',str(root/p)],text=True).split()[0])
         for p in paths if (root/p).exists())
available=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines()
                   if x.startswith('MemAvailable:')))*1024
if cap-used < 20_000_000: raise SystemExit(f'need 20 MB aggregate headroom; have {cap-used} bytes')
if available < 5*1024**3: raise SystemExit(f'need 5 GiB available RAM; have {available} bytes')
if shutil.disk_usage(root).free < 2*1024**3: raise SystemExit('need 2 GiB free filesystem space')
print(f'preflight aggregate_remaining={cap-used} MemAvailable={available} disk_free={shutil.disk_usage(root).free}')
PY

cmake -S "$source" -B "$build" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DENABLE_TESTS=OFF -DUSE_HUGEPAGE=OFF \
  -DOPT_SUPPORT_ZSTD_TRACE=ON
cmake --build "$build" --target cachesim --parallel 1
sha256sum "$build/bin/cachesim"
