#!/bin/bash
# Fetch the simulator and apply the build fix; called by every figure's build script.
#
# external/NSDI24-SIEVE is the authors' artifact (github.com/cacheMon/NSDI24-SIEVE @ 0861f82),
# shared by all figures. patches/NSDI24-SIEVE-build-fix.patch makes it build with newer compilers
# (GCC 15 / CMake 4) and changes no simulator code; with it the source tree is identical to the
# one the figures were run with (Urcyle/NSDI24-SIEVE @ 0346336). Safe to run repeatedly.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
git submodule update --init external/NSDI24-SIEVE
cd external/NSDI24-SIEVE
P=$ROOT/patches/NSDI24-SIEVE-build-fix.patch
if git apply --reverse --check "$P" 2> /dev/null; then
	echo "simulator: build fix already applied"
else
	git apply "$P" && echo "simulator: build fix applied"
fi
