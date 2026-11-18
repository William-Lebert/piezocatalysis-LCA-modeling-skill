import copy,hashlib,json,subprocess,sys,tempfile,unittest,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];S=ROOT/'piezocatalysis-lca-modeling/scripts';sys.path[:0]=[str(S),str(ROOT/'tests')]
from inventory_handoff import load_handoff
from research_delivery import assemble,verify
from scenario_binding import digest
import test_scenario_binding

@unittest.skipUnless(importlib.util.find_spec('matplotlib'),'optional matplotlib not installed')
class AnalysisDeliveryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.d=Path(self.tmp.name);self.fg=ROOT/'piezocatalysis-lca-modeling/assets/examples/synthetic-cycles/constant.json';self.inv=self.d/'inventory.csv'
  self.run_cli(S/'cyclic_foreground.py',self.fg,'--inventory-csv',self.inv);self.man=Path(str(self.inv)+'.manifest.json');handoff=load_handoff(self.inv,self.man)
  t,a,b=test_scenario_binding.BindingTests().bound_pair();self.contexts=t.contexts
  for r in (a,b):
   r.update(foreground_sha256=hashlib.sha256(self.fg.read_bytes()).hexdigest(),inventory_sha256=handoff['inventory_sha256'],manifest_sha256=handoff['manifest_sha256'],mapping_sha256=None,assignments_sha256=None)
   r['plan'].update(inventory_sha256=handoff['inventory_sha256'],manifest_sha256=handoff['manifest_sha256'],mapping_sha256=None,assignments_sha256=None);r['plan_sha256']=digest(r['plan'])
  for name,obj in [('base.json',a),('alt.json',b),('contexts.json',self.contexts)]: (self.d/name).write_text(json.dumps(obj))
  self.run_cli(S/'scenario_binding.py','compare','--baseline',self.d/'base.json','--scenario',self.d/'alt.json','--baseline-input',self.fg,'--scenario-input',self.fg,'--contexts',self.d/'contexts.json','--output',self.d/'comparison.json')
  self.run_cli(S/'plot_data.py','--kind','scenarios','--report',self.d/'comparison.json','--baseline-input',self.fg,'--scenario-input',self.fg,'--category','category','--output',self.d/'scenario-plot.json','--license-note','fictional')
  self.run_cli(S/'plot_report.py',self.d/'scenario-plot.json','--output-dir',self.d/'scenario-chart','--locale','en','--dpi','72')
  d=json.loads((ROOT/'piezocatalysis-lca-modeling/assets/examples/synthetic-sensitivity/scenarios.json').read_text());fg=json.loads(self.fg.read_text())
  for r in d['routes']:r['scope']['system_boundary']=fg['boundary'];r['scope']['functional_unit']['amount']=fg['treatment_target']['value'];r['scope']['functional_unit']['unit']=fg['treatment_target']['unit']
  (self.d/'sensitivity-spec.json').write_text(json.dumps(d));p=subprocess.run([sys.executable,str(S/'sensitivity_report.py'),str(self.d/'sensitivity-spec.json')],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr);(self.d/'sensitivity-report.json').write_text(p.stdout)
  self.run_cli(S/'plot_data.py','--kind','sensitivity','--report',self.d/'sensitivity-report.json','--route','A','--category','climate','--output',self.d/'sensitivity-plot.json','--license-note','fictional additive approximation')
  self.run_cli(S/'plot_report.py',self.d/'sensitivity-plot.json','--output-dir',self.d/'sensitivity-chart','--locale','en','--dpi','72')
  names={'foreground':self.fg,'inventory':self.inv,'inventory_manifest':self.man,'scenario_baseline_bound':self.d/'base.json','scenario_bound':self.d/'alt.json','scenario_source':self.fg,'scenario_contexts':self.d/'contexts.json','scenario_comparison':self.d/'comparison.json','scenario_plot_data':self.d/'scenario-plot.json','scenario_plot_dir':self.d/'scenario-chart','sensitivity_spec':self.d/'sensitivity-spec.json','sensitivity_report':self.d/'sensitivity-report.json','sensitivity_plot_data':self.d/'sensitivity-plot.json','sensitivity_plot_dir':self.d/'sensitivity-chart'}
  self.spec={'schema_version':'piezolca.research-delivery/1','title':'fictional','license_note':'fictional','artifacts':{k:str(v) for k,v in names.items()}}
 def tearDown(self):self.tmp.cleanup()
 def run_cli(self,*args):
  p=subprocess.run([sys.executable,*map(str,args)],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr);return p.stdout
 def test_complete_replay_checks_and_method_discloses_approximation(self):
  out=self.d/'delivery';m=assemble(self.spec,self.d,out);self.assertEqual(m['status'],'review_required');self.assertEqual(verify(out)['status'],'hashes_match');text=(out/'methods.md').read_text();self.assertIn('不是 openLCA 重新计算',text);self.assertIn('不自动排名',text)
  replay=json.loads((out/'replay-spec.json').read_text());assemble(replay,out,self.d/'replay');self.assertEqual((out/'methods.md').read_bytes(),(self.d/'replay/methods.md').read_bytes());self.assertEqual((out/'artifacts/figure-scenarios/chart.svg').read_bytes(),(self.d/'replay/artifacts/figure-scenarios/chart.svg').read_bytes())
 def test_missing_or_changed_analysis_input_is_rejected(self):
  bad=copy.deepcopy(self.spec);bad['artifacts'].pop('scenario_bound')
  with self.assertRaisesRegex(ValueError,'incomplete'):assemble(bad,self.d,self.d/'missing')
  s=json.loads((self.d/'sensitivity-spec.json').read_text());s['routes'][0]['impact_categories']['climate']['total']+=1;(self.d/'sensitivity-spec.json').write_text(json.dumps(s))
  with self.assertRaises(ValueError):assemble(self.spec,self.d,self.d/'changed')
 def test_changed_bound_scenario_or_figure_is_rejected(self):
  path=self.d/'alt.json';obj=json.loads(path.read_text());obj['coverage']['calculation']['impacts'][0]['amount']+=1;path.write_text(json.dumps(obj))
  with self.assertRaises(ValueError):assemble(self.spec,self.d,self.d/'bad-scenario')
 def test_changed_sensitivity_figure_is_rejected(self):
  (self.d/'sensitivity-chart/chart.svg').write_text('altered')
  with self.assertRaisesRegex(ValueError,'plot output hash mismatch'):assemble(self.spec,self.d,self.d/'bad-figure')
