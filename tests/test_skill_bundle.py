from pathlib import Path
import unittest
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

class SkillBundleTests(unittest.TestCase):
    def test_bundled_helper_matches_tested_source(self):
        self.assertEqual((ROOT / 'route_snap_plan.py').read_bytes(),
                         (ROOT / 'skills/rails-screenshot-plan/scripts/route_snap_plan.py').read_bytes())

    def test_absolute_bundled_helper_is_independent_of_project_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            cwd = Path(directory)
            (cwd / "scripts").mkdir()
            (cwd / "scripts/route_snap_plan.py").write_text("raise RuntimeError('wrong project script')")
            result = subprocess.run([
                "python3", str(ROOT / "skills/rails-screenshot-plan/scripts/route_snap_plan.py"),
                "--routes", str(ROOT / "examples/routes.txt"),
                "--changed", str(ROOT / "examples/changed.txt"),
                "--config", str(ROOT / "examples/config.json"), "--strict"],
                cwd=cwd, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"candidate_plan"', result.stdout)
