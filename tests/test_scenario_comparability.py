import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'piezocatalysis-lca-modeling/scripts'))
from scenario_comparability import assess, FIELDS

class ComparabilityTests(unittest.TestCase):
    def make_case(self):
        result={k:'same' for k in FIELDS};result['lcia_method_uuid']='11111111-1111-4111-8111-111111111111';return result
    def test_matching_declarations(self):
        a=self.make_case(); b=copy.deepcopy(a);a['id']='baseline';b['id']='alternative'
        self.assertEqual(assess({'cases':[a,b]})['status'],'declared_contexts_match')
    def test_boundary_method_and_fu_mismatch_block_ranking(self):
        a=self.make_case();b=copy.deepcopy(a);a['id']='one';b.update(id='two',functional_unit='different',system_boundary='different',lcia_method_uuid='22222222-2222-4222-8222-222222222222')
        r=assess({'cases':[a,b]});self.assertFalse(r['ranking_permitted_by_context_check'])
        self.assertEqual({x['field'] for x in r['issues']},{'functional_unit','system_boundary','lcia_method_uuid'})
    def test_missing_or_placeholder_is_not_a_match(self):
        a=self.make_case();b=copy.deepcopy(a);a['id']='one';b.update(id='two',geography='replace-me',database_version='')
        r=assess({'cases':[a,b]});self.assertFalse(r['ranking_permitted_by_context_check']);self.assertEqual(len(r['issues']),2)
    def test_h2o2_product_basis_mismatch_and_missing_are_blocked(self):
        a=self.make_case();b=copy.deepcopy(a);a.update(id='one',product_basis='net_accumulated');b.update(id='two',product_basis='recovered_product')
        self.assertFalse(assess({'cases':[a,b]})['ranking_permitted_by_context_check'])
        b.pop('product_basis');self.assertFalse(assess({'cases':[a,b]})['ranking_permitted_by_context_check'])

    def test_duplicate_ids_rejected(self):
        a=self.make_case();a['id']='same'
        with self.assertRaisesRegex(ValueError,'case IDs'):assess({'cases':[a,dict(a)]})
    def test_invalid_method_identifier_does_not_pass(self):
        a=self.make_case();b=copy.deepcopy(a);a['id']='one';b['id']='two';a['lcia_method_uuid']=b['lcia_method_uuid']='not-a-uuid'
        self.assertFalse(assess({'cases':[a,b]})['ranking_permitted_by_context_check'])

if __name__ == '__main__':unittest.main()
