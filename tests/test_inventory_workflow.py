"""End-to-end checks using an invented treatment-service inventory."""
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'piezocatalysis-lca-modeling'
SCRIPT = SKILL / 'scripts/audit_and_scale_inventory.py'
EXAMPLE = SKILL / 'assets/examples/synthetic-treatment'

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.case = Path(self.tmp.name)
        for p in EXAMPLE.iterdir(): shutil.copy2(p, self.case / p.name)
    def run_case(self):
        return subprocess.run([sys.executable, str(SCRIPT), '--inventory', str(self.case/'inventory.csv'),
            '--mapping', str(self.case/'dataset_mapping.csv'), '--parameters', str(self.case/'parameters.json'),
            '--system', 'Synthetic-A', '--reference-flow', 'dry catalyst'], capture_output=True, text=True)
    def change_csv(self, name, index, key, value):
        path = self.case/name
        with path.open(newline='') as f: reader = csv.DictReader(f); rows = list(reader); fields = reader.fieldnames
        rows[index][key] = value
        with path.open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    def test_synthetic_service_and_unmapped_flow(self):
        result = self.run_case(); self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report, json.loads((self.case/'expected-report.json').read_text()))
        self.assertEqual(report['scaling']['runs_per_fu'], 10)
        self.assertEqual(report['scaling']['preparation_batches_per_fu'], 1)
        rows = report['flows']; precursor = next(x for x in rows if x['flow_name'] == 'precursor A')
        self.assertAlmostEqual(precursor['amount_per_fu'], 10)
        self.assertAlmostEqual(precursor['dataset_amount_per_fu'], 0.01)
        electricity = [x for x in rows if x['flow_name'] == 'electricity']
        self.assertEqual([x['amount_per_fu'] for x in electricity], [2, 1])
        waste = next(x for x in rows if x['flow_name'] == 'wastewater')
        self.assertEqual(waste['amount_per_fu'], 10); self.assertIsNone(waste['dataset_amount_per_fu'])
        self.assertTrue(any('unmapped' in x for x in report['warnings']))
        self.assertEqual(precursor['source'], 'synthetic synthesis recipe')
    def test_missing_source_rejected(self):
        self.change_csv('inventory.csv', 0, 'source', '')
        result = self.run_case(); self.assertNotEqual(result.returncode, 0); self.assertIn('source', result.stderr)
        self.assertEqual(result.stdout, '')
    def test_unit_mismatch_and_wrong_factor_rejected(self):
        for key, value in [('foreground_unit', 'kg'), ('conversion_factor', '1000')]:
            with self.subTest(key=key):
                shutil.copy2(EXAMPLE/'dataset_mapping.csv', self.case/'dataset_mapping.csv')
                self.change_csv('dataset_mapping.csv', 0, key, value)
                result = self.run_case(); self.assertNotEqual(result.returncode, 0)
    def test_unknown_mapping_id_not_replaced_with_zero(self):
        self.change_csv('inventory.csv', 0, 'dataset_mapping', 'absent')
        result = self.run_case(); self.assertNotEqual(result.returncode, 0); self.assertIn('absent', result.stderr)
        self.assertEqual(result.stdout, '')
    def test_invalid_reuse_and_missing_parameter_source_rejected(self):
        path = self.case/'parameters.json'; params = json.loads(path.read_text())
        for value in (0, -1, float('nan'), '2', True):
            params['effective_uses']['value'] = value; path.write_text(json.dumps(params))
            result = self.run_case(); self.assertNotEqual(result.returncode, 0)
        params['effective_uses']['value'] = 2; params['effective_uses']['source'] = ''; path.write_text(json.dumps(params))
        self.assertNotEqual(self.run_case().returncode, 0)
    def test_missing_or_duplicate_reference_flow_rejected(self):
        self.change_csv('inventory.csv', 2, 'flow_name', 'other')
        self.assertNotEqual(self.run_case().returncode, 0)
        shutil.copy2(EXAMPLE/'inventory.csv', self.case/'inventory.csv')
        lines = (self.case/'inventory.csv').read_text().splitlines()
        with (self.case/'inventory.csv').open('a') as f: f.write(lines[3] + '\n')
        self.assertNotEqual(self.run_case().returncode, 0)
    def test_truncated_csv_reports_error_without_traceback(self):
        with (self.case/'inventory.csv').open('a') as f: f.write('short,row\n')
        result = self.run_case(); self.assertNotEqual(result.returncode, 0); self.assertNotIn('Traceback', result.stderr)
    def test_excluded_flows_are_documented_without_scaling(self):
        self.change_csv('inventory.csv', 0, 'included', 'false')
        result = self.run_case(); self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(any(x['flow_name'] == 'precursor A' for x in report['flows']))
        self.assertEqual(report['excluded_flows'][0]['flow_name'], 'precursor A')
    def test_duplicate_mapping_ids_are_rejected(self):
        self.change_csv('dataset_mapping.csv', 1, 'mapping_id', 'map-precursor')
        result = self.run_case(); self.assertNotEqual(result.returncode, 0)
        self.assertIn('duplicate mapping_id', result.stderr)
    def test_unsupported_units_and_wrong_parameter_units_rejected(self):
        self.change_csv('inventory.csv', 0, 'unit', 'lb')
        self.assertNotEqual(self.run_case().returncode, 0)
        shutil.copy2(EXAMPLE/'inventory.csv', self.case/'inventory.csv')
        path = self.case/'parameters.json'; params = json.loads(path.read_text())
        params['target_removed_mg']['unit'] = 'kg'; path.write_text(json.dumps(params))
        self.assertNotEqual(self.run_case().returncode, 0)
    def test_reproducible_and_inputs_unchanged(self):
        before = {p.name: p.read_bytes() for p in self.case.iterdir()}
        first = self.run_case(); second = self.run_case()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.case.iterdir()})

if __name__ == '__main__': unittest.main()
