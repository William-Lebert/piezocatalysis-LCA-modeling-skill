"""Independent numerical and command-line checks for calculation helpers."""
import importlib.util
import math
from pathlib import Path
import subprocess
import sys
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'piezocatalysis-lca-modeling/scripts/piezocatalysis_calculations.py'
spec = importlib.util.spec_from_file_location('calculations', SCRIPT)
calc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calc)

class CalculationTests(unittest.TestCase):
    def test_hand_calculated_anchors(self):
        self.assertAlmostEqual(calc.removal_fraction(math.log(2), 1), 0.5)
        self.assertAlmostEqual(calc.removed_mass_mg(10, 2, 0.5), 10)
        self.assertAlmostEqual(calc.eeo_kwh_m3_order(0.06, 1, math.log(10)), 1)
        self.assertAlmostEqual(calc.batch_energy_kwh(2, 3), 6)
        self.assertAlmostEqual(calc.preparation_share(2, 10), 0.2)
        self.assertAlmostEqual(calc.treatment_scale(100, 10), 10)

    def test_small_rate_is_not_rounded_to_zero(self):
        self.assertGreater(calc.removal_fraction(1e-20, 1), 0)

    def test_zero_boundaries(self):
        self.assertEqual(calc.removal_fraction(1, 0), 0)
        self.assertEqual(calc.batch_energy_kwh(0, 0), 0)
        self.assertEqual(calc.removed_mass_mg(0, 1, 0), 0)

    def test_nonfinite_inputs_rejected_at_every_position(self):
        cases = [(calc.removal_fraction, [1, 1]), (calc.removed_mass_mg, [1, 1, 0.5]),
                 (calc.eeo_kwh_m3_order, [1, 1, 1]), (calc.batch_energy_kwh, [1, 1]),
                 (calc.preparation_share, [1, 1]), (calc.treatment_scale, [1, 1])]
        for fn, args in cases:
            for i in range(len(args)):
                for bad in (float('nan'), float('inf'), float('-inf')):
                    values = args.copy(); values[i] = bad
                    with self.subTest(fn=fn.__name__, position=i, bad=bad):
                        with self.assertRaises(ValueError): fn(*values)

    def test_overflow_rejected(self):
        for fn, args in [(calc.batch_energy_kwh, (1e308, 2)),
                         (calc.treatment_scale, (1e308, 1e-308)),
                         (calc.eeo_kwh_m3_order, (1e308, 1e-308, 1)),
                         (calc.eeo_kwh_m3_order, (1, 1e308, 1))]:
            with self.subTest(fn=fn.__name__):
                with self.assertRaises(ValueError): fn(*args)

    def test_invalid_physical_boundaries(self):
        cases = [(calc.removal_fraction, (0, 1)), (calc.removal_fraction, (1, -1)),
                 (calc.removed_mass_mg, (1, 1, 1.1)), (calc.eeo_kwh_m3_order, (-1, 1, 1)),
                 (calc.preparation_share, (1, 0)), (calc.treatment_scale, (0, 1))]
        for fn, args in cases:
            with self.subTest(fn=fn.__name__):
                with self.assertRaises(ValueError): fn(*args)

    def test_cli_rejects_invalid_without_traceback(self):
        p = subprocess.run([sys.executable, str(SCRIPT), 'energy', '--power-kw', 'nan', '--time-h', '1'], capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertNotIn('Traceback', p.stderr)
        self.assertIn('finite', p.stderr)

    def test_cli_scale_overflow_does_not_print_partial_result(self):
        p = subprocess.run([sys.executable, str(SCRIPT), 'scale', '--target-removed-mg', '1e200',
                            '--removed-per-run-mg', '1', '--catalyst-dose-g', '1e200',
                            '--dry-batch-yield-g', '1'], capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(p.stdout, '')

if __name__ == '__main__': unittest.main()
