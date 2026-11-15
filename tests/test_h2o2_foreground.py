import copy,csv,json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];S=ROOT/'piezocatalysis-lca-modeling/scripts';sys.path.insert(0,str(S))
from h2o2_foreground import build
from inventory_handoff import load_handoff
from audit_and_scale_inventory import audit

class H2O2Tests(unittest.TestCase):
 def setUp(self):self.d=json.loads((ROOT/'piezocatalysis-lca-modeling/assets/examples/synthetic-h2o2/case.json').read_text())
 def test_product_allocation_and_energy(self):
  r=build(self.d);self.assertEqual(r['campaign']['campaigns_per_functional_unit'],10000);self.assertEqual(r['campaign']['preparation_batches_per_functional_unit'],20)
  a={x['activity_id']:x for x in r['functional_unit_flows']};self.assertEqual(a['prep-electricity']['amount'],40);self.assertAlmostEqual(a['ultrasound']['amount'],40);self.assertEqual(a['water']['amount'],50);self.assertEqual(a['water']['unit'],'L')
  self.assertTrue(any('not automatically equivalent' in x for x in r['warnings']))
 def test_missing_net_product_is_not_zero_impact(self):
  self.d['net_product_per_campaign']['value']=None;r=build(self.d);self.assertIsNone(r['campaign']['campaigns_per_functional_unit']);self.assertTrue(all(x['amount'] is None for x in r['functional_unit_flows']))
 def test_reject_wet_catalyst_and_invalid_basis(self):
  for k,v in [('catalyst_mass_basis','wet'),('product_basis','gross')]:
   with self.subTest(k=k):
    d=copy.deepcopy(self.d);d[k]=v
    with self.assertRaises(ValueError):build(d)
 def test_disposed_catalyst_without_waste_reported(self):
  self.d['catalyst_destination']='disposed';r=build(self.d)
  self.assertTrue(any('no identified catalyst waste' in x for x in r['warnings']))
 def test_duplicate_or_overlapping_activity_rejected(self):
  self.d['campaign_activities'][0]['activity_id']='precursor'
  with self.assertRaises(ValueError):build(self.d)
 def test_csv_handoff_and_second_scaling_guard(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'out.csv';cmd=[sys.executable,str(S/'h2o2_foreground.py'),str(ROOT/'piezocatalysis-lca-modeling/assets/examples/synthetic-h2o2/case.json'),'--inventory-csv',str(path)]
   run=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(run.returncode,0,run.stderr)
   h=load_handoff(path,path.with_name(path.name+'.manifest.json'));self.assertEqual(h['amount_basis'],'per_functional_unit');self.assertEqual(h['product_basis'],'net_accumulated');self.assertEqual(len(h['rows']),5)
   with self.assertRaisesRegex(ValueError,'already scaled per functional unit'):audit(path,Path(tmp)/'absent.csv',Path(tmp)/'absent.json','fictional piezocatalytic H2O2','dry catalyst')
   run=subprocess.run(cmd,capture_output=True,text=True);self.assertNotEqual(run.returncode,0)

if __name__=='__main__':unittest.main()
