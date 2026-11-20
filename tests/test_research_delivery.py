import copy,csv,hashlib,importlib.util,json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SCRIPTS=ROOT/'piezocatalysis-lca-modeling/scripts';sys.path.insert(0,str(SCRIPTS))
from research_delivery import assemble,verify,candidate_matches_plan
from result_coverage import contribution_summary
from inventory_handoff import load_handoff
class DeliveryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.dir=Path(self.tmp.name);self.fg=ROOT/'piezocatalysis-lca-modeling/assets/examples/synthetic-evidence/foreground.json';self.inv=self.dir/'inventory.csv';self.man=Path(str(self.inv)+'.manifest.json')
  proc=subprocess.run([sys.executable,str(SCRIPTS/'cyclic_foreground.py'),str(self.fg),'--inventory-csv',str(self.inv)],capture_output=True,text=True);self.assertEqual(proc.returncode,0,proc.stderr)
  self.spec={'schema_version':'piezolca.research-delivery/1','title':'Synthetic test','license_note':'fictional only','artifacts':{'foreground':str(self.fg),'inventory':str(self.inv),'inventory_manifest':str(self.man)},'evidence_sources':{}}
 def tearDown(self):self.tmp.cleanup()
 def test_partial_delivery_explicit_gaps_and_replay(self):
  out=self.dir/'bundle';r=assemble(self.spec,self.dir,out);self.assertEqual(r['status'],'review_required');self.assertTrue(any('not supplied' in x for x in r['warnings']));self.assertEqual(verify(out)['status'],'hashes_match')
  replay=json.loads((out/'replay-spec.json').read_text());r2=assemble(replay,out,self.dir/'replayed');self.assertEqual(r2['warnings'],r['warnings'])
  self.assertIn('不会重新运行 openLCA',(out/'README.md').read_text());self.assertIn('100 mg 水相表观污染物去除',(out/'methods.md').read_text())
 def test_tampered_bundle_is_detected(self):
  out=self.dir/'bundle';assemble(self.spec,self.dir,out);(out/'methods.md').write_text('modified')
  with self.assertRaisesRegex(ValueError,'changed'):verify(out)
 def test_empty_manifest_does_not_pass_verification(self):
  out=self.dir/'bundle';assemble(self.spec,self.dir,out);p=out/'delivery-manifest.json';m=json.loads(p.read_text());m['files']=[];p.write_text(json.dumps(m))
  with self.assertRaisesRegex(ValueError,'missing or duplicate artifact roles'):verify(out)
 def test_manifest_path_traversal_rejected(self):
  out=self.dir/'bundle';assemble(self.spec,self.dir,out);p=out/'delivery-manifest.json';m=json.loads(p.read_text());m['files'][0]['path']='../escape';p.write_text(json.dumps(m))
  with self.assertRaisesRegex(ValueError,'invalid or duplicate'):verify(out)
 def test_bad_inventory_and_mismatched_foreground_fail(self):
  self.inv.write_text(self.inv.read_text()+'changed')
  with self.assertRaisesRegex(ValueError,'inventory does not match'):assemble(self.spec,self.dir,self.dir/'bundle')
  self.assertFalse((self.dir/'bundle').exists())
 def test_rehashed_inventory_cannot_relabel_evidence_or_source(self):
  for field,value in (('evidence_class','measured'),('source','fabricated lab record')):
   with self.subTest(field=field):
    raw=self.inv.read_bytes();manifest=self.man.read_bytes()
    with self.inv.open(newline='') as f:
     reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
    rows[0][field]=value
    with self.inv.open('w',newline='') as f:
     writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    m=json.loads(manifest);m['inventory_sha256']=hashlib.sha256(self.inv.read_bytes()).hexdigest();self.man.write_text(json.dumps(m))
    with self.assertRaisesRegex(ValueError,'evidence class or source differs'):assemble(self.spec,self.dir,self.dir/('bad-'+field))
    self.inv.write_bytes(raw);self.man.write_bytes(manifest)
 def test_source_outer_whitespace_matches_csv_normalization(self):
  fg=json.loads(self.fg.read_text());fg['preparation_activities'][0]['quantity']['source']='  synthetic scenario  '
  foreground=self.dir/'foreground-spaced.json';foreground.write_text(json.dumps(fg));inv=self.dir/'spaced.csv'
  p=subprocess.run([sys.executable,str(SCRIPTS/'cyclic_foreground.py'),str(foreground),'--inventory-csv',str(inv)],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)
  spec=copy.deepcopy(self.spec);spec['artifacts'].update(foreground=str(foreground),inventory=str(inv),inventory_manifest=str(inv)+'.manifest.json')
  self.assertEqual(assemble(spec,self.dir,self.dir/'spaced-bundle')['status'],'review_required')
 def test_disposal_manifest_cannot_lend_evidence_to_legacy_foreground(self):
  manifest=json.loads(self.man.read_text())
  manifest['campaign']['final_recovered_fate']={'route':'invented','source':'invented','evidence_class':'scenario'}
  self.man.write_text(json.dumps(manifest))
  with self.assertRaisesRegex(ValueError,'disposal evidence'):
   assemble(self.spec,self.dir,self.dir/'bundle')
  self.assertFalse((self.dir/'bundle').exists())
 def test_incomplete_pairs_fail(self):
  for role in ('mapping','evidence_spec','domain_report','coverage','plot_data','cycle_plot_data','candidate_review'):
   with self.subTest(role=role):
    spec=copy.deepcopy(self.spec);spec['artifacts'][role]=str(self.fg)
    with self.assertRaises(ValueError):assemble(spec,self.dir,self.dir/('out-'+role))
 def test_real_evidence_and_domain_report_are_rebuilt(self):
  ex=ROOT/'piezocatalysis-lca-modeling/assets/examples/synthetic-evidence';ev=self.dir/'evidence.json';dr=self.dir/'domain-report.json'
  run=subprocess.run([sys.executable,str(SCRIPTS/'evidence_chain.py'),str(ex/'evidence.json'),'--foreground',str(self.fg),'--inventory',str(self.inv),'--manifest',str(self.man)],capture_output=True,text=True);self.assertEqual(run.returncode,0,run.stderr);ev.write_text(run.stdout)
  run=subprocess.run([sys.executable,str(SCRIPTS/'piezocatalysis_checks.py'),str(ex/'protocol.json'),'--foreground',str(self.fg),'--evidence',str(ev),'--domain',str(ex/'domain.json')],capture_output=True,text=True);self.assertEqual(run.returncode,0,run.stderr);dr.write_text(run.stdout)
  self.spec['artifacts'].update(evidence_spec=str(ex/'evidence.json'),evidence_report=str(ev),domain_protocol=str(ex/'protocol.json'),domain_input=str(ex/'domain.json'),domain_report=str(dr))
  self.spec['evidence_sources']={'synthetic-lab':str(ex/'synthetic-observations.csv')}
  out=self.dir/'linked';r=assemble(self.spec,self.dir,out);self.assertTrue(any('rebuilt from supplied CSV' in c for c in r['checks']));self.assertTrue(any('ph_adjustment' in w for w in r['warnings']))
  self.assertEqual(verify(out)['verified_files'],len(r['files']))
  manifest=out/'delivery-manifest.json'
  for role in ('evidence_report','evidence_source:synthetic-lab'):
   with self.subTest(omitted=role):
    missing=dict(r,files=[item for item in r['files'] if item['role']!=role])
    manifest.write_text(json.dumps(missing),encoding='utf-8')
    with self.assertRaisesRegex(ValueError,role):verify(out)
  bad=json.loads(dr.read_text());bad['issues']=[];dr.write_text(json.dumps(bad))
  with self.assertRaisesRegex(ValueError,'domain report differs'):assemble(self.spec,self.dir,self.dir/'bad')
 def test_evidence_source_hash_mismatch_fails(self):
  ex=ROOT/'piezocatalysis-lca-modeling/assets/examples/synthetic-evidence';ev=self.dir/'evidence.json'
  run=subprocess.run([sys.executable,str(SCRIPTS/'evidence_chain.py'),str(ex/'evidence.json'),'--foreground',str(self.fg),'--inventory',str(self.inv),'--manifest',str(self.man)],capture_output=True,text=True);self.assertEqual(run.returncode,0,run.stderr);ev.write_text(run.stdout)
  bad=self.dir/'raw.csv';bad.write_text('different');self.spec['artifacts'].update(evidence_spec=str(ex/'evidence.json'),evidence_report=str(ev));self.spec['evidence_sources']={'synthetic-lab':str(bad)}
  with self.assertRaisesRegex(ValueError,'source hash mismatch'):assemble(self.spec,self.dir,self.dir/'bad')
 def test_calculation_cannot_silently_use_two_functional_units(self):
  calc={'setup':{'amount':2},'impacts':[{'category':{'@id':'c','name':'fictional','refUnit':'kg'},'amount':2}]}
  coverage={'schema_version':'piezolca.result-coverage/1','calculation':calc};(self.dir/'calc.json').write_text(json.dumps(calc));(self.dir/'coverage.json').write_text(json.dumps(coverage))
  self.spec['artifacts'].update(calculation=str(self.dir/'calc.json'),coverage=str(self.dir/'coverage.json'))
  with self.assertRaisesRegex(ValueError,'exactly one'):assemble(self.spec,self.dir,self.dir/'bundle')
 def test_selected_candidate_reference_must_match_plan_details(self):
  candidate={'process_uuid':'p','name':'process','process_version':'1','process_type':'LCI_RESULT','geography':'CN','reference_flow_uuid':'f','reference_product':'product','flow_property_uuid':'prop','unit_uuid':'u','reference_is_input':False,'dataset_unit':'kg'}
  plan={k:v for k,v in candidate.items() if k!='dataset_unit'};plan['unit_name']='kg'
  self.assertTrue(candidate_matches_plan(candidate,plan));plan['geography']='GLO';self.assertFalse(candidate_matches_plan(candidate,plan));plan['geography']='CN';plan['unit_name']='g';self.assertFalse(candidate_matches_plan(candidate,plan))
 def test_model_plan_cannot_change_mapping_without_changing_inputs(self):
  h=load_handoff(self.inv,self.man);rows=[]
  for x in h['rows']:
   rows.append({'activity_id':x['activity_id'],'flow_name':x['flow_name'],'unit':x['unit'],'direction':x['direction'],'amount_per_functional_unit':x['amount_per_functional_unit'],'mapping_id':x['mapping_id'],'mapping_type':x['mapping_type'],'mapping_user_asserted':x['mapping_user_asserted'],'status':'unresolved','issues':x['issues']})
  plan={'schema_version':'piezolca.cycle-model-plan/1','inventory_sha256':h['inventory_sha256'],'manifest_sha256':h['manifest_sha256'],'mapping_sha256':None,'assignments_sha256':None,'rows':rows,'summary':{'unresolved_rows':len(rows)}}
  plan['rows'][0]['mapping_type']='exact';path=self.dir/'plan.json';path.write_text(json.dumps(plan));self.spec['artifacts']['model_plan']=str(path)
  with self.assertRaisesRegex(ValueError,'mapping differs from handoff'):assemble(self.spec,self.dir,self.dir/'bundle')
 def test_calculation_and_coverage_from_different_runs_rejected(self):
  calc={'setup':{'amount':1},'impacts':[{'category':{'@id':'c','name':'fictional','refUnit':'kg'},'amount':2}],'warnings':[]}
  other=copy.deepcopy(calc);other['impacts'][0]['amount']=3
  coverage={'schema_version':'piezolca.result-coverage/1','calculation':other};(self.dir/'calc.json').write_text(json.dumps(calc));(self.dir/'coverage.json').write_text(json.dumps(coverage))
  self.spec['artifacts'].update(calculation=str(self.dir/'calc.json'),coverage=str(self.dir/'coverage.json'))
  with self.assertRaisesRegex(ValueError,'does not contain the supplied calculation'):assemble(self.spec,self.dir,self.dir/'bundle')
 @unittest.skipUnless(importlib.util.find_spec('matplotlib'),'optional matplotlib not installed')
 def test_cycle_figure_is_rebuilt_and_tampering_is_rejected(self):
  data=self.dir/'cycle-plot.json';fig=self.dir/'figure'
  p=subprocess.run([sys.executable,str(SCRIPTS/'plot_data.py'),'--kind','cycles','--report',str(self.fg),'--output',str(data),'--license-note','fictional'],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)
  p=subprocess.run([sys.executable,str(SCRIPTS/'plot_report.py'),str(data),'--output-dir',str(fig),'--locale','en','--dpi','72'],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)
  out=self.dir/'with-cycle'
  self.spec['artifacts'].update(cycle_plot_data=str(data),cycle_plot_dir=str(fig));r=assemble(self.spec,self.dir,out)
  self.assertTrue(any('Cyclic plot data recomputed' in x for x in r['checks']))
  self.assertEqual(verify(out)['verified_files'],len(r['files']))
  role='figure-cycles_chart.png'
  missing=dict(r,files=[item for item in r['files'] if item['role']!=role])
  (out/'delivery-manifest.json').write_text(json.dumps(missing),encoding='utf-8')
  with self.assertRaisesRegex(ValueError,role):verify(out)
  (fig/'chart.svg').write_text('changed')
  with self.assertRaisesRegex(ValueError,'plot output hash mismatch'):assemble(self.spec,self.dir,self.dir/'broken')
 def test_coverage_category_cannot_be_relabelled(self):
  category={'@id':'c','name':'fictional','refUnit':'kg'};impact={'category':category,'amount':2,'contributions':[]}
  calc={'setup':{'amount':1,'target':{'@id':'sys'},'impactMethod':{'@id':'method'}},'target':{'@id':'sys'},'impact_method':{'@id':'method'},'functional_unit_user_asserted':'synthetic','impacts':[impact]}
  coverage={'schema_version':'piezolca.result-coverage/1','calculation':calc,'selected_category':dict(category,name='different'),'hotspots':contribution_summary(impact)}
  (self.dir/'calc.json').write_text(json.dumps(calc));(self.dir/'coverage.json').write_text(json.dumps(coverage));self.spec['artifacts'].update(calculation=str(self.dir/'calc.json'),coverage=str(self.dir/'coverage.json'))
  with self.assertRaisesRegex(ValueError,'category or contributions differ'):assemble(self.spec,self.dir,self.dir/'bundle')
 def test_lcia_csv_formula_escaping_and_unbound_warning(self):
  category={'@id':'c','name':'=fictional','refUnit':'kg'};impact={'category':category,'amount':2,'contributions':[]}
  calc={'setup':{'amount':1,'target':{'@id':'sys'},'impactMethod':{'@id':'method'}},'target':{'@id':'sys'},'impact_method':{'@id':'method'},'functional_unit_user_asserted':'synthetic service','impacts':[impact],'warnings':[]}
  coverage={'schema_version':'piezolca.result-coverage/1','calculation':calc,'selected_category':category,'hotspots':contribution_summary(impact)};(self.dir/'calc.json').write_text(json.dumps(calc));(self.dir/'coverage.json').write_text(json.dumps(coverage))
  self.spec['artifacts'].update(calculation=str(self.dir/'calc.json'),coverage=str(self.dir/'coverage.json'));out=self.dir/'bundle';r=assemble(self.spec,self.dir,out)
  with (out/'lcia-results.csv').open(encoding='utf-8-sig',newline='') as f:row=next(csv.DictReader(f))
  self.assertEqual(row['category_name'],"'=fictional");self.assertEqual(row['functional_unit_user_asserted'],'synthetic service');self.assertTrue(any('not been independently checked' in x for x in r['warnings']))
if __name__=='__main__':unittest.main()
