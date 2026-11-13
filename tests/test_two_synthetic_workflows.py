"""Two fictional end-to-end inventory-to-partial-impact checks; no LCA data."""
import copy
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'piezocatalysis-lca-modeling'
EXAMPLES = ROOT / 'assets/examples'
SCRIPTS = ROOT / 'scripts'


class TwoSyntheticWorkflowTests(unittest.TestCase):
    def run_script(self, name, *args):
        result = subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return result.stdout

    def run_case(self, spec):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            source = EXAMPLES / 'synthetic-treatment'
            with (source / 'inventory.csv').open(newline='') as stream:
                reader = csv.DictReader(stream)
                rows, fields = list(reader), reader.fieldnames
            for index, amount in spec['row_amounts'].items():
                rows[index]['amount'] = str(amount)
            rows[0]['direction'] = 'INPUT'
            rows[0]['evidence_class'] = 'SCENARIO'
            inventory = directory / 'inventory.csv'
            with inventory.open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            params = json.loads((source / 'parameters.json').read_text())
            params['service_definition']['value'] = spec['service']
            for name in ('target_removed_mg', 'removed_per_run_mg', 'catalyst_dose_g', 'effective_uses'):
                params[name]['value'] = spec[name]
            param_path = directory / 'parameters.json'
            param_path.write_text(json.dumps(params))
            self.assertIn('PASS:', self.run_script('validate_inventory.py', inventory))
            report = json.loads(self.run_script('audit_and_scale_inventory.py',
                '--inventory', inventory, '--mapping', source / 'dataset_mapping.csv',
                '--parameters', param_path, '--system', 'Synthetic-A', '--reference-flow', 'dry catalyst'))
            self.assertAlmostEqual(report['scaling']['runs_per_fu'], spec['runs'])
            self.assertAlmostEqual(report['scaling']['preparation_batches_per_fu'], spec['batches'])
            flows = {(item['stage'], item['flow_name']): item for item in report['flows']}
            self.assertAlmostEqual(flows['preparation', 'precursor A']['amount_per_fu'], spec['precursor'])
            self.assertAlmostEqual(flows['preparation', 'precursor A']['dataset_amount_per_fu'], spec['precursor'] / 1000)
            self.assertAlmostEqual(flows['preparation', 'electricity']['amount_per_fu'], spec['prep_kwh'])
            self.assertAlmostEqual(flows['treatment', 'electricity']['amount_per_fu'], spec['treat_kwh'])
            self.assertAlmostEqual(flows['treatment', 'wastewater']['amount_per_fu'], spec['wastewater'])
            self.assertIsNone(flows['treatment', 'wastewater']['dataset_amount_per_fu'])
            self.assertTrue(any('unmapped' in warning for warning in report['warnings']))
            scale_text = self.run_script('piezocatalysis_calculations.py', 'scale',
                '--target-removed-mg', spec['target_removed_mg'], '--removed-per-run-mg', spec['removed_per_run_mg'],
                '--catalyst-dose-g', spec['catalyst_dose_g'], '--dry-batch-yield-g', rows[2]['amount'])
            values = dict(line.split('=') for line in scale_text.splitlines())
            self.assertAlmostEqual(float(values['batch_share_per_FU']) / spec['effective_uses'], spec['batches'])

            # Fictional unit factors for only the three mapped flows. Unmapped wastewater
            # is deliberately omitted, so these are partial indicators, not full LCIA.
            preparation = flows['preparation', 'precursor A']['amount_per_fu'] * 0.1 + flows['preparation', 'electricity']['amount_per_fu'] * 0.5
            treatment = flows['treatment', 'electricity']['amount_per_fu'] * 0.5
            self.assertAlmostEqual(preparation + treatment, spec['partial_base'])
            example = json.loads((EXAMPLES / 'synthetic-sensitivity/scenarios.json').read_text())
            routes = []
            for rid, factor in [('A', 1.0), ('B', 0.8)]:
                route = copy.deepcopy(example['routes'][0])
                route['id'] = rid
                route['scope']['functional_unit']['amount'] = spec['target_removed_mg']
                route['scope']['functional_unit']['description'] = spec['service']
                route['impact_categories'] = {'partial': {'unit': 'fictional impact units',
                    'total': (preparation + treatment) * factor,
                    'source': 'fictional factors for three mapped flows only; excludes unmapped wastewater',
                    'evidence_class': 'calculated'}}
                route['components'] = [
                    {'id': 'preparation', 'source': 'fictional factors', 'evidence_class': 'calculated',
                     'impacts': {'partial': preparation * factor}},
                    {'id': 'treatment_electricity', 'source': 'fictional factors', 'evidence_class': 'calculated',
                     'impacts': {'partial': treatment * factor}}]
                routes.append(route)
            data = {'description': 'fictional partial indicator; wastewater excluded, not a full LCA',
                    'routes': routes, 'scenarios': [{'id': 'double_treatment', 'variable': 'treatment energy',
                        'baseline': 1, 'value': 2, 'unit': 'ratio', 'evidence_class': 'scenario',
                        'source': 'fictional linear assumption', 'adjustments': [
                            {'route': 'A', 'component': 'treatment_electricity', 'operator': 'linear'}]}]}
            scenario = directory / 'scenario.json'
            scenario.write_text(json.dumps(data))
            result = json.loads(self.run_script('sensitivity_report.py', scenario))
            self.assertAlmostEqual(result['cases'][0]['results']['A']['partial']['absolute'], spec['partial_base'])
            self.assertAlmostEqual(result['cases'][1]['results']['A']['partial']['absolute'], spec['partial_double'])
            self.assertAlmostEqual(result['cases'][0]['results']['B']['partial']['absolute'], spec['partial_base'] * 0.8)

    def test_case_one(self):
        self.run_case({'service': 'fictional removal of 100 mg; 10 mg per run',
            'target_removed_mg': 100, 'removed_per_run_mg': 10, 'catalyst_dose_g': 1, 'effective_uses': 2,
            'row_amounts': {}, 'runs': 10, 'batches': 1, 'precursor': 10, 'prep_kwh': 2, 'treat_kwh': 1,
            'wastewater': 10, 'partial_base': 2.5, 'partial_double': 3.0})

    def test_case_two(self):
        self.run_case({'service': 'fictional removal of 180 mg; 15 mg per run',
            'target_removed_mg': 180, 'removed_per_run_mg': 15, 'catalyst_dose_g': 2, 'effective_uses': 3,
            'row_amounts': {0: 7.5, 1: 4, 2: 4, 3: 0.25, 4: 2}, 'runs': 12, 'batches': 2,
            'precursor': 15, 'prep_kwh': 8, 'treat_kwh': 3, 'wastewater': 24,
            'partial_base': 7.0, 'partial_double': 8.5})


if __name__ == '__main__':
    unittest.main()
