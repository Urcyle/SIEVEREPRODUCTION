import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from sieve_repro.zipf import (frequency_counts, generate_phase_change,
                              generate_phase_change_zstd, phase_change_expected_digest,
                              phase_change_frequency_counts)


@unittest.skipUnless(shutil.which("zstd"), "zstd CLI is required")
class CompressedPhaseGeneratorTests(unittest.TestCase):
    def test_streamed_zstd_matches_raw_recipe_and_records_exact_phases(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            raw = root / "expected.oracleGeneral"
            compressed = root / "phase.oracleGeneral.zst"
            kwargs = {"objects": 100, "requests_per_phase": 1_003,
                      "alpha": 1.0, "seeds": (42, 43), "batch_size": 257}
            generate_phase_change(raw, **kwargs)
            result = generate_phase_change_zstd(compressed, **kwargs)
            decoded = subprocess.run(["zstd", "-q", "-dc", str(compressed)],
                                     check=True, capture_output=True).stdout
            expected_unique = [
                int((frequency_counts(raw, objects=100, start=phase * 1_003,
                                      requests=1_003, id_offset=phase * 100) > 0).sum())
                for phase in (0, 1)]
            self.assertEqual(decoded, raw.read_bytes())
            self.assertEqual(result["record_count"], 2_006)
            self.assertEqual(result["raw_bytes"], 2_006 * 24)
            self.assertEqual(result["unique_objects_per_phase"], expected_unique)
            self.assertEqual(result["raw_sha256"], hashlib.sha256(decoded).hexdigest())
            self.assertFalse(Path(str(compressed) + ".part").exists())

    def test_requires_compressed_suffix_and_valid_level(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.zst"
            with self.assertRaises(ValueError):
                generate_phase_change_zstd(path.with_suffix(".raw"), objects=2,
                                           requests_per_phase=2, alpha=1,
                                           seeds=(1, 2))
            with self.assertRaises(ValueError):
                generate_phase_change_zstd(path, objects=2, requests_per_phase=2,
                                           alpha=1, seeds=(1, 2), compression_level=0)

    def test_output_cap_discards_partial_trace_without_overwriting_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "capped.oracleGeneral.zst"
            with self.assertRaisesRegex(RuntimeError, "partial file discarded"):
                generate_phase_change_zstd(path, objects=100, requests_per_phase=1_003,
                                           alpha=1, seeds=(42, 43), max_output_bytes=1)
            self.assertFalse(path.exists())
            self.assertFalse(Path(str(path) + ".part").exists())
            existing = path.with_name("existing.oracleGeneral.zst")
            existing.touch()
            with self.assertRaises(FileExistsError):
                generate_phase_change_zstd(existing, objects=2, requests_per_phase=2, alpha=1,
                                           seeds=(1, 2), max_output_bytes=1)

    def test_compressed_phase_counter_and_seed_digest_match_raw_reference(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            raw = root / "expected.oracleGeneral"
            compressed = root / "phase.oracleGeneral.zst"
            kwargs = {"objects": 100, "requests_per_phase": 1_003,
                      "alpha": 1.0, "seeds": (42, 43), "batch_size": 257}
            generate_phase_change(raw, **kwargs)
            result = generate_phase_change_zstd(compressed, **kwargs)
            raw_counts = [frequency_counts(raw, objects=100, start=phase * 1_003,
                                           requests=1_003, id_offset=phase * 100)
                          for phase in (0, 1)]
            compressed_counts = phase_change_frequency_counts(
                compressed, objects=100, requests_per_phase=1_003)
            expected = phase_change_expected_digest(**kwargs)
            self.assertEqual([c.tolist() for c in compressed_counts],
                             [c.tolist() for c in raw_counts])
            self.assertEqual(expected["stream_sha256"], result["raw_sha256"])
            self.assertEqual(expected["unique_objects_per_phase"],
                             result["unique_objects_per_phase"])


if __name__ == "__main__":
    unittest.main()
