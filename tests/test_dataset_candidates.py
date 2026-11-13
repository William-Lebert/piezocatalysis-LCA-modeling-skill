"""Candidate selection uses fictional openLCA process descriptors."""
import sys
import unittest
import csv
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'piezocatalysis-lca-modeling/scripts'))
from dataset_candidates import find_candidates


class DatasetCandidateTests(unittest.TestCase):
    def test_same_named_processes_require_review(self):
        processes = [
            {'@id': '00000000-0000-4000-8000-000000000001', 'name': 'electricity mix', 'location': 'CN'},
            {'@id': '00000000-0000-4000-8000-000000000002', 'name': 'electricity mix', 'location': 'GLO'},
        ]
        result = find_candidates({'dataset_name': 'electricity mix'}, processes)
        self.assertEqual(result['status'], 'ambiguous')
        self.assertEqual(len(result['candidates']), 2)
        self.assertIsNone(result['selected_process_uuid'])

    def test_geography_narrows_candidates_without_selecting(self):
        rows = [{'@id': '00000000-0000-4000-8000-000000000001', 'name': 'electricity mix', 'location': 'CN'},
                {'@id': '00000000-0000-4000-8000-000000000002', 'name': 'electricity mix', 'location': 'GLO'}]
        result = find_candidates({'dataset_name': 'electricity mix', 'geography': 'CN'}, rows)
        self.assertEqual(result['status'], 'needs_review')
        self.assertEqual(result['candidates'][0]['location'], 'CN')
        self.assertIsNone(result['selected_process_uuid'])

    def test_unknown_uuid_does_not_fall_back_to_name(self):
        rows = [{'@id': '00000000-0000-4000-8000-000000000001', 'name': 'electricity mix'}]
        result = find_candidates({'dataset_name': 'electricity mix', 'process_uuid': '00000000-0000-4000-8000-000000000099'}, rows)
        self.assertEqual(result['status'], 'not_found')
        self.assertEqual(result['candidates'], [])

    def test_descriptor_with_missing_location_does_not_crash(self):
        rows = [{'@id': '00000000-0000-4000-8000-000000000001', 'name': 'electricity mix', 'location': None}]
        result = find_candidates({'dataset_name': 'electricity mix', 'geography': 'CN'}, rows)
        self.assertEqual(result['status'], 'not_found')

    def test_present_uuid_with_changed_name_needs_explicit_resolution(self):
        rows = [{'@id': '00000000-0000-4000-8000-000000000001', 'name': 'different dataset', 'location': 'CN'}]
        result = find_candidates({'dataset_name': 'electricity mix', 'geography': 'CN',
                                  'process_uuid': rows[0]['@id']}, rows)
        self.assertEqual(result['status'], 'metadata_mismatch')
        self.assertIsNone(result['selected_process_uuid'])

    def test_invalid_inclusion_flag_does_not_silently_drop_flow(self):
        from dataset_candidates import report
        row = {'_row': '2', 'included': 'perhaps'}
        with self.assertRaisesRegex(ValueError, 'included'):
            report([row], [], [], {})

    def test_cli_flags_database_and_unit_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            example = ROOT / 'piezocatalysis-lca-modeling/assets/examples/synthetic-treatment'
            with (example / 'dataset_mapping.csv').open() as f:
                rows = list(csv.DictReader(f))
            rows[0]['database_version'] = 'old'
            rows[1]['dataset_unit'] = 'kg'
            with (tmp/'mapping.csv').open('w', newline='') as f:
                w = csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
            (tmp/'descriptors.json').write_text(json.dumps({'type':'Process', 'descriptors':[]}))
            command = [sys.executable, str(ROOT/'piezocatalysis-lca-modeling/scripts/dataset_candidates.py'),
                       '--inventory', str(example/'inventory.csv'), '--mapping', str(tmp/'mapping.csv'),
                       '--descriptors', str(tmp/'descriptors.json'), '--database', 'Synthetic DB',
                       '--database-version', '1.0', '--system-model', 'synthetic']
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            report = json.loads(run.stdout)
            by_flow = {r['foreground_flow']: r for r in report['rows']}
            self.assertEqual(by_flow['precursor A']['status'], 'database_mismatch')
            self.assertEqual(by_flow['electricity']['status'], 'unit_mismatch')
            self.assertEqual(by_flow['wastewater']['status'], 'not_found')
            self.assertIsNone(by_flow['wastewater']['selected_process_uuid'])

    def test_four_flow_synthetic_example(self):
        example = ROOT/'piezocatalysis-lca-modeling/assets/examples/synthetic-mapping'
        command = [sys.executable, str(ROOT/'piezocatalysis-lca-modeling/scripts/dataset_candidates.py'),
                   '--inventory', str(example/'inventory.csv'), '--mapping', str(example/'mapping.csv'),
                   '--descriptors', str(example/'processes.json'), '--database', 'Synthetic DB',
                   '--database-version', '1.0', '--system-model', 'synthetic']
        run = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        rows = {r['foreground_flow']: r for r in json.loads(run.stdout)['rows']}
        self.assertEqual({k: v['status'] for k, v in rows.items()},
                         {'electricity': 'ambiguous', 'water': 'needs_review',
                          'reagent': 'not_found', 'wastewater': 'not_found'})
        self.assertTrue(all(r['selected_process_uuid'] is None for r in rows.values()))
        csv_run = subprocess.run(command + ['--format', 'csv'], capture_output=True, text=True)
        self.assertEqual(csv_run.returncode, 0, csv_run.stderr)
        table = list(csv.DictReader(csv_run.stdout.splitlines()))
        self.assertEqual(len(table), 5)
        self.assertEqual(sum(r['foreground_flow'] == 'electricity' for r in table), 2)
        self.assertTrue(any(r['status'] == 'not_found' and not r['candidate_uuid'] for r in table))


if __name__ == '__main__':
    unittest.main()
