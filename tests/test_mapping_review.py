import copy,csv,io,json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'piezocatalysis-lca-modeling/scripts'))
from mapping_review import collect,decision_rows,finalize,MAPPING_FIELDS,write_csv
from inventory_handoff import load_handoff
A='11111111-1111-4111-8111-111111111111';B='22222222-2222-4222-8222-222222222222';C='33333333-3333-4333-8333-333333333333'
class FakeClient:
 def __init__(self):self.calls=[]
 def call(self,method,p):
  self.calls.append((method,p))
  ds=[{'@id':A,'name':'fictional electricity','location':'CN'},{'@id':B,'name':'fictional electricity','location':'GLO'}]
  if method=='data/get/descriptors':return ds
  if method=='data/get':
   uid=p['@id'];geo='CN' if uid==A else 'GLO'
   return {'@type':'Process','@id':uid,'name':'fictional electricity','location':{'name':geo},'processType':'LCI_RESULT','version':'1',
           'exchanges':[{'isQuantitativeReference':True,'isInput':False,'flow':{'@id':C,'name':'electricity'},'flowProperty':{'@id':A},'unit':{'@id':B,'name':'kWh'}}]}
  raise AssertionError(method)

def handoff():
 return {'schema_version':'piezolca.handoff/1','inventory_sha256':'inv','manifest_sha256':'man','amount_basis':'per_functional_unit',
  'rows':[{'activity_id':'power','flow_name':'ultrasound electricity','unit':'kWh','included':True,'direction':'input','amount_per_functional_unit':1},
          {'activity_id':'waste','flow_name':'waste','unit':'kg','included':True,'direction':'output','amount_per_functional_unit':None}]}
def context():return {'database':'fictional','database_version':'1','system_model':'synthetic'}
def decisions(report):
 ds=list(decision_rows(report));ds[0].update(decision='selected',match_type='proxy',rationale='fictional proxy',expected_bias='unknown',geography_rationale='fictional CN',technology_rationale='fictional technology',reviewer='synthetic reviewer',review_date='2026-01-01')
 if len(ds)>1:ds[1].update(decision='rejected',rationale='fictional alternative',reviewer='synthetic reviewer',review_date='2026-01-01')
 return ds
