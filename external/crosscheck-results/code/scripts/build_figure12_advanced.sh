#!/usr/bin/env bash
# Apply local Figure 12a/b variants to the isolated paper-era source copy and build serially.
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
artifact="$root/external/NSDI24-SIEVE"
source="$root/build/figure12c-compat-source/libCacheSim"
build="$root/build/figure12a-twoq-sieve"
expected=0861f8261c37b8286a70449a1defb5a4749c72d2
actual=$(git -C "$artifact" rev-parse HEAD)
[[ "$actual" == "$expected" ]] || { echo "artifact commit mismatch: $actual" >&2; exit 1; }
[[ -z $(git -C "$artifact" status --porcelain) ]] || { echo 'artifact checkout is dirty' >&2; exit 1; }
[[ -d "$source" ]] || { echo 'create the compatibility source copy first with scripts/build_figure12c_compat.sh' >&2; exit 1; }

arc="$source/libCacheSim/cache/eviction/ARC.c"
twoq="$source/libCacheSim/cache/eviction/TwoQ.c"
sieve="$source/libCacheSim/cache/eviction/Sieve.c"
if ! rg -q 'Am-type=LRU' "$twoq"; then
  patch --forward --batch -d "$source" -p1 < "$root/patches/figure12a-twoq-sieve.patch"
fi
if ! rg -q 'T2_sieve_pointer' "$arc"; then
  patch --forward --batch -d "$source" -p1 < "$root/patches/figure12b-arc-sieve.patch"
fi
if ! rg -q 'LIBCACHESIM_DEBUG_ARC_SIEVE' "$arc"; then
  patch --forward --batch -d "$source" -p1 < "$root/patches/figure12-state-audit-debug.patch"
fi
rg -q 'LIBCACHESIM_DEBUG_TWOQ_SIEVE' "$twoq" || { echo 'TwoQ state audit patch missing' >&2; exit 1; }
rg -q 'Sieve_debug_state' "$sieve" || { echo 'SIEVE state audit helper missing' >&2; exit 1; }

python3 - "$root" <<'PY'
import shutil, subprocess, sys
from pathlib import Path
root=Path(sys.argv[1]); cap=10*1024**3
paths=['build','data','docs','external/NSDI24-SIEVE','local_results','paper_reference']
used=sum(int(subprocess.check_output(['du','-sb',str(root/p)],text=True).split()[0])
         for p in paths if (root/p).exists())
remaining=cap-used
available=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines()
                   if x.startswith('MemAvailable:')))*1024
if remaining < 20_000_000: raise SystemExit(f'need 20 MB aggregate headroom; have {remaining} bytes')
if available < 5*1024**3: raise SystemExit(f'need 5 GiB available RAM; have {available} bytes')
if shutil.disk_usage(root).free < 2*1024**3: raise SystemExit('need 2 GiB free filesystem space')
print(f'preflight aggregate_remaining={remaining} MemAvailable={available} disk_free={shutil.disk_usage(root).free}')
PY

cmake -S "$source" -B "$build" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DENABLE_TESTS=OFF -DUSE_HUGEPAGE=OFF \
  -DOPT_SUPPORT_ZSTD_TRACE=ON
cmake --build "$build" --target cachesim --parallel 1
sha256sum "$build/bin/cachesim"
