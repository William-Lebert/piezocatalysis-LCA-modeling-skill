#!/usr/bin/env python3
"""Compare declared study contexts before interpreting scenario rankings."""
import argparse
import json
from pathlib import Path
import sys
import uuid

FIELDS = ('functional_unit', 'system_boundary', 'geography', 'reference_period',
          'database', 'database_version', 'system_model', 'lcia_method_uuid',
          'lcia_method_version', 'mapping_scope', 'allocation', 'recycling_approach', 'electricity_scenario')


def assess(data):
    if not isinstance(data, dict) or not isinstance(data.get('cases'), list) or len(data['cases']) < 2:
        raise ValueError('at least two case declarations are required')
    cases = data['cases']
    identifiers = set()
    issues = []
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get('id'), str) or not case['id'].strip() or case['id'] in identifiers:
            raise ValueError('case IDs must be unique, nonempty strings')
        identifiers.add(case['id'])
        for field in FIELDS:
            if not isinstance(case.get(field), str) or not case[field].strip() or 'replace-me' in case[field].lower():
                issues.append({'case': case['id'], 'field': field, 'status': 'missing_or_placeholder'})
        method_id = case.get('lcia_method_uuid')
        if isinstance(method_id, str) and method_id.strip() and 'replace-me' not in method_id.lower():
            try:
                uuid.UUID(method_id)
            except ValueError:
                issues.append({'case': case['id'], 'field': 'lcia_method_uuid', 'status': 'invalid_uuid'})
    for field in FIELDS:
        values = {case[field].strip() for case in cases if isinstance(case.get(field), str) and case[field].strip() and 'replace-me' not in case[field].lower()}
        if len(values) > 1:
            issues.append({'field': field, 'status': 'mismatch', 'values_by_case': {case['id']: case.get(field) for case in cases}})
    return {'status': 'not_comparable' if issues else 'declared_contexts_match',
            'ranking_permitted_by_context_check': not issues, 'issues': issues,
            'checked_fields': list(FIELDS),
            'note': 'Declarations are user supplied. Matching text is a necessary context check, not independent verification of models or evidence.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path)
    args = p.parse_args()
    try:
        result = assess(json.loads(args.input.read_text(encoding='utf-8')))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result['ranking_permitted_by_context_check'] else 2
    except (ValueError, TypeError, OSError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__': sys.exit(main())
