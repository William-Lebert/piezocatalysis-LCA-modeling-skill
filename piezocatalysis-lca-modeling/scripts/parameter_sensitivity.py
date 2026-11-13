#!/usr/bin/env python3
"""Recalculate one-parameter scenarios using an existing openLCA product system."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace

from openlca_readonly import Client, IPCError, calculate, numeric, valid_uuid
from validate_inventory import EVIDENCE


def metadata_fingerprint(folder):
    digest = hashlib.sha256()
    count = 0
    for path in sorted(folder.rglob('*')):
        if path.is_file():
            stat = path.stat()
            digest.update((str(path.relative_to(folder)) + '\0' + str(stat.st_size) + '\0' + str(stat.st_mtime_ns) + '\n').encode())
            count += 1
    return {'sha256': digest.hexdigest(), 'files': count,
            'basis': 'relative file paths, sizes and mtimes; not a content checksum'}


def require_text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name}: nonempty text required')
    return value.strip()


def resolve_change(change, available):
    if not isinstance(change, dict):
        raise ValueError('scenario must be an object')
    name = require_text(change.get('name'), 'parameter name')
    if 'context_id' not in change:
        raise ValueError('context_id required (null for a global parameter)')
    context_id = change['context_id']
    matches = [p for p in available if p.get('name') == name and
               (p.get('context') or {}).get('@id') == context_id]
    if len(matches) != 1:
        raise ValueError(f'parameter not found or ambiguous: {name}')
    param = matches[0]
    if param.get('isProtected') is True:
        raise ValueError(f'{name}: parameter is protected')
    value = numeric(change.get('value'), f'{name} value')
    baseline = numeric(param.get('value'), f'{name} baseline')
    for bound in ('minimum', 'maximum'):
        if bound in change:
            limit = numeric(change[bound], f'{name} {bound}')
            if (bound == 'minimum' and (value < limit or baseline < limit)) or (bound == 'maximum' and (value > limit or baseline > limit)):
                raise ValueError(f'{name}: value or baseline outside {bound}')
    if value == baseline:
        raise ValueError(f'{name}: scenario must differ from baseline')
    require_text(change.get('unit'), f'{name} unit')
    require_text(change.get('source'), f'{name} source')
    if change.get('evidence_class') not in EVIDENCE:
        raise ValueError(f'{name}: invalid evidence_class')
    result = {'name': name, 'value': value}
    if context_id is not None:
        context = param.get('context') or {}
        if not isinstance(context_id, str) or context.get('@type') not in ('Process', 'ImpactCategory'):
            raise ValueError(f'{name}: invalid context')
        result['context'] = {'@type': context['@type'], '@id': context_id}
    return result


def compare_impacts(baseline, alternative):
    def indexed(rows):
        output = {}
        for row in rows:
            category = row.get('category', {})
            key = category.get('@id')
            if not key or key in output:
                raise ValueError('impact category ID missing or duplicated')
            output[key] = row
        return output
    a, b = indexed(baseline), indexed(alternative)
    if a.keys() != b.keys() or not a:
        raise ValueError('impact categories differ across cases')
    result = []
    for key, row in a.items():
        cat = row['category']; other = b[key]['category']
        require_text(cat.get('refUnit'), 'impact category unit')
        if cat.get('name') != other.get('name') or cat.get('refUnit') != other.get('refUnit'):
            raise ValueError('impact category labels or units differ across cases')
        base = numeric(row['amount'], 'baseline impact')
        val = numeric(b[key]['amount'], 'alternative impact')
        delta = numeric(val - base, 'impact difference')
        percent = delta / abs(base) * 100 if base else None
        if percent is not None and not math.isfinite(percent):
            percent = None
        result.append({'category': cat, 'baseline': base, 'amount': val, 'unit': cat.get('refUnit'),
                       'delta': delta, 'change_percent': percent})
    return result


def run(client, spec, input_sha256, connection):
    if not isinstance(spec, dict) or not isinstance(spec.get('model'), dict) or not isinstance(spec.get('context'), dict):
        raise ValueError('model and context objects are required')
    model, context = spec['model'], spec['context']
    for key in ('system_id', 'method_id', 'unit_id', 'flow_property_id'):
        valid_uuid(model.get(key, ''))
    for key in ('software_version', 'database_label', 'database_version', 'system_model',
                'functional_unit', 'unit_label', 'system_boundary', 'mapping_notes', 'lcia_method_label', 'lcia_version'):
        require_text(context.get(key), key)
    amount = numeric(model.get('amount'), 'functional-unit amount')
    if amount <= 0:
        raise ValueError('functional-unit amount must be positive')
    scenarios = spec.get('scenarios')
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError('scenarios must be a nonempty list')
    params = client.call('data/get/parameters', {'@type': 'ProductSystem', '@id': model['system_id']})
    if not isinstance(params, list) or any(not isinstance(p, dict) for p in params):
        raise ValueError('invalid model parameters returned')
    seen = {'baseline'}; resolved = []
    for scenario in scenarios:
        sid = require_text(scenario.get('id'), 'scenario id')
        if sid in seen:
            raise ValueError(f'duplicate scenario id: {sid}')
        seen.add(sid)
        resolved.append((scenario, resolve_change(scenario, params)))
    args = SimpleNamespace(**model, **{k:context[k] for k in ('software_version','database_label','database_version',
                            'system_model','functional_unit','unit_label')}, wait_seconds=60, parameters=[])
    started = datetime.now(timezone.utc).isoformat()
    baseline = calculate(client, args)
    cases = []
    for scenario, override in resolved:
        args.parameters = [override]
        calculated = calculate(client, args)
        cases.append({'id': scenario['id'], 'change_user_supplied': scenario,
                      'override_sent': override, 'calculation': calculated,
                      'comparison': compare_impacts(baseline['impacts'], calculated['impacts'])})
    return {'report_type': 'openlca_parameter_recalculation', 'started_utc': started,
            'completed_utc': datetime.now(timezone.utc).isoformat(), 'input_sha256': input_sha256,
            'code_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                (Path(__file__), Path(__file__).with_name('openlca_readonly.py'),
                 Path(__file__).with_name('openlca_local_launch.py'),
                 Path(__file__).with_name('openlca_guard')/'localhost-agent.jar')},
            'software_and_database_user_asserted': context, 'model': model,
            'connection': connection, 'model_parameters_at_start': params, 'baseline': baseline, 'cases': cases,
            'limitations': ['Actual openLCA recalculation, not additive contribution approximation.',
                'Database identity, parameter units, model applicability and context are user asserted.',
                'Each scenario changes one parameter and assumes all others remain fixed.',
                'A zero baseline gives a null percentage. Scenarios do not represent a probability distribution.']}


def redacted_summary(report):
    cases = []
    for i, case in enumerate(report['cases'], 1):
        cases.append({'case': f'case-{i}', 'percentage_changes': [x['change_percent'] for x in case['comparison']]})
    return {'report_type':'redacted_scenario_summary', 'scenario_count':len(cases),
            'impact_category_count':len(report['baseline']['impacts']), 'cases':cases,
            'note':'Names, identifiers and absolute impacts omitted; review before sharing under the relevant license.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('spec',type=Path)
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument('--port',type=int)
    source.add_argument('--start-local',action='store_true')
    p.add_argument('--workspace',type=Path)
    p.add_argument('--database')
    p.add_argument('--openlca-app',type=Path,default=Path('/Applications/openLCA.app'))
    p.add_argument('--summary',type=Path,help='new redacted summary JSON file')
    args=p.parse_args()
    if (args.start_local and (args.workspace is None or not args.database)) or (not args.start_local and (args.workspace is not None or args.database)):
        p.error('--start-local requires --workspace and --database; neither is used with --port')
    try:
        raw=args.spec.read_bytes()
        def bad_constant(x): raise ValueError('non-standard JSON constant: '+x)
        spec=json.loads(raw,parse_constant=bad_constant)
        source_before = metadata_fingerprint(args.workspace/'databases'/args.database) if args.start_local else None
        with ExitStack() as stack:
            if args.start_local:
                from openlca_local_launch import launch
                port=stack.enter_context(launch(args.openlca_app,args.workspace,args.database))
                connection={'mode':'guarded_temporary_clone','database_name':args.database}
                if spec.get('context',{}).get('database_label') != args.database:
                    raise ValueError('database_label must match cloned database name')
            else:
                port=args.port
                connection={'mode':'existing_local_service','identity_verification':'user_asserted'}
            report=run(Client(port,timeout=120),spec,hashlib.sha256(raw).hexdigest(),connection)
        if args.start_local:
            source_after = metadata_fingerprint(args.workspace/'databases'/args.database)
            report['connection']['source_metadata_before'] = source_before
            report['connection']['source_metadata_after'] = source_after
            report['connection']['source_metadata_unchanged'] = source_before == source_after
            if source_before != source_after:
                report['limitations'].append('Source database file metadata changed during the run; inspect before reproducing.')
        output=json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)
        if args.summary:
            with args.summary.open('x',encoding='utf-8') as f:
                json.dump(redacted_summary(report),f,ensure_ascii=False,indent=2,allow_nan=False)
                f.write('\n')
        print(output)
        return 0
    except (OSError,UnicodeError,ValueError,TypeError,KeyError,OverflowError,IPCError,argparse.ArgumentTypeError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr)
        return 1


if __name__=='__main__':
    sys.exit(main())
