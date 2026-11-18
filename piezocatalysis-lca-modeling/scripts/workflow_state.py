#!/usr/bin/env python3
"""Record and recheck declared workflow files and upstream stage records; never runs LCA."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

SCHEMA = 'piezolca.workflow-state/1'
STAGES = ('intake', 'evidence', 'scope', 'foreground', 'mapping', 'validation',
          'execution', 'lcia_qa', 'sensitivity', 'reporting')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(paths):
    result = []
    for path in paths:
        p = Path(path).resolve(strict=True)
        if not p.is_file():
            raise ValueError('not a file: ' + str(p))
        if any(item['path'] == str(p) for item in result):
            raise ValueError('duplicate file: ' + str(p))
        result.append({'path': str(p), 'sha256': digest(p)})
    return result


def check(path, visiting=None):
    path = Path(path).resolve(strict=True)
    visiting = set() if visiting is None else visiting
    if path in visiting:
        raise ValueError('cyclic stage dependency: ' + str(path))
    visiting.add(path)
    try:
        state = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(state, dict) or state.get('schema_version') != SCHEMA or state.get('stage') not in STAGES:
            raise ValueError('invalid workflow state: ' + str(path))
        issues = []
        for key in ('inputs', 'outputs', 'dependencies'):
            entries = state.get(key)
            if not isinstance(entries, list) or (key == 'outputs' and not entries):
                raise ValueError('invalid ' + key + ' in ' + str(path))
            for item in entries:
                if not isinstance(item, dict) or not isinstance(item.get('path'), str) or not isinstance(item.get('sha256'), str):
                    raise ValueError('invalid ' + key + ' entry in ' + str(path))
                target = Path(item['path'])
                try:
                    if digest(target) != item['sha256']:
                        issues.append(key + ' changed: ' + str(target))
                    if key == 'dependencies':
                        upstream = check(target, visiting)
                        issues.extend(upstream['issues'])
                except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                    issues.append(key + ' unavailable or invalid: ' + str(target) + ' (' + str(exc) + ')')
        required=state.get('required_inputs',[])
        if not isinstance(required,list) or any(not isinstance(x,str) or not x for x in required) or len(required)!=len(set(required)):
            raise ValueError('invalid required inputs in '+str(path))
        listed={x['path'] for x in state['inputs']}
        for target in required:
            if target not in listed:issues.append('required input not declared: '+target)
        return {'stage': state['stage'], 'file_integrity': 'BLOCKED' if issues else 'PASS',
                'scientific_review': 'NOT_EVALUATED', 'issues': issues,
                'note': 'Only declared files and dependencies were checked; this does not verify scientific validity or completeness.'}
    finally:
        visiting.remove(path)


def record(stage, inputs, outputs, dependencies, destination, required_inputs=()):
    if stage not in STAGES:
        raise ValueError('unknown stage: ' + str(stage))
    ins, outs, deps = snapshot(inputs), snapshot(outputs), snapshot(dependencies)
    required=[x['path'] for x in snapshot(required_inputs)]
    if not set(required).issubset({x['path'] for x in ins}):raise ValueError('required input must also be listed as an input')
    if not outs:
        raise ValueError('at least one existing output file is required')
    for dependency in deps:
        result = check(dependency['path'])
        if result['file_integrity'] != 'PASS':
            raise ValueError('upstream state is stale or unavailable: ' + dependency['path'])
    state = {'schema_version': SCHEMA, 'stage': stage, 'inputs': ins, 'outputs': outs,
             'dependencies': deps, 'scientific_review': 'NOT_EVALUATED'}
    if required:state['required_inputs']=required
    with Path(destination).open('x', encoding='utf-8') as stream:
        json.dump(state, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('record')
    p.add_argument('--stage', choices=STAGES, required=True)
    p.add_argument('--input', action='append', default=[])
    p.add_argument('--output', action='append', default=[])
    p.add_argument('--depends-on', action='append', default=[])
    p.add_argument('--require-input', action='append', default=[], help='declare a critical file that must also be supplied with --input')
    p.add_argument('--state', type=Path, required=True)
    p = sub.add_parser('check')
    p.add_argument('state', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'record':
            record(args.stage, args.input, args.output, args.depends_on, args.state, args.require_input)
            result = check(args.state)
        else:
            result = check(args.state)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result['file_integrity'] == 'PASS' else 2
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
