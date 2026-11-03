#!/bin/bash
# Check that every tool, library and file the replication needs is present, and print its version.
# Each line says OK or MISSING, plus the guide step that installs it (docs/MANUAL_GUIDE.md).
#
# usage: bash scripts/check_tools.sh
# Run it after each setup step; at the end every line should say OK.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../config/settings.sh"

missing=0
# check <name> <installed-by> <command that prints a version, fails if absent>
check() {
	local name=$1 step=$2 v
	shift 2
	if v=$("$@" 2>/dev/null | head -n 1) && [[ -n $v ]]; then
		printf "  OK       %-28s %s\n" "$name" "$v"
	else
		printf "  MISSING  %-28s -> %s\n" "$name" "$step"
		missing=$((missing + 1))
	fi
}
pkg() { dpkg-query -W -f='${Version}\n' "$1" 2>/dev/null | grep .; }
file_ok() { [[ -e $1 ]] && echo "${2:-present}"; }

echo "System"
check "Ubuntu" "WSL2 + Ubuntu (step 1)" lsb_release -ds
check "CPUs visible to WSL" "C:\\Users\\<you>\\.wslconfig (step 1)" nproc
check "memory" "C:\\Users\\<you>\\.wslconfig (step 1)" sh -c "free -h | awk '/Mem:/ {print \$2}'"
check "free disk in repo" "need ~300 GB" sh -c "df -h '${REPO_ROOT}' | awk 'NR==2 {print \$4}'"

echo "Getting the code (step 2)"
check "git" "sudo apt install git (step 2)" git --version
check "gh (GitHub CLI)" "sudo apt install gh (step 2)" gh --version
check "GitHub login" "gh auth login (step 2)" sh -c "gh auth status 2>&1 | grep -m1 -o 'Logged in to github.com account [^ ]*'"

echo "Build tools and libraries (step 4: setup/01_install_dependencies.sh)"
check "gcc" "setup/01" sh -c "gcc --version | head -n1"
check "g++" "setup/01" sh -c "g++ --version | head -n1"
check "make" "setup/01" sh -c "make --version | head -n1"
check "cmake" "setup/01" sh -c "cmake --version | head -n1"
check "libglib2.0-dev" "setup/01" pkg libglib2.0-dev
check "libgoogle-perftools-dev" "setup/01" pkg libgoogle-perftools-dev
check "xxhash" "setup/01" pkg xxhash
check "zstd 1.5.0 library" "setup/01" file_ok /usr/local/lib/libzstd.so.1.5.0 "/usr/local/lib/libzstd.so.1.5.0"
check "zstd command" "setup/01" sh -c "zstd --version"
check "xgboost (optional)" "setup/01" sh -c "ls /usr/local/lib | grep -m1 libxgboost"
check "LightGBM (optional)" "setup/01" sh -c "ls /usr/local/lib | grep -m1 lightgbm"
check "patch" "setup/01" sh -c "patch --version | head -n1"
check "bc" "setup/01" sh -c "bc --version | head -n1"
check "wget" "setup/01" sh -c "wget --version | head -n1"
check "GNU time" "setup/01" file_ok /usr/bin/time "/usr/bin/time"
check "python3" "setup/01" python3 --version

echo "Simulator (step 5: setup/02_build_simulator.sh)"
# an empty submodule folder would make `git -C` fall back to this repo, so check a real file first
check "authors' code (submodule)" "git submodule update --init (step 3)" \
	sh -c "[ -f '${SIEVE_REPO}/libCacheSim/CMakeLists.txt' ] && git -C '${SIEVE_REPO}' log --oneline -1 | cut -c1-60"
check "cachesim" "setup/02" file_ok "${CACHESIM}" "${CACHESIM#"${REPO_ROOT}/"}"
check "cachesim, paper TinyLFU" "setup/02" file_ok "${CACHESIM_PAPER_TINYLFU}" "${CACHESIM_PAPER_TINYLFU#"${REPO_ROOT}/"}"

echo "Python (step 6: setup/03_python_env.sh)"
PY=${REPO_ROOT}/.venv/bin/python
check ".venv python" "setup/03" "$PY" --version
for m in pandas numpy matplotlib; do
	check "$m" "setup/03" "$PY" -c "import $m; print($m.__version__)"
done

echo
if [[ $missing -eq 0 ]]; then
	echo "ALL OK"
else
	echo "${missing} MISSING - run the step shown next to each"
fi
