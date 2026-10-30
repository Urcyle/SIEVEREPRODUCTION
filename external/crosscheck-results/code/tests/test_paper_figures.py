"""The paper-order figure set must rebuild from saved data and contain all 14 figures."""

import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PaperFigureTests(unittest.TestCase):
    def test_all_fourteen_figures_rebuild_from_saved_results_in_three_formats(self):
        with tempfile.TemporaryDirectory() as folder:
            done = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/build_paper_figures.py")], cwd=ROOT,
                                  capture_output=True, text=True, timeout=600,
                                  env={**os.environ, "SIEVE_PAPER_FIGURE_DIR": folder})
            self.assertEqual(done.returncode, 0, done.stderr[-800:])
            names = sorted(p.stem for p in Path(folder).glob("*.png"))
            main = [n for n in names if not re.match(r"fig\d\d[b-z]_", n)]
            self.assertEqual([n[:5] for n in main], [f"fig{i:02d}" for i in range(1, 15)])
            self.assertEqual(sorted(n[:6] for n in names if re.match(r"fig\d\d[b-z]_", n)),
                             ["fig03b", "fig03c", "fig04c", "fig05b", "fig05c", "fig08c", "fig10c"])
            for stem in names:
                for ext in ("png", "svg", "pdf"):
                    self.assertGreater((Path(folder) / f"{stem}.{ext}").stat().st_size, 4000, f"{stem}.{ext}")

    def test_committed_figures_and_readme_exist_for_every_paper_figure(self):
        out = ROOT / "local_results/paper_figures"
        for i in range(1, 15):
            self.assertEqual(len(list(out.glob(f"fig{i:02d}_*.png"))), 1, i)
        self.assertEqual(len(list(out.glob("fig??[b-z]_*.png"))), 7)
        readme = (out / "README.md").read_text()
        for i in range(1, 15):
            self.assertIn(f"| {i} |", readme)

    def test_labels_that_keep_unreproduced_work_honest_are_in_the_source(self):
        source = (ROOT / "scripts/build_paper_figures.py").read_text()
        for phrase in ("proprietary", "not run", "not CacheLib", "paper (digitized)", "Tencent Photo not run"):
            self.assertIn(phrase, source)


if __name__ == "__main__":
    unittest.main()
