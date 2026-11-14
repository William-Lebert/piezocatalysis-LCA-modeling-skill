import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'piezocatalysis-lca-modeling/scripts'))
from uncertainty_readiness import assess
from synthetic_joint_uncertainty import run


def record(id):
    return {'id':id,'unit':'kW','source':'synthetic evidence','geography':'synthetic','time_scope':'synthetic',
            'evidence_class':'scenario','sample_count':None,'distribution':{'type':'empirical_joint','basis':'fictional paired states'},'censoring':'none'}


def good():
    return {'parameters':[record('power'),record('duration')], 'dependencies_reviewed':True,
            'dependencies':[{'parameters':['power','duration'],'relation':'joint','basis':'fictional paired states'}],
            'coverage':{'system_boundary_complete':True,'background_uncertainty_reviewed':True,'background_uncertainty_represented':True,'impact_method_reviewed':True}}


class UncertaintyReadinessTests(unittest.TestCase):
    def test_complete_declarations_are_only_ready_for_method_review(self):
        result=assess(good());self.assertEqual(result['status'],'declared_inputs_ready_for_method_review')
        self.assertEqual(len(result['warnings']),2)
    def test_missing_distribution_dependency_and_background_block(self):
        x=good();x['parameters'][0]['distribution']={'type':'unknown'};x['dependencies'][0]['relation']='unknown';x['coverage']['background_uncertainty_reviewed']=False
        r=assess(x);self.assertEqual(r['status'],'evidence_gaps');self.assertEqual(len(r['issues']),3)
    def test_detection_limit_needs_value_and_treatment(self):
        x=good();x['parameters'][0]['censoring']='below_loq';r=assess(x)
        self.assertEqual({i.get('field') for i in r['issues']},{'detection_limit','censoring_treatment'})
    def test_unknown_data_and_correlation_not_zero(self):
        x=good();x['parameters'][0]['censoring']='missing';x['dependencies_reviewed']=False
        r=assess(x);self.assertEqual({i.get('field') for i in r['issues']},{'observation','dependencies_reviewed'})
    def test_fixed_assumption_and_low_replicates_visible(self):
        x=good();x['parameters'][0].update(evidence_class='measured',sample_count=1,distribution={'type':'fixed','basis':'instrument reported only as fixed'})
        statuses={v['status'] for v in assess(x)['warnings']};self.assertIn('fixed_conditionally_no_uncertainty_propagated',statuses);self.assertIn('limited_or_missing_replicate_information',statuses)
    def test_duplicate_or_invalid_dependency_rejected(self):
        x=good();x['dependencies'].append(copy.deepcopy(x['dependencies'][0]))
        with self.assertRaisesRegex(ValueError,'duplicate'):assess(x)


class SyntheticJointTests(unittest.TestCase):
    def example(self):
        p=Path(__file__).resolve().parents[1]/'piezocatalysis-lca-modeling/assets/examples/synthetic-uncertainty/joint-demo.json'
        return json.loads(p.read_text())
    def test_seeded_run_matches_exact_joint_moments(self):
        d=self.example();a=run(d);self.assertEqual(a,run(d));self.assertEqual(a['analytical_mean'],3.5)
        self.assertEqual(a['analytical_population_standard_deviation'],.5);self.assertAlmostEqual(a['sample_mean'],3.5,delta=.03)
        self.assertEqual(sum(a['state_counts'].values()),10000)
    def test_independence_changes_joint_distribution(self):
        d=self.example();d['joint_states']=[{'id':str(i),'probability':.25,'paired_inputs':{'p':p,'t':t},'response':p*t+p} for i,(p,t) in enumerate([(1,1),(1,2),(2,1),(2,2)])]
        self.assertEqual(run(d)['analytical_mean'],3.75)
        self.assertNotEqual(run(d)['analytical_mean'],run(self.example())['analytical_mean'])
    def test_not_synthetic_and_invalid_probability_rejected(self):
        d=self.example();d['purpose']='real_study'
        with self.assertRaisesRegex(ValueError,'synthetic'):run(d)
        d=self.example();d['joint_states'][0]['probability']=.8
        with self.assertRaisesRegex(ValueError,'sum to 1'):run(d)
    def test_incomplete_or_nonfinite_paired_state_rejected(self):
        d=self.example();d['joint_states'][1]['paired_inputs'].pop('duration')
        with self.assertRaisesRegex(ValueError,'same paired inputs'):run(d)
        d=self.example();d['joint_states'][1]['paired_inputs']['duration']=float('nan')
        with self.assertRaisesRegex(ValueError,'finite numeric'):run(d)

if __name__=='__main__':unittest.main()
