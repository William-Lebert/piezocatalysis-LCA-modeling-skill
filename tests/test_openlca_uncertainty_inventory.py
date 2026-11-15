import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'piezocatalysis-lca-modeling/scripts'))
from openlca_uncertainty_inventory import count_uncertainty,inspect
from openlca_readonly import IPCError

class Client:
 def __init__(self):self.calls=[]
 def call(self,method,params):
  self.calls.append(method);typ=params['@type'];uid=params['@id']
  if typ=='ProductSystem':return {'@type':typ,'@id':uid,'processes':[{'@id':'p','name':'fictional'}]}
  if typ=='ImpactCategory':return {'@type':typ,'@id':uid,'impactFactors':[{}, {'uncertainty':{'distributionType':'NORMAL'}}]}
  if typ=='Process':return {'@type':typ,'@id':uid,'processType':'LCI_RESULT','exchanges':[{'isQuantitativeReference':True},{},{'uncertainty':{'distributionType':'LOG_NORMAL'}}]}
  raise AssertionError(typ)

class InventoryTests(unittest.TestCase):
 def test_selected_counts_and_read_only(self):
  c=Client();r=inspect(c,'s','i');self.assertEqual(r['processes'][0]['exchanges']['count'],2);self.assertEqual(r['processes'][0]['exchanges']['uncertainty_nonempty_count'],1)
  self.assertEqual(r['selected_category_factors']['uncertainty_nonempty_count'],1);self.assertEqual(set(c.calls),{'data/get'})
 def test_absent_uncertainty_not_misclassified_as_zero(self):
  r=count_uncertainty([{}, {'uncertainty':None}]);self.assertEqual(r['uncertainty_nonempty_count'],0);self.assertIn('does not mean zero',r['scope'])
 def test_missing_process_is_error(self):
  c=Client();old=c.call
  def call(method,params):return None if params['@type']=='Process' else old(method,params)
  c.call=call
  with self.assertRaises(IPCError):inspect(c,'s','i')

if __name__=='__main__':unittest.main()
