"""Exercise scenario changes independently of the openLCA integration."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'piezocatalysis-lca-modeling/scripts'))
from scenario_binding import check_fixed_foreground, check_links
from scenario_suite import activity_changes, check_recalculation, without_changes


def activity():
    return {'activity_id': 'ultrasound', 'status': 'preflight_matches_review_still_required',
            'stage': 'treatment', 'cycle_id': None, 'flow_name': 'electricity', 'direction': 'input',
            'unit': 'kWh', 'amount_per_functional_unit': 2, 'dataset_amount_per_functional_unit': 2,
            'mapping_user_asserted': {'rationale': 'regional scenario'},
            'actual_reference': {'process_uuid': 'national', 'reference_product': 'low-voltage electricity',
                                 'unit_name': 'kWh', 'geography': 'CN', 'reference_is_input': False,
                                 'flow_property_uuid': 'energy', 'unit_uuid': 'kwh'}}


def case(row, **change):
    inputs = {'foreground': 'input', 'inventory': 'inventory', 'manifest': 'manifest', 'mapping': 'mapping'}
    change = {'variable': 'power', 'setting': '120%', 'source': 'synthetic', 'activities': ['ultrasound'], **change}
    return {'inputs': inputs, 'capture': {'plan': {'rows': [row]}}, 'change': change}


class ScenarioSuiteTests(unittest.TestCase):
    def test_energy_change_must_match_declared_scope(self):
        source = {'power': {'value': 10}, 'duration': 60}
        alt = {'power': {'value': 12}, 'duration': 60}
        baseline = case(activity())
        higher = case(dict(activity(), amount_per_functional_unit=2.4),
                      kind='foreground', source_pointers=['/power'])
        actual, = activity_changes(baseline, higher, source, alt)
        self.assertEqual((actual['baseline_amount'], actual['scenario_amount']), (2, 2.4))
        with self.assertRaisesRegex(ValueError, 'declared source'):
            activity_changes(baseline, higher, source, dict(alt, duration=30))

    def test_provider_change_requires_same_product_unit_and_amount(self):
        source = {'power': 10}
        base = case(activity())
        row = activity()
        row['actual_reference'].update(process_uuid='regional', geography='CN-SWG')
        alt = case(row, kind='background')
        actual, = activity_changes(base, alt, source, source)
        self.assertEqual((actual['baseline_provider'], actual['scenario_provider']), ('national', 'regional'))
        row['actual_reference']['unit_uuid'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'preserve reference product'):
            activity_changes(base, alt, source, source)

    def test_negative_or_overlapping_pointer_is_rejected(self):
        with self.assertRaises(ValueError):
            without_changes({'cycle': [10, 20]}, ['/cycle/-1'])
        with self.assertRaises(ValueError):
            without_changes({'cycle': [10, 20]}, ['/cycle/0', '/cycle/0'])

    def test_fixed_foreground_records_stage_basis_and_rejects_hidden_elementary_flows(self):
        def exchange(flow, input_, reference=False):
            return {'flow': {'@id': flow, 'flowType': 'PRODUCT_FLOW'}, 'amount': 1,
                    'isInput': input_, 'isQuantitativeReference': reference,
                    'unit': {'@id': 'service'}, 'flowProperty': {'@id': 'basis'}}
        processes = {'root': {'exchanges': [exchange('fu', False, True), exchange('stage-ref', True)]},
                     'stage': {'exchanges': [exchange('stage-ref', False, True)]}}
        binding = {'root_uuid': 'root', 'stages': ['stage'], 'unit_uuid': 'service', 'property_uuid': 'basis'}
        self.assertEqual(check_fixed_foreground(processes, binding), {
            'stage': {'flow_uuid': 'stage-ref', 'unit_uuid': 'service', 'flow_property_uuid': 'basis'},
        })
        changed = deepcopy(processes)
        changed['stage']['exchanges'].append({'flow': {'flowType': 'ELEMENTARY_FLOW'}})
        with self.assertRaisesRegex(ValueError, 'technical exchanges'):
            check_fixed_foreground(changed, binding)

    def test_root_exchanges_are_bound_to_each_reference_provider(self):
        binding = {'root_uuid': 'root', 'system_uuid': 'system', 'stages': ['stage-a', 'stage-b'],
                   'unit_uuid': 'service', 'property_uuid': 'basis', 'activities': []}
        refs = {stage: {'flow_uuid': stage+'-output', 'unit_uuid': 'service',
                        'flow_property_uuid': 'basis'} for stage in binding['stages']}
        rows = [{'process': {'@id': 'root'}, 'is_input': True, 'amount': 1, 'status': 'linked',
                 'flow': {'@id': ref['flow_uuid']}, 'unit': {'@id': 'service'}, 'flow_property': {'@id': 'basis'},
                 'links': [{'provider': {'@id': stage}, 'flow': {'@id': ref['flow_uuid']}}]}
                for stage, ref in refs.items()]
        coverage = {'calculation': {'target': {'@id': 'system'},
                                    'setup': {'target': {'@id': 'system'}, 'amount': 1,
                                              'unit': {'@id': 'service'}, 'flowProperty': {'@id': 'basis'}}},
                    'link_review': {'technical_exchanges': rows}}
        plan = {'rows': []}
        self.assertEqual(check_links(plan, coverage, binding, strict_basis=True,
                                     stage_references=refs)['checked_activities'], 0)
        rows[0]['unit']['@id'] = 'different'
        with self.assertRaisesRegex(ValueError, 'root stage link differs'):
            check_links(plan, coverage, binding, strict_basis=True, stage_references=refs)
        rows[0]['unit']['@id'] = 'service'
        rows[0]['links'][0]['provider'], rows[1]['links'][0]['provider'] = (
            rows[1]['links'][0]['provider'], rows[0]['links'][0]['provider'])
        with self.assertRaisesRegex(ValueError, 'root stage link differs'):
            check_links(plan, coverage, binding, strict_basis=True, stage_references=refs)

    def test_recalculation_rejects_renamed_or_missing_cases(self):
        baseline = {'id': 'baseline', 'change': None, 'inputs': {}, 'binding': {}}
        alternative = {**baseline, 'id': 'power'}
        reference = {'configuration': {}, 'cases': [baseline, alternative]}
        for cases in ([baseline, dict(alternative, id='another')], [baseline]):
            with self.assertRaisesRegex(ValueError, 'case declarations'):
                check_recalculation(reference, {'configuration': {}, 'cases': cases})
