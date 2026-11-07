"""Independent hand anchors and failure cases for sensitivity report."""
import copy, json, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'piezocatalysis-lca-modeling/scripts/sensitivity_report.py'
EXAMPLE=ROOT/'piezocatalysis-lca-modeling/assets/examples/synthetic-sensitivity/scenarios.json'

class SensitivityTests(unittest.TestCase):
    def run_data(self, data, extra=()):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'input.json';p.write_text(json.dumps(data),encoding='utf8')
            return subprocess.run([sys.executable,str(SCRIPT),str(p),*extra],capture_output=True,text=True)
    def setUp(self): self.data=json.loads(EXAMPLE.read_text())
    def test_hand_anchors_and_ranking_reversal(self):
        r=self.run_data(self.data);self.assertEqual(r.returncode,0,r.stderr);x=json.loads(r.stdout)
        baseline=x['cases'][0];power=x['cases'][1];yield_case=x['cases'][2];proxy=x['cases'][3]
        self.assertEqual(baseline['results']['A']['climate']['absolute'],3)
        self.assertEqual(power['results']['A']['climate']['absolute'],5)
        self.assertAlmostEqual(power['results']['A']['climate']['change_percent'],200/3)
        self.assertEqual(power['results']['A']['energy']['absolute'],20)
        self.assertEqual(baseline['rankings']['climate']['groups'],[['A'],['B']])
        self.assertEqual(power['rankings']['climate']['groups'],[['B'],['A']])
        self.assertTrue(power['rankings']['climate']['changed_from_baseline'])
        self.assertEqual(yield_case['results']['A']['climate']['absolute'],2.5)
        self.assertEqual(proxy['results']['A']['climate']['absolute'],5)
    def test_incompatible_scopes_or_impact_units_rejected(self):
        for field in ('system_boundary','system_model','database_version','lcia_version','geography','allocation','illumination_decision','electricity_scenario','cutoff_rules','temporal_scope'):
            d=copy.deepcopy(self.data);d['routes'][1]['scope'][field]='different'
            with self.subTest(field=field):self.assertNotEqual(self.run_data(d).returncode,0)
        d=copy.deepcopy(self.data);d['routes'][1]['impact_categories']['climate']['unit']='different'
        self.assertNotEqual(self.run_data(d).returncode,0)
        d=copy.deepcopy(self.data);d['routes'][1]['scope']['functional_unit']['amount']=1
        self.assertNotEqual(self.run_data(d).returncode,0)
        d=copy.deepcopy(self.data);d['routes'][1]['scope']['extra_boundary']='excluded'
        self.assertNotEqual(self.run_data(d).returncode,0)
    def test_missing_contribution_and_inconsistent_total_rejected(self):
        d=copy.deepcopy(self.data);del d['routes'][0]['components'][0]['impacts']['climate']
        self.assertNotEqual(self.run_data(d).returncode,0)
        d=copy.deepcopy(self.data);d['routes'][0]['impact_categories']['climate']['total']=10
        self.assertNotEqual(self.run_data(d).returncode,0)
        d=copy.deepcopy(self.data);d['routes'][0]['components_are_non_overlapping']=False
        self.assertNotEqual(self.run_data(d).returncode,0)
        d=copy.deepcopy(self.data);del d['routes'][0]['components'][0]['evidence_class']
        self.assertNotEqual(self.run_data(d).returncode,0)
        d=copy.deepcopy(self.data);d['routes'][0]['result_basis']='normalized'
        self.assertNotEqual(self.run_data(d).returncode,0)
    def test_missing_scenario_source_and_duplicate_adjustment_rejected(self):
        d=copy.deepcopy(self.data);d['scenarios'][0]['source']=''
        self.assertNotEqual(self.run_data(d).returncode,0)
        d=copy.deepcopy(self.data);d['scenarios'][0]['adjustments'].append(d['scenarios'][0]['adjustments'][0])
        self.assertNotEqual(self.run_data(d).returncode,0)
    def test_replacement_evidence_is_independent_from_scenario(self):
        d=copy.deepcopy(self.data)
        scenario=next(x for x in d['scenarios'] if x['id']=='A_proxy_alternative')
        scenario['evidence_class']='scenario'
        scenario['adjustments'][0]['replacement_evidence_class']='proxy'
        r=self.run_data(d);self.assertEqual(r.returncode,0,r.stderr)
        case=next(x for x in json.loads(r.stdout)['cases'] if x['id']=='A_proxy_alternative')
        component=case['components']['A']['preparation']
        self.assertEqual(component['evidence_class'],'proxy')
        self.assertEqual(component['scenario_evidence_class'],'scenario')
        self.assertEqual(component['baseline_source'],d['routes'][0]['components'][0]['source'])
        self.assertEqual(component['baseline_evidence_class'],d['routes'][0]['components'][0]['evidence_class'])
        del scenario['adjustments'][0]['replacement_evidence_class']
        r=self.run_data(d);self.assertNotEqual(r.returncode,0)
        self.assertIn('replacement_evidence_class',r.stderr)

    def test_missing_replacement_not_filled_with_zero(self):
        d=copy.deepcopy(self.data);del d['scenarios'][2]['adjustments'][0]['replacement_impacts']['energy']
        self.assertNotEqual(self.run_data(d).returncode,0)
    def test_baseline_zero_reports_null_percentage(self):
        d=copy.deepcopy(self.data);a=d['routes'][0]
        a['impact_categories']['climate']['total']=0
        for item in a['components']:item['impacts']['climate']=0
        r=self.run_data(d);self.assertEqual(r.returncode,0,r.stderr)
        self.assertIsNone(json.loads(r.stdout)['cases'][1]['results']['A']['climate']['change_percent'])
    def test_nan_and_invalid_json_do_not_traceback(self):
        d=copy.deepcopy(self.data);d['routes'][0]['components'][0]['impacts']['energy']=float('nan')
        r=self.run_data(d);self.assertNotEqual(r.returncode,0);self.assertNotIn('Traceback',r.stderr)
    def test_ties_and_single_variable_are_reported(self):
        d=copy.deepcopy(self.data);d['routes'][1]['impact_categories']['climate']['total']=3
        d['routes'][1]['components'][0]['impacts']['climate']=1
        r=self.run_data(d);self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(json.loads(r.stdout)['cases'][0]['rankings']['climate']['groups'],[['A','B']])
    def test_csv_is_not_allowed_to_overwrite_existing_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'report.csv';p.write_text('do not overwrite')
            r=self.run_data(self.data,('--csv',str(p)))
            self.assertNotEqual(r.returncode,0);self.assertEqual(p.read_text(),'do not overwrite')
    def test_alternative_grid_changes_both_routes(self):
        r=self.run_data(self.data);self.assertEqual(r.returncode,0,r.stderr)
        case=next(c for c in json.loads(r.stdout)['cases'] if c['id']=='alternative_grid')
        self.assertEqual(case['results']['A']['climate']['absolute'],2)
        self.assertEqual(case['results']['B']['climate']['absolute'],3)
    def test_generated_report_matches_committed_synthetic_example(self):
        r=self.run_data(self.data);self.assertEqual(r.returncode,0,r.stderr)
        expected=EXAMPLE.parent/'expected-report.json'
        self.assertEqual(json.loads(r.stdout),json.loads(expected.read_text(encoding='utf8')))
    def test_underflow_is_not_reported_as_zero(self):
        d=copy.deepcopy(self.data);d['scenarios'][0]['baseline']=1e308;d['scenarios'][0]['value']=1e-308
        self.assertNotEqual(self.run_data(d).returncode,0)
    def test_recovery_fraction_outside_range_rejected(self):
        d=copy.deepcopy(self.data);next(x for x in d['scenarios'] if x['id']=='A_recovery_change')['value']=1.1
        self.assertNotEqual(self.run_data(d).returncode,0)
    def test_csv_escapes_formula_and_exports_values(self):
        d=copy.deepcopy(self.data);d['routes'][0]['id']='=unsafe'
        for sc in d['scenarios']:
            for item in sc['adjustments']:
                if item['route']=='A':item['route']='=unsafe'
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'report.csv';r=self.run_data(d,('--csv',str(path)))
            self.assertEqual(r.returncode,0,r.stderr)
            import csv
            with path.open(encoding='utf8',newline='') as stream:
                rows=list(csv.DictReader(stream))
            self.assertTrue(any(x['route']=="'=unsafe" for x in rows))
            self.assertEqual(len(rows),len(d['routes'])*len(d['routes'][0]['impact_categories'])*(len(d['scenarios'])+1))

if __name__=='__main__':unittest.main()
