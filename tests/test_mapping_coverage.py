"""Independent synthetic reference exchange and characterization coverage cases."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'piezocatalysis-lca-modeling/scripts'))
from mapping_coverage import review_process, review_method, review_link


class MappingCoverageTests(unittest.TestCase):
    def setUp(self):
        self.process = {'@id':'p', 'name':'electricity', 'version':'1', 'location':{'name':'CN'}, 'processType':'LCI_RESULT',
            'exchanges':[{'isQuantitativeReference':True,'isInput':False,'flow':{'@id':'f','name':'electricity','flowType':'PRODUCT_FLOW'},
                          'flowProperty':{'@id':'prop'},'unit':{'@id':'u','name':'kWh'}}]}
        self.request = {'name':'electricity','process_version':'1','geography':'CN','reference_flow_uuid':'f','reference_product':'electricity',
                        'flow_property_uuid':'prop','unit_uuid':'u','reference_is_input':False,'foreground_unit':'MJ','conversion_factor':1/3.6}
        self.method = {'@id':'m','name':'method','version':'2','impactCategories':[{'@id':'c'}]}
        self.category = {'@id':'c','name':'climate','version':'1','impactFactors':[{'flow':{'@id':'co2'},'unit':{'@id':'kg'},'flowProperty':{'@id':'mass'},'value':1.0}]}
        self.mreq = {'method_name':'method','method_version':'2','categories':[{'category_uuid':'c','category_name':'climate','category_version':'1',
            'flows':[{'flow_uuid':'co2','unit_uuid':'kg','flow_property_uuid':'mass'}, {'flow_uuid':'other','unit_uuid':'kg','flow_property_uuid':'mass'}]}]}

    def test_conversion_and_metadata_with_no_inferred_provider(self):
        r=review_process(self.request,self.process)
        self.assertEqual(r['issues'],[])
        self.assertAlmostEqual(r['conversion_factor_calculated'],1/3.6)
        self.assertEqual(r['provider_link_status'],'not_checked')
        self.assertEqual(r['status'],'metadata_matches_review_required')

    def test_wrong_geography_reference_version_and_factor(self):
        q=dict(self.request,geography='GLO',reference_flow_uuid='old',process_version='0',conversion_factor=3.6)
        issues=review_process(q,self.process)['issues']
        self.assertTrue({'geography_mismatch','reference_flow_uuid_mismatch','process_version_mismatch','conversion_factor_mismatch'} <= set(issues))
        self.assertEqual(review_process(q,None)['status'],'process_not_found')

    def test_waste_reference_direction_and_missing_reference(self):
        p=copy.deepcopy(self.process); p['exchanges'][0]['isInput']=True; p['exchanges'][0]['flow']['flowType']='WASTE_FLOW'
        self.assertIn('reference_is_input_mismatch', review_process(self.request,p)['issues'])
        p['exchanges']=[]
        self.assertEqual(review_process(self.request,p)['status'],'reference_exchange_invalid')

    def test_factor_presence_missing_factor_and_unit_mismatch(self):
        r=review_method(self.mreq,self.method,{'c':self.category})
        self.assertEqual([f['status'] for f in r['categories'][0]['flows']],['factor_present','no_characterization_factor'])
        self.assertEqual(r['categories'][0]['flows'][0]['factor_value'],1.0)
        q=copy.deepcopy(self.mreq); q['categories'][0]['flows'][0]['unit_uuid']='wrong'
        self.assertEqual(review_method(q,self.method,{'c':self.category})['categories'][0]['flows'][0]['status'],'factor_unit_or_property_unverified')

    def test_method_version_and_category_membership(self):
        q=copy.deepcopy(self.mreq); q['method_version']='old'; q['categories'][0]['category_uuid']='other'
        r=review_method(q,self.method,{})
        self.assertIn('method_version_mismatch',r['issues'])
        self.assertEqual(r['categories'][0]['status'],'category_not_in_method')

    def test_zero_factor_is_present_not_missing(self):
        self.category['impactFactors'][0]['value']=0
        f=review_method(self.mreq,self.method,{'c':self.category})['categories'][0]['flows'][0]
        self.assertEqual((f['status'],f['factor_value']),('factor_present',0))

    def test_missing_factor_unit_and_property_are_not_verified_by_matching_nulls(self):
        self.category['impactFactors'][0].pop('unit'); self.category['impactFactors'][0].pop('flowProperty')
        q=copy.deepcopy(self.mreq);q['categories'][0]['flows'][0].pop('unit_uuid');q['categories'][0]['flows'][0].pop('flow_property_uuid')
        f=review_method(q,self.method,{'c':self.category})['categories'][0]['flows'][0]
        self.assertEqual(f['status'],'factor_unit_or_property_unverified')

    def test_formula_and_missing_factor_values_require_review(self):
        factor=self.category['impactFactors'][0];factor.pop('value')
        f=review_method(self.mreq,self.method,{'c':self.category})['categories'][0]['flows'][0]
        self.assertEqual(f['status'],'factor_value_unavailable')
        factor['formula']='x*2';factor['value']=1.0
        f=review_method(self.mreq,self.method,{'c':self.category})['categories'][0]['flows'][0]
        self.assertEqual(f['status'],'factor_formula_requires_evaluation')

    def test_provider_link_is_checked_for_specific_consumer_exchange(self):
        req={'exchange_internal_id':2,'flow_uuid':'f','is_input':True}
        consumer={'@id':'consumer','exchanges':[{'internalId':2,'flow':{'@id':'f'},'isInput':True}]}
        link={'process':{'@id':'consumer'},'provider':{'@id':'p'},'flow':{'@id':'f'},'exchange':{'internalId':2}}
        self.assertEqual(review_link(req,{'processLinks':[link]},consumer,'p')['status'],'linked_to_selected_provider')
        self.assertEqual(review_link(req,{'processLinks':[]},consumer,'p')['status'],'not_linked')
        self.assertEqual(review_link(req,{'processLinks':[link]},consumer,'other')['status'],'different_or_multiple_provider_links')
        self.assertEqual(review_link(dict(req,is_input=False),{'processLinks':[link]},consumer,'p')['status'],'consumer_exchange_mismatch')

if __name__ == '__main__': unittest.main()
