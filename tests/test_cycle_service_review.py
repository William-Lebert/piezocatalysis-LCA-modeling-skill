import copy,csv,hashlib,io,json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];S=ROOT/'piezocatalysis-lca-modeling/scripts';sys.path.insert(0,str(S))
from evidence_chain import audit,read_json
from cycle_service_review import review
from research_delivery import assemble,verify
EX=ROOT/'piezocatalysis-lca-modeling/assets/examples/synthetic-cycle-service';FG=EX.parent/'synthetic-evidence/foreground.json'
class CycleServiceTests(unittest.TestCase):
 def setUp(self):
  self.fg,self.fh=read_json(FG);self.es,_=read_json(EX/'evidence.json');self.spec,_=read_json(EX/'service.json');self.ev=audit(self.es,EX,self.fg,self.fh)
 def test_sample_links_and_exact_threshold(self):
  r=review(self.spec,self.fg,self.fh,self.ev);self.assertEqual([x['criterion_status'] for x in r['cycles']],['meets_declared_criterion']*2);self.assertTrue(all(x['sample_links_complete_user_asserted'] for x in r['cycles']));self.assertEqual(r['observed_cycle_count'],2);self.assertFalse(r['ranking_permitted']);self.assertEqual(r['status'],'review_required')
 def test_equal_values_wrong_sample_or_cycle_rejected(self):
  for key,value in [('cycle_id','2'),('sample_id','wrong'),('sample_role','effluent')]:
   s=copy.deepcopy(self.es);link=next(x for x in s['links'] if x['target']=='/cycles/0/influent_concentration');link['sample'][key]=value
   with self.subTest(key=key),self.assertRaisesRegex(ValueError,'sample'):audit(s,EX,self.fg,self.fh)
 def test_missing_sample_declaration_stays_review_required(self):
  ev=copy.deepcopy(self.ev);ev['links'][0].pop('sample_user_asserted',None)
  entry=next(x for x in ev['links'] if x['target']=='/cycles/0/influent_concentration');entry.pop('sample_user_asserted')
  r=review(self.spec,self.fg,self.fh,ev);self.assertFalse(r['cycles'][0]['sample_links_complete_user_asserted']);self.assertFalse(r['ranking_permitted'])
 def test_inconsistent_sample_pair_does_not_claim_a_complete_link(self):
  ev=copy.deepcopy(self.ev);entry=next(x for x in ev['links'] if x['target']=='/cycles/0/influent_concentration');entry['sample_user_asserted']['sample_id']='different-sample'
  r=review(self.spec,self.fg,self.fh,ev);self.assertFalse(r['cycles'][0]['sample_links_complete_user_asserted']);self.assertIn('volume and concentration sample IDs differ',r['cycles'][0]['sample_issues'][0])
 def test_threshold_missing_censored_and_volume_changes(self):
  for kind,expected in [('above','does_not_meet_declared_criterion'),('missing','not_evaluated'),('below_ok','meets_declared_criterion'),('below_uncertain','not_evaluated')]:
   fg=copy.deepcopy(self.fg);q=fg['cycles'][0]['effluent_concentration']
   if kind=='above':q['value']=11
   if kind=='missing':q.update(value=None,qualifier='missing')
   if kind=='below_ok':q.update(value=None,qualifier='below_loq',limit=9)
   if kind=='below_uncertain':q.update(value=None,qualifier='below_loq',limit=11)
   fg['cycles'][0]['effluent_volume']['value']=0.8
   with self.subTest(kind=kind):
    r=review(self.spec,fg,self.fh,self.ev);self.assertEqual(r['cycles'][0]['criterion_status'],expected);self.assertIn('sampling_or_volume_change_requires_review',{x['status'] for x in r['issues']})
 def test_removal_service_and_assumed_lifetime_are_distinct(self):
  s=copy.deepcopy(self.spec);s['service'].update(kind='apparent_pollutant_removal',criterion={'value':10,'unit':'mg','source':'fictional','evidence_class':'scenario'});s['lifetime'].update(kind='assumed',cycles=100)
  r=review(s,self.fg,self.fh,self.ev);self.assertEqual(r['cycles'][0]['criterion_status'],'meets_declared_criterion');self.assertEqual(r['observed_cycle_count'],2);self.assertIn('not_observed_lifetime_requires_review',{i['status'] for i in r['issues']})
 def test_catalyst_loss_is_reported_without_assuming_destination(self):
  fg=copy.deepcopy(self.fg);fg['cycles'][0]['catalyst_recovered']['value']=0.8;fg['cycles'][1]['catalyst_added']['value']=0.2
  r=review(self.spec,fg,self.fh,self.ev);self.assertAlmostEqual(r['cycles'][0]['catalyst_unaccounted_g'],0.2);self.assertIn('unknown_or_unaccounted',{i['status'] for i in r['issues']})
 def test_delivery_rechecks_sample_and_service_files(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp);inv=d/'inventory.csv';p=subprocess.run([sys.executable,str(S/'cyclic_foreground.py'),str(FG),'--inventory-csv',str(inv)],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)
   ev=d/'evidence.json';p=subprocess.run([sys.executable,str(S/'evidence_chain.py'),str(EX/'evidence.json'),'--foreground',str(FG),'--inventory',str(inv),'--manifest',str(inv)+'.manifest.json'],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr);ev.write_text(p.stdout)
   sr=d/'service.json';p=subprocess.run([sys.executable,str(S/'cycle_service_review.py'),str(EX/'service.json'),'--foreground',str(FG),'--evidence',str(ev)],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr);sr.write_text(p.stdout)
   spec={'schema_version':'piezolca.research-delivery/1','title':'fictional','license_note':'fictional','artifacts':{'foreground':str(FG),'inventory':str(inv),'inventory_manifest':str(inv)+'.manifest.json','evidence_spec':str(EX/'evidence.json'),'evidence_report':str(ev),'cycle_service_spec':str(EX/'service.json'),'cycle_service_report':str(sr)},'evidence_sources':{'synthetic-lab':str(EX/'observations.csv')}}
   out=d/'delivery';r=assemble(spec,d,out);self.assertEqual(r['status'],'review_required');self.assertEqual(verify(out)['status'],'hashes_match');self.assertIn('不自动转换为处理水量功能单位',(out/'methods.md').read_text());replay=json.loads((out/'replay-spec.json').read_text());assemble(replay,out,d/'replay')
   bad=json.loads(sr.read_text());bad['cycles'][0]['criterion_status']='does_not_meet_declared_criterion';sr.write_text(json.dumps(bad))
   with self.assertRaisesRegex(ValueError,'differs from rebuilt'):assemble(spec,d,d/'bad')
if __name__=='__main__':unittest.main()
