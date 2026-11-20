#!/usr/bin/env python3
"""Capture and reproduce one-factor openLCA scenarios in prepared product systems."""

import argparse
import csv
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from evidence_chain import build_foreground
from mapping_coverage import ident
from openlca_readonly import Client, IPCError, valid_uuid
from parameter_sensitivity import compare_impacts, require_text
from scenario_binding import capture, check_links, check_plan_source, digest

SCHEMA = 'piezolca.scenario-suite/1'
FILES = {'foreground': 'foreground.json', 'inventory': 'inventory.csv',
         'manifest': 'inventory.csv.manifest.json', 'mapping': 'mapping.csv',
         'assignments': 'assignments.csv'}
HASH_KEYS = dict(foreground='foreground_sha256', inventory='inventory_sha256',
                 manifest='manifest_sha256', mapping='mapping_sha256', assignments='assignments_sha256')
CONTEXT = ('database', 'software', 'functional_unit_user_asserted',
           'unit_label_user_asserted', 'impact_method')


def read_json(raw):
    def invalid(value):
        raise ValueError('invalid JSON number: ' + value)
    return json.loads(raw, parse_constant=invalid)


def without_changes(source, pointers):
    def key_for(node, token):
        if not isinstance(node, list):
            return token
        if not token.isascii() or not token.isdecimal() or str(int(token)) != token:
            raise ValueError('invalid array index in source pointer')
        return int(token)

    result = deepcopy(source)
    paths = []
    for pointer in pointers:
        if not isinstance(pointer, str) or not pointer.startswith('/') or pointer == '/':
            raise ValueError('source changes require JSON pointers')
        tokens = [s.replace('~1', '/').replace('~0', '~') for s in pointer[1:].split('/')]
        if any(tokens[:len(path)] == path or path[:len(tokens)] == tokens for path in paths):
            raise ValueError('source change pointers must not overlap')
        paths.append(tokens)
        node = result
        for token in tokens[:-1]:
            node = node[key_for(node, token)]
        key = key_for(node, tokens[-1])
        if node[key] is None:
            raise ValueError('source change points to an empty value')
        node[key] = None
    return result


def captured_case(case):
    record = case['capture']
    inputs = case['inputs']
    if record['schema_version'] != 'piezolca.bound-scenario/2' or record['strict_exchange_basis'] is not True:
        raise ValueError('suite requires a strict bound scenario capture')
    if set(inputs) != set(FILES):
        raise ValueError('case input files are incomplete')
    for name, text in inputs.items():
        if hashlib.sha256(text.encode('utf-8')).hexdigest() != record[HASH_KEYS[name]]:
            raise ValueError(case['id'] + ': input hash changed: ' + name)
    if any(record['plan'].get(key) != record[key] for key in
           ('inventory_sha256', 'manifest_sha256', 'mapping_sha256', 'assignments_sha256')):
        raise ValueError(case['id'] + ': capture plan does not match the archived inputs')
    source = read_json(inputs['foreground'].encode('utf-8'))
    calc = record['coverage']['calculation']
    for key, value in (('foreground_semantic', source), ('plan', record['plan']),
                       ('coverage', record['coverage']), ('calculation', calc),
                       ('binding', record['binding']), ('parameters', record['parameters_at_calculation'])):
        if digest(value) != record[key + '_sha256']:
            raise ValueError(case['id'] + ': capture digest changed: ' + key)
    if record['binding'] != case['binding']:
        raise ValueError('case binding differs from capture')
    basis = record['system_reference']
    if (basis['ref_process'] != case['binding']['root_uuid']
            or basis['target_unit'] != case['binding']['unit_uuid']
            or basis['target_flow_property'] != case['binding']['property_uuid']
            or not basis.get('reference_flow') or basis.get('reference_exchange_id') is None):
        raise ValueError('scenario reference differs from capture')
    if (check_links(record['plan'], record['coverage'], case['binding'], strict_basis=True,
                    stage_references=record.get('stage_references')) != record['link_check']
            or record['parameter_overrides']
            or calc['setup'].get('parameters')):
        raise ValueError('captured exchange or fixed-parameter check differs')
    check_plan_source(record['plan'], source)
    model, service = build_foreground(source)
    scope = {key: model.get(key) for key in ('functional_unit', 'boundary', 'product_basis', 'product_definition')}
    scope['functional_unit_type'] = service
    if record['plan'].get('database_name_user_asserted') is None or any(
            record['plan'].get(k) != v for k, v in scope.items()):
        raise ValueError('captured plan scope differs from foreground')
    return source, calc, scope


