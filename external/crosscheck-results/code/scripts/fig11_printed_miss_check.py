#!/usr/bin/env python3
"""Compare our Figure 11 miss ratios with the 18 values printed above the paper's bars.

The values were typed from the paper's Figure 11 (page 1238); they are published numbers, kept
here only for this check and never plotted as local data. Reads saved summaries; no simulation.
"""

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# (alpha, capacity fraction): (LRU, FIFO, SIEVE) printed miss ratios, two decimals
PRINTED = {
    (0.8, 0.1): (0.51, 0.55, 0.43), (1.0, 0.1): (0.22, 0.25, 0.18), (1.2, 0.1): (0.05, 0.06, 0.04),
    (0.8, 0.001): (0.90, 0.91, 0.80), (1.0, 0.001): (0.60, 0.63, 0.49), (1.2, 0.001): (0.25, 0.28, 0.19),
}
OUT = ROOT / "local_results/instructions/figure11_printed_miss_ratio_check.csv"


def main() -> None:
    rows = list(csv.DictReader((ROOT / "local_results/instructions/instructions_paper_all_summary.csv").open(newline="")))
    out = []
    for (alpha, fraction), printed in PRINTED.items():
        for policy, value in zip(("lru", "fifo", "sieve"), printed):
            found = [r for r in rows if float(r["alpha"]) == alpha and float(r["capacity_fraction"]) == fraction and r["policy"] == policy]
            if len(found) != 1:
                raise SystemExit(f"expected one saved row for {alpha} {fraction} {policy}, found {len(found)}")
            ours = float(found[0]["miss_ratio"])
            out.append({"alpha": alpha, "capacity_fraction": fraction, "policy": policy.upper(), "paper_printed": f"{value:.2f}",
                        "ours_exact": f"{ours:.6f}", "ours_rounded": f"{ours:.2f}", "equal_at_two_decimals": f"{ours:.2f}" == f"{value:.2f}"})
    with OUT.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, tuple(out[0]))
        writer.writeheader()
        writer.writerows(out)
    print(f"{sum(r['equal_at_two_decimals'] for r in out)} of {len(out)} equal at two decimals")


if __name__ == "__main__":
    main()
