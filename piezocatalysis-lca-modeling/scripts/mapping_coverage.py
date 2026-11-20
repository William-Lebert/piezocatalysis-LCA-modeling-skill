#!/usr/bin/env python3
"""Review one selected openLCA process and selected LCIA flow coverage, without editing data."""
import argparse
from contextlib import ExitStack
import json
import math
from pathlib import Path
import sys

from audit_and_scale_inventory import unit_factor
from openlca_readonly import Client, EntityNotFound, IPCError, valid_uuid


def ident(obj):
    return obj.get('@id') if isinstance(obj, dict) else None


def read_entity(client, kind, uid):
    try:
        value = client.call('data/get', {'@type': kind, '@id': uid})
    except EntityNotFound:
        return None
    if value is None:
        return None
    if not isinstance(value, dict) or ident(value) != uid or value.get('@type') != kind:
        raise IPCError(f'{kind} returned an invalid or mismatched entity')
    return value


def review_process(request, process):
    issues = []
    if process is None:
        return {'status': 'process_not_found', 'issues': ['process_not_found']}
    ref = [e for e in process.get('exchanges', []) if e.get('isQuantitativeReference') is True]
    if len(ref) != 1:
        return {'status': 'reference_exchange_invalid', 'issues': ['reference_exchange_invalid']}
    ref = ref[0]
    loc = process.get('location') or {}
    actual = {'process_uuid': ident(process), 'name': process.get('name'),
              'process_type': process.get('processType'), 'process_version': process.get('version'),
              'geography': loc.get('name') if isinstance(loc, dict) else loc,
              'reference_flow_uuid': ident(ref.get('flow')), 'reference_product': (ref.get('flow') or {}).get('name'),
              'flow_type': (ref.get('flow') or {}).get('flowType'),
              'flow_property_uuid': ident(ref.get('flowProperty')), 'unit_uuid': ident(ref.get('unit')),
              'unit': (ref.get('unit') or {}).get('name'), 'reference_is_input': ref.get('isInput')}
    for key in ('name', 'geography', 'process_version', 'reference_flow_uuid', 'reference_product',
                'flow_property_uuid', 'unit_uuid', 'reference_is_input'):
        if key not in request or request[key] in ('', None):
            issues.append(key + '_unverified')
        elif request[key] != actual[key]:
            issues.append(key + '_mismatch')
    try:
        conversion = unit_factor(request['foreground_unit'], actual['unit'])
        declared = request['conversion_factor']
        if isinstance(declared, bool) or not isinstance(declared, (int, float)) or not math.isfinite(declared) or not math.isclose(conversion, declared, rel_tol=1e-9, abs_tol=0):
            issues.append('conversion_factor_mismatch')
    except (ValueError, KeyError, TypeError):
        conversion = None
        issues.append('unit_conversion_unverified')
    # A matching reference exchange does not prove a product-system link.
    return {'status': 'needs_review' if issues else 'metadata_matches_review_required',
            'issues': issues, 'actual_reference': actual, 'conversion_factor_calculated': conversion,
            'provider_link_status': 'not_checked', 'review_status': request.get('review_status', 'pending')}


def factor_status(matches, property_id, unit_id):
    if not matches:
        return 'no_characterization_factor'
    if len(matches) != 1:
        return 'multiple_factors_review_required'
    factor = matches[0]
    if (not property_id or not unit_id or ident(factor.get('flowProperty')) != property_id
            or ident(factor.get('unit')) != unit_id):
        return 'factor_unit_or_property_unverified'
    if factor.get('location'):
        return 'regional_factor_requires_review'
    if factor.get('formula'):
        return 'factor_formula_requires_evaluation'
    value = factor.get('value')
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return 'factor_value_unavailable'
    return 'factor_present'


def review_method(request, method, categories):
    if method is None:
        return {'status': 'method_not_found', 'issues': ['method_not_found'], 'categories': []}
    issues = []
    for key, field in (('method_name', 'name'), ('method_version', 'version')):
        if request.get(key) in ('', None): issues.append(key + '_unverified')
        elif request[key] != method.get(field): issues.append(key + '_mismatch')
    members = {ident(c) for c in method.get('impactCategories', [])}
    rows = []
    for query in request['categories']:
        cid = query['category_uuid']
        cat = categories.get(cid)
        if cid not in members:
            rows.append({'category_uuid': cid, 'status': 'category_not_in_method', 'flows': []}); continue
        if cat is None:
            rows.append({'category_uuid': cid, 'status': 'category_not_found', 'flows': []}); continue
        if not isinstance(cat.get('impactFactors'), list):
            rows.append({'category_uuid': cid, 'status': 'factor_data_unavailable', 'flows': []}); continue
        catissues = []
        for key, field in (('category_name', 'name'), ('category_version', 'version')):
            if query.get(key) in ('', None): catissues.append(key + '_unverified')
            elif query[key] != cat.get(field): catissues.append(key + '_mismatch')
        flows = []
        for flow in query['flows']:
            matches = [f for f in cat.get('impactFactors', []) if ident(f.get('flow')) == flow['flow_uuid']]
            status = factor_status(matches, flow.get('flow_property_uuid'), flow.get('unit_uuid'))
            flows.append({'flow_uuid': flow['flow_uuid'], 'status': status,
                          'matching_factor_count': len(matches),
                          'factor_value': matches[0].get('value') if status == 'factor_present' else None,
                          'factor_formula': matches[0].get('formula') if status == 'factor_formula_requires_evaluation' else None})
        rows.append({'category_uuid': cid, 'name': cat.get('name'), 'version': cat.get('version'),
                     'issues': catissues, 'flows': flows})
    return {'status': 'needs_review' if issues else 'metadata_matches_review_required',
            'method_uuid': ident(method), 'name': method.get('name'), 'version': method.get('version'),
            'issues': issues, 'categories': rows}


