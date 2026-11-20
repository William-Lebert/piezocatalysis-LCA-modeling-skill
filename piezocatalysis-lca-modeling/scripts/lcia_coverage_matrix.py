#!/usr/bin/env python3
"""Check LCIA factors for selected flows and calculated categories through read-only IPC."""

import argparse
from collections import Counter
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import sys

from mapping_coverage import factor_status, ident, read_entity
from openlca_readonly import Client, IPCError, valid_uuid


def reference_basis(client, flow, cache):
    properties = [ident(row.get('flowProperty')) for row in flow.get('flowProperties', [])
                  if row.get('isRefFlowProperty') is True]
    if len(properties) != 1 or not properties[0]:
        return None, None, None
    property_id = properties[0]
    if property_id not in cache:
        prop = read_entity(client, 'FlowProperty', property_id)
        group_id = ident((prop or {}).get('unitGroup'))
        group = read_entity(client, 'UnitGroup', group_id) if group_id else None
        units = [unit for unit in (group or {}).get('units', []) if unit.get('isRefUnit') is True]
        unit = units[0] if len(units) == 1 else {}
        cache[property_id] = property_id, ident(unit), unit.get('name')
    return cache[property_id]


def audit(client, calculation, flow_ids, category_ids=None):
    method_ref = calculation['impact_method']
    method_id = valid_uuid(ident(method_ref))
    if method_id != ident(calculation['setup'].get('impactMethod')):
        raise IPCError('calculated method and setup identities differ')
    method = read_entity(client, 'ImpactMethod', method_id)
    if (method is None or method.get('name') != method_ref.get('name')
            or method_ref.get('version') not in (None, method.get('version'))):
        raise IPCError('live LCIA method differs from calculation')
    members = {ident(row) for row in method['impactCategories']}
    results = {ident(row['category']): row['category'] for row in calculation['impacts']}
    if len(results) != len(calculation['impacts']):
        raise IPCError('calculation has duplicate categories')
    selected = category_ids if category_ids is not None else list(results)
    if not selected or len(set(selected)) != len(selected) or not set(selected) <= (members & results.keys()):
        raise IPCError('select distinct categories belonging to the calculated method')
    if not flow_ids or len(set(flow_ids)) != len(flow_ids):
        raise IPCError('select at least one distinct flow UUID')

    categories = []
    for category_id in selected:
        category = read_entity(client, 'ImpactCategory', valid_uuid(category_id))
        ref = results[category_id]
        if (category is None or category.get('name') != ref.get('name')
                or category.get('refUnit') != ref.get('refUnit')
                or ref.get('version') not in (None, category.get('version'))):
            raise IPCError('live impact category differs from calculation: ' + category_id)
        if not isinstance(category.get('impactFactors'), list):
            raise IPCError('impact factor data unavailable: ' + category_id)
        categories.append(category)

    inventory = calculation.get('total_flows')
    if not isinstance(inventory, list):
        raise IPCError('calculation has no total inventory; use --include-total-flows')
    occurrences_by_flow = {flow_id: [] for flow_id in flow_ids}
    for entry in inventory:
        flow_id = ident(entry['enviFlow']['flow'])
        if flow_id in occurrences_by_flow:
            occurrences_by_flow[flow_id].append(entry)
    factors_by_category = {}
    for category in categories:
        factors = {flow_id: [] for flow_id in flow_ids}
        for factor in category['impactFactors']:
            flow_id = ident(factor.get('flow'))
            if flow_id in factors:
                factors[flow_id].append(factor)
        factors_by_category[ident(category)] = factors
    basis_cache = {}
    rows = []
    flows = []
    for flow_id in flow_ids:
        flow = read_entity(client, 'Flow', valid_uuid(flow_id))
        if flow is None:
            raise IPCError('flow not found: ' + flow_id)
        kind = flow.get('flowType')
        if kind not in ('ELEMENTARY_FLOW', 'PRODUCT_FLOW', 'WASTE_FLOW'):
            raise IPCError('flow type unavailable: ' + flow_id)
        elementary = kind == 'ELEMENTARY_FLOW'
        occurrences = occurrences_by_flow[flow_id]
        if any(entry['enviFlow']['flow'].get(key) != flow.get(key)
               for entry in occurrences for key in ('name', 'category', 'flowType')):
            raise IPCError('live flow differs from calculated inventory: ' + flow_id)
        property_id, unit_id, unit_name = reference_basis(client, flow, basis_cache) if elementary else (None, None, None)
        if unit_name and any(entry['enviFlow']['flow'].get('refUnit') != unit_name for entry in occurrences):
            raise IPCError('live reference unit differs from calculated inventory: ' + flow_id)
        flows.append({'flow_uuid': flow_id, 'name': flow.get('name'), 'flow_type': kind,
                      'compartment': flow.get('category') if elementary else None,
                      'reference_flow_property_uuid': property_id, 'reference_unit_uuid': unit_id,
                      'reference_unit': unit_name,
                      'inventory_occurrences': occurrences})
        for category in categories:
            matches = factors_by_category[ident(category)][flow_id]
            status = (factor_status(matches, property_id, unit_id) if elementary
                      else 'not_applicable_technical_flow')
            value = matches[0]['value'] if status == 'factor_present' else None
            rows.append({'flow_uuid': flow_id, 'category_uuid': ident(category),
                         'observed_in_inventory': bool(occurrences),
                         'status': 'explicit_zero_factor' if value == 0 else status,
                         'factor_value': value, 'matching_factors': matches})
    return {'schema_version': 'piezolca.lcia-coverage-matrix/1',
            'database': calculation.get('database'), 'target': calculation.get('target'),
            'method': {'uuid': method_id, 'name': method.get('name'), 'version': method.get('version')},
            'categories': [{'uuid': ident(c), 'name': c.get('name'), 'unit': c.get('refUnit'),
                            'version': c.get('version')} for c in categories],
            'flows': flows, 'checks': rows, 'counts_by_status': dict(Counter(row['status'] for row in rows)),
            'scope': ('Live factor definitions for selected pairs only. The reference flow property and unit are '
                      'checked by UUID. Inventory presence and factor status are independent. Review direction, '
                      'regionalization and applicability before interpreting an impact.')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--calculation', required=True, type=Path)
    parser.add_argument('--flow-id', action='append', required=True, type=valid_uuid)
    parser.add_argument('--category-id', action='append', type=valid_uuid,
                        help='repeat to select categories or omit for all calculated categories')
    connection = parser.add_mutually_exclusive_group(required=True)
    connection.add_argument('--port', type=int)
    connection.add_argument('--start-local', action='store_true')
    parser.add_argument('--workspace', type=Path)
    parser.add_argument('--database')
    parser.add_argument('--openlca-app', type=Path, default=Path('/Applications/openLCA.app'))
    args = parser.parse_args()
    if args.start_local and not (args.workspace and args.database):
        parser.error('--start-local requires --workspace and --database')
    if not args.start_local and (args.workspace or args.database):
        parser.error('--workspace and --database are for --start-local only')
    try:
        raw = args.calculation.read_bytes()
        calculation = json.loads(raw)
        if args.start_local and (calculation.get('database') or {}).get('name') != args.database:
            raise ValueError('database name differs from calculation record')
        with ExitStack() as stack:
            if args.start_local:
                from openlca_local_launch import launch
                port = stack.enter_context(launch(args.openlca_app, args.workspace, args.database))
            else:
                port = args.port
            report = audit(Client(port, timeout=120), calculation, args.flow_id, args.category_id)
        report['calculation_sha256'] = hashlib.sha256(raw).hexdigest()
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (OSError, KeyError, TypeError, ValueError, IPCError, argparse.ArgumentTypeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
