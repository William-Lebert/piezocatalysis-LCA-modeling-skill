import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'piezocatalysis-lca-modeling/scripts'))
from experimental_quality import audit

def record():return json.loads((ROOT/'piezocatalysis-lca-modeling/assets/examples/synthetic-cycles/constant.json').read_text())
def case(id,r):return {'id':id,'record':r,'geography':'fictional','time_scope':'fictional','calibration':'fictional assumption'}

class QualityTests(unittest.TestCase):
 def test_missing_and_censored_preserved_without_imputation(self):
  x=record();q=x['cycles'][1]['effluent_concentration'];q.update(value=None,qualifier='below_loq',limit=2)
  d={'campaigns':[case('c1',x)],'dependency_reviewed':False,'distribution_basis_reviewed':False};r=audit(d)
  v=next(x for x in r['variables'] if x['field']=='cycle/2/effluent_concentration')
  self.assertIsNone(v['observations'][0]['value']);self.assertEqual(v['censored_count'],1);self.assertEqual(v['observations'][0]['limit'],2)
  self.assertTrue(any(x['status']=='censored_observation_not_imputed' for x in r['issues']))
 def test_missing_detection_limit_is_reported(self):
  x=record();x['cycles'][1]['effluent_concentration'].update(value=None,qualifier='below_loq')
  r=audit({'campaigns':[case('c',x)]});self.assertTrue(any(x['status']=='detection_limit_missing_or_invalid' for x in r['issues']))
 def test_paired_correlation_and_evidence_label(self):
  cases=[]
  for i,(p,t) in enumerate([(100,60),(125,50),(150,40)]):
   x=record();act=x['cycles'][0]['activities'][0];act['power']['value']=p;act['duration']['value']=t;cases.append(case(str(i),x))
  r=audit({'campaigns':cases,'dependency_reviewed':True,'distribution_basis_reviewed':True})
  pair=next(x for x in r['paired_power_duration'] if x['activity'].endswith('ultrasound-1'))
  self.assertEqual(pair['pair_count'],3);self.assertAlmostEqual(pair['pearson_descriptive'],-1)
  v=next(x for x in r['variables'] if x['field'].endswith('ultrasound-1/power'));self.assertEqual(v['measured_count'],0)
 def test_mixed_units_are_not_aggregated(self):
  a=record();b=record();b['cycles'][0]['activities'][0]['power'].update(value=.1,unit='kW')
  r=audit({'campaigns':[case('a',a),case('b',b)]});v=next(x for x in r['variables'] if x['field'].endswith('ultrasound-1/power'))
  self.assertIsNone(v['sample_standard_deviation']);self.assertTrue(any(x['status']=='unit_mismatch_no_aggregation' for x in r['issues']))
 def test_mixed_evidence_and_unverified_calibration_are_visible(self):
  a=record();b=record();b['cycles'][0]['activities'][0]['power']['evidence_class']='measured'
  r=audit({'campaigns':[case('a',a),case('b',b)]});v=next(x for x in r['variables'] if x['field'].endswith('ultrasound-1/power'))
  self.assertIsNone(v['sample_standard_deviation']);self.assertTrue(any(x['status']=='mixed_evidence_no_aggregation' for x in r['issues']))
  self.assertTrue(any(x['status']=='not_verified' and x['field']=='calibration_status' for x in r['issues']))
 def test_missing_provenance_and_duplicate_campaign(self):
  a=case('a',record());a['calibration']='';r=audit({'campaigns':[a]});self.assertTrue(any(x['field']=='calibration' for x in r['issues']))
  with self.assertRaises(ValueError):audit({'campaigns':[a,copy.deepcopy(a)]})

if __name__=='__main__':unittest.main()