def review_link(request, system, consumer, provider_id):
    if system is None:
        return {'status': 'product_system_not_found'}
    if consumer is None:
        return {'status': 'consumer_not_found'}
    if not isinstance(system.get('processLinks'), list):
        return {'status': 'link_data_unavailable'}
    exchanges = [e for e in consumer.get('exchanges', []) if e.get('internalId') == request['exchange_internal_id']]
    if len(exchanges) != 1:
        return {'status': 'consumer_exchange_not_unique'}
    exchange = exchanges[0]
    if ident(exchange.get('flow')) != request['flow_uuid'] or exchange.get('isInput') != request['is_input']:
        return {'status': 'consumer_exchange_mismatch'}
    for key, field in (('unit_uuid', 'unit'), ('flow_property_uuid', 'flowProperty')):
        if key in request and request[key] != ident(exchange.get(field)):
            return {'status': 'consumer_exchange_mismatch', 'field': key}
    links = [link for link in system.get('processLinks', [])
             if ident(link.get('process')) == ident(consumer)
             and (link.get('exchange') or {}).get('internalId') == request['exchange_internal_id']]
    matching = [link for link in links if ident(link.get('provider')) == provider_id
                and ident(link.get('flow')) == request['flow_uuid']]
    if len(matching) == 1 and len(links) == 1: status = 'linked_to_selected_provider'
    elif not links: status = 'not_linked'
    else: status = 'different_or_multiple_provider_links'
    return {'status': status, 'matching_links': len(matching), 'all_links_for_exchange': len(links)}


def audit(client, request):
    p = request['process']; m = request['method']
    valid_uuid(p['process_uuid']); valid_uuid(m['method_uuid'])
    if not isinstance(m['categories'], list) or not m['categories']:
        raise ValueError('at least one impact category is required')
    for cat in m['categories']:
        valid_uuid(cat['category_uuid'])
        if not isinstance(cat['flows'], list) or not cat['flows']:
            raise ValueError('at least one selected elementary flow is required per category')
        for flow in cat['flows']: valid_uuid(flow['flow_uuid'])
    process = read_entity(client, 'Process', p['process_uuid'])
    method = read_entity(client, 'ImpactMethod', m['method_uuid'])
    members = {ident(x) for x in (method or {}).get('impactCategories', [])}
    cats = {c['category_uuid']: read_entity(client, 'ImpactCategory', c['category_uuid'])
            for c in m['categories'] if c['category_uuid'] in members}
    result = {'database_user_asserted': request.get('database'),
            'database_identity_verification': 'user_asserted_not_verified',
            'process': review_process(p, process), 'method': review_method(m, method, cats),
            'scope': 'Only requested flow UUIDs and selected categories were checked. Factor presence does not establish system connection or impact completeness; zero calculated impact alone does not establish coverage.'}
    if request.get('link'):
        link = request['link']
        for key in ('system_uuid', 'consumer_uuid', 'flow_uuid'): valid_uuid(link[key])
        for key in ('unit_uuid', 'flow_property_uuid'):
            if key in link:
                valid_uuid(link[key])
        if isinstance(link['exchange_internal_id'], bool) or not isinstance(link['exchange_internal_id'], int) or not isinstance(link['is_input'], bool):
            raise ValueError('link requires an integer exchange_internal_id and boolean is_input')
        system = read_entity(client, 'ProductSystem', link['system_uuid'])
        consumer = read_entity(client, 'Process', link['consumer_uuid'])
        result['link'] = review_link(link, system, consumer, p['process_uuid'])
        ref = result['process'].get('actual_reference')
        if ref and result['link']['status'] == 'linked_to_selected_provider':
            if ref['reference_flow_uuid'] != link['flow_uuid']:
                result['link']['status'] = 'provider_reference_flow_mismatch'
            elif not isinstance(ref['reference_is_input'], bool) or ref['reference_is_input'] == link['is_input']:
                result['link']['status'] = 'provider_reference_direction_mismatch'
        result['process']['provider_link_status'] = result['link']['status']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True, type=Path)
    conn = parser.add_mutually_exclusive_group(required=True)
    conn.add_argument('--port', type=int); conn.add_argument('--start-local', action='store_true')
    parser.add_argument('--workspace', type=Path); parser.add_argument('--database')
    parser.add_argument('--openlca-app', type=Path, default=Path('/Applications/openLCA.app'))
    args = parser.parse_args()
    if args.start_local != bool(args.workspace and args.database): parser.error('--start-local requires --workspace and --database')
    try:
        def bad(v): raise ValueError('invalid JSON constant: ' + v)
        request = json.loads(args.request.read_text(encoding='utf-8'), parse_constant=bad)
        with ExitStack() as stack:
            if args.start_local:
                from openlca_local_launch import launch
                port = stack.enter_context(launch(args.openlca_app, args.workspace, args.database))
            else: port = args.port
            report = audit(Client(port, timeout=120), request)
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError, IPCError, argparse.ArgumentTypeError) as exc:
        print('ERROR:', exc, file=sys.stderr); return 1


if __name__ == '__main__': sys.exit(main())
