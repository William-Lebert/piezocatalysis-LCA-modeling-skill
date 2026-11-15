import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'piezocatalysis-lca-modeling/scripts'))
from result_coverage import contribution_summary, factors_for_selected, link_review

class CoverageTests(unittest.TestCase):
    def test_explicit_zero_factor_is_not_missing(self):
        cat={'impactFactors':[{'flow':{'@id':'zero'},'value':0.0},{'flow':{'@id':'positive'},'value':2.0}]}
        rows=factors_for_selected(cat,['zero','missing','positive'])
        self.assertEqual([r['status'] for r in rows],['explicit_zero_factor','no_factor_for_flow_uuid','factor_value_present'])
        self.assertEqual(rows[0]['matching_factors'][0]['value'],0.0)
    def test_cancellation_does_not_produce_misleading_percentages(self):
        impact={'amount':0.0,'contributions':[{'amount':2,'techFlow':{'provider':{'@id':'p'}}},{'amount':-2,'techFlow':{'provider':{'@id':'q'}}}]}
        s=contribution_summary(impact);self.assertTrue(s['has_positive_and_negative']);self.assertFalse(s['shares_available'])
        self.assertTrue(all(x['share_percent'] is None for x in s['contributions_by_absolute_amount']))
    def test_true_zero_and_positive_shares(self):
        s=contribution_summary({'amount':0.0,'contributions':[{'amount':0,'techFlow':{}}]})
        self.assertEqual(s['total'],0);self.assertFalse(s['shares_available'])
        s=contribution_summary({'amount':4,'contributions':[{'amount':1,'techFlow':{}},{'amount':3,'techFlow':{}}]})
        self.assertEqual([r['share_percent'] for r in s['contributions_by_absolute_amount']],[75,25])
    def test_unlinked_waste_is_separate_from_elementary_and_reference(self):
        system={'processes':[{'@id':'p'}],'processLinks':[]}
        proc={'exchanges':[{'internalId':1,'isQuantitativeReference':True,'flow':{'flowType':'PRODUCT_FLOW'}},
                           {'internalId':2,'isInput':False,'flow':{'@id':'w','flowType':'WASTE_FLOW'}},
                           {'internalId':3,'flow':{'@id':'e','flowType':'ELEMENTARY_FLOW'}}]}
        rows=link_review(system,{'p':proc})['technical_exchanges'];self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['status'],'unlinked_candidate');self.assertEqual(rows[0]['flow']['@id'],'w')
    def test_ambiguous_multiple_links_marked_for_review(self):
        link={'process':{'@id':'p'},'exchange':{'internalId':2},'flow':{'@id':'w'}}
        system={'processes':[{'@id':'p'}],'processLinks':[link,link]}
        proc={'exchanges':[{'internalId':2,'flow':{'@id':'w','flowType':'WASTE_FLOW'}}]}
        self.assertEqual(link_review(system,{'p':proc})['technical_exchanges'][0]['status'],'link_requires_review')

if __name__=='__main__':unittest.main()
