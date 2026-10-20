#!/usr/bin/env python3
"""Write the run queues (manifests/*.tsv) for scripts/run_queue.sh.

usage: make_manifests.py twitter <choices.tsv>  > manifests/twitter.tsv

One line per cluster from choose_twitter.py output.
Columns: dataset  trace_file  sample_ratio  max_req  log_file
"""
import sys


def twitter(choices):
    for line in open(choices):
        if line.startswith("cluster\t"):
            continue
        c, version, extra, cap, *_ = line.rstrip("\n").split("\t")
        if version == "full" and int(cap) > 0:
            f, cap = f"data/twitter/{c}.oracleGeneral.first{cap}.zst", -1  # prefix file
        elif version == "full":
            f = f"data/twitter/{c}.oracleGeneral.zst"
        else:
            f = f"data/twitter/{version}/{c}.oracleGeneral.{version}.zst"
        yield "twitter", f, extra, cap, f"results/raw/twitter/{c}.log"


if __name__ == "__main__":
    if sys.argv[1] != "twitter":
        sys.exit("usage: make_manifests.py twitter <choices.tsv>")
    rows = twitter(sys.argv[2])
    print("# dataset\ttrace_file\tsample_ratio\tmax_req\tlog_file")
    for r in rows:
        print("\t".join(map(str, r)))
