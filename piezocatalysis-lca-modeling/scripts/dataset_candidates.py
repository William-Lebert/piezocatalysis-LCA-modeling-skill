#!/usr/bin/env python3
"""Suggest openLCA process candidates for an inventory; review every candidate."""
import argparse
from contextlib import ExitStack
import csv
import json
import math
from pathlib import Path
import sys
import uuid

from audit_and_scale_inventory import MAPPING_FIELDS, csv_rows, number, unit_factor
from openlca_readonly import Client, IPCError, descriptors
from validate_inventory import BOOLEAN, REQUIRED


def find_candidates(request, processes):
    name = request.get('dataset_name', '').strip().casefold()
    geography = request.get('geography', '').strip().casefold()
    identifier = request.get('process_uuid', '').strip()
    if identifier:
        try:
            identifier = str(uuid.UUID(identifier))
        except ValueError:
            return {'status': 'invalid_uuid', 'candidate_count': 0, 'candidates': [], 'selected_process_uuid': None}
        matches = [p for p in processes if (p.get('@id') or '').lower() == identifier]
        mismatch = any((name and name not in (p.get('name') or '').casefold()) or
                       (geography and geography != (p.get('location') or '').casefold()) for p in matches)
    else:
        matches = [p for p in processes if name and name in (p.get('name') or '').casefold()
                   and (not geography or geography == (p.get('location') or '').casefold())]
        mismatch = False
    matches.sort(key=lambda p: (p.get('name') or '', p.get('location') or '', p.get('@id') or ''))
    status = ('metadata_mismatch' if mismatch else 'ambiguous' if len(matches) > 1
              else 'needs_review' if matches else 'not_found')
    return {'status': status, 'candidate_count': len(matches), 'candidates': matches[:20],
            'selected_process_uuid': None}


def report(inventory, mappings, processes, context):
    by_id = {}
    for m in mappings:
        key = m['mapping_id']
        if not key or key in by_id:
            raise ValueError('mapping_id must be nonempty and unique')
        by_id[key] = m
    output = []
    for row in inventory:
        included = row['included'].lower()
        if included not in BOOLEAN:
            raise ValueError(f'inventory row {row["_row"]}: invalid included flag')
        if included not in ('true', '1', 'yes'):
            continue
        mapping_id = row['dataset_mapping']
        mapping = by_id.get(mapping_id)
        record = {'inventory_row': int(row['_row']), 'system': row['system'], 'stage': row['stage'],
                  'foreground_flow': row['flow_name'], 'foreground_unit': row['unit'],
                  'mapping_id': mapping_id or None, 'selected_process_uuid': None}
        status = None
        if mapping_id and mapping is None:
            status = 'unknown_mapping'
        elif mapping:
            if any(mapping[k] != context[k] for k in ('database', 'database_version', 'system_model')):
                status = 'database_mismatch'
            elif mapping['foreground_flow'] != row['flow_name'] or mapping['foreground_unit'] != row['unit']:
                status = 'foreground_mismatch'
            else:
                try:
                    expected = unit_factor(mapping['foreground_unit'], mapping['dataset_unit'])
                    factor = number(mapping['conversion_factor'], 'conversion_factor', positive=True)
                    if not math.isclose(factor, expected, rel_tol=1e-9, abs_tol=0):
                        status = 'unit_mismatch'
                except ValueError:
                    status = 'unit_mismatch'
        if status:
            record.update(status=status, candidate_count=0, candidates=[])
        else:
            request = dict(mapping) if mapping else {'dataset_name': row['flow_name']}
            record.update(find_candidates(request, processes))
        output.append(record)
    return {'database_user_asserted': context, 'rows': output,
            'note': 'Candidates are not selected automatically. Confirm database identity, reference product, flow property, unit and provider in openLCA.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', required=True, type=Path)
    parser.add_argument('--mapping', required=True, type=Path)
    parser.add_argument('--database', required=True)
    parser.add_argument('--database-version', required=True)
    parser.add_argument('--system-model', required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--descriptors', type=Path, help='JSON output of openlca_readonly.py list --type Process')
    source.add_argument('--port', type=int, help='local openLCA IPC port')
    source.add_argument('--start-local', action='store_true', help='start a guarded database clone')
    parser.add_argument('--workspace', type=Path)
    parser.add_argument('--openlca-app', type=Path, default=Path('/Applications/openLCA.app'))
    parser.add_argument('--format', choices=('json', 'csv'), default='json')
    args = parser.parse_args()
    if args.start_local != (args.workspace is not None):
        parser.error('--workspace is required only with --start-local')
    if any(not x.strip() for x in (args.database, args.database_version, args.system_model)):
        parser.error('database, database-version and system-model must be nonempty')
    try:
        inventory = csv_rows(args.inventory, REQUIRED)
        mappings = csv_rows(args.mapping, MAPPING_FIELDS)
        with ExitStack() as stack:
            if args.descriptors:
                data = json.loads(args.descriptors.read_text(encoding='utf-8'))
                if not isinstance(data, dict) or data.get('type') != 'Process':
                    raise ValueError('descriptors file must contain a Process descriptor list')
                processes = data.get('descriptors')
            else:
                if args.start_local:
                    from openlca_local_launch import launch
                    port = stack.enter_context(launch(args.openlca_app, args.workspace, args.database))
                else:
                    port = args.port
                processes = descriptors(Client(port, timeout=120), 'Process')
            if not isinstance(processes, list) or any(not isinstance(x, dict) for x in processes):
                raise ValueError('invalid process descriptors')
            result = report(inventory, mappings, processes, {'database': args.database,
                'database_version': args.database_version, 'system_model': args.system_model})
        if args.format == 'json':
            print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        else:
            fields = ['inventory_row', 'system', 'stage', 'foreground_flow', 'foreground_unit', 'mapping_id',
                      'status', 'candidate_count', 'candidate_uuid', 'candidate_name', 'candidate_location',
                      'candidate_category', 'process_type', 'database', 'database_version', 'system_model']
            writer = csv.DictWriter(sys.stdout, fieldnames=fields)
            writer.writeheader()
            for row in result['rows']:
                for candidate in row['candidates'] or [{}]:
                    out = {key: row.get(key) for key in fields}
                    out.update(result['database_user_asserted'])
                    out.update(candidate_uuid=candidate.get('@id'), candidate_name=candidate.get('name'),
                               candidate_location=candidate.get('location'), candidate_category=candidate.get('category'),
                               process_type=candidate.get('processType'))
                    writer.writerow(out)
        return 0
    except (OSError, UnicodeError, ValueError, TypeError, csv.Error, IPCError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
