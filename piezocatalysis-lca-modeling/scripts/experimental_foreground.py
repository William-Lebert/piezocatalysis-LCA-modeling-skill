#!/usr/bin/env python3
"""Build traceable experimental foreground inventories for two functional-unit families."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import sys

from audit_and_scale_inventory import UNITS, number, scaled_product, unit_factor
from validate_inventory import EVIDENCE

CONCENTRATION = {'mg/L': 1.0, 'ug/L': 0.001, 'µg/L': 0.001, 'μg/L': 0.001, 'g/L': 1000.0}
POWER = {'W': 0.001, 'kW': 1.0}
TIME = {'min': 1 / 60, 'h': 1.0}
CANONICAL = {'mass': 'g', 'volume': 'L', 'energy': 'kWh'}
CSV_FIELDS = ['system', 'stage', 'flow_name', 'amount', 'unit', 'direction', 'evidence_class',
              'source', 'dataset_mapping', 'included', 'note', 'activity_id', 'overlap_group']


def quantity(item, label, unit_factors, *, positive=False, allow_missing=False):
    if not isinstance(item, dict):
        raise ValueError(f'{label}: quantity object is required')
    unit, source, evidence = item.get('unit'), item.get('source'), item.get('evidence_class')
    if unit not in unit_factors or not isinstance(source, str) or not source.strip() or evidence not in EVIDENCE:
        raise ValueError(f'{label}: supported unit, source and evidence_class are required')
    value = item.get('value')
    if value is None and allow_missing:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{label}: value must be a JSON number')
    value = number(value, label, positive=positive)
    return scaled_product(value, unit_factors[unit], label)


def units_for(dimension):
    return {unit: factor for unit, (kind, factor) in UNITS.items() if kind == dimension}


def build(data):
    if not isinstance(data, dict) or not isinstance(data.get('system'), str) or not data['system'].strip():
        raise ValueError('system is required')
    if not isinstance(data.get('boundary'), str) or not data['boundary'].strip():
        raise ValueError('boundary is required')
    yield_g = quantity(data.get('dry_yield'), 'dry_yield', units_for('mass'), positive=True, allow_missing=True)
    target_g = quantity(data.get('production_target'), 'production_target', units_for('mass'), positive=True)
    target_mg = quantity(data.get('treatment_target'), 'treatment_target', units_for('mass'), positive=True) * 1000
    treatment = data.get('treatment')
    if not isinstance(treatment, dict):
        raise ValueError('treatment object is required')
    volume = quantity(treatment.get('volume'), 'volume', units_for('volume'), positive=True, allow_missing=True)
    cin = quantity(treatment.get('influent'), 'influent', CONCENTRATION, allow_missing=True)
    effluent_data = treatment.get('effluent')
    qualifier = effluent_data.get('qualifier', 'exact') if isinstance(effluent_data, dict) else None
    if qualifier not in ('exact', 'below_loq', 'below_lod', 'missing'):
        raise ValueError('effluent qualifier must be exact, below_loq, below_lod, or missing')
    effluent = quantity(effluent_data, 'effluent', CONCENTRATION, allow_missing=True)
    interval = None
    removed = None
    if qualifier in ('below_loq', 'below_lod'):
        if effluent is not None:
            raise ValueError(f'{qualifier} effluent must not have an exact value')
        limit = effluent_data.get('limit')
        limit_data = {**effluent_data, 'value': limit}
        limit_mg_l = quantity(limit_data, 'effluent limit', CONCENTRATION, positive=True)
        if cin is not None and volume is not None:
            interval = [scaled_product(max(0, cin - limit_mg_l), volume, 'removal lower bound'),
                        scaled_product(cin, volume, 'removal upper bound')]
    elif qualifier == 'missing':
        if effluent is not None:
            raise ValueError('missing effluent must not have a value')
    elif effluent is not None and cin is not None and volume is not None:
        if effluent > cin:
            raise ValueError('effluent exceeds influent; check concentration data')
        removed = scaled_product(cin - effluent, volume, 'apparent removed mass')
    dose_g = quantity(treatment.get('catalyst_dose'), 'catalyst_dose', units_for('mass'), positive=True, allow_missing=True)
    uses = quantity(treatment.get('effective_uses'), 'effective_uses', {'uses': 1}, positive=True, allow_missing=True)
    if uses is not None and uses < 1:
        raise ValueError('effective_uses must be at least one')
    production_batches = target_g / yield_g if yield_g is not None else None
    runs = target_mg / removed if removed is not None and removed > 0 else None
    treatment_batches = scaled_product(runs, dose_g, 'catalyst demand') / yield_g / uses if None not in (runs, dose_g, uses, yield_g) else None
    if not all(math.isfinite(x) and x > 0 for x in (production_batches, runs, treatment_batches) if x is not None):
        raise ValueError('invalid scaling result')
    flows, excluded, seen_ids, overlap, flow_keys, warnings = [], [], set(), set(), set(), []
    if yield_g is None:
        warnings.append('Dry catalyst yield is missing: preparation cannot be scaled.')
    if runs is None:
        warnings.append('Treatment scaling unavailable: concentration decrease is zero, missing or not exact, or volume is missing.')
    if treatment_batches is None:
        warnings.append('Preparation allocation to treatment is unavailable: check removal, catalyst dose and reuse.')
    for entry in data.get('flows', []):
        activity = entry.get('activity_id')
        if not isinstance(activity, str) or not activity or activity in seen_ids:
            raise ValueError('activity_id must be unique and nonempty')
        seen_ids.add(activity)
        stage, name, direction, included = entry.get('stage'), entry.get('flow_name'), entry.get('direction'), entry.get('included')
        if stage not in ('preparation', 'treatment') or not isinstance(name, str) or not name.strip() or direction not in ('input', 'output') or not isinstance(included, bool):
            raise ValueError(f'{activity}: invalid stage, flow_name, direction or included')
        group = entry.get('overlap_group')
        if included and group:
            if group in overlap:
                raise ValueError(f'{activity}: overlapping included activity group {group}')
            overlap.add(group)
        if not included and not entry.get('exclusion_reason'):
            raise ValueError(f'{activity}: exclusion_reason required')
        key = (stage, name.casefold(), direction)
        if included and key in flow_keys:
            warnings.append(f'{activity}: repeated flow in one stage; check for duplicate accounting.')
        if included:
            flow_keys.add(key)
        if 'quantity' in entry and ('power' in entry or 'duration' in entry):
            raise ValueError(f'{activity}: provide quantity or power and duration, not both')
        if 'quantity' in entry:
            q = entry['quantity']; unit = q.get('unit')
            if unit not in UNITS:
                raise ValueError(f'{activity}: unsupported unit')
            value = quantity(q, activity, {unit: 1.0}, allow_missing=True)
            evidence, source = q['evidence_class'], q['source']
            derivation = None
        else:
            p, t = entry.get('power'), entry.get('duration')
            power = quantity(p, activity + ' power', POWER, allow_missing=True)
            duration = quantity(t, activity + ' duration', TIME, allow_missing=True)
            value = None if power is None or duration is None else scaled_product(power, duration, activity + ' energy')
            unit, evidence = 'kWh', 'calculated'
            source = 'power: ' + p['source'] + '; duration: ' + t['source']
            derivation = {'power': p, 'duration': t}
        if value is None:
            warnings.append(f'{activity}: amount is missing; not replaced with zero.')
        record = {'activity_id': activity, 'stage': stage, 'flow_name': name, 'direction': direction,
                  'value': value, 'unit': unit, 'evidence_class': evidence, 'source': source,
                  'derivation': derivation,
                  'overlap_group': group or '',
                  'dataset_mapping': entry.get('dataset_mapping', ''), 'included': included,
                  'note': entry.get('exclusion_reason', '') if not included else entry.get('note', '')}
        (flows if included else excluded).append(record)
    mass_inputs = [f for f in flows if f['stage'] == 'preparation' and f['direction'] == 'input'
                   and UNITS[f['unit']][0] == 'mass']
    mass_input_g = (sum(f['value'] * unit_factor(f['unit'], 'g') for f in mass_inputs)
                    if mass_inputs and all(f['value'] is not None for f in mass_inputs) else None)
    if mass_input_g is not None and yield_g is not None and yield_g > mass_input_g:
        warnings.append('Dry yield exceeds the listed mass inputs; check omitted materials and mass basis.')
    def scaled(items, batch_scale, run_scale):
        result = []
        for f in items:
            if f['stage'] == 'treatment' and run_scale == 'exclude':
                continue
            factor = batch_scale if f['stage'] == 'preparation' else run_scale
            target = CANONICAL[UNITS[f['unit']][0]]
            amount = None if f['value'] is None or factor is None else scaled_product(f['value'], factor * unit_factor(f['unit'], target), f['activity_id'])
            result.append({**{k: v for k, v in f.items() if k not in ('value', 'unit')},
                           'original_value': f['value'], 'original_unit': f['unit'], 'amount': amount, 'unit': target})
        return result
    return {'system': data['system'], 'boundary': data['boundary'],
            'mass_check': {'dry_yield_g': yield_g, 'listed_preparation_mass_inputs_g': mass_input_g,
                           'note': 'Only listed mass-unit inputs are summed; this is not a complete mass balance.'},
            'removal': {'apparent_removed_mg_per_run': removed, 'range_mg_per_run': interval,
                        'effluent_qualifier': qualifier, 'inputs': {'volume': treatment['volume'],
                        'influent': treatment['influent'], 'effluent': treatment['effluent']},
                        'note': 'Assumes the stated volume applies to both concentrations; concentration decrease is not proof of pollutant mineralization.'},
            'production': {'functional_unit': data['production_target'], 'preparation_batches': production_batches,
                           'dry_yield': data['dry_yield'],
                           'flows': scaled(flows, production_batches, 'exclude')},
            'treatment': {'functional_unit': data['treatment_target'], 'treatment_runs': runs,
                          'preparation_batches': treatment_batches, 'catalyst_dose': treatment['catalyst_dose'],
                          'catalyst_loading_mg_per_l': dose_g * 1000 / volume if dose_g is not None and volume is not None else None,
                          'effective_uses': treatment['effective_uses'], 'flows': scaled(flows, treatment_batches, runs)},
            'inventory_flows': flows, 'excluded_flows': excluded, 'warnings': warnings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--inventory-csv', type=Path, help='write a new foreground inventory CSV')
    args = parser.parse_args()
    try:
        data = json.loads(args.input.read_text(encoding='utf-8'))
        result = build(data)
        if args.inventory_csv:
            with args.inventory_csv.open('x', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                writer.writeheader()
                for flow in result['inventory_flows'] + result['excluded_flows']:
                    writer.writerow({'system': data['system'], 'stage': flow['stage'], 'flow_name': flow['flow_name'],
                        'amount': flow['value'], 'unit': flow['unit'], 'direction': flow['direction'],
                        'evidence_class': flow['evidence_class'], 'source': flow['source'],
                        'dataset_mapping': flow['dataset_mapping'], 'included': str(flow['included']).lower(), 'note': flow['note'],
                        'activity_id': flow['activity_id'], 'overlap_group': flow['overlap_group']})
                y = data['dry_yield']
                writer.writerow({'system': data['system'], 'stage': 'preparation', 'flow_name': 'dry catalyst',
                    'amount': y['value'], 'unit': y['unit'], 'direction': 'output', 'evidence_class': y['evidence_class'],
                    'source': y['source'], 'dataset_mapping': '', 'included': 'true', 'note': 'reference output per preparation batch',
                    'activity_id': 'dry-catalyst-reference', 'overlap_group': ''})
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, OverflowError, ZeroDivisionError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
