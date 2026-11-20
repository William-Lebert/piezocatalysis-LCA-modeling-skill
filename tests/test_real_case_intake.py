"""Exercise the intake entry point and replay with realistic fictional records."""
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'piezocatalysis-lca-modeling'
SCRIPTS = SKILL / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from real_case_intake import import_case


class RealCaseIntakeTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name)
        self.example = self.path / 'example'
        shutil.copytree(SKILL / 'assets/examples/synthetic-intake', self.example)

    def data(self, name):
        return json.loads((self.path / 'output' / name).read_text())

    def edit_rows(self, change):
        path = self.example / 'exact-observations.csv'
        with path.open(newline='', encoding='utf-8') as stream:
            reader = csv.DictReader(stream)
            rows, fields = list(reader), reader.fieldnames
        change(rows)
        with path.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def test_exact_import_and_existing_audit_replay(self):
        output = self.path / 'output'
        completed = subprocess.run([sys.executable, str(SCRIPTS / 'real_case_intake.py'),
                                    str(self.example / 'exact-intake.json'), '--output-dir', str(output)],
                                   capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        summary = json.loads(completed.stdout)
        self.assertEqual(summary['coverage'], {'quantity_count': 26, 'linked_count': 26, 'unlinked_count': 0})
        self.assertEqual(summary['unselected_record_ids'], ['R-repeat'])
        evidence = self.data('evidence-report.json')
        self.assertAlmostEqual(evidence['campaign']['apparent_removal_mg'], 32.5)
        self.assertAlmostEqual(summary['campaigns_per_functional_unit'], 2)
        foreground = self.data('foreground.json')
        self.assertEqual(foreground['cycles'][0]['effluent_concentration']['value'], 0)
        flows = {row['activity_id']: row for row in evidence['functional_unit_flows']}
        self.assertAlmostEqual(flows['ultrasound-1']['amount'], 0.12)
        self.assertAlmostEqual(flows['ultrasound-2']['amount'], 0.18)
        self.assertIn('meter-log:', flows['ultrasound-2']['source'])
        quantity_link = next(row for row in evidence['links'] if row['target'] == '/cycles/1/activities/0/quantity')
        self.assertEqual(quantity_link['original']['locator_user_asserted'], 'CSV data record 1, column reading_wh')
        self.assertEqual(quantity_link['original']['sha256'], hashlib.sha256((self.example / 'meter-log.csv').read_bytes()).hexdigest())
        sample_link = next(row for row in evidence['links'] if row['target'] == '/cycles/0/effluent_concentration')
        self.assertEqual(sample_link['sample_user_asserted']['sample_id'], 'effluent-1')
        self.assertIn('/cycles/1/effluent_volume', evidence['inventory_traces'][0]['allocation_input_pointers'])
        command = [sys.executable, str(SCRIPTS / 'evidence_chain.py'), str(output / 'evidence.json'),
                   '--foreground', str(output / 'foreground.json'), '--inventory', str(output / 'inventory.csv'),
                   '--manifest', str(output / 'inventory.csv.manifest.json')]
        replay = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(replay.returncode, 0, replay.stderr)
        self.assertEqual(json.loads(replay.stdout)['links'], evidence['links'])
        (self.example / 'meter-log.csv').write_text('changed\n')
        changed = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(changed.returncode, 1)
        self.assertIn('original source SHA-256 mismatch', changed.stderr)

    def test_censored_and_missing_observations_leave_scaling_unavailable(self):
        summary = import_case(self.example / 'gaps-intake.json', self.path / 'output')
        self.assertEqual(summary['records'], {'exact': 23, 'missing': 1, 'below_lod': 1, 'below_loq': 1})
        self.assertIsNone(summary['campaigns_per_functional_unit'])
        evidence = self.data('evidence-report.json')
        self.assertAlmostEqual(evidence['campaign']['apparent_removal_interval_mg'][0], 35.9)
        self.assertAlmostEqual(evidence['campaign']['apparent_removal_interval_mg'][1], 38)
        self.assertTrue(all(flow['amount'] is None for flow in evidence['functional_unit_flows']))
        foreground = self.data('foreground.json')
        self.assertEqual(foreground['cycles'][0]['effluent_concentration']['limit'], 0.5)
        self.assertEqual(foreground['cycles'][1]['effluent_concentration']['limit'], 1.5)
        self.assertIsNone(foreground['cycles'][0]['activities'][0]['duration']['value'])
        with self.assertRaises(FileExistsError):
            import_case(self.example / 'gaps-intake.json', self.path / 'output')

    def test_missing_runtime_does_not_erase_known_inventory_amounts(self):
        def omit_runtime(rows):
            duration = next(row for row in rows if row['target'] == '/cycles/0/activities/0/duration')
            duration.update(qualifier='missing', value='')
        self.edit_rows(omit_runtime)
        summary = import_case(self.example / 'exact-intake.json', self.path / 'output')
        self.assertEqual(summary['records']['missing'], 1)
        self.assertEqual(summary['campaigns_per_functional_unit'], 2)
        rows = {row['activity_id']: row for row in self.data('evidence-report.json')['functional_unit_flows']}
        self.assertIsNone(rows['ultrasound-1']['amount'])
        self.assertAlmostEqual(rows['ultrasound-2']['amount'], 0.18)

    def test_rejects_ambiguous_or_invalid_inputs_without_outputs(self):
        original = (self.example / 'exact-observations.csv').read_bytes()
        checks = [
            (lambda rows: rows[-1].update(selected='yes'), 'multiple records selected'),
            (lambda rows: next(r for r in rows if r['target'] == '/cycles/1/effluent_concentration' and r['selected'] == 'yes').update(sample_id='effluent-1'), 'reused across cycles'),
            (lambda rows: next(r for r in rows if r['target'] == '/cycles/1/effluent_volume').update(sample_id='other-sample'), 'refer to different samples'),
            (lambda rows: next(r for r in rows if r['target'] == '/cycles/0/activities/0/power').update(unit='kg'), 'incompatible or unsupported unit'),
            (lambda rows: next(r for r in rows if r['target'] == '/cycles/0/activities/0/power').update(energy_basis='rated_power', evidence_class='measured'), 'cannot be marked measured'),
            (lambda rows: rows[0].update(selected='no'), 'no record selected'),
        ]
        for change, message in checks:
            with self.subTest(message=message):
                (self.example / 'exact-observations.csv').write_bytes(original)
                self.edit_rows(change)
                with self.assertRaisesRegex(ValueError, message):
                    import_case(self.example / 'exact-intake.json', self.path / 'output')
                self.assertFalse((self.path / 'output').exists())
