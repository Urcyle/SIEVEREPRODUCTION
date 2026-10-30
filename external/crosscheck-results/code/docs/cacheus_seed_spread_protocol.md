# Protocol: are the random-policy disagreements in Figure 4 seed draws? (frozen 2026-10-23, before the runs)

**Code review finding.** The artifact seeds its random generator from the clock (`srand(time(NULL)); set_rand_seed(rand());` in `cli_parser`/`main`; our `patches/controlled-seed.patch` replaces it by a fixed seed for controlled runs). So every default run of CACHEUS, LHD or Hyperbolic is a different random draw, including the authors' runs for the paper. SIEVEREPRODUCTION (default seeds) reproduces the paper's CACHEUS/LHD/Hyperbolic points **exactly in most cells** (difference 0.0000 in 37 of 48 compared) and differs in a few: CACHEUS on `meta_rnha` (+0.0039 small, +0.0102 large), `wiki_2016u` small (-0.0489), `wiki_2019u` large (-0.1283), `tencent_photo2` large (+0.0325), and LHD on both Tencent traces at the large cache (+0.0039, +0.0052). Our own controlled seeds (42-44) differ from the paper in more cells because a fixed seed is simply a third draw.

**Hypothesis.** The cells where two draws disagree are the cells where the policy is genuinely seed-sensitive, and the spread over many seeds covers both values.

**Test (the one cell family for which we hold the trace: `meta_rnha`).** CACHEUS with the pinned artifact build plus the controlled-seed patch (`build/seeded-baselines`), seeds 1-8, at the saved capacities (0.1%: 35,040 objects; 10%: 3,504,028), cold start, sizes ignored. 16 runs. Reduction from FIFO against the saved FIFO counters.

**Rule.** *Supported* if the range over the 8 seeds is at least 0.004 at 0.1% and at least 0.010 at 10% (the paper-versus-default-draw differences above), and the paper's value (0.0148 / 0.0481) and SIEVEREPRODUCTION's (0.0187 / 0.0583) both lie within the observed min-max or within 0.002 of it. *Not supported* otherwise. A pass shows that seed draws can produce the observed disagreement, not which seed the authors had.

## Outcome (2026-10-23)

16 runs (`local_results/cacheus_seed_spread/runs.csv`, `spread.csv`; `python3 -B scripts/cacheus_seed_spread.py summarize`). **By the rule declared above: "not supported"** - the range over the eight seeds at the 0.1% cache is 0.0026, below the 0.004 threshold (the 10% range, 0.0129, and both coverage conditions pass).

| cache | seeds 1-8 (reduction from FIFO) | min-max | paper | SIEVEREPRODUCTION (clock-seeded run) |
|---|---|---|---|---|
| 0.1% | 0.0173, 0.0173, 0.0150, 0.0148, 0.0148, 0.0148, 0.0148, 0.0148 | 0.0148-0.0173 | 0.0148 | 0.0187 |
| 10% | 0.0611, 0.0611, 0.0488, 0.0482, 0.0482, 0.0482, 0.0482, 0.0482 | 0.0482-0.0611 | 0.0481 | 0.0583 |

What the runs do show (descriptive, not part of the rule): CACHEUS on this trace is **seed-sensitive and bimodal**: five or six of eight seeds give one value, which equals the paper's (0.0148 exactly at 0.1%; 0.0482 against 0.0481 at 10%), and two seeds give a higher one (0.0173 and 0.0611). Our earlier controlled seed 42 sits in the modal group (0.0143, 0.0478). SIEVEREPRODUCTION's default run (0.0187, 0.0583) lies above all our eight seeds at 0.1% and within 0.003 of the high mode at 10%. So the paper-versus-default-draw disagreement on `meta_rnha` is within what seed draws produce, and the paper's value is the common outcome; but the declared rule's range threshold was not met at the small cache, and one trace does not settle the other disagreeing cells (`wiki_2016u`, `wiki_2019u`, `tencent_photo2`), whose traces we do not hold.
