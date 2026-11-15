import copy,json,math,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'piezocatalysis-lca-modeling/scripts'))
from plot_data import cycles,stage_contributions,scenarios,sensitivity


def fixture():
 ps=[{'activity_id':'a','direction':'input','stage':'preparation','status':'preflight_matches_review_still_required','issues':[],'dataset_amount_per_functional_unit':2,'actual_reference':{'process_uuid':'p','reference_flow_uuid':'f','unit_name':'kg','reference_is_input':False}},
     {'activity_id':'b','direction':'input','stage':'treatment','status':'preflight_matches_review_still_required','issues':[],'dataset_amount_per_functional_unit':1,'actual_reference':{'process_uuid':'q','reference_flow_uuid':'g','unit_name':'kg','reference_is_input':False}}]
 bs=[{'activity_id':'a','process_uuid':'x','provider_uuid':'p','flow_uuid':'f','unit':'kg','amount':2,'is_input':True},
     {'activity_id':'b','process_uuid':'y','provider_uuid':'q','flow_uuid':'g','unit':'kg','amount':1,'is_input':True}]
 def exchange(r,i):return {'process':{'@id':r['process_uuid']},'flow':{'@id':r['flow_uuid']},'unit':{'name':'kg'},'amount':r['amount'],'is_input':True,'status':'linked','exchange_internal_id':i,'links':[{'provider':{'@id':r['provider_uuid']}}]}
 def contrib(pid,value):return {'tech_flow':{'provider':{'@id':pid,'processType':'LCI_RESULT'}},'amount':value}
 report={'schema_version':'piezolca.result-coverage/1','calculation':{'target':{'@id':'system'},'functional_unit_user_asserted':'1 synthetic service','setup':{'amount':1},'database':{},'impact_method':{},'warnings':[]},
         'link_review':{'technical_exchanges':[exchange(bs[0],1),exchange(bs[1],1),
           {'process':{'@id':'root'},'flow':{'@id':'fx'},'unit':{'name':'service'},'amount':1,'is_input':True,'status':'linked','exchange_internal_id':2,'links':[{'provider':{'@id':'x'}}]},
           {'process':{'@id':'root'},'flow':{'@id':'fy'},'unit':{'name':'service'},'amount':1,'is_input':True,'status':'linked','exchange_internal_id':3,'links':[{'provider':{'@id':'y'}}]}]},
         'selected_category':{'@id':'cat','name':'synthetic impact','refUnit':'kg'},'hotspots':{'total':0,'contributions_by_absolute_amount':[contrib('p',3),contrib('q',-3),{'tech_flow':{'provider':{'@id':'x','processType':'UNIT_PROCESS'},'flow':{'@id':'fx'}},'amount':0},{'tech_flow':{'provider':{'@id':'y','processType':'UNIT_PROCESS'},'flow':{'@id':'fy'}},'amount':0}]}}
 plan={'schema_version':'piezolca.cycle-model-plan/1','amount_basis':'per_functional_unit','model_warnings':[],'rows':ps}
 binding={'system_uuid':'system','root_uuid':'root','stages':['x','y'],'activities':bs}
 return report,plan,binding

class PlotDataTests(unittest.TestCase):
 def example(self,name):return json.loads((ROOT/'piezocatalysis-lca-modeling/assets/examples'/name).read_text())
 def test_cycle_exact_and_censored_not_zero(self):
  a=cycles(self.example('synthetic-cycles/constant.json'));self.assertEqual(a['rows'][0]['apparent_removal_mg'],10);self.assertAlmostEqual(a['rows'][0]['treatment_energy_kwh'],.1)
  b=cycles(self.example('synthetic-cycles/variable-censored.json'));c=[r for r in b['rows'] if r['effluent_qualifier']=='below_loq'][0]
  self.assertIsNone(c['apparent_removal_mg']);self.assertIsNotNone(c['removal_upper_mg'])
 def test_signed_offset_preserved_without_percent(self):
  r,p,b=fixture();d=stage_contributions(r,p,b);self.assertEqual(d['total'],0);self.assertEqual([x['contribution'] for x in d['rows']],[3,-3])
 def test_true_zero_background_is_not_missing(self):
  r,p,b=fixture();r['hotspots']['contributions_by_absolute_amount'][0]['amount']=0;r['hotspots']['contributions_by_absolute_amount'][1]['amount']=0
  d=stage_contributions(r,p,b);self.assertEqual([x['contribution'] for x in d['rows']],[0,0])
 def test_missing_provider_is_rejected(self):
  r,p,b=fixture();r['hotspots']['contributions_by_absolute_amount'].pop(1);r['hotspots']['total']=3
  with self.assertRaisesRegex(ValueError,'missing or ambiguous'):stage_contributions(r,p,b)
 def test_untracked_exchange_is_rejected(self):
  r,p,b=fixture();r['link_review']['technical_exchanges'].append({'process':{'@id':'x'},'exchange_internal_id':99})
  with self.assertRaisesRegex(ValueError,'unaccounted'):stage_contributions(r,p,b)
 def test_wrong_binding_and_units_are_rejected(self):
  r,p,b=fixture();b['activities'][0]['unit']='g'
  with self.assertRaisesRegex(ValueError,'binding'):stage_contributions(r,p,b)
 def test_nonunit_root_scaling_is_rejected(self):
  r,p,b=fixture();r['link_review']['technical_exchanges'][2]['amount']=2
  with self.assertRaisesRegex(ValueError,'one service'):stage_contributions(r,p,b)
 def test_calculation_amount_must_be_one(self):
  r,p,b=fixture();r['calculation']['setup']['amount']=2
  with self.assertRaisesRegex(ValueError,'exactly one'):stage_contributions(r,p,b)
 def test_scenario_mismatch_blocks_plot_and_partial_is_labeled(self):
  source=self.example('synthetic-cycles/constant.json');cat={'@id':'c','name':'test','refUnit':'kg'}
  r={'schema_version':'piezolca.cycle-scenario-comparison/1','context_check':{'status':'declared_contexts_match'},'ranking_permitted':False,'impacts':[{'category':cat,'unit':'kg','baseline':2,'amount':3,'delta':1}],'baseline_warnings':[],'scenario_warnings':[]}
  d=scenarios(r,source,source,'c');self.assertFalse(d['ranking_permitted']);self.assertTrue(d['warnings']);self.assertIn('apparent pollutant removal',d['functional_unit']['description'])
  r['ranking_permitted']=True;d=scenarios(r,source,source,'c');self.assertFalse(d['ranking_permitted']);self.assertTrue(d['source_report_ranking_permitted'])
  other=copy.deepcopy(source);other['treatment_target']['value']=99
  with self.assertRaisesRegex(ValueError,'functional units'):scenarios(r,source,other,'c')
  r['context_check']['status']='not_comparable'
  with self.assertRaisesRegex(ValueError,'incompatible'):scenarios(r,source,source,'c')
 def test_sensitivity_keeps_signed_single_scenarios(self):
  d=sensitivity(self.example('synthetic-sensitivity/expected-report.json'),'A','climate')
  self.assertTrue(any(r['delta']<0 for r in d['rows']));self.assertTrue(any(r['delta']>0 for r in d['rows']))
  self.assertTrue(any('not an inferred low/high' in w for w in d['warnings']))
 def test_sensitivity_mismatched_unit_rejected(self):
  d=self.example('synthetic-sensitivity/expected-report.json');d['cases'][1]['results']['A']['climate']['unit']='other'
  with self.assertRaisesRegex(ValueError,'unit or baseline'):sensitivity(d,'A','climate')

if __name__=='__main__':unittest.main()
