import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'piezocatalysis-lca-modeling/scripts'))
from domain_review import assess,compare_services,compare_declarations,COMMON,EXTRA


def make(kind='apparent_pollutant_removal'):
 def f(name,t):
  if t=='text':return {'status':'provided','value':'fictional '+name,'source':'synthetic','evidence_class':'scenario'}
  units={'mass':'g','volume':'L','concentration':'mg/L'}
  return {'status':'provided','value':1,'unit':units[t],'basis':'fictional measurement','source':'synthetic','evidence_class':'scenario'}
 fields={name:f(name,t) for name,t in {**COMMON,**EXTRA[kind]}.items()}
 unit='L' if kind=='treated_water' else 'g'
 service={'kind':kind,'functional_unit':{'value':1,'unit':unit},'definition':'fictional service','source':'synthetic','evidence_class':'scenario'}
 if kind=='h2o2_product':service['product_basis']='net_accumulated'
 if kind=='catalyst_production':service['catalyst_basis']='dry'
 return {'service':service,'fields':fields}

def handoff(d):
 s=d['service'];return {'amount_basis':'per_functional_unit','functional_unit_type':s['kind'],'functional_unit':s['functional_unit'],
 'product_basis':s.get('product_basis'),'product_definition':s['definition'] if s['kind']=='h2o2_product' else None,'boundary':d['fields']['system_boundary']['value'],'rows':[],'model_warnings':[]}

class DomainTests(unittest.TestCase):
 def test_four_service_types(self):
  for k in ('treated_water','apparent_pollutant_removal','h2o2_product','catalyst_production'):
   d=make(k);r=assess(d,handoff(d));self.assertEqual(r['status'],'declarations_complete_review_required',r)
 def test_censored_and_missing_limit_never_become_zero(self):
  d=make();d['fields']['effluent_concentration'].update(value=None,qualifier='below_loq',limit=3)
  r=assess(d,handoff(d));self.assertTrue(any(x['status']=='censored_not_imputed' for x in r['issues']))
  d['fields']['effluent_concentration'].pop('limit');self.assertTrue(any(x['status']=='detection_limit_missing_or_invalid' for x in assess(d,handoff(d))['issues']))
 def test_mass_difference_and_censored_interval(self):
  d=make();d['fields']['influent_concentration']['value']=20;d['fields']['effluent_concentration']['value']=8
  self.assertEqual(assess(d,handoff(d))['water_phase_observation']['apparent_mass_difference_mg'],12)
  d['fields']['effluent_concentration'].update(value=None,qualifier='below_loq',limit=3)
  o=assess(d,handoff(d))['water_phase_observation'];self.assertIsNone(o['apparent_mass_difference_mg']);self.assertEqual(o['censored_apparent_difference_interval_mg'],[17,20])
 def test_censored_interval_requires_a_valid_provided_observation(self):
  d=make();eff=d['fields']['effluent_concentration'];eff.update(qualifier='below_loq',limit=3,value=2)
  self.assertIsNone(assess(d,handoff(d))['water_phase_observation']['censored_apparent_difference_interval_mg'])
  eff.update(status='missing',value=None)
  self.assertIsNone(assess(d,handoff(d))['water_phase_observation']['censored_apparent_difference_interval_mg'])
 def test_mismatched_sampling_basis_blocks_mass_calculation(self):
  d=make();d['fields']['effluent_volume']['basis']='other cycle'
  r=assess(d,handoff(d));self.assertIsNone(r['water_phase_observation']['apparent_mass_difference_mg'])
  self.assertTrue(any(i['field']=='water_sample_basis' for i in r['issues']))
 def test_missing_exclusion_reason_and_source(self):
  d=make();d['fields']['external_oxidants']={'status':'not_applicable'};d['fields']['sampling_protocol']['source']=''
  statuses={i['status'] for i in assess(d,handoff(d))['issues']};self.assertIn('exclusion_reason_missing',statuses);self.assertIn('source_missing',statuses)
 def test_functional_unit_and_boundary_mismatches(self):
  d=make();h=handoff(d);h['functional_unit']={'value':2,'unit':'g'};h['boundary']='other'
  issues={x['field'] for x in assess(d,h)['issues']};self.assertIn('handoff.functional_unit',issues);self.assertIn('handoff.system_boundary',issues)
 def test_equivalent_mass_units_and_different_service(self):
  a=make()['service'];b=copy.deepcopy(a);b['functional_unit']={'value':1000,'unit':'mg'}
  self.assertTrue(compare_services(a,b)['comparable']);b['kind']='h2o2_product';self.assertFalse(compare_services(a,b)['comparable'])
 def test_product_basis_and_dry_catalyst(self):
  a=make('h2o2_product')['service'];b=copy.deepcopy(a);b['product_basis']='recovered_product'
  self.assertFalse(compare_services(a,b)['comparable']);a=make('catalyst_production')['service'];b=copy.deepcopy(a);b['catalyst_basis']='wet'
  self.assertFalse(compare_services(a,b)['comparable'])
 def test_missing_mapping_and_proxy_not_ready(self):
  d=make();h=handoff(d);h['rows']=[{'activity_id':'p','included':True,'issues':['unmapped'],'mapping_type':'proxy'}]
  r=assess(d,h);self.assertEqual(r['status'],'needs_review');self.assertTrue(r['warnings'])
 def test_pollutant_identity_and_performance_differ_block_comparison(self):
  a=make();b=copy.deepcopy(a);b['fields']['pollutant_identity']['value']='other pollutant'
  r=compare_declarations(a,b);self.assertFalse(r['declarations_match']);self.assertIn('pollutant_identity_mismatch',r['issues']);self.assertFalse(r['ranking_permitted'])
  b=copy.deepcopy(a);b['fields']['performance_criteria']={'status':'missing'}
  self.assertIn('performance_criteria_not_verified',compare_declarations(a,b)['issues'])
 def test_source_hash_mismatch_is_reported(self):
  d=make();h=handoff(d);h['input_sha256']='original'
  self.assertEqual(assess(d,h,'original')['source_input_sha256_check'],'matches_manifest')
  r=assess(d,h,'different');self.assertEqual(r['source_input_sha256_check'],'mismatch_or_missing');self.assertTrue(any(i['field']=='handoff.source_input_sha256' for i in r['issues']))
 def test_no_handoff_not_verified(self):self.assertTrue(any(x['field']=='handoff' for x in assess(make())['issues']))

if __name__=='__main__':unittest.main()
