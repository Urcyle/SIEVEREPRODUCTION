#!/bin/bash
# Fetch the simulator and apply the patches; called by every figure's build script.
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
# The patches build on each other, in this order:
#   1. NSDI24-SIEVE-build-fix: builds with newer compilers (no simulator code changed)
#   2. SIEVE-G: external/sieve-g, SIEVE with a ghost list, a new algorithm "sieveg[-<ratio>]";
#      it changes no other algorithm
#   3. SIEVE-G-fp: SIEVE-G's optional lean ghost of 16-bit fingerprints, "sieveg-fp[-<ratio>]"
# Find the last one already applied, and apply the ones after it.
PATCHES=(NSDI24-SIEVE-build-fix SIEVE-G SIEVE-G-fp)
last=-1
for ((i = ${#PATCHES[@]} - 1; i >= 0; i--)); do
	if git apply --reverse --check "$ROOT/patches/${PATCHES[$i]}.patch" 2> /dev/null; then
		last=$i
		break
	fi
done
for ((i = 0; i < ${#PATCHES[@]}; i++)); do
	if ((i <= last)); then
		echo "simulator: ${PATCHES[$i]} already applied"
	else
		git apply "$ROOT/patches/${PATCHES[$i]}.patch" && echo "simulator: ${PATCHES[$i]} applied"
	fi
done
