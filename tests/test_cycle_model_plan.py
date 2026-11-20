import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'piezocatalysis-lca-modeling/scripts'))
from cycle_model_plan import preflight
from openlca_readonly import EntityNotFound

PID='11111111-1111-4111-8111-111111111111';FID='22222222-2222-4222-8222-222222222222';PROP='33333333-3333-4333-8333-333333333333';UNIT='44444444-4444-4444-8444-444444444444'
LOC='66666666-6666-4666-8666-666666666666'
class FakeClient:
 def __init__(self):
  self.location={'@type':'Location','@id':LOC,'code':'CN','name':'China'}
  self.process={'@type':'Process','@id':PID,'name':'fictional electricity','version':'1','processType':'LCI_RESULT','exchanges':[{'isQuantitativeReference':True,'isInput':False,'flow':{'@id':FID,'name':'electricity'},'flowProperty':{'@id':PROP},'unit':{'@id':UNIT,'name':'kWh'}}]}
  self.process['location']={'@id':LOC,'name':'China'}
  self.calls=[]
 def call(self,method,params):
  if method!='data/get':raise AssertionError('unexpected RPC method')
  key=(params['@type'],params['@id']);self.calls.append(key)
  if key==('Location',LOC):return self.location
  if key==('Process',PID):return self.process
  raise EntityNotFound('resource not found')

def case():
 m={'database':'synthetic','process_uuid':PID,'dataset_name':'fictional electricity','geography':'CN','reference_flow_uuid':FID,'reference_product':'electricity','flow_property_uuid':PROP,'unit_uuid':UNIT,'dataset_unit':'kWh','reference_is_input':'false','process_version':'1'}
 row={'included':True,'issues':[],'mapping_user_asserted':m,'activity_id':'power','stage':'treatment','cycle_id':'1','flow_name':'power','direction':'input','amount_per_functional_unit':2,'unit':'kWh','mapping_id':'p','mapping_type':'exact','dataset_amount_per_functional_unit':2}
 return {'schema_version':'piezolca.handoff/1','system':'fictional','boundary':'synthetic','functional_unit':{'value':1},'amount_basis':'per_functional_unit','inventory_sha256':'i','manifest_sha256':'m','mapping_sha256':'map','assignments_sha256':'a','handoff_code_sha256':'h','model_warnings':[],'campaign':{},'rows':[row]}

class ModelPlanTests(unittest.TestCase):
 def test_matching_reference_and_cache(self):
  h=case();h['rows'].append(dict(h['rows'][0],activity_id='power2'));c=FakeClient();r=preflight(h,c,'synthetic')
  self.assertEqual(r['summary']['matched_rows'],2);self.assertEqual(c.calls,[('Process',PID),('Location',LOC)]);self.assertEqual(r['rows'][0]['dataset_amount_per_functional_unit'],2)
 def test_system_snapshot_reuses_process_and_reloads_location_per_preflight(self):
  client=FakeClient();processes={PID:client.process}
  self.assertEqual(preflight(case(),client,'synthetic',system_processes=processes)['summary']['matched_rows'],1)
  client.location['code']='GLO'
  changed=preflight(case(),client,'synthetic',system_processes=processes)
  self.assertIn('geography_database_mismatch',changed['rows'][0]['issues'])
  self.assertEqual(client.calls,[('Location',LOC),('Location',LOC)])
 def test_unmapped_never_becomes_zero(self):
  h=case();h['rows'][0].update(mapping_user_asserted=None,issues=['unmapped'],dataset_amount_per_functional_unit=None)
  r=preflight(h,FakeClient(),'synthetic');self.assertEqual(r['summary']['status'],'partial');self.assertIsNone(r['rows'][0]['dataset_amount_per_functional_unit'])
 def test_terminal_disposal_checks_actual_reference_flow_type(self):
  handoff = case()
  row = handoff['rows'][0]
  row.update(activity_id='final-recovered-catalyst', direction='output', unit='g',
             amount_per_functional_unit=5, dataset_amount_per_functional_unit=0.005)
  row['mapping_user_asserted'].update(reference_is_input='true', dataset_unit='kg')
  client = FakeClient()
  reference = client.process['exchanges'][0]
  reference['isInput'] = True
  reference['unit']['name'] = 'kg'
  reference['flow']['flowType'] = 'PRODUCT_FLOW'
  rejected = preflight(handoff, client, 'synthetic')['rows'][0]
  self.assertIn('terminal_disposal_reference_not_waste', rejected['issues'])
  self.assertIsNone(rejected['dataset_amount_per_functional_unit'])
  reference['flow']['flowType'] = 'WASTE_FLOW'
  accepted = preflight(handoff, client, 'synthetic')['rows'][0]
  self.assertEqual(accepted['dataset_amount_per_functional_unit'], 0.005)

 def test_stale_unit_region_and_reference_detected(self):
  h=case();c=FakeClient();c.process['exchanges'][0]['unit']['name']='MJ';c.location['code']='GLO';c.process['exchanges'][0]['isInput']=True
  r=preflight(h,c,'synthetic');issues=r['rows'][0]['issues']
  self.assertTrue({'dataset_unit_database_mismatch','geography_database_mismatch','reference_direction_database_mismatch'}<=set(issues));self.assertIsNone(r['rows'][0]['dataset_amount_per_functional_unit'])
 def test_unreviewed_and_missing_process_do_not_become_linked(self):
  h=case();h['rows'][0]['issues']=['pending_human_review'];c=FakeClient();r=preflight(h,c,'synthetic');self.assertEqual(c.calls,[]);self.assertEqual(r['summary']['unresolved_rows'],1)
  h=case();h['rows'][0]['mapping_user_asserted']['process_uuid']='55555555-5555-4555-8555-555555555555';r=preflight(h,c,'synthetic');self.assertIn('process_uuid_not_found',r['rows'][0]['issues'])
 def test_database_and_version_mismatch(self):
  h=case();r=preflight(h,FakeClient(),'other');self.assertIn('database_name_mismatch',r['rows'][0]['issues'])
  h=case();h['rows'][0]['mapping_user_asserted']['process_version']='old';r=preflight(h,FakeClient(),'synthetic');self.assertIn('process_version_database_mismatch',r['rows'][0]['issues'])

if __name__=='__main__':unittest.main()
