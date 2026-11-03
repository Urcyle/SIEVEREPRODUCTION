import json
import unittest

try:
    import sieve_repro.zipf8_original_scale as study
    select_seed, summarize_records = study.select_seed, study.summarize_records
except ImportError:
    study = None
    select_seed = None
    summarize_records = None


class OriginalScaleZipfSummaryTests(unittest.TestCase):
    def test_seed_selector_preserves_accepted_seeds_and_rejects_unsupported_seed(self):
        self.assertIsNotNone(select_seed)
        select_seed(42)
        select_seed(43)
        self.assertEqual(study.CONFIG["trace_parameters"]["seed"], 43)
        select_seed(44)
        self.assertEqual(study.CONFIG["trace_parameters"]["seed"], 44)
        with self.assertRaises(ValueError):
            select_seed(45)
        select_seed(42)

    def test_rejects_incomplete_or_mismatched_capacity_grid(self):
        self.assertIsNotNone(summarize_records)
        records = [self.record(policy, fraction, capacity=int(100 * fraction))
                   for fraction in (0.1, 0.2)
                   for policy in ("lru", "lfu", "arc", "sieve")][:-1]
        with self.assertRaises(ValueError):
            summarize_records(records, fractions=(0.1, 0.2), policies=("lru", "lfu", "arc", "sieve"))

    def test_computes_miss_ratio_from_exact_saved_integer_counters(self):
        self.assertIsNotNone(summarize_records)
        records = [self.record(policy, fraction, capacity=int(100 * fraction))
                   for fraction in (0.1, 0.2)
                   for policy in ("lru", "lfu", "arc", "sieve")]
        rows = summarize_records(records, fractions=(0.1, 0.2),
                                 policies=("lru", "lfu", "arc", "sieve"))
        self.assertEqual(len(rows), 8)
        self.assertEqual(rows[0]["misses"], 5)
        self.assertEqual(rows[0]["requests"], 100)
        self.assertEqual(rows[0]["miss_ratio"], 0.05)

    def test_trace_recipe_matches_historical_zipf_source_blob(self):
        recipe = json.loads(study.TRACE_RECIPE.read_text())
        revision = study._historical_source_revision(
            "sieve_repro/zipf.py", recipe["zipf_definition_sha256"])
        self.assertEqual(revision, "b4efe090bfd216b7efcdb32154e2fa817a1b5094")
        self.assertNotEqual(study.file_sha256(study.ROOT / "sieve_repro/zipf.py"),
                            recipe["zipf_definition_sha256"])

    @staticmethod
    def record(policy, fraction, capacity):
        return {"status": "complete", "exit_code": 0, "run_id": f"{policy}-{fraction}",
                "spec": {"workload_label": "zipf8_original_scale_seed42",
                         "policy": policy, "capacity_fraction": fraction,
                         "trace_sha256": study.CONFIG.get("trace_raw_sha256", "a" * 64),
                         "binary_sha256": study.CONFIG.get("counter_binary_sha256", "b" * 64),
                         "ignore_object_size": True, "warmup_seconds": -1, "threads": 1},
                "cache_size": capacity, "unique_objects": 100, "n_req": 100,
                "n_miss": 5, "elapsed_seconds": 1.0, "peak_rss_kib": 1000}


if __name__ == "__main__":
    unittest.main()
