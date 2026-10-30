"""Smoke coverage for the public module entry point."""

import subprocess
import sys
import unittest
from pathlib import Path


class SmokeTest(unittest.TestCase):
    def test_module_entry_point(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--help"],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("central notice pipeline (M10)", result.stdout)
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
