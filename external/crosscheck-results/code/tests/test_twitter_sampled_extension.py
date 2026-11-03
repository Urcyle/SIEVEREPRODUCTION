import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import twitter_sampled_extension as ext


class TwitterSampledExtensionTests(unittest.TestCase):
    def test_clusters_policies_and_partition_match_the_frozen_protocol(self):
        text = (ROOT / "docs/twitter_sampled_extension_protocol.md").read_text()
        listed = set(map(int, re.search(r"N in \{([0-9, ]+)\}", text).group(1).split(",")))
        self.assertEqual(set(ext.CONFIG["clusters"]), listed)
        self.assertEqual(sorted(c for part in ext.CONFIG["worker_partition"] for c in part), sorted(ext.CONFIG["clusters"]))
        self.assertEqual(ext.CONFIG["capacity_fractions"], [0.001, 0.1])
        self.assertEqual(len(ext.CONFIG["core_policies"] + ext.CONFIG["extra_policies"]), 12)

    def test_heldout_set_matches_variant_amendment_6(self):
        text = (ROOT / "docs/variant_protocol.md").read_text()
        self.assertIn("Amendment 6", text)
        self.assertIn("**37, 40, 43, 46, 52, 54**", text)
        self.assertEqual(set(ext.HELDOUT2), {37, 40, 43, 46, 52, 54})
        self.assertEqual(ext.GHOST_CONFIGS, ("ghost0.5", "ghost1.0"))

    def test_peak_estimate_follows_amendment_1(self):
        self.assertEqual(ext.estimate({"unique_objects": 1_000_000}), 2**30 + 250_000_000)

    def test_exact_capacity_is_floor_of_exact_unique_count_only_when_configured(self):
        meta = {"unique_objects": 1_907_377}
        if ext.CONFIG.get("exact_capacity_objects"):
            self.assertEqual(ext.exact_capacity(meta, 0.001), 1907)
            self.assertEqual(ext.exact_capacity(meta, 0.1), 190737)
        else:
            self.assertIsNone(ext.exact_capacity(meta, 0.001))

    def test_every_policy_has_a_paper_label(self):
        for policy in ext.CONFIG["core_policies"] + ext.CONFIG["extra_policies"]:
            self.assertIn(policy, ext.LABELS)


class SavedResultTests(unittest.TestCase):
    def test_batch_summaries_have_every_planned_run_but_the_documented_omissions(self):
        import csv
        for path, expected, clusters in (("local_results/twitter_sampled_extension/sample100_extension.csv", 144, 6),
                                         ("local_results/twitter_sample10_extension/sample10_extension.csv", 263, 11)):
            rows = list(csv.DictReader((ROOT / path).open(newline="")))
            self.assertEqual(len(rows), expected, path)
            self.assertEqual(len({r["trace"] for r in rows}), clusters)
            for r in rows:
                self.assertGreater(int(r["requests"]), 0)
                self.assertLessEqual(float(r["reduction_from_fifo"]), 1.0)
        omitted = (ROOT / "local_results/twitter_sample10_extension/omitted.csv").read_text()
        self.assertIn("25,0.001,cacheus", omitted)

    def test_ghost_verdicts_match_the_reported_claim(self):
        import csv
        rows = list(csv.DictReader((ROOT / "local_results/variants_heldout3/ghost_heldout2_plus_3_verdict.csv").open(newline="")))
        by = {(float(r["capacity_fraction"]), r["config"]): r for r in rows}
        self.assertEqual(by[(0.001, "ghost0.5")]["passes_rule"], "True")
        self.assertEqual(by[(0.1, "ghost0.5")]["passes_rule"], "False")
        self.assertEqual(by[(0.001, "ghost1.0")]["passes_rule"], "False")
        self.assertEqual(by[(0.1, "ghost1.0")]["passes_rule"], "False")
        self.assertTrue(all(int(r["n"]) == 17 for r in rows))


if __name__ == "__main__":
    unittest.main()
