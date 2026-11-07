"""CLI regression tests using temporary inventories and the standard library."""

import csv
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "piezocatalysis-lca-modeling/scripts/validate_inventory.py"
)
VALID_ROW = {
    "system": "Synthetic-A",
    "stage": "preparation",
    "flow_name": "precursor",
    "amount": "1.0",
    "unit": "g",
    "direction": "input",
    "evidence_class": "scenario",
    "source": "synthetic test data",
    "dataset_mapping": "",
    "included": "true",
    "note": "Synthetic example",
}


class ValidateInventoryTests(unittest.TestCase):
    def run_inventory(self, **changes):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inventory.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(VALID_ROW))
                writer.writeheader()
                writer.writerow(VALID_ROW)
                writer.writerow({**VALID_ROW, **changes})
            return subprocess.run(
                [sys.executable, str(SCRIPT), str(path)],
                capture_output=True,
                text=True,
                check=False,
            )

    def assert_rejected(self, amount, message):
        result = self.run_inventory(amount=amount)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn(f"ERROR: row 3 (Synthetic-A / precursor): {message}", result.stdout)
        self.assertIn("FAILED: 1 error(s), 0 warning(s)", result.stdout)

    def test_valid_inventory(self):
        result = self.run_inventory()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "PASS: 0 errors, 0 warning(s)\n")

    def test_zero_is_valid(self):
        result = self.run_inventory(amount="0")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "PASS: 0 errors, 0 warning(s)\n")

    def test_nan_rejected(self):
        self.assert_rejected("NaN", "amount must be finite")

    def test_infinity_rejected(self):
        self.assert_rejected("Infinity", "amount must be finite")

    def test_negative_infinity_rejected(self):
        self.assert_rejected("-Infinity", "amount must be finite")

    def test_non_numeric_rejected(self):
        self.assert_rejected("not-a-number", "amount is not numeric")

    def test_negative_rejected(self):
        self.assert_rejected("-1", "negative amount requires an explicit credit workflow")

    def test_excluded_without_note_warns(self):
        result = self.run_inventory(included="false", note="")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn(
            "WARNING: row 3 (Synthetic-A / precursor): excluded flow has no rationale in note",
            result.stdout,
        )
        self.assertIn("PASS: 0 errors, 1 warning(s)", result.stdout)


if __name__ == "__main__":
    unittest.main()
