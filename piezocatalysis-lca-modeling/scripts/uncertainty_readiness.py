#!/usr/bin/env python3
"""Inventory declared uncertainty evidence and identify gaps before simulation."""
import argparse
import json
import math
from pathlib import Path
import sys

EVIDENCE = {'measured', 'reported', 'calculated', 'proxy', 'scenario'}
KINDS = {'unknown', 'fixed', 'uniform', 'normal', 'lognormal', 'triangular', 'empirical_joint'}


def text(value):
    return isinstance(value, str) and bool(value.strip()) and 'replace-me' not in value.lower()


def assess(data):
    if not isinstance(data, dict) or not isinstance(data.get('parameters'), list) or not data['parameters']:
        raise ValueError('parameters must be a nonempty list')
    issues, warnings, names, entries = [], [], set(), []
    for p in data['parameters']:
        if not isinstance(p, dict) or not text(p.get('id')) or p['id'] in names:
            raise ValueError('each parameter needs a unique nonempty id')
        name = p['id']; names.add(name)
        for field in ('unit', 'source', 'geography', 'time_scope'):
            if not text(p.get(field)): issues.append({'id':name, 'field':field, 'status':'missing'})
        if p.get('evidence_class') not in EVIDENCE:
            issues.append({'id':name, 'field':'evidence_class', 'status':'missing_or_invalid'})
        count = p.get('sample_count')
        if count is not None and (isinstance(count, bool) or not isinstance(count, int) or count < 0):
            raise ValueError(f'{name}: sample_count must be null or a nonnegative integer')
        if p.get('evidence_class') == 'measured' and (count is None or count < 2):
            warnings.append({'id':name, 'status':'limited_or_missing_replicate_information'})
        if p.get('evidence_class') in ('proxy','scenario'):
            warnings.append({'id':name, 'status':'proxy_or_scenario_not_measured_evidence'})
        dist = p.get('distribution')
        if not isinstance(dist, dict) or dist.get('type') not in KINDS:
            raise ValueError(f'{name}: distribution type invalid')
        kind = dist['type']
        if kind == 'unknown': issues.append({'id':name, 'field':'distribution', 'status':'unknown'})
        elif not text(dist.get('basis')): issues.append({'id':name, 'field':'distribution_basis', 'status':'missing'})
        if kind == 'fixed': warnings.append({'id':name, 'status':'fixed_conditionally_no_uncertainty_propagated'})
        if p.get('censoring') not in ('none','below_lod','below_loq','missing','unknown'):
            issues.append({'id':name, 'field':'censoring', 'status':'missing_or_invalid'})
        if p.get('censoring') in ('below_lod','below_loq'):
            limit=p.get('detection_limit')
            if isinstance(limit,bool) or not isinstance(limit,(int,float)) or not math.isfinite(limit) or limit<=0:
                issues.append({'id':name, 'field':'detection_limit', 'status':'missing_or_invalid'})
            if not text(p.get('censoring_treatment')):
                issues.append({'id':name, 'field':'censoring_treatment', 'status':'missing'})
            warnings.append({'id':name, 'status':'censored_observation_requires_explicit_treatment'})
        if p.get('censoring') in ('missing','unknown'):
            issues.append({'id':name, 'field':'observation', 'status':'missing_or_unknown'})
        entries.append({'id':name, 'evidence_class':p.get('evidence_class'), 'sample_count':count,
                        'distribution':kind, 'censoring':p.get('censoring')})
    if data.get('dependencies_reviewed') is not True:
        issues.append({'field':'dependencies_reviewed','status':'not_confirmed'})
    deps = data.get('dependencies')
    if not isinstance(deps, list): raise ValueError('dependencies must be a list')
    seen_pairs=set()
    for dep in deps:
        if not isinstance(dep,dict) or not isinstance(dep.get('parameters'),list) or len(dep['parameters'])!=2:
            raise ValueError('each dependency needs two distinct parameter IDs')
        a,b=dep['parameters']
        if a not in names or b not in names or a==b:
            raise ValueError('dependency refers to unknown or identical parameters')
        pair=tuple(sorted((a,b)))
        if pair in seen_pairs: raise ValueError('duplicate dependency pair')
        seen_pairs.add(pair)
        relation=dep.get('relation')
        if relation not in ('joint','independent','unknown'):
            raise ValueError('dependency relation must be joint, independent or unknown')
        if relation=='unknown' or not text(dep.get('basis')):
            issues.append({'parameters':list(pair),'field':'dependency','status':'unresolved'})
    coverage=data.get('coverage')
    if not isinstance(coverage,dict): raise ValueError('coverage object is required')
    for key in ('system_boundary_complete','background_uncertainty_reviewed','background_uncertainty_represented','impact_method_reviewed'):
        if coverage.get(key) is not True: issues.append({'field':key,'status':'not_confirmed'})
    return {'status':'evidence_gaps' if issues else 'declared_inputs_ready_for_method_review',
            'parameters':entries,'issues':issues,'warnings':warnings,
            'note':'This checks declarations only, not the adequacy or numerical validity of a probability distribution. Fixed parameters are excluded from uncertainty propagation. A model interval is not an experimental confidence interval.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);a=p.parse_args()
    try:
        result=assess(json.loads(a.input.read_text(encoding='utf-8')))
        print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
        return 0 if not result['issues'] else 2
    except (ValueError,TypeError,OSError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
