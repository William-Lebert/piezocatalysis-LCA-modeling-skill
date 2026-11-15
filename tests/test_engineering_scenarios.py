import copy,hashlib,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'piezocatalysis-lca-modeling/scripts'))
from engineering_scenarios import build_report
EX=ROOT/'piezocatalysis-lca-modeling/assets/examples/synthetic-engineering'
class EngineeringScenariosTests(unittest.TestCase):
 def setUp(self):self.spec=json.loads((EX/'spec.json').read_text())
 def test_independent_scale_and_activity_changes(self):
  out=build_report(self.spec,EX); cases={c['id']:c for c in out['scenarios']}
  self.assertTrue(cases['higher-power']['parameters'][0]['outside_measured_range'])
  self.assertFalse(cases['scale-study']['parameters'][0]['bound_to_input'])
  self.assertTrue(cases['grid-study']['electricity_grid_changed'])
  self.assertTrue(any(x['activity_id']=='oxidant-2' and x['baseline'] is None and x['delta'] is None for x in cases['add-oxidant']['inventory_comparison']))
  self.assertEqual(cases['longer-life']['campaign']['cycle_count'],3)
  self.assertAlmostEqual(cases['longer-life']['campaign']['campaigns_per_functional_unit'],100/30)
  changed=lambda case,activity: next(r for r in cases[case]['inventory_comparison'] if r['activity_id']==activity)
  self.assertAlmostEqual(changed('longer-time','ultrasound-2')['delta'],0.25)
  self.assertAlmostEqual(changed('more-washing','clean-water-2')['delta'],1.0)
  self.assertAlmostEqual(changed('add-oxidant','oxidant-2')['scenario'],0.5)
  self.assertTrue(all(not c['ranking_permitted'] and c['actual_openlca_comparison'] is None for c in cases.values()))
 def test_parameter_must_match_input_and_units(self):
  self.spec['scenarios'][0]['parameters'][0]['value']=151
  with self.assertRaisesRegex(ValueError,'differs from input'):build_report(self.spec,EX)
  self.spec=json.loads((EX/'spec.json').read_text());self.spec['scenarios'][0]['parameters'][0]['measured_range']['unit']='kW'
  with self.assertRaisesRegex(ValueError,'range or unit'):build_report(self.spec,EX)
 def test_incompatible_functional_unit_disables_delta(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);baseline=json.loads((EX/'baseline.json').read_text());other=copy.deepcopy(baseline);other['treatment_target']['value']=200
   (p/'a.json').write_text(json.dumps(baseline));(p/'b.json').write_text(json.dumps(other))
   s={'schema_version':'piezolca.engineering-scenarios/1','baseline_input':'a.json','background_electricity':self.spec['background_electricity'],'scenarios':[{'id':'s','label':'s','input':'b.json','parameters':[]}]}
   case=build_report(s,p)['scenarios'][0];self.assertFalse(case['functional_unit_and_boundary_match']);self.assertTrue(all(row['delta'] is None for row in case['inventory_comparison']))
 def test_reject_inconsistent_impact_delta(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);baseline=EX/'baseline.json';scenario=EX/'higher-power.json';fake=p/'comparison.json'
   hashes={'baseline-input':hashlib.sha256(baseline.read_bytes()).hexdigest(),'scenario-input':hashlib.sha256(scenario.read_bytes()).hexdigest()}
   fake.write_text(json.dumps({'schema_version':'piezolca.cycle-scenario-comparison/1','input_sha256':hashes,'context_check':{'status':'declared_contexts_match'},'impacts':[{'category':{'@id':'a','name':'A','refUnit':'kg'},'baseline':1,'amount':2,'delta':99,'unit':'kg'}]}))
   self.spec['baseline_input']=str(baseline);self.spec['scenarios']=self.spec['scenarios'][:1];self.spec['scenarios'][0]['input']=str(scenario);self.spec['scenarios'][0]['comparison']=str(fake)
   with self.assertRaisesRegex(ValueError,'delta mismatch'):build_report(self.spec,p)
 def test_reject_unrelated_actual_results(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);fake=p/'wrong.json';fake.write_text(json.dumps({'schema_version':'piezolca.cycle-scenario-comparison/1','input_sha256':{'baseline-input':'fake','scenario-input':'fake'}}))
   self.spec['baseline_input']=str(EX/'baseline.json');self.spec['scenarios']=self.spec['scenarios'][:1];self.spec['scenarios'][0]['input']=str(EX/'higher-power.json');self.spec['scenarios'][0]['comparison']=str(fake)
   with self.assertRaisesRegex(ValueError,'do not match'):build_report(self.spec,p)
if __name__=='__main__':unittest.main()
