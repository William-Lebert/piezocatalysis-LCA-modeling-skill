import copy,csv,hashlib,json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];S=ROOT/'piezocatalysis-lca-modeling/scripts';sys.path.insert(0,str(S))
from evidence_chain import audit,read_json
from research_delivery import assemble,verify
from scenario_comparability import assess
EX=ROOT/'piezocatalysis-lca-modeling/assets/examples/synthetic-h2o2'

class H2O2DeliveryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.dir=Path(self.tmp.name);self.fg,self.fh=read_json(EX/'case.json');self.es,_=read_json(EX/'evidence.json')
  self.inv=self.dir/'inventory.csv';self.man=Path(str(self.inv)+'.manifest.json')
  p=subprocess.run([sys.executable,str(S/'h2o2_foreground.py'),str(EX/'case.json'),'--inventory-csv',str(self.inv)],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)
  self.ev=self.dir/'evidence.json';p=subprocess.run([sys.executable,str(S/'evidence_chain.py'),str(EX/'evidence.json'),'--foreground',str(EX/'case.json'),'--inventory',str(self.inv),'--manifest',str(self.man)],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr);self.ev.write_text(p.stdout)
  self.spec={'schema_version':'piezolca.research-delivery/1','title':'fictional','license_note':'synthetic','artifacts':{'foreground':str(EX/'case.json'),'inventory':str(self.inv),'inventory_manifest':str(self.man),'evidence_spec':str(EX/'evidence.json'),'evidence_report':str(self.ev)},'evidence_sources':{'synthetic-h2o2':str(EX/'observations.csv')}}
 def tearDown(self):self.tmp.cleanup()
 def test_evidence_allocation_and_delivery_replay(self):
  ev=json.loads(self.ev.read_text());self.assertEqual(ev['coverage']['linked_count'],10);self.assertEqual(ev['product_basis'],'net_accumulated');t={x['activity_id']:x for x in ev['inventory_traces']};self.assertEqual(t['ultrasound']['functional_unit_allocation_factor'],10000);self.assertEqual(t['precursor']['functional_unit_allocation_factor'],20);self.assertIn('/net_product_per_campaign',t['ultrasound']['allocation_input_pointers'])
  out=self.dir/'delivery';r=assemble(self.spec,self.dir,out);self.assertEqual(r['functional_unit_type'],'h2o2_product');self.assertEqual(r['product_basis'],'net_accumulated');self.assertEqual(r['status'],'review_required');self.assertEqual(verify(out)['status'],'hashes_match');methods=(out/'methods.md').read_text();self.assertIn('H₂O₂ 净积累',methods);self.assertNotIn('水相表观污染物去除',methods)
  replay=json.loads((out/'replay-spec.json').read_text());assemble(replay,out,self.dir/'replay');self.assertEqual((out/'methods.md').read_bytes(),(self.dir/'replay/methods.md').read_bytes())
 def test_product_definition_cannot_be_relabelled(self):
  m=json.loads(self.man.read_text());m['product_basis']='recovered_product';self.man.write_text(json.dumps(m))
  with self.assertRaisesRegex(ValueError,'product basis or definition'):audit(self.es,EX,self.fg,self.fh,self.inv,self.man)
  with self.assertRaisesRegex(ValueError,'product basis or definition'):assemble(self.spec,self.dir,self.dir/'bad')
 def test_evidence_report_product_basis_cannot_be_relabelled(self):
  ev=json.loads(self.ev.read_text());ev['product_basis']='recovered_product';self.ev.write_text(json.dumps(ev))
  with self.assertRaisesRegex(ValueError,'evidence product function differs'):assemble(self.spec,self.dir,self.dir/'bad')
 def test_recovered_product_delivery_keeps_its_own_basis(self):
  fg=copy.deepcopy(self.fg);fg['product_basis']='recovered_product';fg['product_definition']='fictional recovered product measurement';path=self.dir/'recovered.json';path.write_text(json.dumps(fg));inv=self.dir/'recovered.csv'
  p=subprocess.run([sys.executable,str(S/'h2o2_foreground.py'),str(path),'--inventory-csv',str(inv)],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)
  es=copy.deepcopy(self.es);es['foreground_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();es['sources'][0]['path']=str(EX/'observations.csv');ep=self.dir/'source-evidence.json';ep.write_text(json.dumps(es))
  p=subprocess.run([sys.executable,str(S/'evidence_chain.py'),str(ep),'--foreground',str(path),'--inventory',str(inv),'--manifest',str(inv)+'.manifest.json'],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr);ev=self.dir/'recovered-evidence.json';ev.write_text(p.stdout)
  spec=copy.deepcopy(self.spec);spec['artifacts'].update(foreground=str(path),inventory=str(inv),inventory_manifest=str(inv)+'.manifest.json',evidence_spec=str(ep),evidence_report=str(ev));out=self.dir/'recovered-delivery';r=assemble(spec,self.dir,out)
  self.assertEqual(r['product_basis'],'recovered_product');self.assertIn('H₂O₂ 回收产品',(out/'methods.md').read_text())
 def test_reported_production_preserved_from_evidence_through_delivery(self):
  foreground = copy.deepcopy(self.fg)
  foreground['product_basis'] = 'reported_production'
  foreground['product_definition'] = 'Fictional table reports production on a molar basis.'
  foreground['reported_product_per_campaign'] = foreground.pop('net_product_per_campaign')
  foreground_path = self.dir / 'literature.json'
  foreground_path.write_text(json.dumps(foreground))
  inventory = self.dir / 'literature.csv'
  manifest = Path(str(inventory) + '.manifest.json')
  subprocess.run([sys.executable, str(S/'h2o2_foreground.py'), str(foreground_path), '--inventory-csv', str(inventory)],
                 check=True, capture_output=True, text=True)
  evidence_spec = copy.deepcopy(self.es)
  evidence_spec['foreground_sha256'] = hashlib.sha256(foreground_path.read_bytes()).hexdigest()
  evidence_spec['sources'][0]['path'] = str(EX/'observations.csv')
  for link in evidence_spec['links']:
   if link['target'] == '/net_product_per_campaign':
    link['target'] = '/reported_product_per_campaign'
  evidence_path = self.dir / 'literature-spec.json'
  evidence_path.write_text(json.dumps(evidence_spec))
  result = subprocess.run([sys.executable, str(S/'evidence_chain.py'), str(evidence_path), '--foreground', str(foreground_path),
                           '--inventory', str(inventory), '--manifest', str(manifest)], check=True, capture_output=True, text=True)
  report_path = self.dir / 'literature-evidence.json'
  report_path.write_text(result.stdout)
  report = json.loads(result.stdout)
  self.assertIn('reported_h2o2_g', report['campaign'])
  self.assertNotIn('net_h2o2_g', report['campaign'])
  ultrasound = next(x for x in report['inventory_traces'] if x['activity_id'] == 'ultrasound')
  self.assertIn('/reported_product_per_campaign', ultrasound['allocation_input_pointers'])
  spec = copy.deepcopy(self.spec)
  spec['artifacts'].update(foreground=str(foreground_path), inventory=str(inventory), inventory_manifest=str(manifest),
                           evidence_spec=str(evidence_path), evidence_report=str(report_path))
  output = self.dir / 'literature-delivery'
  assembled = assemble(spec, self.dir, output)
  self.assertEqual(assembled['product_basis'], 'reported_production')
  self.assertIn('H₂O₂ 文献报告产量', (output/'methods.md').read_text())

 def test_changed_source_or_class_rejected_even_with_rehashed_manifest(self):
  for field,value in [('source','false source'),('evidence_class','measured')]:
   with self.subTest(field=field):
    original=self.inv.read_bytes();origman=self.man.read_bytes()
    with self.inv.open(newline='') as f:r=csv.DictReader(f);fields=r.fieldnames;rows=list(r)
    rows[0][field]=value
    with self.inv.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    m=json.loads(origman);m['inventory_sha256']=hashlib.sha256(self.inv.read_bytes()).hexdigest();self.man.write_text(json.dumps(m))
    with self.assertRaisesRegex(ValueError,'evidence class or source'):audit(self.es,EX,self.fg,self.fh,self.inv,self.man)
    with self.assertRaisesRegex(ValueError,'evidence class or source'):assemble(self.spec,self.dir,self.dir/'bad')
    self.inv.write_bytes(original);self.man.write_bytes(origman)
 def test_zero_product_cannot_be_attached_to_calculation(self):
  fg=copy.deepcopy(self.fg);fg['net_product_per_campaign']['value']=0;file=self.dir/'zero.json';file.write_text(json.dumps(fg));inv=self.dir/'zero.csv';p=subprocess.run([sys.executable,str(S/'h2o2_foreground.py'),str(file),'--inventory-csv',str(inv)],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)
  calc=self.dir/'calc.json';cov=self.dir/'coverage.json';calc.write_text('{}');cov.write_text('{}');spec={'schema_version':'piezolca.research-delivery/1','title':'fictional','license_note':'synthetic','artifacts':{'foreground':str(file),'inventory':str(inv),'inventory_manifest':str(inv)+'.manifest.json','calculation':str(calc),'coverage':str(cov)}}
  # Nonempty objects reach the product-specific gate.
  calc.write_text('{"synthetic":true}');cov.write_text('{"synthetic":true}')
  with self.assertRaisesRegex(ValueError,'product amount is unavailable'):assemble(spec,self.dir,self.dir/'zero-delivery')
 def test_missing_or_zero_product_preserves_unknown_inventory(self):
  from h2o2_foreground import build
  for value in (None,0):
   fg=copy.deepcopy(self.fg);fg['net_product_per_campaign']['value']=value;r=build(fg)
   with self.subTest(value=value):
    self.assertIsNone(r['campaign']['campaigns_per_functional_unit']);self.assertTrue(all(x['amount'] is None for x in r['functional_unit_flows']))
 def test_incompatible_product_bases_do_not_compare(self):
  base={'functional_unit':'1 kg H2O2','functional_unit_type':'h2o2_product','system_boundary':'synthetic','geography':'GLO','reference_period':'2026','database':'synthetic','database_version':'1','system_model':'cutoff','lcia_method_uuid':'48f3c24f-26d3-4a40-b537-cef6ad0a720a','lcia_method_version':'1','mapping_scope':'partial','allocation':'one','recycling_approach':'none','electricity_scenario':'one'}
  a=dict(base,id='a',product_basis='net_accumulated');b=dict(base,id='b',product_basis='recovered_product');r=assess({'cases':[a,b]});self.assertFalse(r['ranking_permitted_by_context_check'])
if __name__=='__main__':unittest.main()
