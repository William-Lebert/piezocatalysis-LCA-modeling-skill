#!/usr/bin/env python3
"""Audit a foreground inventory and scale it to a pollutant-removal service.

All input data and datasets remain external. This tool does not calculate LCIA.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

from validate_inventory import REQUIRED, EVIDENCE, DIRECTIONS, BOOLEAN

MAPPING_FIELDS = {'mapping_id', 'foreground_flow', 'foreground_unit', 'database', 'database_version',
                  'system_model', 'dataset_name', 'reference_product', 'dataset_unit', 'geography',
                  'match_type', 'conversion_factor', 'rationale', 'expected_bias', 'alternative_dataset', 'review_status'}
PARAMETER_UNITS = {'target_removed_mg': 'mg', 'removed_per_run_mg': 'mg',
                   'catalyst_dose_g': 'g', 'effective_uses': 'uses'}
# Factors to base units: g, L and kWh. Do not infer incompatible conversions.
UNITS = {'mg': ('mass', 0.001), 'g': ('mass', 1), 'kg': ('mass', 1000),
         'mL': ('volume', 0.001), 'L': ('volume', 1), 'm3': ('volume', 1000),
         'Wh': ('energy', 0.001), 'kWh': ('energy', 1), 'MJ': ('energy', 1 / 3.6)}
TRUE = {'true', '1', 'yes'}
FALSE = {'false', '0', 'no'}


def csv_rows(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)):
            raise ValueError(f'{path.name}: duplicate column names')
        missing = required - set(fields)
        if missing:
            raise ValueError(f'{path.name}: missing columns: {", ".join(sorted(missing))}')
        result = []
        for row_no, row in enumerate(reader, 2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f'{path.name} row {row_no}: incorrect number of columns')
            row = {key: value.strip() for key, value in row.items()}
            row['_row'] = str(row_no)
            result.append(row)
        return result


def number(value: object, label: str, minimum: float = 0, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f'{label}: must be a finite number')
    try:
        result = float(value)
    except (ValueError, OverflowError):
        raise ValueError(f'{label}: must be a finite number') from None
    if not math.isfinite(result) or result < minimum or (positive and result <= minimum):
        raise ValueError(f'{label}: must be finite and {">" if positive else ">="} {minimum}')
    return result


def finite(value: float, label: str) -> float:
    if not math.isfinite(value):
        raise ValueError(f'{label}: non-finite result')
    return value


def scaled_product(a: float, b: float, label: str) -> float:
    value = finite(a * b, label)
    if a != 0 and b != 0 and value == 0:
        raise ValueError(f'{label}: numeric underflow')
    return value


def require(row: dict, keys: set[str], label: str) -> None:
    for key in sorted(keys):
        if not isinstance(row.get(key), str) or not row[key].strip():
            raise ValueError(f'{label}: {key} is required')


def unit_factor(source: str, target: str) -> float:
    if source not in UNITS or target not in UNITS:
        raise ValueError(f'unsupported unit conversion: {source} -> {target}')
    if UNITS[source][0] != UNITS[target][0]:
        raise ValueError(f'incompatible units: {source} -> {target}')
    return UNITS[source][1] / UNITS[target][1]


def load_parameters(path: Path) -> dict:
    def invalid_constant(v: str) -> None:
        raise ValueError(f'non-standard JSON constant: {v}')
    data = json.loads(path.read_text(encoding='utf-8'), parse_constant=invalid_constant)
    if not isinstance(data, dict):
        raise ValueError('parameters: must be an object')
    service = data.get('service_definition')
    if not isinstance(service, dict):
        raise ValueError('parameters.service_definition: object is required')
    require(service, {'value', 'source', 'evidence_class'}, 'parameters.service_definition')
    if service['evidence_class'] not in EVIDENCE:
        raise ValueError('parameters.service_definition: invalid evidence class')
    for key, unit in PARAMETER_UNITS.items():
        item = data.get(key)
        if not isinstance(item, dict):
            raise ValueError(f'parameters.{key}: object is required')
        require(item, {'unit', 'evidence_class', 'source'}, f'parameters.{key}')
        if item['unit'] != unit:
            raise ValueError(f'parameters.{key}: unit must be {unit}')
        if item['evidence_class'] not in EVIDENCE:
            raise ValueError(f'parameters.{key}: invalid evidence class')
        if isinstance(item.get('value'), bool) or not isinstance(item.get('value'), (int, float)):
            raise ValueError(f'parameters.{key}.value: must be a JSON number')
        value = number(item.get('value'), f'parameters.{key}.value', positive=True)
        if key == 'effective_uses' and value < 1:
            raise ValueError('parameters.effective_uses: must be at least 1')
    return data


def audit(inventory_path: Path, mapping_path: Path, parameters_path: Path, system: str, reference: str) -> dict:
    parameters = load_parameters(parameters_path)
    inventory = csv_rows(inventory_path, REQUIRED)
    mapping_rows = csv_rows(mapping_path, MAPPING_FIELDS)
    warnings = []
    for key in (*PARAMETER_UNITS, 'service_definition'):
        if any('replace-me' in str(parameters[key].get(field, '')).lower() for field in ('source', 'value')):
            warnings.append(f'parameters.{key}: contains placeholder')
    mappings = {}
    for m in mapping_rows:
        label = f'mapping row {m["_row"]}'
        require(m, MAPPING_FIELDS - {'alternative_dataset', 'rationale', 'expected_bias'}, label)
        if m['mapping_id'] in mappings:
            raise ValueError(f'{label}: duplicate mapping_id {m["mapping_id"]}')
        if m['match_type'] not in {'exact', 'proxy', 'constructed'}:
            raise ValueError(f'{label}: match_type must be exact, proxy, or constructed')
        if m['review_status'] not in {'pending', 'reviewed'}:
            raise ValueError(f'{label}: review_status must be pending or reviewed')
        if m['match_type'] in {'proxy', 'constructed'}:
            require(m, {'rationale', 'expected_bias'}, label)
            if not m['alternative_dataset']:
                warnings.append(f'{label}: no alternative dataset recorded for sensitivity')
        factor = number(m['conversion_factor'], f'{label} conversion_factor', positive=True)
        expected = unit_factor(m['foreground_unit'], m['dataset_unit'])
        if not math.isclose(factor, expected, rel_tol=1e-9, abs_tol=0):
            raise ValueError(f'{label}: conversion factor does not match units (expected {expected:g})')
        if m['review_status'] == 'pending':
            warnings.append(f'{label}: mapping {m["mapping_id"]} is pending human review')
        if any('replace-me' in value.lower() for key, value in m.items() if key != '_row'):
            warnings.append(f'{label}: mapping contains placeholder')
        mappings[m['mapping_id']] = m
    rows = [r for r in inventory if r['system'] == system]
    if not rows:
        raise ValueError(f'system not found: {system}')
    included, excluded = [], []
    for r in rows:
        label = f'inventory row {r["_row"]}'
        require(r, {'system', 'stage', 'flow_name', 'unit', 'direction', 'evidence_class', 'source', 'included'}, label)
        if r['direction'] not in DIRECTIONS or r['evidence_class'] not in EVIDENCE:
            raise ValueError(f'{label}: invalid direction or evidence_class')
        flag = r['included'].lower()
        if flag not in BOOLEAN:
            raise ValueError(f'{label}: invalid included flag')
        number(r['amount'], f'{label} amount')
        if 'replace-me' in r['source'].lower():
            warnings.append(f'{label}: source contains placeholder')
        if flag in FALSE:
            if not r['note']:
                warnings.append(f'{label}: excluded flow has no rationale')
            excluded.append(r)
            continue
        if r['stage'] not in {'preparation', 'treatment'}:
            raise ValueError(f'{label}: included stage must be preparation or treatment')
        if r['unit'] not in UNITS:
            raise ValueError(f'{label}: unsupported unit {r["unit"]}')
        included.append(r)
    refs = [r for r in included if r['stage'] == 'preparation' and r['direction'] == 'output' and r['flow_name'] == reference]
    if len(refs) != 1:
        raise ValueError('exactly one included preparation reference output is required')
    ref = refs[0]
    yield_g = scaled_product(number(ref['amount'], 'reference yield', positive=True), unit_factor(ref['unit'], 'g'), 'reference yield')
    p = {k: float(parameters[k]['value']) for k in PARAMETER_UNITS}
    runs = finite(p['target_removed_mg'] / p['removed_per_run_mg'], 'runs per FU')
    if runs == 0:
        raise ValueError('runs per FU: numeric underflow')
    demand = scaled_product(runs, p['catalyst_dose_g'], 'catalyst demand')
    batches = finite(demand / yield_g / p['effective_uses'], 'preparation batches per FU')
    if batches == 0:
        raise ValueError('preparation batches per FU: numeric underflow')
    if not any(r['stage'] == 'treatment' for r in included):
        warnings.append('no included treatment flows; verify the treatment boundary')
    flows = []
    seen = set()
    for r in included:
        if r is ref:
            continue
        label = f'inventory row {r["_row"]}'
        key = (r['stage'], r['direction'], r['flow_name'], r['unit'])
        if key in seen:
            warnings.append(f'{label}: duplicate flow key; verify whether repeated operations are intended')
        seen.add(key)
        scaled = scaled_product(float(r['amount']), batches if r['stage'] == 'preparation' else runs, f'{label} scaled amount')
        mapping_id = r['dataset_mapping']
        mapped_amount = None
        m = None
        if mapping_id:
            m = mappings.get(mapping_id)
            if m is None:
                raise ValueError(f'{label}: unknown mapping_id {mapping_id}')
            if m['foreground_flow'] != r['flow_name'] or m['foreground_unit'] != r['unit']:
                raise ValueError(f'{label}: mapping flow or foreground unit does not match')
            mapped_amount = scaled_product(scaled, float(m['conversion_factor']), f'{label} dataset amount')
        else:
            warnings.append(f'{label}: unmapped flow {r["flow_name"]}; dataset amount unavailable')
        flows.append({'inventory_row': int(r['_row']), 'stage': r['stage'], 'flow_name': r['flow_name'],
                      'direction': r['direction'], 'original_amount': float(r['amount']), 'unit': r['unit'],
                      'evidence_class': r['evidence_class'], 'source': r['source'], 'note': r['note'],
                      'amount_per_fu': scaled, 'mapping_id': mapping_id or None,
                      'dataset_amount_per_fu': mapped_amount, 'dataset_unit': m['dataset_unit'] if m else None,
                      'mapping': {k: v for k, v in m.items() if k != '_row'} if m else None})
    return {'report_type': 'foreground_inventory_scaling', 'system': system,
            'functional_unit': {'description': parameters['service_definition']['value'], 'amount': p['target_removed_mg'], 'unit': 'mg'},
            'parameters': parameters, 'reference_output': {'flow_name': ref['flow_name'], 'amount': float(ref['amount']),
                'unit': ref['unit'], 'yield_g': yield_g, 'evidence_class': ref['evidence_class'], 'source': ref['source']},
            'scaling': {'runs_per_fu': runs, 'preparation_batches_per_fu': batches},
            'assumptions': ['Equal pollutant removal and catalyst dose per run.',
                'Effective uses allocate preparation burden evenly; recovery losses and changing performance must be reflected in this assumption.',
                'Preparation entries are per synthesis batch; treatment entries are per run.',
                'No LCIA is calculated; mappings require human review.'],
            'flows': flows, 'excluded_flows': [{k: v for k, v in r.items() if k != '_row'} for r in excluded],
            'warnings': warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('inventory', 'mapping', 'parameters'):
        parser.add_argument('--' + arg, type=Path, required=True)
    parser.add_argument('--system', required=True)
    parser.add_argument('--reference-flow', required=True)
    args = parser.parse_args()
    try:
        report = audit(args.inventory, args.mapping, args.parameters, args.system, args.reference_flow)
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    except (OSError, UnicodeError, ValueError, OverflowError, ZeroDivisionError, csv.Error) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
