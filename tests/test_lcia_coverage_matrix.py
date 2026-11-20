"""Check LCIA factor coverage with independent calculation and live entity fixtures."""
import copy
from pathlib import Path
import sys
import unittest
from collections import Counter
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'piezocatalysis-lca-modeling/scripts'))
from lcia_coverage_matrix import audit
from mapping_coverage import review_link
from openlca_readonly import IPCError


class Entities:
    def __init__(self, entities):
        self.entities = {entity['@id']: entity for entity in entities}
        self.reads = Counter()

    def call(self, operation, ref):
        if operation != 'data/get':
            raise AssertionError(operation)
        self.reads[ref['@type']] += 1
        return self.entities.get(ref['@id'])


class CoverageMatrixTests(unittest.TestCase):
    def setUp(self):
        method, climate, toxicity, carbon, resource, product, prop, unit, group = (
            str(UUID(int=n)) for n in range(1, 10))
        self.method_id, self.climate_id, self.toxicity_id = method, climate, toxicity
        self.flow_ids = [carbon, resource, product]
        carbon_ref = {'@id': carbon, 'name': 'Carbon dioxide, fossil',
                      'category': 'Elementary flows/Emission to air/unspecified', 'flowType': 'ELEMENTARY_FLOW'}
        resource_ref = {'@id': resource, 'name': 'Bismuth', 'flowType': 'ELEMENTARY_FLOW'}
        product_ref = {'@id': product, 'name': 'Bismuth nitrate pentahydrate', 'flowType': 'PRODUCT_FLOW'}
        basis = [{'isRefFlowProperty': True, 'flowProperty': {'@id': prop}}]
        factor = {'flow': carbon_ref, 'flowProperty': {'@id': prop}, 'unit': {'@id': unit}, 'value': 1.0}
        method_ref = {'@id': method, 'name': 'Example method'}
        climate_ref = {'@id': climate, 'name': 'Climate', 'refUnit': 'kg CO2 eq'}
        toxicity_ref = {'@id': toxicity, 'name': 'Toxicity', 'refUnit': 'kg DCB eq'}
        self.client = Entities([
            dict(method_ref, **{'@type': 'ImpactMethod', 'version': '1',
                                'impactCategories': [climate_ref, toxicity_ref]}),
            dict(climate_ref, **{'@type': 'ImpactCategory', 'impactFactors': [factor]}),
            dict(toxicity_ref, **{'@type': 'ImpactCategory', 'impactFactors':
                                 [dict(factor, value=0), dict(factor, flow=resource_ref, value=2)]}),
            dict(carbon_ref, **{'@type': 'Flow', 'flowProperties': basis}),
            dict(resource_ref, **{'@type': 'Flow', 'flowProperties': basis}),
            dict(product_ref, **{'@type': 'Flow'}),
            {'@type': 'FlowProperty', '@id': prop, 'unitGroup': {'@id': group}},
            {'@type': 'UnitGroup', '@id': group,
             'units': [{'@id': unit, 'name': 'kg', 'isRefUnit': True}]},
        ])
        self.calculation = {'impact_method': method_ref, 'setup': {'impactMethod': method_ref},
                            'impacts': [{'category': climate_ref}, {'category': toxicity_ref}],
                            'total_flows': [
                                {'enviFlow': {'flow': dict(carbon_ref, refUnit='kg'), 'isInput': False}, 'amount': 10},
                                {'enviFlow': {'flow': product_ref, 'isInput': True}, 'amount': 4},
                            ]}

    def test_factor_presence_is_independent_of_inventory_occurrence(self):
        matrix = audit(self.client, self.calculation, self.flow_ids)
        self.assertEqual(self.client.reads['FlowProperty'], 1)
        self.assertEqual(self.client.reads['UnitGroup'], 1)
        rows = [(c['status'], c['observed_in_inventory'], c['factor_value']) for c in matrix['checks']]
        self.assertEqual(rows, [
            ('factor_present', True, 1.0), ('explicit_zero_factor', True, 0),
            ('no_characterization_factor', False, None), ('factor_present', False, 2),
            ('not_applicable_technical_flow', True, None), ('not_applicable_technical_flow', True, None),
        ])
        self.assertEqual(matrix['flows'][0]['compartment'], 'Elementary flows/Emission to air/unspecified')
        self.assertEqual(matrix['flows'][2]['inventory_occurrences'][0]['enviFlow']['isInput'], True)

    def test_factor_needing_review_is_not_reported_as_covered(self):
        category = self.client.entities[self.climate_id]
        original = category['impactFactors'][0]
        for factors, expected in [
            ([dict(original, unit={'@id': 'different'})], 'factor_unit_or_property_unverified'),
            ([dict(original, location={'@id': 'location'})], 'regional_factor_requires_review'),
            ([dict(original, formula='a*2')], 'factor_formula_requires_evaluation'),
            ([dict(original, value=None)], 'factor_value_unavailable'),
            ([original, original], 'multiple_factors_review_required'),
        ]:
            with self.subTest(expected=expected):
                category['impactFactors'] = factors
                matrix = audit(self.client, self.calculation, self.flow_ids[:1], [self.climate_id])
                self.assertEqual(matrix['checks'][0]['status'], expected)
                self.assertIsNone(matrix['checks'][0]['factor_value'])

    def test_live_method_and_category_must_match_calculated_metadata(self):
        calculation = copy.deepcopy(self.calculation)
        calculation['impact_method']['version'] = 'old'
        with self.assertRaisesRegex(IPCError, 'method differs'):
            audit(self.client, calculation, self.flow_ids)
        self.client.entities[self.climate_id]['refUnit'] = 'unexpected'
        with self.assertRaisesRegex(IPCError, 'category differs'):
            audit(self.client, self.calculation, self.flow_ids)
        with self.assertRaisesRegex(IPCError, 'distinct categories'):
            audit(self.client, self.calculation, self.flow_ids, [self.climate_id, self.climate_id])

    def test_stale_inventory_reference_unit_cannot_use_current_factors(self):
        self.calculation['total_flows'][0]['enviFlow']['flow']['refUnit'] = 'g'
        with self.assertRaisesRegex(IPCError, 'reference unit differs'):
            audit(self.client, self.calculation, self.flow_ids)

    def test_link_requires_requested_consumer_unit_and_property(self):
        request = {'exchange_internal_id': 1, 'flow_uuid': 'flow', 'is_input': True,
                   'unit_uuid': 'kwh', 'flow_property_uuid': 'energy'}
        consumer = {'@id': 'consumer', 'exchanges': [
            {'internalId': 1, 'flow': {'@id': 'flow'}, 'isInput': True,
             'unit': {'@id': 'kwh'}, 'flowProperty': {'@id': 'energy'}}
        ]}
        system = {'processLinks': [{'process': {'@id': 'consumer'}, 'flow': {'@id': 'flow'},
                                    'provider': {'@id': 'provider'}, 'exchange': {'internalId': 1}}]}
        self.assertEqual(review_link(request, system, consumer, 'provider')['status'], 'linked_to_selected_provider')
        for field in ('unit_uuid', 'flow_property_uuid'):
            result = review_link(dict(request, **{field: 'wrong'}), system, consumer, 'provider')
            self.assertEqual(result, {'status': 'consumer_exchange_mismatch', 'field': field})


if __name__ == '__main__':
    unittest.main()