class MappingReviewTests(unittest.TestCase):
 def setUp(self):
  self.h=handoff();self.q={'queries':[{'activity_id':'power','name_contains':'fictional electricity'}]};self.c=FakeClient();self.report=collect(self.h,self.q,self.c,context())
 def test_collect_and_explicit_pending_handoff(self):
  r=self.report;self.assertEqual(r['rows'][0]['matched_count'],2);self.assertEqual(r['unqueried_activity_ids'],['waste'])
  self.assertEqual(r['rows'][0]['candidates'][0]['actual_reference']['reference_product'],'electricity')
  out,mapping,assignments=finalize(r,decisions(r),self.h,'dec','review');self.assertEqual(out['selected_count'],1);self.assertEqual(out['activities_without_selection'],['waste'])
  self.assertEqual(mapping[0]['review_status'],'pending');self.assertEqual(mapping[0]['match_type'],'proxy');self.assertEqual(assignments[0]['activity_id'],'power');self.assertIn('GLO',mapping[0]['alternative_dataset']);self.assertIn('(rejected)',mapping[0]['alternative_dataset'])
 def test_existing_mapping_id_is_preserved_and_shared_ids_do_not_spill(self):
  h=handoff();h['rows'][0]['mapping_id']='existing-map';r=collect(h,self.q,FakeClient(),context())
  _,maps,assignments=finalize(r,decisions(r),h,'d','r');self.assertEqual(maps[0]['mapping_id'],'existing-map');self.assertEqual(assignments[0]['mapping_id'],'existing-map')
  h['rows'][1]['mapping_id']='existing-map';r=collect(h,self.q,FakeClient(),context())
  with self.assertRaisesRegex(ValueError,'shared or conflicts'):finalize(r,decisions(r),h,'d','r')
  h=handoff();h['rows'][1]['mapping_id']='review-power';r=collect(h,self.q,FakeClient(),context())
  with self.assertRaisesRegex(ValueError,'shared or conflicts'):finalize(r,decisions(r),h,'d','r')
 def test_existing_inventory_mapping_id_roundtrips(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);data=json.loads((ROOT/'piezocatalysis-lca-modeling/assets/examples/synthetic-cycles/constant.json').read_text())
   data['cycles'][0]['activities'][0]['dataset_mapping']='existing-map';source=p/'source.json';source.write_text(json.dumps(data));inv=p/'inventory.csv'
   run=subprocess.run([sys.executable,str(ROOT/'piezocatalysis-lca-modeling/scripts/cyclic_foreground.py'),str(source),'--inventory-csv',str(inv)],capture_output=True,text=True);self.assertEqual(run.returncode,0,run.stderr)
   manifest=Path(str(inv)+'.manifest.json');h=load_handoff(inv,manifest);report=collect(h,{'queries':[{'activity_id':'ultrasound-1','process_uuids':[A]}]},FakeClient(),context())
   _,m,a=finalize(report,decisions(report),h,'d','r');write_csv(p/'mapping.csv',MAPPING_FIELDS,m);write_csv(p/'assignments.csv',['activity_id','mapping_id'],a)
   x=load_handoff(inv,manifest,p/'mapping.csv',p/'assignments.csv');row=next(v for v in x['rows'] if v['activity_id']=='ultrasound-1');self.assertEqual(row['mapping_id'],'existing-map');self.assertIn('pending_human_review',row['issues'])
 def test_no_automatic_selection(self):
  out,m,a=finalize(self.report,list(decision_rows(self.report)),self.h,'d','r');self.assertEqual(m,[]);self.assertEqual(a,[]);self.assertEqual(set(out['activities_without_selection']),{'power','waste'})
 def test_require_proxy_context_and_no_duplicate_selections(self):
  ds=decisions(self.report);ds[0]['rationale']=''
  with self.assertRaisesRegex(ValueError,'rationale'):finalize(self.report,ds,self.h,'d','r')
  ds=decisions(self.report);ds[1].update(decision='selected',match_type='proxy',rationale='alternative',expected_bias='unknown',geography_rationale='fictional',technology_rationale='fictional',reviewer='synthetic',review_date='2026-01-01')
  with self.assertRaisesRegex(ValueError,'more than one selected'):finalize(self.report,ds,self.h,'d','r')
 def test_review_date_requires_real_iso_date(self):
  ds=decisions(self.report);ds[0]['review_date']='2026-99-99'
  with self.assertRaisesRegex(ValueError,'ISO date'):finalize(self.report,ds,self.h,'d','r')
 def test_stale_or_tampered_metadata_rejected(self):
  ds=decisions(self.report);ds[0]['geography']='GLO'
  with self.assertRaisesRegex(ValueError,'metadata differs'):finalize(self.report,ds,self.h,'d','r')
  h=copy.deepcopy(self.h);h['inventory_sha256']='other'
  with self.assertRaisesRegex(ValueError,'inventory or manifest differs'):finalize(self.report,decisions(self.report),h,'d','r')
  r=copy.deepcopy(self.report);r['rows'][0]['foreground_unit']='kg'
  with self.assertRaisesRegex(ValueError,'foreground metadata differs'):finalize(r,decisions(r),self.h,'d','r')
 def test_geography_code_and_name_are_different_fields(self):
  class Geography(FakeClient):
   def call(self,m,p):
    if m=='data/get' and p['@type']=='Location':return {'@type':'Location','@id':p['@id'],'name':'China','code':'CN'}
    v=super().call(m,p)
    if m=='data/get' and p['@type']=='Process':v['location']={'@type':'Location','@id':C,'name':'China'}
    return v
  q={'queries':[{'activity_id':'power','process_uuids':[A]}]};r=collect(self.h,q,Geography(),context());a=r['rows'][0]['candidates'][0]
  self.assertEqual(a['actual_reference']['geography'],'CN');self.assertEqual(a['actual_reference']['geography_name'],'China');self.assertEqual(a['actual_reference']['location_verification'],'code_matches');self.assertNotIn('geography_descriptor_code_mismatch',a['issues'])
  class Wrong(Geography):
   def call(self,m,p):
    v=super().call(m,p)
    if m=='data/get' and p['@type']=='Location':v['code']='XX'
    return v
  r=collect(self.h,q,Wrong(),context());self.assertIn('geography_descriptor_code_mismatch',r['rows'][0]['candidates'][0]['issues'])
 def test_missing_and_truncated_candidates_visible(self):
  q={'queries':[{'activity_id':'power','process_uuids':[C]}]};r=collect(self.h,q,FakeClient(),context())
  self.assertEqual(r['rows'][0]['missing_requested_uuids'],[C]);self.assertEqual(r['rows'][0]['candidates'],[])
  class Many(FakeClient):
   def call(self,m,p):
    if m=='data/get/descriptors':return [{'@id':str(__import__('uuid').UUID(int=i+1)),'name':'fictional electricity','location':'CN'} for i in range(21)]
    uid=p['@id'];return {'@type':'Process','@id':uid,'name':'fictional electricity','location':{'name':'CN'},'exchanges':[]}
  self.assertTrue(collect(self.h,self.q,Many(),context())['rows'][0]['truncated'])
 def test_duplicate_activity_in_review_cannot_be_finalized(self):
  report=copy.deepcopy(self.report);extra=copy.deepcopy(report['rows'][0]);extra['candidates']=[];report['rows'].append(extra)
  with self.assertRaisesRegex(ValueError,'duplicate activity'):finalize(report,decisions(report),self.h,'d','r')
 def test_direction_mismatch_cannot_be_selected(self):
  h=handoff();h['rows'][0]['direction']='output';r=collect(h,self.q,FakeClient(),context())
  with self.assertRaisesRegex(ValueError,'reference_direction_mismatch'):finalize(r,decisions(r),h,'d','r')
 def test_density_requires_source_and_correct_dimensions(self):
  h=handoff();h['rows'][0]['unit']='L';c=FakeClient();original=c.call
  def call(m,p):
   v=original(m,p)
   if m=='data/get':v['exchanges'][0]['unit']['name']='kg'
   return v
  c.call=call;r=collect(h,self.q,c,context());ds=decisions(r);ds[0].update(conversion_type='density',density_kg_per_l='1',density_source='fictional',density_evidence_class='scenario')
  _,maps,_=finalize(r,ds,h,'d','r');self.assertEqual(maps[0]['conversion_factor'],1);self.assertEqual(maps[0]['review_status'],'pending')
  ds[0]['density_source']=''
  with self.assertRaisesRegex(ValueError,'density_source'):finalize(r,ds,h,'d','r')
 def test_output_is_compatible_with_existing_handoff(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);inv=p/'inventory.csv';fg=ROOT/'piezocatalysis-lca-modeling/assets/examples/synthetic-cycles/constant.json'
   run=subprocess.run([sys.executable,str(ROOT/'piezocatalysis-lca-modeling/scripts/cyclic_foreground.py'),str(fg),'--inventory-csv',str(inv)],capture_output=True,text=True)
   self.assertEqual(run.returncode,0,run.stderr);manifest=Path(str(inv)+'.manifest.json');h=load_handoff(inv,manifest)
   report=collect(h,{'queries':[{'activity_id':'ultrasound-1','process_uuids':[A]}]},FakeClient(),context());ds=decisions(report);_,m,a=finalize(report,ds,h,'d','r')
   write_csv(p/'mapping.csv',MAPPING_FIELDS,m);write_csv(p/'assignments.csv',['activity_id','mapping_id'],a)
   new=load_handoff(inv,manifest,p/'mapping.csv',p/'assignments.csv');selected=next(x for x in new['rows'] if x['activity_id']=='ultrasound-1')
   self.assertIn('pending_human_review',selected['issues']);self.assertEqual(selected['mapping_type'],'proxy');self.assertTrue(any(x['mapping_type']=='unmapped' for x in new['rows']))
if __name__=='__main__':unittest.main()
