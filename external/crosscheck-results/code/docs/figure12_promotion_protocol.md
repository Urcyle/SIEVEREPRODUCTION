# Protocol: why do ARC-SIEVE and TwoQ-SIEVE lose in our Figure 12 when they win in the paper? (frozen 2026-10-23, before any run)

## The mismatch

Paper (section 6.2, Figure 12a/b): replacing the LRU of ARC (frequent-object queue only), TwoQ and LeCaR with SIEVE improves each; "ARC-SIEVE achieves the best efficiency among all compared algorithms at both small and large cache sizes", on average -3.7% misses against ARC. Ours (`docs/figure12_public_selected_seven_report.md`, seven public traces, equal weight, mean reduction from FIFO): ARC-LRU 0.0387 / 0.0720 against ARC-SIEVE -0.0156 / 0.0524 (0.1% / 10% cache); TwoQ-LRU -0.0068 / 0.0780 against TwoQ-SIEVE -0.0095 / 0.0759; LeCaR-LRU 0.0270 / 0.0619 against LeCaR-SIEVE -0.0168 / -0.0091. The substitutions lose here. The earlier note in the report ("hypothesis: ARC/LeCaR adaptation relies on LRU-ordered ghost lists") was never tested.

## Code review of our implementation (`patches/figure12b-arc-sieve.patch`, `patches/figure12a-twoq-sieve.patch`)

* ARC-SIEVE keeps ARC's T1/T2/B1/B2 and replaces only T2's order with a SIEVE queue (hit: set the visited bit; eviction: SIEVE hand). This matches the paper's sentence "for ARC, we only replace the LRU for frequent objects". TwoQ-SIEVE swaps the `Am` queue for the artifact's own SIEVE cache. Both were already checked against independent Python models after every request (`scripts/verify_arc_sieve_model.py`, `verify_twoq_sieve_model.py`), so the code does what it says.
* **What it says may not be what the paper's implementation does.** An object enters T2 (or `Am`) *because it was just hit* (second hit in T1, or a hit in the B1/B2 ghost lists, or a ghost hit in Aout). Our patch inserts it at the head of the SIEVE queue with the visited bit **cleared** (`obj->misc.freq = 0` in `ARC.c` at the two insertion sites; `Sieve_insert` sets `freq = 0` for `Am`). In an LRU queue the same object would sit at the MRU end and be the last to leave. In a SIEVE queue the hand sweeps from the tail toward the head, and a just-promoted object at the head, unvisited, is the first thing the hand reaches once it has swept the older objects: the "instant demotion" mechanism we measured for SIEVE at tiny caches (`docs/sieve_variants_report.md`), now applied to every object that has just proved itself popular. A natural implementation of "move the object to the SIEVE queue" that goes through the normal hit path would mark it visited.
* Not changed, and not suspected: the visited-bit semantics on later hits, the hand wrap-around, the ghost-list sizes, ARC's p adaptation.

## Hypothesis (declared now) and variants

**H1.** Marking the promoted object visited when it enters the SIEVE queue removes most of the loss.

Two opt-in parameters added on top of the existing patches (new patch `patches/figure12-promote-visited.patch`, built into a separate binary; defaults leave behaviour unchanged): `ARC T2-promote=visited` (both insertion sites set `misc.freq = 1`) and `TwoQ Am-promote=visited` (after inserting into `Am`, set `sieve.freq = 1`). LeCaR is not tested here: its SIEVE queue receives new misses, not promoted hits, so the mechanism does not apply; that is a separate open question.

## Data, controls, decision rule

* The seven traces and both capacities of the existing Figure 12 grid (meta_reag, meta_rprn, meta_rnha, twitter_cluster10, 26, 50, wiki_2019t; 0.1% and 10%), with the saved capacities (`capacity_objects`) and the saved ARC-LRU, ARC-SIEVE, TwoQ-LRU, TwoQ-SIEVE counters of that grid as references. 28 new runs (2 policies x 14 trace-capacity points).
* **Control:** with default parameters the new binary must reproduce the saved ARC-LRU, ARC-SIEVE, TwoQ-LRU and TwoQ-SIEVE counters of `meta_reag` at both capacities exactly. If it does not, nothing below is reported as a result.
* **Rule.** For each policy and capacity, over the seven traces: H1 is *supported* if the visited variant (a) beats the unvisited variant on at least 5 of 7 traces and (b) has an equal-weight mean reduction above that of the LRU original (ARC-LRU, TwoQ-LRU). It is *partly supported* if (a) holds but not (b). Otherwise it is *not supported*. Outcomes are reported as they are; a "supported" result would show the paper's gain is reachable by this implementation choice, not that the paper used it (the authors' code for these variants is not in the artifact).
* Sampling variation: ARC and TwoQ are deterministic; no seeds.

