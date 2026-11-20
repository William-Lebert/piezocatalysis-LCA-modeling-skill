#!/usr/bin/env python3
"""Build an experimental foreground from an explicitly recorded catalyst campaign."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import sys

from audit_and_scale_inventory import UNITS, scaled_product, unit_factor
from experimental_foreground import CANONICAL, CONCENTRATION, CSV_FIELDS, POWER, TIME, quantity, units_for
from validate_inventory import EVIDENCE

TERMINAL_CATALYST_ACTIVITY = 'final-recovered-catalyst'


def q(item, label, units, positive=False):
    return quantity(item, label, units, positive=positive, allow_missing=True)


def finite_sum(values, label):
    if any(v is None for v in values):
        return None
    try:
        result = math.fsum(values)
    except OverflowError as exc:
        raise ValueError(f'{label}: overflow') from exc
    if not math.isfinite(result):
        raise ValueError(f'{label}: non-finite result')
    return result


def activity(entry, stage, cycle, ids, groups):
    if not isinstance(entry, dict):
        raise ValueError('activity must be an object')
    ident = entry.get('activity_id')
    if not isinstance(ident, str) or not ident.strip() or ident in ids or ident == TERMINAL_CATALYST_ACTIVITY:
        raise ValueError('activity_id must be unique and nonempty across the campaign')
    ids.add(ident)
    name, direction, kind = entry.get('flow_name'), entry.get('direction'), entry.get('kind')
    if not isinstance(name, str) or not name.strip() or direction not in ('input', 'output') or kind not in ('energy', 'material', 'waste'):
        raise ValueError(f'{ident}: flow_name, direction and kind (energy/material/waste) required')
    if kind == 'waste' and direction != 'output':
        raise ValueError(f'{ident}: waste activity must be an output')
    if kind in ('energy', 'material') and direction != 'input':
        raise ValueError(f'{ident}: energy/material activity must be an input')
    # Catalyst replenishment and final recovered catalyst have dedicated fields.
    if entry.get('is_catalyst') is True:
        raise ValueError(f'{ident}: catalyst replenishment/disposal belongs in catalyst accounting fields')
    included = entry.get('included', True)
    if not isinstance(included, bool):
        raise ValueError(f'{ident}: included must be boolean')
    note = entry.get('note', '')
    if not included and not note:
        raise ValueError(f'{ident}: excluded activity requires a note')
    group = entry.get('overlap_group', '')
    if group and included:
        if not isinstance(group, str) or group in groups:
            raise ValueError(f'{ident}: duplicate overlap_group')
        groups.add(group)
    if 'quantity' in entry:
        if 'power' in entry or 'duration' in entry:
            raise ValueError(f'{ident}: provide quantity or power and duration, not both')
        value = entry['quantity']; unit = value.get('unit')
        if unit not in UNITS:
            raise ValueError(f'{ident}: unsupported unit')
        amount = q(value, ident, {unit: 1.0})
        source, evidence, derivation = value['source'], value['evidence_class'], None
    else:
        power, duration = entry.get('power'), entry.get('duration')
        p = q(power, ident + ' power', POWER)
        t = q(duration, ident + ' duration', TIME)
        amount = None if p is None or t is None else scaled_product(p, t, ident)
        unit, evidence = 'kWh', 'calculated'
        source = 'power: ' + power['source'] + '; duration: ' + duration['source']
        derivation = {'power': power, 'duration': duration}
    if kind == 'energy' and UNITS[unit][0] != 'energy':
        raise ValueError(f'{ident}: energy activity needs an energy unit')
    return {'activity_id': ident, 'stage': stage, 'cycle': cycle, 'flow_name': name,
            'direction': direction, 'kind': kind, 'value': amount, 'unit': unit,
            'source': source, 'evidence_class': evidence, 'dataset_mapping': entry.get('dataset_mapping', ''),
            'included': included, 'note': note, 'overlap_group': group, 'derivation': derivation}


def build(data):
    if not isinstance(data, dict) or any(not isinstance(data.get(k), str) or not data[k].strip() for k in ('system', 'boundary')):
        raise ValueError('system and boundary are required')
    mass = units_for('mass'); volume_units = units_for('volume')
    basis = data.get('catalyst_mass_basis')
    if basis not in ('dry', 'wet', 'unknown'):
        raise ValueError('catalyst_mass_basis must be dry, wet or unknown')
    dry_yield = q(data.get('dry_yield'), 'dry_yield', mass, positive=True)
    target_g = quantity(data.get('treatment_target'), 'treatment_target', mass, positive=True)
    target_mg = scaled_product(target_g, 1000, 'target mg')
    initial = q(data.get('initial_catalyst'), 'initial_catalyst', mass, positive=True)
    cycles = data.get('cycles')
    if not isinstance(cycles, list) or not cycles:
        raise ValueError('at least one cycle is required')
    ids, groups, cycle_ids = set(), set(), set()
    prep_entries = data.get('preparation_activities')
    if not isinstance(prep_entries, list) or not prep_entries:
        raise ValueError('at least one preparation activity is required')
    preparation = [activity(x, 'preparation', None, ids, groups) for x in prep_entries]
    treatments, reports, additions, prev_recovered = [], [], [], None
    for index, cycle in enumerate(cycles):
        label = cycle.get('cycle_id') if isinstance(cycle, dict) else None
        if not isinstance(label, str) or not label.strip() or label in cycle_ids:
            raise ValueError('cycle_id must be unique and nonempty')
        cycle_ids.add(label)
        add = q(cycle.get('catalyst_added'), label + ' catalyst_added', mass)
        loaded = q(cycle.get('catalyst_loaded'), label + ' catalyst_loaded', mass, positive=True)
        recovered = q(cycle.get('catalyst_recovered'), label + ' catalyst_recovered', mass)
        additions.append(add)
        prior = initial if index == 0 else prev_recovered
        expected = None if prior is None or add is None else finite_sum([prior, add], 'catalyst continuity')
        continuity = None if expected is None or loaded is None else math.isclose(expected, loaded, rel_tol=1e-7, abs_tol=1e-12)
        if continuity is False:
            raise ValueError(f'{label}: catalyst loaded disagrees with prior recovered plus added')
        if loaded is not None and recovered is not None and recovered > loaded and not math.isclose(recovered, loaded, rel_tol=1e-7, abs_tol=1e-12):
            raise ValueError(f'{label}: recovered catalyst exceeds loaded mass')
        loss = None if loaded is None or recovered is None else max(0.0, loaded - recovered)
        prev_recovered = recovered
        vin = q(cycle.get('influent_volume'), label + ' influent_volume', volume_units, positive=True)
        vout = q(cycle.get('effluent_volume'), label + ' effluent_volume', volume_units, positive=True)
        cin = q(cycle.get('influent_concentration'), label + ' influent_concentration', CONCENTRATION)
        eff = cycle.get('effluent_concentration')
        qualifier = eff.get('qualifier', 'exact') if isinstance(eff, dict) else None
        if qualifier not in ('exact', 'missing', 'below_lod', 'below_loq'):
            raise ValueError(f'{label}: invalid effluent qualifier')
        cout = q(eff, label + ' effluent_concentration', CONCENTRATION)
        if qualifier != 'exact' and cout is not None:
            raise ValueError(f'{label}: censored or missing effluent must have null value')
        incoming = None if vin is None or cin is None else scaled_product(vin, cin, label + ' incoming mass')
        outgoing = None if vout is None or cout is None else scaled_product(vout, cout, label + ' outgoing mass')
        exact = None if incoming is None or outgoing is None or qualifier != 'exact' else finite_sum([incoming, -outgoing], label + ' apparent removal')
        interval = None
        if qualifier in ('below_lod', 'below_loq'):
            limit = quantity({**eff, 'value': eff.get('limit')}, label + ' limit', CONCENTRATION, positive=True)
            if incoming is not None and vout is not None:
                interval = [finite_sum([incoming, -scaled_product(limit, vout, label + ' limit mass')], label + ' lower bound'), incoming]
        elif exact is not None:
            interval = [exact, exact]
        acts = cycle.get('activities')
        if not isinstance(acts, list):
            raise ValueError(f'{label}: activities must be a list')
        treatments.extend(activity(a, 'treatment', label, ids, groups) for a in acts)
        reports.append({'cycle_id': label, 'catalyst_added_g': add, 'catalyst_loaded_g': loaded,
                        'catalyst_recovered_g': recovered, 'catalyst_unaccounted_g': loss,
                        'catalyst_continuity_verified': continuity, 'influent_mass_mg': incoming,
                        'effluent_mass_mg': outgoing, 'apparent_removal_mg': exact,
                        'apparent_removal_interval_mg': interval, 'effluent_qualifier': qualifier,
                        'observations': cycle})
    destination = data.get('final_recovered_destination')
    if destination not in ('disposed', 'retained', 'unknown'):
        raise ValueError('final_recovered_destination must be disposed, retained or unknown')
    fate = data.get('final_recovered_fate')
    if 'final_recovered_fate' in data:
        text_fields = ('route', 'source')
        if (destination == 'unknown' or not isinstance(fate, dict)
                or any(not isinstance(fate.get(key), str) or not fate[key].strip()
                       or 'replace-me' in fate[key].lower() for key in text_fields)
                or fate.get('evidence_class') not in EVIDENCE):
            raise ValueError('final_recovered_fate requires a known destination, route, source and evidence_class')
        fate = {key: fate[key].strip() for key in (*text_fields, 'evidence_class')}
    fresh = finite_sum([initial] + additions, 'fresh catalyst')
    unaccounted = finite_sum([r['catalyst_unaccounted_g'] for r in reports], 'campaign unaccounted catalyst')
    total_removed = finite_sum([r['apparent_removal_mg'] for r in reports], 'campaign removal')
    intervals = [r['apparent_removal_interval_mg'] for r in reports]
    total_interval = ([finite_sum([x[0] for x in intervals], 'removal lower'),
                       finite_sum([x[1] for x in intervals], 'removal upper')] if all(x is not None for x in intervals) else None)
    scale = None if total_removed is None or total_removed <= 0 else target_mg / total_removed
    batches = None if fresh is None or dry_yield is None or basis != 'dry' else fresh / dry_yield
    if any(x is not None and (not math.isfinite(x) or x < 0) for x in (scale, batches)):
        raise ValueError('invalid campaign scaling')
    results = []
    for item in preparation + treatments:
        factor = None if scale is None else (None if batches is None else scale * batches) if item['stage'] == 'preparation' else scale
        unit = CANONICAL[UNITS[item['unit']][0]]
        amount = None if item['value'] is None or factor is None else scaled_product(item['value'], factor * unit_factor(item['unit'], unit), item['activity_id'])
        results.append({**item, 'campaign_value': item['value'], 'campaign_unit': item['unit'], 'amount': amount, 'unit': unit})
    if destination == 'disposed':
        amount = None
        if basis == 'dry' and prev_recovered is not None and scale is not None:
            amount = scaled_product(prev_recovered, scale, 'final catalyst disposal')
        source = 'final recovered catalyst: ' + cycles[-1]['catalyst_recovered']['source']
        note = 'disposal route must be mapped'
        if fate is not None:
            source += '; destination evidence: ' + fate['source']
            note = 'Declared disposal route: ' + fate['route'] + ' (' + fate['evidence_class'] + ')'
        results.append({'activity_id': TERMINAL_CATALYST_ACTIVITY, 'stage': 'treatment', 'cycle': reports[-1]['cycle_id'],
                        'flow_name': 'final recovered catalyst for disposal', 'direction': 'output', 'kind': 'waste',
                        'amount': amount, 'unit': 'g', 'source': source,
                        'evidence_class': 'calculated', 'dataset_mapping': '', 'included': True, 'note': note,
                        'overlap_group': '', 'derivation': None, 'campaign_value': prev_recovered, 'campaign_unit': 'g'})
    warnings = []
    observed_flows = set()
    for item in preparation + treatments:
        key = (item['stage'], item['cycle'], item['flow_name'].casefold(), item['direction'])
        if item['included'] and key in observed_flows:
            warnings.append(f"{item['activity_id']}: repeated flow in one stage/cycle; check double counting.")
        if item['included']:
            observed_flows.add(key)
    if scale is None: warnings.append('Exact positive campaign removal unavailable; no functional-unit scaling is calculated.')
    if batches is None: warnings.append('Fresh catalyst allocation unavailable; preparation amounts remain unknown.')
    if basis != 'dry': warnings.append('Catalyst masses are not declared dry; they cannot be divided by dry yield without conversion.')
    if any(r['catalyst_continuity_verified'] is None for r in reports): warnings.append('Some catalyst continuity checks are unavailable.')
    if destination == 'unknown': warnings.append('Final recovered catalyst destination is unknown.')
    if destination == 'disposed' and basis != 'dry':
        warnings.append('Final disposal amount is unavailable on a dry mass basis.')
    if any(r['catalyst_unaccounted_g'] is None or r['catalyst_unaccounted_g'] > 0 for r in reports):
        warnings.append('Catalyst losses are unaccounted mass; their destination is not assumed.')
    if any(r['amount'] is None for r in results if r['included']): warnings.append('Some included inventory amounts are unknown.')
    return {'system': data['system'], 'boundary': data['boundary'], 'functional_unit': data['treatment_target'],
            'campaign': {'cycle_count': len(cycles), 'catalyst_mass_basis': basis, 'initial_catalyst_g': initial, 'fresh_catalyst_g': fresh,
                         'preparation_batches': batches, 'apparent_removal_mg': total_removed,
                         'apparent_removal_interval_mg': total_interval, 'campaigns_per_functional_unit': scale,
                         'final_recovered_g': prev_recovered, 'final_recovered_destination': destination,
                         'final_recovered_fate': fate, 'unaccounted_catalyst_g': unaccounted,
                         'input_evidence': {'initial_catalyst': data['initial_catalyst'], 'dry_yield': data['dry_yield']},
                         'allocation_note': 'Allocate all initial and added fresh catalyst to this campaign; no credit for retained residual. Scaling repeats the complete campaign fractionally.'},
            'cycles': reports, 'functional_unit_flows': results, 'warnings': warnings,
            'interpretation': 'Water-phase mass change only; no assertion of mineralization or complete mass balance.'}


def check_disposal_evidence(expected_campaign, declared_campaign):
    """Keep explicit disposal evidence tied to the foreground that produced it."""
    declared = declared_campaign or {}
    if expected_campaign.get('final_recovered_fate') is None and declared.get('final_recovered_fate') is None:
        return
    fields = ('catalyst_mass_basis', 'final_recovered_destination', 'final_recovered_fate')
    if any(expected_campaign.get(key) != declared.get(key) for key in fields):
        raise ValueError('disposal evidence in the inventory manifest differs from the foreground')


def write_inventory(result, raw, input_name, inventory_path):
    manifest_path = inventory_path.with_name(inventory_path.name + '.manifest.json')
    if inventory_path.exists() or manifest_path.exists():
        raise FileExistsError('inventory or associated manifest already exists')
    with io.StringIO(newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS + ['cycle_id', 'inventory_schema_version', 'amount_basis']); writer.writeheader()
        for flow in result['functional_unit_flows']:
            writer.writerow({'system': result['system'], 'stage': flow['stage'], 'flow_name': flow['flow_name'],
                'amount': flow['amount'], 'unit': flow['unit'], 'direction': flow['direction'],
                'evidence_class': flow['evidence_class'], 'source': flow['source'],
                'dataset_mapping': flow['dataset_mapping'], 'included': str(flow['included']).lower(),
                'note': flow['note'], 'activity_id': flow['activity_id'], 'overlap_group': flow['overlap_group'], 'cycle_id': flow['cycle'] or '',
                'inventory_schema_version': 'piezolca.inventory/2', 'amount_basis': 'per_functional_unit'})
        csv_bytes = f.getvalue().encode('utf-8')
    scripts = Path(__file__).resolve().parent
    manifest = {'schema_version': 'piezolca.inventory-manifest/1',
                'inventory_schema_version': 'piezolca.inventory/2', 'amount_basis': 'per_functional_unit',
                'inventory_sha256': hashlib.sha256(csv_bytes).hexdigest(),
                'input_sha256': hashlib.sha256(raw).hexdigest(), 'input_name': input_name,
                'generator': 'cyclic_foreground', 'generator_version': '1.0.0',
                'code_sha256': {name: hashlib.sha256((scripts / name).read_bytes()).hexdigest() for name in
                                ('cyclic_foreground.py', 'experimental_foreground.py', 'audit_and_scale_inventory.py', 'validate_inventory.py')},
                'system': result['system'], 'boundary': result['boundary'],
                'functional_unit_type': 'apparent_pollutant_removal', 'functional_unit': result['functional_unit'],
                'scaling': {'campaigns_per_functional_unit': result['campaign']['campaigns_per_functional_unit'],
                            'allocation_note': result['campaign']['allocation_note']},
                'campaign': {'catalyst_mass_basis': result['campaign']['catalyst_mass_basis'],
                             'final_recovered_destination': result['campaign']['final_recovered_destination'],
                             'loss_g_by_cycle': [{'cycle_id': c['cycle_id'], 'loss_g': c['catalyst_unaccounted_g']} for c in result['cycles']]},
                'warnings': result['warnings']}
    if result['campaign']['final_recovered_fate'] is not None:
        manifest['campaign']['final_recovered_fate'] = result['campaign']['final_recovered_fate']
    with inventory_path.open('xb') as f:
        f.write(csv_bytes)
    with manifest_path.open('x', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, allow_nan=False); f.write('\n')
    return manifest_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--inventory-csv', type=Path, help='write a new functional-unit inventory CSV')
    args = parser.parse_args()
    try:
        def bad(value): raise ValueError('invalid JSON number: ' + value)
        raw = args.input.read_bytes()
        result = build(json.loads(raw, parse_constant=bad))
        if args.inventory_csv:
            write_inventory(result, raw, args.input.name, args.inventory_csv)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)); return 0
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, OverflowError, ZeroDivisionError) as exc:
        print('ERROR:', exc, file=sys.stderr); return 1


if __name__ == '__main__': sys.exit(main())
