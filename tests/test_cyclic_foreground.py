"""Physical and functional-unit checks using fictional cycle observations."""
import copy
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'piezocatalysis-lca-modeling'
sys.path.insert(0, str(SKILL / 'scripts'))
from cyclic_foreground import build
from experimental_foreground import build as legacy_build

EXAMPLES = SKILL / 'assets/examples/synthetic-cycles'


def case(name):
    return json.loads((EXAMPLES / (name + '.json')).read_text())


class CyclicForegroundTests(unittest.TestCase):
    def test_constant_campaign_matches_legacy_scaling(self):
        result = build(case('constant'))
        legacy = legacy_build(json.loads((SKILL/'assets/examples/synthetic-foreground/case-a.json').read_text()))
        self.assertEqual(result['campaign']['apparent_removal_mg'],20)
        self.assertEqual(result['campaign']['campaigns_per_functional_unit'],5)
        self.assertAlmostEqual(result['campaign']['preparation_batches']*5,legacy['treatment']['preparation_batches'])
        new = result['functional_unit_flows']
        old = {r['activity_id']:r for r in legacy['treatment']['flows']}
        self.assertAlmostEqual(next(r['amount'] for r in new if r['activity_id']=='prep-electricity'),old['prep-energy']['amount'])
        self.assertAlmostEqual(sum(r['amount'] for r in new if r['activity_id'].startswith('ultrasound-')),old['ultrasound']['amount'])
        self.assertEqual(next(r['amount'] for r in new if r['activity_id']=='final-recovered-catalyst'),5)

    def test_variable_exact_mass_units_and_allocation(self):
        r=build(case('variable-exact')); c=r['campaign']; flows={x['activity_id']:x for x in r['functional_unit_flows']}
        self.assertEqual([x['apparent_removal_mg'] for x in r['cycles']],[10,8,9])
        self.assertAlmostEqual(c['fresh_catalyst_g'],1.3)
        self.assertAlmostEqual(c['preparation_batches'],0.26)
        self.assertEqual(c['campaigns_per_functional_unit'],2)
        self.assertAlmostEqual(flows['precursor']['amount'],5.2)
        self.assertAlmostEqual(flows['regen-reagent-2']['amount'],0.1)
        self.assertAlmostEqual(flows['regen-energy-2']['amount'],0.1)
        self.assertAlmostEqual(flows['final-recovered-catalyst']['amount'],1)
        self.assertAlmostEqual(sum(x['catalyst_unaccounted_g'] for x in r['cycles']),0.8)
        self.assertTrue(all(x['catalyst_continuity_verified'] for x in r['cycles']))

    def test_censored_measurement_preserves_bounds_and_does_not_scale(self):
        r=build(case('variable-censored'))
        self.assertEqual(r['cycles'][2]['apparent_removal_interval_mg'],[9,12])
        self.assertEqual(r['campaign']['apparent_removal_interval_mg'],[27,30])
        self.assertIsNone(r['campaign']['apparent_removal_mg'])
        self.assertIsNone(r['campaign']['campaigns_per_functional_unit'])
        self.assertTrue(all(x['amount'] is None for x in r['functional_unit_flows']))

    def test_missing_recovery_is_unknown_not_zero(self):
        d=case('variable-exact');d['cycles'][0]['catalyst_recovered']['value']=None
        r=build(d)
        self.assertIsNone(r['cycles'][0]['catalyst_unaccounted_g'])
        self.assertIsNone(r['cycles'][1]['catalyst_continuity_verified'])
        self.assertTrue(any('continuity' in x for x in r['warnings']))

    def test_invalid_mass_continuity_and_excess_recovery_rejected(self):
        d=case('variable-exact');d['cycles'][1]['catalyst_loaded']['value']=1.2
        with self.assertRaisesRegex(ValueError,'loaded disagrees'):build(d)
        d=case('constant');d['cycles'][1]['catalyst_recovered']['value']=1.1
        with self.assertRaisesRegex(ValueError,'recovered catalyst exceeds'):build(d)

    def test_terminal_fate_preserves_basis_source_and_unexplained_losses(self):
        data = case('variable-exact')
        data['final_recovered_fate'] = {'route': 'Fictional incineration',
                                        'source': 'Synthetic disposal sheet R2',
                                        'evidence_class': 'scenario'}
        result = build(data)
        terminal = next(flow for flow in result['functional_unit_flows']
                        if flow['activity_id'] == 'final-recovered-catalyst')
        self.assertAlmostEqual(terminal['amount'], 1)
        self.assertIn('Synthetic disposal sheet R2', terminal['source'])
        self.assertAlmostEqual(result['campaign']['unaccounted_catalyst_g'], 0.8)
        for basis in ('wet', 'unknown'):
            with self.subTest(basis=basis):
                result = build(dict(data, catalyst_mass_basis=basis))
                terminal = next(flow for flow in result['functional_unit_flows']
                                if flow['activity_id'] == 'final-recovered-catalyst')
                self.assertIsNone(terminal['amount'])
        with self.assertRaisesRegex(ValueError, 'final_recovered_fate'):
            build(dict(data, final_recovered_destination='unknown'))
        with self.assertRaisesRegex(ValueError, 'final_recovered_fate'):
            build(dict(data, final_recovered_fate={'route': 'Fictional incineration'}))

    def test_no_silent_loss_disposal_or_reuse_credit(self):
        d=case('variable-exact');d['final_recovered_destination']='retained'
        r=build(d)
        self.assertFalse(any(x['activity_id']=='final-recovered-catalyst' for x in r['functional_unit_flows']))
        self.assertAlmostEqual(r['campaign']['fresh_catalyst_g'],1.3)
        self.assertTrue(any('unaccounted mass' in x for x in r['warnings']))

    def test_wet_catalyst_is_not_divided_by_dry_yield(self):
        d=case('constant');d['catalyst_mass_basis']='wet'
        r=build(d)
        self.assertIsNone(r['campaign']['preparation_batches'])
        self.assertIsNone(next(x['amount'] for x in r['functional_unit_flows'] if x['activity_id']=='precursor'))
        self.assertTrue(any('not declared dry' in x for x in r['warnings']))

    def test_missing_volume_and_negative_net_removal(self):
        d=case('constant');d['cycles'][0]['effluent_volume']['value']=None
        r=build(d);self.assertIsNone(r['cycles'][0]['apparent_removal_mg']);self.assertIsNone(r['campaign']['campaigns_per_functional_unit'])
        d=case('constant');d['cycles'][0]['effluent_concentration']['value']=100;d['cycles'][1]['effluent_concentration']['value']=100
        r=build(d);self.assertEqual(r['campaign']['apparent_removal_mg'],-160);self.assertIsNone(r['campaign']['campaigns_per_functional_unit'])

    def test_duplicate_activities_and_catalyst_counting_blocked(self):
        d=case('constant');d['cycles'][1]['activities'][0]['activity_id']='ultrasound-1'
        with self.assertRaisesRegex(ValueError,'activity_id'):build(d)
        d=case('constant');d['cycles'][0]['activities'][1]['is_catalyst']=True
        with self.assertRaisesRegex(ValueError,'catalyst replenishment'):build(d)
        d=case('constant');d['cycles'][0]['activities'][0]['overlap_group']='meter';d['cycles'][0]['activities'][1]['overlap_group']='meter'
        with self.assertRaisesRegex(ValueError,'overlap_group'):build(d)
        d=case('constant'); duplicate=copy.deepcopy(d['cycles'][0]['activities'][0]);duplicate['activity_id']='other-meter'
        d['cycles'][0]['activities'].append(duplicate)
        self.assertTrue(any('repeated flow' in x for x in build(d)['warnings']))

    def test_csv_is_functional_unit_inventory_and_validator_accepts_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'inventory.csv'
            p=subprocess.run([sys.executable,str(SKILL/'scripts/cyclic_foreground.py'),str(EXAMPLES/'variable-exact.json'),'--inventory-csv',str(output)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            p=subprocess.run([sys.executable,str(SKILL/'scripts/validate_inventory.py'),str(output)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            with output.open() as f:rows=list(csv.DictReader(f))
            self.assertEqual(float(next(x for x in rows if x['activity_id']=='regen-reagent-2')['amount']),0.1)

    def test_censored_csv_preserves_empty_amounts_and_is_rejected_by_inventory_validator(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'unknown.csv'
            run=subprocess.run([sys.executable,str(SKILL/'scripts/cyclic_foreground.py'),str(EXAMPLES/'variable-censored.json'),
                                '--inventory-csv',str(output)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
            with output.open() as f: rows=list(csv.DictReader(f))
            self.assertTrue(all(row['amount']=='' for row in rows))
            validation=subprocess.run([sys.executable,str(SKILL/'scripts/validate_inventory.py'),str(output)],capture_output=True,text=True)
            self.assertNotEqual(validation.returncode,0)

if __name__=='__main__': unittest.main()
