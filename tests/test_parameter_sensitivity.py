"""Scenario parameter validation with fictional model metadata."""
import sys
import unittest
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'piezocatalysis-lca-modeling/scripts'))
from parameter_sensitivity import resolve_change, compare_impacts, redacted_summary, metadata_fingerprint


class ParameterSensitivityTests(unittest.TestCase):
    def test_unknown_parameter_rejected_before_calculation(self):
        available=[{'name':'power','value':2.0,'context':{'@type':'Process','@id':'aaa'}}]
        with self.assertRaisesRegex(ValueError, 'not found'):
            resolve_change({'name':'missing','context_id':'aaa','value':4,'unit':'kW',
                            'source':'synthetic','evidence_class':'scenario'}, available)

    def test_bounds_protected_and_parameter_context(self):
        context={'@type':'Process','@id':'aaa'}
        params=[{'name':'reuse','value':2.0,'context':context,'isProtected':False}]
        change={'name':'reuse','context_id':'aaa','value':4,'unit':'uses','minimum':1,
                'source':'synthetic','evidence_class':'scenario'}
        self.assertEqual(resolve_change(change,params)['value'],4)
        with self.assertRaisesRegex(ValueError,'minimum'):
            resolve_change({**change,'value':0},params)
        with self.assertRaisesRegex(ValueError,'protected'):
            resolve_change(change,[{**params[0],'isProtected':True}])

    def test_impact_comparison_reports_delta_and_zero_baseline(self):
        category={'@id':'cat','name':'Synthetic impact','refUnit':'unit'}
        baseline=[{'category':category,'amount':0.0}]
        alternative=[{'category':category,'amount':2.0}]
        result=compare_impacts(baseline,alternative)[0]
        self.assertEqual(result['delta'],2)
        self.assertIsNone(result['change_percent'])

    def test_missing_impact_unit_rejected(self):
        category={'@id':'cat','name':'Synthetic impact'}
        with self.assertRaisesRegex(ValueError,'unit'):
            compare_impacts([{'category':category,'amount':1}], [{'category':category,'amount':2}])

    def test_shareable_summary_drops_model_identifiers_and_names(self):
        report={'baseline':{'impacts':[{'category':{'name':'private dataset'}}]},
                'cases':[{'id':'private case','comparison':[{'change_percent':25}]}]}
        summary=redacted_summary(report)
        self.assertNotIn('private',str(summary))
        self.assertEqual(summary['cases'][0]['percentage_changes'],[25])

    def test_database_metadata_fingerprint_changes_with_file_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'data').write_text('a')
            first=metadata_fingerprint(root)
            (root/'data').write_text('longer')
            self.assertNotEqual(first['sha256'], metadata_fingerprint(root)['sha256'])


if __name__ == '__main__':
    unittest.main()
