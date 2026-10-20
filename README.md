# SIEVE (NSDI'24): reproduction of Figures 3, 4, 5, 8 and 9

Reproduction of the efficiency results of *SIEVE is Simpler than LRU: an Efficient Turn-Key
Eviction Algorithm for Web Caches* (Zhang et al., NSDI'24), with the simulator of the authors'
artifact. Each figure was replicated in its own repository; this repository collects them
under `external/`, together with the one simulator they all use.

| figure | folder | what | result |
|---|---|---|---|
| 3c, 3f | [external/sieve-fig3](external/sieve-fig3/README.md) | miss ratio reduction from FIFO on the Twitter traces (24 of 54 clusters, scaled down) | rank correlation with the paper 0.96 (large cache) and 0.98 (small); SIEVE's mean within 0.003 |
| 4a, 4b | [external/sieve-fig4](external/sieve-fig4/README.md) | per-trace reduction on Meta KV, Meta CDN, Tencent Photo, Wiki (whole traces) | SIEVE equal to the paper to 4 decimals on all 26 points; its rank the paper's on 25 |
| 5 | [external/sieve-fig4/fig5](external/sieve-fig4/fig5/README.md) | best algorithm per dataset, from the Figure 3 and 4 results | 7 of the 8 public-dataset bars exact; Twitter close |
| 8 | [external/fig8](external/fig8/README.md) | miss ratio and popular object ratio over cache size, Zipf α = 1 | miss ratios within 0.0014 (LRU, ARC, SIEVE); popular-ratio ordering the paper's at 7 of 8 sizes |
| 9 | [external/fig9](external/fig9/README.md) | the same over the Zipf skew, and SIEVE's hand over time | miss ratios within 0.003; hand wraps 0 / 1–2 / 5–7 vs the paper's 0 / 2 / 7 |

Panels a, b, d and e of Figure 3 use proprietary traces (CDN1, CDN2) and are not reproduced.

## Layout

```
external/NSDI24-SIEVE/   the authors' artifact (simulator: libCacheSim), git submodule,
                         github.com/cacheMon/NSDI24-SIEVE @ 0861f82
patches/                 NSDI24-SIEVE-build-fix.patch: lets it build with newer compilers
scripts/setup_simulator.sh   fetches the submodule and applies the patch
external/sieve-fig3/     Figure 3c/3f    copy of Urcyle/sieve-fig3 @ 1d318f4
external/sieve-fig4/     Figures 4 and 5 copy of Urcyle/sieve-fig4 @ 6271e61
external/fig8/           Figure 8        copy of Urcyle/fig8 @ 2245a86
external/fig9/           Figure 9        copy of Urcyle/fig9 @ 7d4169e
paper/nsdi24-sieve.pdf   the paper (the figures' extraction scripts read their values from it)
requirements.txt         the Python packages of the figures' scripts
```

Each folder under `external/` is a copy of the committed files of that repository at the commit
shown, unchanged except for one line in its build script (below). Inside a copy:

* `external/NSDI24-SIEVE` is a link to the shared `external/NSDI24-SIEVE` (each original
  repository had the simulator as its own submodule);
* in `fig9`, `external/fig8` is a link to `external/fig8` (the original used the Figure 8
  repository as a submodule).

* files that were identical in several repositories are stored once and linked from the others:
  `paper/nsdi24-sieve.pdf` and `requirements.txt` (top level), and in `sieve-fig4`
  `results/fig5_inputs/twitter_fig3.csv` (Figure 3's `results/twitter.csv`, the Twitter input of
  Figure 5) and `scripts/download.sh` (the same as Figure 3's).

So every script finds its files at the paths it was written for, and nothing is stored twice.
On Windows, clone inside WSL2 so that these links work.
The one change in each build script (`sieve-fig3/scripts/build.sh`, `sieve-fig4/scripts/build.sh`,
`fig8/fig8/build.sh`; `fig9/fig9/build.sh` builds through Figure 8's) replaces
`git submodule update` with `scripts/setup_simulator.sh`.

**The simulator.** The figures were run with `Urcyle/NSDI24-SIEVE @ 0346336`: the authors'
artifact plus a build fix for GCC 15 / CMake 4 that changes no simulator code (three build
files: `robin_hood.h` gains a missing `#include`, the dependency and install scripts). Here the
artifact comes from its public origin and the fix is the patch; artifact + patch is exactly the
source tree of `0346336` (same git tree hash). Where the figures' READMEs say "@ 0346336", this
is that source.

## How to reproduce

Requirements: Linux or WSL2, cmake, a C/C++ compiler, glib2 and zstd development headers,
python3 with venv. Then, per figure, from its folder (the README of each figure has the details
and the run times; Figures 3 and 4 download tens to hundreds of GB of traces and run for many
hours, Figures 8 and 9 take minutes):

```bash
git clone --recurse-submodules https://github.com/Urcyle/SIEVEREPRODUCTION.git
cd SIEVEREPRODUCTION
scripts/setup_simulator.sh

cd external/fig8 && fig8/build.sh && fig8/run.sh && .venv/bin/python -I fig8/plot_fig8.py   # Figure 8
cd ../fig9 && fig9/build.sh && fig9/run.sh                                                 # Figure 9 (needs fig8 built)
cd ../sieve-fig4 && scripts/build.sh                                                       # Figures 4, 5: see fig4/README.md
cd ../sieve-fig3 && scripts/build.sh                                                       # Figure 3: see its README.md
```

Traces, Python environments, compiled tools and run scratch files are not part of the repository
(`.gitignore`); the scripts download or generate them.
