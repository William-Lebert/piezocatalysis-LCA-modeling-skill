"""End-to-end tests for fictional experimental foreground inventories."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import csv
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'piezocatalysis-lca-modeling'
SCRIPT = SKILL / 'scripts/experimental_foreground.py'
EXAMPLE = SKILL / 'assets/examples/synthetic-foreground'


class ExperimentalForegroundTests(unittest.TestCase):
    def run_case(self, path):
        p = subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def test_case_a_mass_and_functional_units(self):
        report = self.run_case(EXAMPLE/'case-a.json')
        self.assertEqual(report['removal']['apparent_removed_mg_per_run'], 10)
        self.assertEqual(report['production']['preparation_batches'], 200)
        self.assertEqual(report['treatment']['treatment_runs'], 10)
        self.assertEqual(report['treatment']['preparation_batches'], 1)
        self.assertEqual(report['treatment']['catalyst_loading_mg_per_l'], 1000)
        self.assertEqual(report['mass_check']['listed_preparation_mass_inputs_g'], 10)
        by_id = {x['activity_id']: x for x in report['treatment']['flows']}
        self.assertAlmostEqual(by_id['ultrasound']['amount'], 1)
        self.assertEqual(by_id['ultrasound']['unit'], 'kWh')
        self.assertTrue(any(x['activity_id']=='transport' for x in report['excluded_flows']))

    def test_case_b_unit_conversion_and_treatment_boundary(self):
        report = self.run_case(EXAMPLE/'case-b.json')
        self.assertEqual(report['removal']['apparent_removed_mg_per_run'], 15)
        self.assertEqual(report['production']['preparation_batches'], 100)
        self.assertEqual(report['treatment']['treatment_runs'], 10)
        self.assertAlmostEqual(report['treatment']['preparation_batches'], 0.1)
        self.assertEqual(report['treatment']['catalyst_loading_mg_per_l'], 1000)
        production = {r['activity_id']: r for r in report['production']['flows']}
        treatment = {r['activity_id']: r for r in report['treatment']['flows']}
        self.assertNotIn('ultrasound', production)
        self.assertAlmostEqual(production['prep-energy']['amount'], 200)
        self.assertAlmostEqual(treatment['ultrasound']['amount'], 1)
        self.assertAlmostEqual(treatment['wastewater']['amount'], 5)
        self.assertAlmostEqual(treatment['precursor']['amount'], 2)

    def test_below_detection_keeps_interval_and_unknown_scaling(self):
        data = json.loads((EXAMPLE/'case-a.json').read_text())
        data['treatment']['effluent'].update(value=None, qualifier='below_loq', limit=2)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'case.json'; path.write_text(json.dumps(data))
            report=self.run_case(path)
        self.assertIsNone(report['removal']['apparent_removed_mg_per_run'])
        self.assertEqual(report['removal']['range_mg_per_run'], [18, 20])
        self.assertIsNone(report['treatment']['treatment_runs'])
        self.assertTrue(all(r['amount'] is None for r in report['treatment']['flows']))
        self.assertEqual(report['production']['preparation_batches'], 200)

    def test_below_detection_limit_and_unicode_micro_units(self):
        data=json.loads((EXAMPLE/'case-a.json').read_text())
        data['treatment']['effluent'].update(value=None, unit='µg/L', qualifier='below_lod', limit=2000)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'case.json';path.write_text(json.dumps(data,ensure_ascii=False))
            report=self.run_case(path)
        self.assertEqual(report['removal']['range_mg_per_run'], [18,20])
        self.assertEqual(report['removal']['effluent_qualifier'], 'below_lod')

    def test_duplicate_overlap_group_rejected(self):
        data = json.loads((EXAMPLE/'case-a.json').read_text())
        data['flows'][2]['overlap_group'] = 'same-meter'
        data['flows'][3]['overlap_group'] = 'same-meter'
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'case.json';path.write_text(json.dumps(data))
            run=subprocess.run([sys.executable,str(SCRIPT),str(path)],capture_output=True,text=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn('overlapping',run.stderr)

    def test_csv_export_uses_existing_inventory_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path=Path(tmp)/'inventory.csv'
            run=subprocess.run([sys.executable,str(SCRIPT),str(EXAMPLE/'case-a.json'),
                                '--inventory-csv',str(csv_path)],capture_output=True,text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            validate=subprocess.run([sys.executable,str(SKILL/'scripts/validate_inventory.py'),str(csv_path)],capture_output=True,text=True)
            self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)
            self.assertIn('dry catalyst',csv_path.read_text())
            example = SKILL/'assets/examples/synthetic-treatment'
            scaled=subprocess.run([sys.executable,str(SKILL/'scripts/audit_and_scale_inventory.py'),
                '--inventory',str(csv_path),'--mapping',str(example/'dataset_mapping.csv'),
                '--parameters',str(example/'parameters.json'),'--system','Synthetic-A',
                '--reference-flow','dry catalyst'],capture_output=True,text=True)
            self.assertEqual(scaled.returncode, 0, scaled.stderr)
            self.assertEqual(json.loads(scaled.stdout)['scaling']['runs_per_fu'], 10)

    def test_missing_measurement_is_not_zero(self):
        data=json.loads((EXAMPLE/'case-a.json').read_text())
        data['flows'][1]['quantity']['value']=None
        data['treatment']['catalyst_dose']['value']=None
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'case.json';path.write_text(json.dumps(data))
            report=self.run_case(path)
        self.assertIsNone(report['treatment']['preparation_batches'])
        self.assertIsNone(next(x for x in report['production']['flows'] if x['activity_id']=='wash')['amount'])
        self.assertTrue(report['warnings'])

    def test_derived_power_retains_source_evidence(self):
        report=self.run_case(EXAMPLE/'case-a.json')
        energy=next(x for x in report['treatment']['flows'] if x['activity_id']=='ultrasound')
        self.assertEqual(energy['evidence_class'], 'calculated')
        self.assertEqual(energy['derivation']['power']['evidence_class'], 'scenario')
        self.assertEqual(energy['derivation']['duration']['source'], 'fictional duration')

    def test_invalid_effluent_mass_relation_fails(self):
        data=json.loads((EXAMPLE/'case-a.json').read_text())
        data['treatment']['effluent']['value']=21
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'case.json';path.write_text(json.dumps(data))
            run=subprocess.run([sys.executable,str(SCRIPT),str(path)],capture_output=True,text=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn('effluent exceeds',run.stderr)

    def test_missing_yield_leaves_preparation_unscaled(self):
        data=json.loads((EXAMPLE/'case-a.json').read_text())
        data['dry_yield']['value']=None
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'case.json';path.write_text(json.dumps(data))
            report=self.run_case(path)
        self.assertIsNone(report['production']['preparation_batches'])
        self.assertIsNone(report['treatment']['preparation_batches'])
        self.assertEqual(report['treatment']['treatment_runs'], 10)
        ultrasound=next(x for x in report['treatment']['flows'] if x['activity_id']=='ultrasound')
        self.assertEqual(ultrasound['amount'], 1)

    def test_zero_removal_preserves_observation_and_production_result(self):
        data=json.loads((EXAMPLE/'case-a.json').read_text())
        data['treatment']['effluent']['value']=20
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'case.json';path.write_text(json.dumps(data))
            report=self.run_case(path)
        self.assertEqual(report['removal']['apparent_removed_mg_per_run'],0)
        self.assertIsNone(report['treatment']['treatment_runs'])
        self.assertEqual(report['production']['preparation_batches'],200)

    def test_case_b_csv_agrees_with_existing_treatment_scaler(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path=Path(tmp)/'inventory.csv'
            run=subprocess.run([sys.executable,str(SCRIPT),str(EXAMPLE/'case-b.json'),
                                '--inventory-csv',str(csv_path)],capture_output=True,text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            example=SKILL/'assets/examples/synthetic-treatment'
            params=json.loads((example/'parameters.json').read_text())
            for key,value in [('target_removed_mg',150),('removed_per_run_mg',15),
                              ('catalyst_dose_g',0.5),('effective_uses',5)]:
                params[key]['value']=value
            pp=Path(tmp)/'parameters.json';pp.write_text(json.dumps(params))
            result=subprocess.run([sys.executable,str(SKILL/'scripts/audit_and_scale_inventory.py'),
                '--inventory',str(csv_path),'--mapping',str(example/'dataset_mapping.csv'),
                '--parameters',str(pp),'--system','Synthetic-B','--reference-flow','dry catalyst'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            scaling=json.loads(result.stdout)['scaling']
            self.assertEqual(scaling['runs_per_fu'],10)
            self.assertAlmostEqual(scaling['preparation_batches_per_fu'],0.1)