def activity_changes(baseline, case, source, alternative):
    change = case['change']
    kind = change['kind']
    for key in ('variable', 'setting', 'source'):
        require_text(change.get(key), 'change ' + key)
    expected = change['activities']
    if (not isinstance(expected, list) or not expected or len(set(expected)) != len(expected)
            or any(not isinstance(x, str) or not x for x in expected)):
        raise ValueError('declare the exact distinct affected activity IDs')
    a, b = (c['capture']['plan']['rows'] for c in (baseline, case))
    indexed = [{row['activity_id']: row for row in rows if row['status'] != 'excluded'} for rows in (a, b)]
    left, right = indexed
    amount_fields = ('stage', 'cycle_id', 'flow_name', 'direction', 'unit', 'amount_per_functional_unit')
    ref_fields = ('reference_product', 'unit_name', 'reference_is_input', 'flow_property_uuid', 'unit_uuid')
    changed_amounts, changed_providers = set(), set()
    details = []
    for aid in sorted(left.keys() | right.keys()):
        x, y = left.get(aid), right.get(aid)
        xref, yref = ((row.get('actual_reference') or {}) if row else {} for row in (x, y))
        if x is None or y is None or any(x[k] != y[k] for k in amount_fields):
            changed_amounts.add(aid)
        if x is not None and y is not None:
            if x['status'] != y['status']:
                raise ValueError(aid + ': unresolved or connected status changed')
            if xref != yref or x['mapping_user_asserted'] != y['mapping_user_asserted']:
                if (not xref or not yref or xref['process_uuid'] == yref['process_uuid']
                        or any(xref[k] != yref[k] for k in ref_fields)
                        or x['dataset_amount_per_functional_unit'] != y['dataset_amount_per_functional_unit']):
                    raise ValueError(aid + ': replacement must preserve reference product, basis and dataset amount')
                changed_providers.add(aid)
        if aid in changed_amounts or aid in changed_providers:
            details.append({'activity_id': aid,
                            'baseline_amount': x['amount_per_functional_unit'] if x else None,
                            'scenario_amount': y['amount_per_functional_unit'] if y else None,
                            'unit': (x or y)['unit'],
                            'baseline_provider': xref.get('process_uuid'), 'scenario_provider': yref.get('process_uuid'),
                            'baseline_geography': xref.get('geography'), 'scenario_geography': yref.get('geography')})
    pointers = change.get('source_pointers', [])
    if not isinstance(pointers, list) or len(set(pointers)) != len(pointers):
        raise ValueError('source_pointers must be an array of distinct JSON pointers')
    if kind == 'foreground':
        if (not pointers or source == alternative or changed_providers or set(expected) != changed_amounts
                or without_changes(source, pointers) != without_changes(alternative, pointers)
                or baseline['inputs']['mapping'] != case['inputs']['mapping']):
            raise ValueError('foreground change differs from declared source and activity scope')
        # Repeated activities may be added or removed, but their mapping must already exist.
        for aid in left.keys() ^ right.keys():
            row = (left | right)[aid]
            if row['status'] != 'preflight_matches_review_still_required' or not any(
                    other.get('mapping_user_asserted') == row['mapping_user_asserted']
                    for other in (right if aid in left else left).values()):
                raise ValueError(aid + ': added or removed activity has no common reviewed mapping')
    elif kind == 'background':
        if (pointers or source != alternative or changed_amounts or set(expected) != changed_providers
                or any(baseline['inputs'][key] != case['inputs'][key]
                       for key in ('foreground', 'inventory', 'manifest'))):
            raise ValueError('background change differs from declared provider scope')
    else:
        raise ValueError('change kind must be foreground or background')
    return details


