import copy,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'piezocatalysis-lca-modeling/scripts'));sys.path.insert(0,str(ROOT/'tests'))
from scenario_binding import check_system_reference,check_links,check_parameter_overrides,compare_bound,digest
from test_plot_data import fixture
import test_cycle_scenario_compare

class BindingTests(unittest.TestCase):
 def test_product_system_reference_must_match_root_and_units(self):
  b={'root_uuid':'root','unit_uuid':'unit','property_uuid':'property'}
  system={'refProcess':{'@id':'root'},'targetUnit':{'@id':'unit'},'targetFlowProperty':{'@id':'property'},'refExchange':{'internalId':1,'flow':{'@id':'ref-flow'}}}
  root={'@id':'root','exchanges':[{'internalId':1,'flow':{'@id':'ref-flow'},'isQuantitativeReference':True}]}
  self.assertEqual(check_system_reference(system,root,b)['reference_flow'],'ref-flow')
  for key in ('refProcess','targetUnit','targetFlowProperty'):
   wrong=copy.deepcopy(system);wrong[key]={'@id':'wrong'}
   with self.subTest(key=key),self.assertRaises(ValueError):check_system_reference(wrong,root,b)
  root['exchanges'][0]['isQuantitativeReference']=False
  with self.assertRaises(ValueError):check_system_reference(system,root,b)
 def test_parameter_override_must_match_real_unprotected_snapshot(self):
  available=[{'name':'power','value':1,'context':{'@id':'process','@type':'Process'}}];good={'name':'power','value':2,'context':{'@id':'process','@type':'Process'}}
  check_parameter_overrides([good],available)
  for bad in ([dict(good,name='missing')],[dict(good,value=float('nan'))],[good,good],[dict(good,context={'@id':'process','@type':'ImpactCategory'})]):
   with self.subTest(bad=bad),self.assertRaises(ValueError):check_parameter_overrides(bad,available)
  with self.assertRaisesRegex(ValueError,'protected'):check_parameter_overrides([good],[dict(available[0],isProtected=True)])
 def test_checked_exchange_provider_and_missing_link(self):
  report,plan,b=fixture();report['calculation']['setup'].update(target={'@id':'system'},unit={'@id':'unit'},flowProperty={'@id':'property'});b.update(unit_uuid='unit',property_uuid='property')
  self.assertEqual(check_links(plan,report,b)['checked_activities'],2)
  for key,value in [('provider_uuid','other'),('unit','g'),('amount',3),('process_uuid','other')]:
   q=copy.deepcopy(b);q['activities'][0][key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):check_links(plan,report,q)
  q=copy.deepcopy(report);q['link_review']['technical_exchanges'][0]['links']=[]
  with self.assertRaises(ValueError):check_links(plan,q,b)
 def test_internal_ids_distinguish_identical_exchanges_in_one_process(self):
  report, plan, binding = fixture()
  report['calculation']['setup'].update(target={'@id':'system'}, unit={'@id':'unit'}, flowProperty={'@id':'property'})
  binding.update(unit_uuid='unit', property_uuid='property')
  duplicate = dict(binding['activities'][0], activity_id='another-cycle')
  binding['activities'].append(duplicate)
  plan['rows'].append(dict(plan['rows'][0], activity_id='another-cycle'))
  rows = report['link_review']['technical_exchanges']
  original_id = rows[0]['exchange_internal_id']
  rows.append(dict(rows[0], exchange_internal_id=200))
  with self.assertRaisesRegex(ValueError, 'ambiguous'):
   check_links(plan, report, binding)
  binding['activities'][0]['exchange_internal_id'] = original_id
  duplicate['exchange_internal_id'] = 200
  self.assertEqual(check_links(plan, report, binding)['checked_activities'], 3)
  duplicate['exchange_internal_id'] = original_id
  with self.assertRaisesRegex(ValueError, 'ambiguous'):
   check_links(plan, report, binding)

 def test_duplicate_stage_exchange_id_is_ambiguous_even_with_different_flows(self):
  report, plan, binding = fixture()
  report['calculation']['setup'].update(target={'@id':'system'}, unit={'@id':'unit'}, flowProperty={'@id':'property'})
  binding.update(unit_uuid='unit', property_uuid='property')
  rows = report['link_review']['technical_exchanges']
  self.assertEqual(check_links(plan, report, binding)['checked_activities'], 2)
  rows.append(dict(rows[0], flow={'@id':'another-flow'}))
  with self.assertRaisesRegex(ValueError, 'ambiguous'):
   check_links(plan, report, binding)

 def test_untracked_exchange_and_nonunit_root_blocked(self):
  report,plan,b=fixture();report['calculation']['setup'].update(target={'@id':'system'},unit={'@id':'unit'},flowProperty={'@id':'property'});b.update(unit_uuid='unit',property_uuid='property')
  altered=copy.deepcopy(report);altered['link_review']['technical_exchanges'].append({'process':{'@id':'x'},'exchange_internal_id':999})
  with self.assertRaisesRegex(ValueError,'unaccounted'):check_links(plan,altered,b)
  altered=copy.deepcopy(report);altered['link_review']['technical_exchanges'][2]['amount']=2
  with self.assertRaisesRegex(ValueError,'root stage'):check_links(plan,altered,b)
 def bound_pair(self):
  t=test_cycle_scenario_compare.CycleScenarioTests();t.setUp();method=t.contexts['cases'][0]['lcia_method_uuid'];t.calc['impact_method']['@id']=method
  for c in t.contexts['cases']:c['system_boundary']=t.source['boundary']
  t.calc['target']={'@id':'system'};t.calc['setup'].update(target={'@id':'system'},unit={'@id':'unit'},flowProperty={'@id':'property'});t.plan.update(inventory_sha256='inv',manifest_sha256='man',mapping_sha256='map',assignments_sha256='assign',functional_unit=t.source['treatment_target'],boundary=t.source['boundary'])
  binding={'system_uuid':'system','root_uuid':'root','unit_uuid':'unit','property_uuid':'property','stages':['x','y'],'activities':[]};exchanges=[]
  for i,row in enumerate(t.plan['rows']):
   unresolved=row['status']=='unresolved';pid='x' if row['stage']=='preparation' else 'y';flow='flow-'+str(i);provider=None if unresolved else row['actual_reference']['process_uuid']
   if not unresolved:row['actual_reference'].update(reference_flow_uuid=flow,reference_is_input=row['direction']=='output')
   item={'activity_id':row['activity_id'],'process_uuid':pid,'provider_uuid':provider,'flow_uuid':flow,'unit':row['unit'],'amount':row['amount_per_functional_unit'],'is_input':row['direction']=='input'};binding['activities'].append(item)
   exchanges.append({'process':{'@id':pid},'exchange_internal_id':i,'flow':{'@id':flow},'unit':{'name':row['unit']},'amount':item['amount'],'is_input':item['is_input'],'status':'unlinked_candidate' if unresolved else 'linked','links':[] if unresolved else [{'provider':{'@id':provider}}]})
  for i,pid in enumerate(('x','y')):exchanges.append({'process':{'@id':'root'},'exchange_internal_id':100+i,'amount':1,'is_input':True,'status':'linked','links':[{'provider':{'@id':pid}}]})
  coverage={'calculation':t.calc,'link_review':{'technical_exchanges':exchanges}}
  a={'schema_version':'piezolca.bound-scenario/2','status':'observed_in_session_review_required','foreground_semantic_sha256':digest(t.source),'inventory_sha256':'inv','manifest_sha256':'man','mapping_sha256':'map','assignments_sha256':'assign','binding':binding,'system_reference':{'ref_process':'root','target_unit':'unit','target_flow_property':'property','reference_exchange_id':1,'reference_flow':'ref-flow'},'binding_sha256':digest(binding),'provider_snapshots_sha256':'providers','parameter_overrides':[],'parameters_at_calculation':[],'plan':t.plan,'coverage':coverage,'link_check':check_links(t.plan,coverage,binding)}
  a.update(plan_sha256=digest(t.plan),coverage_sha256=digest(coverage),calculation_sha256=digest(t.calc),parameters_sha256=digest([]))
  return t, a,copy.deepcopy(a)
 def test_old_captures_and_wrong_recorded_reference_require_recapture(self):
  t,a,b=self.bound_pair();b['schema_version']='piezolca.bound-scenario/1'
  with self.assertRaisesRegex(ValueError,'recapture'):compare_bound(a,b,t.source,t.source,t.contexts)
  t,a,b=self.bound_pair();b['system_reference']['ref_process']='wrong'
  with self.assertRaisesRegex(ValueError,'reference differs'):compare_bound(a,b,t.source,t.source,t.contexts)
 def test_partial_model_keeps_real_results_but_disables_approximation(self):
  t,a,b=self.bound_pair();r=compare_bound(a,b,t.source,t.source,t.contexts);self.assertTrue(r['impacts']);self.assertFalse(r['ranking_permitted']);self.assertIsNone(r['impacts'][0]['linear_delta_estimate']);self.assertIn('unresolved_foreground_exchanges',r['bound_scenario_comparison']['linear_estimate_unavailable_reasons'])
 def test_wrong_source_background_parameter_method_or_boundary_rejected(self):
  t,a,b=self.bound_pair()
  wrong=copy.deepcopy(t.source);wrong['boundary']='changed'
  with self.assertRaisesRegex(ValueError,'foreground'):compare_bound(a,b,t.source,wrong,t.contexts)
  bad=copy.deepcopy(b);bad['provider_snapshots_sha256']='different'
  with self.assertRaisesRegex(ValueError,'background'):compare_bound(a,bad,t.source,t.source,t.contexts)
  bad=copy.deepcopy(b);bad['parameter_overrides']=[{'name':'x','value':2}]
  with self.assertRaisesRegex(ValueError,'parameter overrides'):compare_bound(a,bad,t.source,t.source,t.contexts)
  bad=copy.deepcopy(b);bad['coverage']['calculation']['impacts'][0]['amount']+=1
  with self.assertRaisesRegex(ValueError,'have changed'):compare_bound(a,bad,t.source,t.source,t.contexts)
  bad=copy.deepcopy(b);bad['coverage']['calculation']['target']['@id']='another-system'
  bad['calculation_sha256']=digest(bad['coverage']['calculation']);bad['coverage_sha256']=digest(bad['coverage'])
  with self.assertRaisesRegex(ValueError,'system differs'):compare_bound(a,bad,t.source,t.source,t.contexts)
  bad=copy.deepcopy(b);bad['plan']['rows'][0]['amount_per_functional_unit']+=1
  bad['plan_sha256']=digest(bad['plan'])
  with self.assertRaisesRegex(ValueError,'plan differs from scenario foreground'):compare_bound(a,bad,t.source,t.source,t.contexts)
  for field,value in [('lcia_method_uuid','22222222-2222-4222-8222-222222222222'),('system_boundary','wrong boundary')]:
   ctx=copy.deepcopy(t.contexts);ctx['cases'][1][field]=value
   with self.subTest(field=field),self.assertRaises(ValueError):compare_bound(a,b,t.source,t.source,ctx)
 def test_parameters_and_offsets_disable_approximation(self):
  t,a,b=self.bound_pair();a['parameters_at_calculation']=[{'name':'synthetic'}];a['parameters_sha256']=digest(a['parameters_at_calculation']);r=compare_bound(a,b,t.source,t.source,t.contexts);self.assertIn('parameters_require_independent_linearity_review',r['bound_scenario_comparison']['linear_estimate_unavailable_reasons'])
  t,a,b=self.bound_pair();a['coverage']['calculation']['impacts'][0]['contributions'][0]['amount']=-1;a['calculation_sha256']=digest(a['coverage']['calculation']);a['coverage_sha256']=digest(a['coverage']);b=copy.deepcopy(a)
  r=compare_bound(a,b,t.source,t.source,t.contexts);self.assertIn('offsetting_contributions',r['bound_scenario_comparison']['linear_estimate_unavailable_reasons'])
 def test_true_zero_is_preserved_and_not_used_for_percentage_or_linear_estimate(self):
  t,a,b=self.bound_pair();a['coverage']['calculation']['impacts'][0]['amount']=0;a['calculation_sha256']=digest(a['coverage']['calculation']);a['coverage_sha256']=digest(a['coverage']);b=copy.deepcopy(a)
  r=compare_bound(a,b,t.source,t.source,t.contexts);self.assertEqual(r['impacts'][0]['baseline'],0);self.assertIsNone(r['impacts'][0]['change_percent']);self.assertIsNone(r['impacts'][0]['linear_delta_estimate']);self.assertIn('zero_baseline_requires_review',r['bound_scenario_comparison']['linear_estimate_unavailable_reasons'])
 def test_complete_fixed_synthetic_background_can_keep_linear_estimate(self):
  t,a,b=self.bound_pair();source=copy.deepcopy(t.source);source['final_recovered_destination']='retained'
  for record in (a,b):
   item=next(x for x in record['binding']['activities'] if x['activity_id']=='final-recovered-catalyst');pid=item['process_uuid'];flow=item['flow_uuid']
   record['binding']['activities']=[x for x in record['binding']['activities'] if x['activity_id']!='final-recovered-catalyst'];record['binding_sha256']=digest(record['binding'])
   record['plan']['rows']=[x for x in record['plan']['rows'] if x['activity_id']!='final-recovered-catalyst'];record['plan_sha256']=digest(record['plan'])
   record['coverage']['link_review']['technical_exchanges']=[x for x in record['coverage']['link_review']['technical_exchanges'] if not ((x.get('process') or {}).get('@id')==pid and (x.get('flow') or {}).get('@id')==flow)];record['coverage_sha256']=digest(record['coverage'])
   record['foreground_semantic_sha256']=digest(source);record['link_check']=check_links(record['plan'],record['coverage'],record['binding'])
  r=compare_bound(a,b,source,source,t.contexts);self.assertEqual(r['bound_scenario_comparison']['linear_estimate_unavailable_reasons'],[]);self.assertEqual(r['impacts'][0]['linear_delta_estimate'],0);self.assertFalse(r['ranking_permitted'])
if __name__=='__main__':unittest.main()