## Outcome (2026-10-23)

**Control passed:** with the new binary and default parameters, ARC-LRU, ARC-SIEVE, TwoQ-LRU and TwoQ-SIEVE on `meta_reag` at both capacities reproduce the saved counters exactly (8 of 8). 28 variant runs completed (`local_results/figure12_promotion/runs.csv`).

**Pre-declared rule: H1 is *not supported* for any of the four policy/capacity cells** (`verdict.csv`): the visited variant beats the unvisited variant on only 1-3 of 7 traces in each cell.

| family, cache | mean reduction: LRU original | SIEVE, promoted unvisited (ours so far) | SIEVE, promoted visited | visited beats unvisited on |
|---|---|---|---|---|
| ARC 0.1% | 0.0387 | -0.0156 | 0.0369 | 3 of 7 |
| ARC 10% | 0.0720 | 0.0524 | 0.0628 | 2 of 7 |
| TwoQ 0.1% | -0.0068 | -0.0095 | -0.0074 | 1 of 7 |
| TwoQ 10% | 0.0780 | 0.0759 | 0.0761 | 1 of 7 |

**What the rule hides, reported as post-hoc** (`posthoc_split_by_trace_family.csv`, written after seeing the table above and not part of the rule): the visited mark does remove two catastrophic losses of ARC-SIEVE, which is where the whole ARC mean difference lives: `twitter_cluster26` at 0.1% (reduction -0.340 unvisited, +0.071 visited, ARC-LRU +0.080) and `twitter_cluster50` at 10% (-0.102, +0.030, ARC-LRU +0.048). That is the instant-demotion mechanism the code review predicted, acting on promoted objects. On the four Meta CDN and Wiki traces, which are the closest analogue of the paper's CDN-dominated corpus, ARC-SIEVE and TwoQ-SIEVE **as we implemented them (promoted objects unvisited) are already at or slightly above their LRU originals**, as in the paper (ARC 0.0495 -> 0.0571 at 0.1% and 0.1133 -> 0.1171 at 10%; TwoQ 0.0574 -> 0.0632 and 0.1048 -> 0.1059), and marking them visited gives that small gain back (0.0483, 0.1018). On our three Twitter traces unvisited ARC-SIEVE collapses (-0.113 at 0.1%, -0.034 at 10%, against +0.024 and +0.017 for ARC-LRU).

**Conclusion (what we can and cannot say).** The Figure 12 disagreement is mostly a trace-mix effect plus one real mechanism, not a coding error: (1) three of our seven traces are Twitter, where SIEVE-based ARC loses heavily at small caches; the paper's average is dominated by CDN traces, where our implementation points the same way as the paper's (small gains of 0.1-0.8 points of reduction, not the 3.7% average miss-ratio reduction, which we cannot reach with these seven files); (2) a promoted object entering the SIEVE queue unvisited is exposed to instant demotion, and marking it visited repairs the Twitter losses at the price of the small CDN gain, so the paper's implementation detail on this point matters and is not stated. LeCaR-SIEVE is untouched by this (no promotion step) and remains unexplained. Nothing here shows what the authors' variant does; their code for these algorithms is not in the artifact.

**LeCaR (superseded 2026-10-23).** The saved LeCaR-SIEVE results this section first quoted came from a build with a hand-wrap bug of our own (the SIEVE hand restarted at the newest object instead of the oldest after wrapping). It was found through a failed control in `docs/lecar_sieve_collapse_protocol.md`, which also has the corrected numbers: LeCaR-SIEVE then gains over LeCaR-LRU on CDN and Wiki traces (0.0508 against 0.0146 at 0.1%, 0.1111 against 0.0714 at 10%) and over the seven-file mean at 10% (0.0775 against 0.0619), and trails it only at 0.1% on Twitter traces. ARC-SIEVE and TwoQ-SIEVE do not share the bug (their hand reset is `queue.prev`, as in the artifact's `Sieve.c`).
