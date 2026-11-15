import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'piezocatalysis-lca-modeling/scripts'))
from cyclic_foreground import build
from cycle_scenario_compare import compare
from scenario_comparability import FIELDS

class CycleScenarioTests(unittest.TestCase):
 def setUp(self):
  self.source=json.loads((ROOT/'piezocatalysis-lca-modeling/assets/examples/synthetic-cycles/constant.json').read_text())
  rows=build(self.source)['functional_unit_flows'];self.plan={'amount_basis':'per_functional_unit','rows':[]};contrib=[]
  for i,r in enumerate(rows):
   pid='provider-'+str(i);unresolved=r['activity_id']=='final-recovered-catalyst'
   self.plan['rows'].append({'activity_id':r['activity_id'],'flow_name':r['flow_name'],'unit':r['unit'],'direction':r['direction'],'stage':r['stage'],'cycle_id':r['cycle'],
     'status':'unresolved' if unresolved else 'preflight_matches_review_still_required','issues':['missing'] if unresolved else [],
     'amount_per_functional_unit':r['amount'],'dataset_amount_per_functional_unit':None if unresolved else r['amount'],
     'mapping_type':'proxy' if i==0 else 'exact','mapping_user_asserted':{'conversion_factor':'1'},
     'actual_reference':{'process_uuid':pid,'unit_name':r['unit']}})
   if not unresolved:contrib.append({'techFlow':{'provider':{'@id':pid}},'amount':r['amount']})
  total=sum(x['amount'] for x in contrib);cat={'@id':'category','name':'synthetic','refUnit':'score'}
  self.calc={'impact_method':{'@id':'method'},'database':{'name':'synthetic','version':'1','system_model':'test'},'functional_unit_user_asserted':'100 mg','setup':{'amount':1},'impacts':[{'category':cat,'amount':total,'contributions':contrib}]}
  fields={k:'same' for k in FIELDS};fields['lcia_method_uuid']='11111111-1111-4111-8111-111111111111'
  self.contexts={'cases':[dict(fields,id='base'),dict(fields,id='case')]}
 def run_case(self,scenario=None,contexts=None,calc=None):
  return compare(self.source,scenario or self.source,self.plan,self.calc,calc or self.calc,contexts or self.contexts)
 def test_baseline_and_unresolved_forbid_ranking(self):
  r=self.run_case();self.assertEqual(r['context_check']['status'],'declared_contexts_match');self.assertFalse(r['ranking_permitted']);self.assertEqual(r['unresolved_activity_ids'],['final-recovered-catalyst']);self.assertAlmostEqual(r['impacts'][0]['linear_delta_estimate'],0)
 def test_automatic_context_checks_never_grant_rankings(self):
  p=copy.deepcopy(self.plan)
  for row in p['rows']:
   if row['status']=='unresolved':row['status']='excluded'
   else:row['mapping_type']='exact'
  source=copy.deepcopy(self.source);source['final_recovered_destination']='retained'
  self.assertFalse(compare(source,source,p,self.calc,self.calc,self.contexts)['ranking_permitted'])
 def test_cycle_two_power_scales_only_bound_exchange(self):
  x=copy.deepcopy(self.source);x['cycles'][1]['activities'][0]['power']['value']=150
  r=self.run_case(x);changed=[v for v in r['activities'] if v['baseline']!=v['scenario']]
  self.assertEqual([v['activity_id'] for v in changed],['ultrasound-2']);self.assertAlmostEqual(changed[0]['scenario'],0.75)
 def test_performance_decrease_rescales_all(self):
  x=copy.deepcopy(self.source);x['cycles'][1]['effluent_concentration']['value']=15
  r=self.run_case(x);self.assertAlmostEqual(r['scenario_campaign']['campaigns_per_functional_unit'],100/15)
  for row in r['activities']:self.assertAlmostEqual(row['scenario'],row['baseline']*4/3)
 def test_functional_unit_method_geography_and_boundary_block(self):
  for field in ('functional_unit','geography','system_boundary','lcia_method_uuid'):
   with self.subTest(field=field):
    ctx=copy.deepcopy(self.contexts);ctx['cases'][1][field]='22222222-2222-4222-8222-222222222222' if field=='lcia_method_uuid' else 'different'
    r=self.run_case(contexts=ctx);self.assertEqual(r['context_check']['status'],'not_comparable');self.assertFalse(r['ranking_permitted'])
 def test_new_activity_or_changed_mapping_fails_closed(self):
  x=copy.deepcopy(self.source);x['cycles'][0]['activities'][0]['flow_name']='different';
  with self.assertRaises(ValueError):self.run_case(x)
  p=copy.deepcopy(self.plan);p['rows'][0]['amount_per_functional_unit']+=1
  with self.assertRaises(ValueError):compare(self.source,self.source,p,self.calc,self.calc,self.contexts)
 def test_actual_method_mismatch_is_reported(self):
  alt=copy.deepcopy(self.calc);alt['impact_method']['@id']='different'
  r=self.run_case(calc=alt);self.assertEqual(r['context_check']['status'],'not_comparable');self.assertFalse(r['ranking_permitted'])

if __name__=='__main__':unittest.main()