def summarize(bundle):
    if bundle['schema_version'] != SCHEMA:
        raise ValueError('unsupported scenario suite schema')
    cases = bundle['cases']
    if not cases or len(cases) < 2 or cases[0]['id'] != 'baseline' or cases[0].get('change') is not None:
        raise ValueError('start with one baseline followed by at least one scenario')
    names = [require_text(c['id'], 'case id') for c in cases]
    if len(set(names)) != len(names):
        raise ValueError('duplicate case id')
    source, calc, scope = captured_case(cases[0])
    control = cases[0]['capture']
    config = bundle['configuration']
    if ident(calc['impact_method']) != config['method_id'] or calc['database']['name'] != config['database_label']:
        raise ValueError('suite calculation configuration differs from baseline')
    rows = []
    seen = {}
    for index, case in enumerate(cases):
        alternative, result, alt_scope = captured_case(case) if index else (source, calc, scope)
        cap = case['capture']
        if (alt_scope != scope or any(calc[k] != result[k] for k in CONTEXT)
                or {k: v for k, v in result['setup'].items() if k != 'target'}
                != {k: v for k, v in calc['setup'].items() if k != 'target'}
                or any(cap[k] != control[k] for k in ('method_snapshot_sha256', 'category_snapshot_sha256'))
                or cap['plan']['database_name_user_asserted'] != config['mapping_database']):
            raise ValueError('case method, calculation settings or study scope differ')
        if (ident(result['setup']['impactMethod']) != config['method_id']
                or ident(cap['coverage']['selected_category']) != config['category_id']):
            raise ValueError('selected method or category differs from suite configuration')
        base_params = {digest(param) for param in control['parameters_at_calculation']
                       if ident(param.get('context')) not in (control['provider_snapshot_hashes'].keys()
                                                              - cap['provider_snapshot_hashes'].keys())}
        case_params = {digest(param) for param in cap['parameters_at_calculation']
                       if ident(param.get('context')) not in (cap['provider_snapshot_hashes'].keys()
                                                              - control['provider_snapshot_hashes'].keys())}
        if base_params != case_params:
            raise ValueError('common calculation parameter defaults differ')
        for pid, checksum in cap['provider_snapshot_hashes'].items():
            if seen.setdefault(pid, checksum) != checksum:
                raise ValueError('common background provider snapshot changed: ' + pid)
        unresolved = cap['link_check']['unresolved_activity_ids']
        if set(unresolved) != set(control['link_check']['unresolved_activity_ids']):
            raise ValueError('scenario changes the unresolved activity set')
        changes = activity_changes(cases[0], case, source, alternative) if index else []
        impacts = compare_impacts(calc['impacts'], result['impacts'])
        rows.append({'id': case['id'], 'change': case.get('change'), 'activity_changes': changes,
                     'unresolved_activity_ids': unresolved, 'impacts': impacts})
    return {'method': calc['impact_method'], 'database': calc['database'], 'scope': scope,
            'functional_unit_user_asserted': calc['functional_unit_user_asserted'],
            'cases': rows, 'ranking_permitted': False, 'status': 'review_required'}


def run(client, configuration, cases):
    for key in ('method_id', 'category_id'):
        valid_uuid(configuration[key])
    records = []
    with TemporaryDirectory(prefix='piezolca-suite-') as tmp:
        paths = {key: Path(tmp)/file for key, file in FILES.items()}
        for case in cases:
            for key, path in paths.items():
                path.write_bytes(case['inputs'][key].encode('utf-8'))
            binding = case['binding']
            args = SimpleNamespace(**{key: configuration[key] for key in
                                      ('method_id', 'wait_seconds', 'software_version', 'database_label',
                                       'database_version', 'system_model', 'functional_unit', 'unit_label',
                                       'mapping_database')},
                                   system_id=valid_uuid(binding['system_uuid']), amount=1,
                                   unit_id=valid_uuid(binding['unit_uuid']),
                                   flow_property_id=valid_uuid(binding['property_uuid']), parameters=[])
            captured = capture(client, *(paths[k] for k in FILES), binding, args,
                               configuration['category_id'], configuration.get('flow_ids', []), strict_basis=True)
            records.append({**case, 'capture': captured})
    bundle = {'schema_version': SCHEMA, 'configuration': configuration, 'cases': records}
    summarize(bundle)
    return bundle


def check_recalculation(reference, current):
    if (reference['configuration'] != current['configuration']
            or len(reference['cases']) != len(current['cases'])
            or any(old[k] != new[k] for old, new in zip(reference['cases'], current['cases'])
                   for k in ('id', 'change', 'inputs', 'binding'))):
        raise ValueError('recalculation case declarations or inputs differ')
    prior = summarize(reference)
    fresh = summarize(current)
    for old, new in zip(reference['cases'], current['cases']):
        for key in ('snapshot_sha256', 'plan_sha256', 'provider_snapshot_hashes'):
            if old['capture'][key] != new['capture'][key]:
                raise ValueError('recalculation model or plan snapshot differs for '+old['id'])
    for old, new in zip(prior['cases'], fresh['cases']):
        for pair in compare_impacts(
                [{'category': i['category'], 'amount': i['amount']} for i in old['impacts']],
                [{'category': i['category'], 'amount': i['amount']} for i in new['impacts']]):
            if not math.isclose(pair['baseline'], pair['amount'], rel_tol=1e-9, abs_tol=1e-12):
                raise ValueError('recalculation differs for '+old['id']+' / '+pair['category']['@id'])


