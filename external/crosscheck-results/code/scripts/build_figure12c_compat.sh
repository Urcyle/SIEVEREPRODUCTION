#!/usr/bin/env bash
# Build an isolated copy with exact counters and a documented-sentinel fix.
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source_dir="$root/external/NSDI24-SIEVE"
expected=0861f8261c37b8286a70449a1defb5a4749c72d2
actual=$(git -C "$source_dir" rev-parse HEAD)
[[ "$actual" == "$expected" ]] || { echo "artifact commit mismatch: $actual" >&2; exit 1; }
[[ -z $(git -C "$source_dir" status --porcelain) ]] || { echo "artifact checkout is dirty" >&2; exit 1; }
available_kib=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
(( available_kib >= 5 * 1024 * 1024 )) || { echo 'need at least 5 GiB available before one-job build' >&2; exit 1; }

python3 - "$root" <<'PY'
import subprocess, sys
from pathlib import Path
root=Path(sys.argv[1])
cap=10*1024**3
paths=['build','data','docs','external/NSDI24-SIEVE','local_results','paper_reference']
used=sum(int(subprocess.check_output(['du','-sb',str(root/p)],text=True).split()[0])
         for p in paths if (root/p).exists())
if cap-used < 150_000_000:
    raise SystemExit(f'need 150 MB aggregate headroom; only {cap-used} bytes remain')
if __import__('shutil').disk_usage(root).free < 2*1024**3:
    raise SystemExit('need 2 GiB free filesystem space before isolated build')
PY

patched="$root/build/figure12c-compat-source"
build="$root/build/figure12c-compat"
[[ ! -e "$patched" && ! -e "$build" ]] || { echo 'compatibility build paths already exist; preserving them' >&2; exit 1; }
mkdir -p "$patched"
git -C "$source_dir" archive HEAD libCacheSim | tar -xf - -C "$patched"
patch --forward --batch -d "$patched" -p1 < "$root/patches/exact-counters.patch"
patch --forward --batch -d "$patched" -p1 < "$root/patches/figure12c-no-future-sentinel.patch"
cmake -S "$patched/libCacheSim" -B "$build" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DENABLE_TESTS=OFF -DUSE_HUGEPAGE=OFF \
  -DOPT_SUPPORT_ZSTD_TRACE=ON
cmake --build "$build" --target cachesim --parallel 1
sha256sum "$build/bin/cachesim"
