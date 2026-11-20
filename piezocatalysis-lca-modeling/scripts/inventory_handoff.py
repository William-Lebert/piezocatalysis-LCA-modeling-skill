#!/usr/bin/env python3
"""Prepare a traceable, reviewable mapping handoff for a cyclic functional-unit inventory."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import uuid

from audit_and_scale_inventory import MAPPING_FIELDS, BOOLEAN, FALSE, TRUE, UNITS, csv_rows, number, scaled_product, unit_factor
from validate_inventory import REQUIRED, EVIDENCE
from cyclic_foreground import TERMINAL_CATALYST_ACTIVITY


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_handoff(inventory_path, manifest_path, mapping_path=None, assignments_path=None):
    def bad(v): raise ValueError('invalid JSON constant: ' + v)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'), parse_constant=bad)
    if not isinstance(manifest, dict) or manifest.get('schema_version') != 'piezolca.inventory-manifest/1':
        raise ValueError('unsupported inventory manifest schema')
    if manifest.get('inventory_schema_version') != 'piezolca.inventory/2' or manifest.get('amount_basis') != 'per_functional_unit':
        raise ValueError('manifest must declare a functional-unit inventory')
    inventory_hash = sha(inventory_path)
    if manifest.get('inventory_sha256') != inventory_hash:
        raise ValueError('inventory does not match manifest SHA-256; regenerate or restore the paired files')
    if not isinstance(manifest.get('functional_unit'), dict) or not manifest.get('system'):
        raise ValueError('manifest lacks functional unit or system')
    rows = csv_rows(inventory_path, REQUIRED | {'activity_id', 'cycle_id', 'inventory_schema_version', 'amount_basis'})
    if not rows: raise ValueError('inventory is empty')
    ids = set()
    for row in rows:
        if row['inventory_schema_version'] != 'piezolca.inventory/2' or row['amount_basis'] != 'per_functional_unit':
            raise ValueError('inventory row has a conflicting schema or basis')
        if row['system'] != manifest['system'] or not row['activity_id'] or row['activity_id'] in ids:
            raise ValueError('inventory system mismatch or duplicate/empty activity_id')
        ids.add(row['activity_id'])
    maps = {}
    if mapping_path:
        for row in csv_rows(mapping_path, MAPPING_FIELDS):
            key = row['mapping_id']
            if not key or key in maps: raise ValueError('mapping_id must be unique and nonempty')
            maps[key] = row
    assignments = {}
    if assignments_path:
        for a in csv_rows(assignments_path, {'activity_id', 'mapping_id'}):
            if a['activity_id'] not in ids or a['activity_id'] in assignments:
                raise ValueError('assignment contains an unknown or duplicate activity_id')
            assignments[a['activity_id']] = a['mapping_id']
    output = []
    for row in rows:
        activity = row['activity_id']; flags = []; mapping = None
        include = row['included'].lower()
        if include not in BOOLEAN: raise ValueError(f'{activity}: invalid included flag')
        if row['direction'].lower() not in ('input', 'output'): raise ValueError(f'{activity}: invalid direction')
        if row['stage'] not in ('preparation', 'treatment'): flags.append('stage_invalid')
        if row['unit'] not in UNITS: flags.append('foreground_unit_unsupported')
        if not row['source'] or 'replace-me' in row['source'].lower(): flags.append('source_missing_or_placeholder')
        if row['evidence_class'].lower() not in EVIDENCE: flags.append('evidence_class_invalid')
        base_id = row['dataset_mapping']; selected = assignments.get(activity, base_id)
        if activity in assignments and base_id and selected != base_id:
            raise ValueError(f'{activity}: assignment conflicts with inventory mapping')
        amount = None
        if row['amount']:
            amount = number(row['amount'], f'{activity} amount')
        elif include in TRUE:
            flags.append('amount_unknown')
        mapped_amount = None
        if include in FALSE:
            status = 'excluded'
            if not row['note']: flags.append('exclusion_reason_missing')
        elif not selected:
            status = 'awaiting_disposal_mapping' if row['direction'].lower() == 'output' else 'unmapped'
            flags.append(status)
        elif selected not in maps:
            status = 'mapping_not_found'; flags.append(status)
        else:
            mapping = maps[selected]
            if activity == TERMINAL_CATALYST_ACTIVITY and manifest.get('generator') == 'cyclic_foreground':
                campaign = manifest.get('campaign') or {}
                fate = campaign.get('final_recovered_fate')
                if (not isinstance(fate, dict) or fate.get('evidence_class') not in EVIDENCE
                        or any(not isinstance(fate.get(key), str) or not fate[key].strip()
                               or 'replace-me' in fate[key].lower() for key in ('route', 'source'))):
                    flags.append('terminal_fate_evidence_missing')
                if campaign.get('final_recovered_destination') != 'disposed' or row['direction'].lower() != 'output':
                    flags.append('terminal_disposal_status_or_direction_mismatch')
                if campaign.get('catalyst_mass_basis') != 'dry':
                    flags.append('terminal_disposal_dry_basis_missing')
            kind, review = mapping['match_type'], mapping['review_status']
            status = kind if kind in ('exact', 'proxy', 'constructed') else 'invalid_match_type'
            if status == 'invalid_match_type': flags.append(status)
            if review not in ('pending', 'reviewed'): flags.append('invalid_review_status')
            elif review != 'reviewed': flags.append('pending_human_review')
            for key in ('database', 'database_version', 'system_model', 'dataset_name', 'reference_product', 'dataset_unit', 'geography'):
                if not mapping[key] or 'replace-me' in mapping[key].lower(): flags.append(key + '_missing')
            if mapping['foreground_flow'] != row['flow_name'] or mapping['foreground_unit'] != row['unit']:
                flags.append('foreground_flow_or_unit_mismatch')
            if kind in ('proxy', 'constructed') and (not mapping['rationale'] or not mapping['expected_bias']):
                flags.append('proxy_rationale_or_bias_missing')
            try:
                factor = number(mapping['conversion_factor'], f'{activity} conversion factor', positive=True)
                if mapping.get('conversion_type', '') == 'density':
                    density = number(mapping.get('density_kg_per_l'), f'{activity} density', positive=True)
                    if not mapping.get('density_source') or mapping.get('density_evidence_class') not in EVIDENCE:
                        raise ValueError('density needs source and evidence class')
                    expected = unit_factor(row['unit'], 'L') * density * unit_factor('kg', mapping['dataset_unit'])
                elif mapping.get('conversion_type', '') in ('', 'unit'):
                    expected = unit_factor(row['unit'], mapping['dataset_unit'])
                else:
                    raise ValueError('unsupported conversion type')
                if not math.isclose(factor, expected, rel_tol=1e-9, abs_tol=0): flags.append('conversion_factor_mismatch')
                elif amount is not None and 'foreground_flow_or_unit_mismatch' not in flags:
                    mapped_amount = scaled_product(amount, factor, f'{activity} mapped amount')
            except ValueError:
                flags.append('unit_conversion_unverified')
            for key in ('process_uuid', 'reference_flow_uuid', 'flow_property_uuid', 'unit_uuid'):
                if not mapping.get(key): flags.append(key + '_unverified')
                else:
                    try: uuid.UUID(mapping[key])
                    except ValueError: flags.append(key + '_invalid')
            direction = mapping.get('reference_is_input', '').lower()
            if direction not in TRUE | FALSE:
                flags.append('reference_direction_unverified')
            elif (direction in TRUE) != (row['direction'].lower() == 'output'):
                flags.append('reference_direction_mismatch')
            if any(flag in {'foreground_flow_or_unit_mismatch', 'conversion_factor_mismatch', 'unit_conversion_unverified',
                            'reference_direction_mismatch', 'invalid_match_type', 'terminal_fate_evidence_missing',
                            'terminal_disposal_status_or_direction_mismatch', 'terminal_disposal_dry_basis_missing'} or flag.endswith('_invalid') for flag in flags):
                mapped_amount = None
        output.append({'inventory_row': int(row['_row']), 'activity_id': activity, 'stage': row['stage'], 'cycle_id': row['cycle_id'] or None,
                       'flow_name': row['flow_name'], 'direction': row['direction'].lower(), 'included': include in TRUE,
                       'amount_per_functional_unit': amount, 'unit': row['unit'], 'source': row['source'],
                       'evidence_class': row['evidence_class'], 'note': row['note'],
                       'mapping_id': selected or None, 'mapping_type': status, 'issues': flags,
                       'dataset_amount_per_functional_unit': mapped_amount,
                       'dataset_amount_status': 'candidate_user_asserted_not_approved' if mapped_amount is not None else 'unavailable',
                       'mapping_user_asserted': {k:v for k,v in mapping.items() if k != '_row'} if mapping else None})
    pending = [r for r in output if r['included'] and r['issues']]
    warnings = manifest.get('warnings')
    if not isinstance(warnings, list) or any(not isinstance(w, str) for w in warnings):
        raise ValueError('manifest warnings must be a list of strings')
    excluded_issues = any(r['issues'] for r in output if not r['included'])
    return {'report_type': 'cyclic_inventory_mapping_handoff', 'schema_version': 'piezolca.handoff/1',
            'system': manifest['system'], 'boundary': manifest.get('boundary'),
            'functional_unit': manifest['functional_unit'], 'functional_unit_type': manifest.get('functional_unit_type'),
            'product_basis': manifest.get('product_basis'), 'product_definition': manifest.get('product_definition'), 'amount_basis': manifest['amount_basis'],
            'inventory_sha256': inventory_hash, 'manifest_sha256': sha(manifest_path), 'input_sha256': manifest.get('input_sha256'),
            'generator': manifest.get('generator'), 'generator_version': manifest.get('generator_version'), 'scaling': manifest.get('scaling'),
            'code_sha256': manifest.get('code_sha256'), 'handoff_code_sha256': sha(Path(__file__)),
            'mapping_sha256': sha(mapping_path) if mapping_path else None,
            'assignments_sha256': sha(assignments_path) if assignments_path else None,
            'model_warnings': warnings, 'campaign': manifest.get('campaign'), 'rows': output,
            'summary': {'total_rows': len(output), 'included_rows': sum(r['included'] for r in output),
                        'included_needing_review': len(pending), 'excluded_rows': sum(not r['included'] for r in output),
                        'status': 'needs_review' if pending or warnings or excluded_issues else 'declarations_complete_review_required'},
            'note': 'Mappings and review status are user assertions, not verified dataset identity or scientific suitability. No product system or LCIA is calculated.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', required=True, type=Path)
    parser.add_argument('--manifest', type=Path, help='defaults to <inventory>.manifest.json')
    parser.add_argument('--mapping', type=Path, help='existing dataset mapping CSV')
    parser.add_argument('--assignments', type=Path, help='CSV: activity_id,mapping_id')
    args = parser.parse_args()
    try:
        manifest = args.manifest or args.inventory.with_name(args.inventory.name + '.manifest.json')
        result = load_handoff(args.inventory, manifest, args.mapping, args.assignments)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)); return 0
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, OverflowError, csv.Error) as exc:
        print('ERROR:', exc, file=sys.stderr); return 1

if __name__ == '__main__': sys.exit(main())