def suite_plot(summary, category_id):
    rows = []
    for case in summary['cases'][1:]:
        impacts = [row for row in case['impacts'] if ident(row['category']) == category_id]
        if len(impacts) != 1:
            raise ValueError('plot category missing or duplicated in scenario suite')
        impact = impacts[0]
        change = case['change']
        rows.append({'case': case['id'], 'variable': change['variable'], 'setting': change['setting'],
                     'delta': impact['delta'], 'unit': impact['unit'], 'source': change['source']})
    rows.sort(key=lambda row: abs(row['delta']), reverse=True)
    unresolved = summary['cases'][0]['unresolved_activity_ids']
    warnings = ['Each bar uses one stated setting and the same declared functional unit.']
    if unresolved:
        warnings.append('Unresolved foreground activities: ' + ', '.join(unresolved))
    return {'kind': 'sensitivity', 'title_zh': '单因素情景重算变化', 'title_en': 'Recalculated one-factor scenarios',
            'category': {'id': category_id, 'name': impact['category']['name'], 'unit': impact['unit']},
            'database': summary['database'], 'method': summary['method'], 'baseline': impact['baseline'],
            'functional_unit': summary['functional_unit_user_asserted'],
            'rows': rows, 'warnings': warnings, 'data_basis': 'Absolute openLCA results, per functional unit'}


def write_csv(summary, stream):
    writer = csv.writer(stream)
    writer.writerow(['case', 'variable', 'setting', 'category_uuid', 'category_name', 'unit',
                     'baseline', 'amount', 'delta', 'change_percent', 'unresolved_activity_ids'])
    for case in summary['cases']:
        change = case['change'] or {}
        for impact in case['impacts']:
            category = impact['category']
            values = [case['id'], change.get('variable'), change.get('setting'), category['@id'],
                      category['name'], impact['unit'], impact['baseline'], impact['amount'],
                      impact['delta'], impact['change_percent'], ', '.join(case['unresolved_activity_ids'])]
            writer.writerow(["'" + v if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@'))
                             else v for v in values])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    for action in ('capture', 'rerun', 'summarize'):
        cmd = sub.add_parser(action)
        cmd.add_argument('input', type=Path)
        cmd.add_argument('--output', type=Path, required=True)
        if action != 'summarize':
            conn = cmd.add_mutually_exclusive_group(required=True)
            conn.add_argument('--workspace', type=Path)
            conn.add_argument('--port', type=int)
            cmd.add_argument('--openlca-app', type=Path, default=Path('/Applications/openLCA.app'))
    args = parser.parse_args()
    try:
        data = read_json(args.input.read_bytes())
        if args.action == 'summarize':
            result = summarize(data)
        else:
            if data['schema_version'] != SCHEMA:
                raise ValueError('unsupported scenario suite schema')
            if args.action == 'capture':
                cases = []
                for case in data['cases']:
                    base = args.input.resolve().parent
                    inputs = {k: (base / case['files'][k]).read_bytes().decode('utf-8') for k in FILES}
                    cases.append({'id': case['id'], 'change': case.get('change'), 'inputs': inputs,
                                  'binding': read_json((base / case['binding']).read_bytes())})
            else:
                summarize(data)
                cases = [{k: c[k] for k in ('id', 'change', 'inputs', 'binding')} for c in data['cases']]
            with ExitStack() as stack:
                port = args.port
                if args.workspace:
                    from openlca_local_launch import launch
                    port = stack.enter_context(launch(args.openlca_app, args.workspace,
                                                      data['configuration']['database_label']))
                result = run(Client(port, 180), data['configuration'], cases)
            if args.action == 'rerun':
                check_recalculation(data, result)
        payload = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n'
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(payload)
        print(args.output)
        return 0
    except (OSError, ValueError, TypeError, KeyError, IndexError, IPCError, argparse.ArgumentTypeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
