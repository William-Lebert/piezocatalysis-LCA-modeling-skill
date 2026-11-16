import copy,csv,hashlib,io,json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'piezocatalysis-lca-modeling/scripts'))
from evidence_chain import audit,read_json
from piezocatalysis_checks import audit as domain_audit
EX=ROOT/'piezocatalysis-lca-modeling/assets/examples/synthetic-evidence'
class EvidenceChainTests(unittest.TestCase):
 def setUp(self):
  self.spec,_=read_json(EX/'evidence.json');self.fg,self.fh=read_json(EX/'foreground.json');self.protocol,_=read_json(EX/'protocol.json');self.domain,_=read_json(EX/'domain.json')
 def test_full_links_unit_conversion_and_domain(self):
  r=audit(self.spec,EX,self.fg,self.fh);self.assertEqual(r['coverage']['linked_count'],27);self.assertEqual(r['coverage']['unlinked_count'],0)
  link=next(x for x in r['links'] if x['target']=='/cycles/0/activities/0/power');self.assertEqual(link['source_unit'],'kW');self.assertEqual(link['target_value_or_limit'],100);self.assertEqual(link['source_cell_text'],'0.1')
  trace=next(x for x in r['inventory_traces'] if x['activity_id']=='ultrasound-1');self.assertEqual(len(trace['direct_input_pointers']),2);self.assertIn('/treatment_target',trace['allocation_input_pointers']);self.assertEqual(trace['unlinked_input_pointers'],[]);self.assertAlmostEqual(trace['campaign_amount'],0.1);self.assertEqual(trace['functional_unit_allocation_factor'],5);self.assertAlmostEqual(trace['amount_per_functional_unit'],0.5);self.assertIn('power converted',trace['formula'])
  review=domain_audit(self.protocol,self.fg,self.fh,r,self.domain);self.assertTrue(all(x['status']=='matches' for x in review['domain_sample_checks']))
  self.assertEqual(review['status'],'needs_review');self.assertIn('disposal_mapping_missing',{x['status'] for x in review['issues']})
 def test_changed_raw_or_foreground_rejected(self):
  spec=copy.deepcopy(self.spec);spec['sources'][0]['sha256']='wrong'
  with self.assertRaisesRegex(ValueError,'raw source SHA-256'):audit(spec,EX,self.fg,self.fh)
  with self.assertRaisesRegex(ValueError,'foreground SHA-256'):audit(self.spec,EX,self.fg,'wrong')
 def test_changed_value_unit_basis_and_class_rejected(self):
  for kind in ('value','unit','basis','class'):
   with self.subTest(kind=kind):
    f=copy.deepcopy(self.fg);s=copy.deepcopy(self.spec);link=next(x for x in s['links'] if x['target']=='/cycles/0/activities/0/power');q=f['cycles'][0]['activities'][0]['power']
    if kind=='value':q['value']=101
    if kind=='unit':q['unit']='mg'
    if kind=='basis':link['basis']='cycle-2'
    if kind=='class':q['evidence_class']='measured'
    with self.assertRaises(ValueError):audit(s,EX,f,self.fh)
 def test_unlinked_not_treated_as_proven(self):
  s=copy.deepcopy(self.spec);s['links'].pop();r=audit(s,EX,self.fg,self.fh);self.assertEqual(r['coverage']['unlinked_count'],1);self.assertEqual(r['status'],'evidence_gaps')
 def test_reused_source_record_is_flagged(self):
  s=copy.deepcopy(self.spec)
  a=next(x for x in s['links'] if x['target']=='/cycles/0/influent_volume')
  b=next(x for x in s['links'] if x['target']=='/cycles/0/effluent_volume')
  b['record']=a['record'];b['basis']=a['basis']
  self.assertIn('source_record_reused_review_required',{x['status'] for x in audit(s,EX,self.fg,self.fh)['issues']})
 def test_equal_values_from_another_cycle_do_not_match_target_basis(self):
  s=copy.deepcopy(self.spec);a=next(x for x in s['links'] if x['target']=='/cycles/0/influent_concentration');b=next(x for x in s['links'] if x['target']=='/cycles/1/influent_concentration')
  a['record']=b['record'];a['basis']=b['basis']
  with self.assertRaisesRegex(ValueError,'cycle basis differs from target cycle'):audit(s,EX,self.fg,self.fh)
 def test_censored_limit_and_missing_never_imputed(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);s=copy.deepcopy(self.spec);f=copy.deepcopy(self.fg);target='/cycles/0/effluent_concentration';link=next(x for x in s['links'] if x['target']==target);q=f['cycles'][0]['effluent_concentration'];q.update(value=None,qualifier='below_loq',limit=3)
   rows=list(csv.DictReader(io.StringIO((EX/'synthetic-observations.csv').read_text())));row=rows[link['record']-1];row.update(value='',qualifier='below_loq',limit='3')
   buf=io.StringIO(newline='');w=csv.DictWriter(buf,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows);raw=buf.getvalue().encode();(p/'raw.csv').write_bytes(raw)
   s['sources'][0].update(path='raw.csv',sha256=hashlib.sha256(raw).hexdigest());r=audit(s,p,f,self.fh);item=next(x for x in r['links'] if x['target']==target)
   self.assertEqual(item['qualifier'],'below_loq');self.assertEqual(item['target_value_or_limit'],3);self.assertEqual(r['status'],'evidence_gaps')
   q['value']=0
   with self.assertRaisesRegex(ValueError,'censored value must be missing'):audit(s,p,f,self.fh)
 def test_domain_mismatch_energy_and_mineralization(self):
  r=audit(self.spec,EX,self.fg,self.fh);d=copy.deepcopy(self.domain);d['fields']['influent_concentration']['value']=99;p=copy.deepcopy(self.protocol);p['ultrasound']['energy_basis']='wall_metered';p['mineralization']={'claim':'claimed'};p['external_oxidant']={'status':'added','source':'synthetic','activity_ids':[]}
  review=domain_audit(p,self.fg,self.fh,r,d);statuses={i['status'] for i in review['issues']}
  self.assertTrue({'mismatch_or_unverified','metered_basis_not_supported_by_power_time_input','independent_measurement_and_source_missing','added_without_inventory_activity'}.issubset(statuses))
 def test_original_file_hash_and_declared_cell_are_distinguished(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);s=copy.deepcopy(self.spec);original=b'fictional original data';(p/'original.bin').write_bytes(original)
   s['originals']=[{'id':'notebook','path':'original.bin','sha256':hashlib.sha256(original).hexdigest()}]
   rows=list(csv.DictReader(io.StringIO((EX/'synthetic-observations.csv').read_text())))
   for row in rows:row.update(original_id='',original_locator='')
   rows[0].update(original_id='notebook',original_locator='sheet 1 cell B2')
   buf=io.StringIO(newline='');w=csv.DictWriter(buf,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows);raw=buf.getvalue().encode();(p/'raw.csv').write_bytes(raw)
   s['sources'][0].update(path='raw.csv',sha256=hashlib.sha256(raw).hexdigest())
   r=audit(s,p,self.fg,self.fh);self.assertEqual(r['links'][0]['original']['verification'],'file_hash_only_not_original_cell');self.assertEqual(r['status'],'evidence_gaps')
   (p/'original.bin').write_bytes(b'changed')
   with self.assertRaisesRegex(ValueError,'original source SHA-256'):audit(s,p,self.fg,self.fh)
 def test_inventory_rebuild_detects_tampering_even_with_updated_hash(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);inv=p/'inventory.csv';manifest=Path(str(inv)+'.manifest.json')
   run=subprocess.run([sys.executable,str(ROOT/'piezocatalysis-lca-modeling/scripts/cyclic_foreground.py'),str(EX/'foreground.json'),'--inventory-csv',str(inv)],capture_output=True,text=True)
   self.assertEqual(run.returncode,0,run.stderr)
   r=audit(self.spec,EX,self.fg,self.fh,inv,manifest);self.assertEqual(r['inventory_rebuilt_and_verified']['activity_count'],9)
   rows=list(csv.DictReader(io.StringIO(inv.read_text())));rows[0]['amount']='999'
   buf=io.StringIO(newline='');w=csv.DictWriter(buf,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows);raw=buf.getvalue().encode();inv.write_bytes(raw)
   m=json.loads(manifest.read_text());m['inventory_sha256']=hashlib.sha256(raw).hexdigest();manifest.write_text(json.dumps(m))
   with self.assertRaisesRegex(ValueError,'inventory differs'):audit(self.spec,EX,self.fg,self.fh,inv,manifest)
 def test_rehashed_inventory_evidence_class_or_source_cannot_change(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);inv=p/'inventory.csv';manifest=Path(str(inv)+'.manifest.json')
   run=subprocess.run([sys.executable,str(ROOT/'piezocatalysis-lca-modeling/scripts/cyclic_foreground.py'),str(EX/'foreground.json'),'--inventory-csv',str(inv)],capture_output=True,text=True);self.assertEqual(run.returncode,0,run.stderr)
   original=inv.read_bytes();original_manifest=manifest.read_bytes()
   for field,value in (('evidence_class','measured'),('source','fabricated lab record')):
    rows=list(csv.DictReader(io.StringIO(original.decode())));rows[0][field]=value
    buf=io.StringIO(newline='');w=csv.DictWriter(buf,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows);raw=buf.getvalue().encode();inv.write_bytes(raw)
    m=json.loads(original_manifest);m['inventory_sha256']=hashlib.sha256(raw).hexdigest();manifest.write_text(json.dumps(m))
    with self.subTest(field=field),self.assertRaisesRegex(ValueError,'evidence class or source differs'):audit(self.spec,EX,self.fg,self.fh,inv,manifest)
 def test_domain_service_pollutant_and_boundary_are_cross_checked(self):
  r=audit(self.spec,EX,self.fg,self.fh);d=copy.deepcopy(self.domain);d['fields']['pollutant_identity']['value']='different pollutant';d['fields']['system_boundary']['value']='different boundary';d['service']['functional_unit']['value']=999
  review=domain_audit(self.protocol,self.fg,self.fh,r,d);issues={(x['field'],x['status']) for x in review['issues']}
  self.assertTrue({('domain.pollutant_identity','declaration_mismatch'),('domain.system_boundary','foreground_mismatch'),('domain.functional_unit','mismatch_or_unverified')}.issubset(issues))
  d=copy.deepcopy(self.domain);d['service']['functional_unit']={'value':0.1,'unit':'g'};review=domain_audit(self.protocol,self.fg,self.fh,r,d)
  self.assertNotIn('domain.functional_unit',{x['field'] for x in review['issues']})
 def test_excluded_auxiliary_cannot_also_list_included_activity(self):
  r=audit(self.spec,EX,self.fg,self.fh);p=copy.deepcopy(self.protocol);p['auxiliary_energy']={'status':'excluded','source':'synthetic','reason':'excluded','activity_ids':['ultrasound-1']}
  self.assertIn('excluded_but_activities_listed',{x['status'] for x in domain_audit(p,self.fg,self.fh,r,self.domain)['issues']})
 def test_ph_illumination_and_cycle_energy_gaps(self):
  r=audit(self.spec,EX,self.fg,self.fh);p=copy.deepcopy(self.protocol)
  p['ph_adjustment']={'status':'added','source':'fictional','activity_ids':[]};p['illumination']={'mode':'illuminated','source':'fictional','activity_ids':[]};p['ultrasound']['activity_ids']=['ultrasound-1']
  issues=domain_audit(p,self.fg,self.fh,r,self.domain)['issues'];statuses={i['status'] for i in issues}
  self.assertTrue({'added_without_inventory_activity','energy_activity_not_declared','no_listed_ultrasound_activity_review_required'}.issubset(statuses))
 def test_evidence_report_foreground_mismatch_and_auxiliary_overlap(self):
  r=audit(self.spec,EX,self.fg,self.fh);r['foreground_sha256']='bad'
  with self.assertRaisesRegex(ValueError,'does not match foreground'):domain_audit(self.protocol,self.fg,self.fh,r,self.domain)
  r['foreground_sha256']=self.fh;p=copy.deepcopy(self.protocol);p['auxiliary_energy']={'status':'included_in_total','source':'fixture','activity_ids':['ultrasound-1']}
  statuses={x['status'] for x in domain_audit(p,self.fg,self.fh,r,self.domain)['issues']};self.assertIn('potential_double_counting',statuses)
if __name__=='__main__':unittest.main()
