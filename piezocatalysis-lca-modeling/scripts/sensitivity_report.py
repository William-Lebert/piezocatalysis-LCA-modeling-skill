#!/usr/bin/env python3
"""Compare sourced absolute LCIA contributions under explicit one-variable scenarios.

This is an additive, user-asserted approximation; it is not an LCA engine.
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import sys
from pathlib import Path

SCOPE_FIELDS = ('system_boundary', 'geography', 'database', 'database_version', 'system_model',
                'allocation', 'lcia_method', 'lcia_version', 'temporal_scope', 'cutoff_rules',
                'recycling_approach', 'electricity_scenario', 'illumination_decision')
EVIDENCE = {'measured', 'reported', 'calculated', 'proxy', 'scenario'}


def obj(x, path):
    if not isinstance(x, dict): raise ValueError(f'{path}: must be an object')
    return x


def text(x, path):
    if not isinstance(x, str) or not x.strip() or 'replace-me' in x.lower():
        raise ValueError(f'{path}: nonempty, non-placeholder text required')
    return x.strip()


def num(x, path):
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ValueError(f'{path}: must be a finite JSON number')
    try: n=float(x)
    except (OverflowError, ValueError): raise ValueError(f'{path}: must be finite') from None
    if not math.isfinite(n): raise ValueError(f'{path}: must be finite')
    return n


def evidence(x, path):
    if not isinstance(x,str) or x not in EVIDENCE:raise ValueError(f'{path}: invalid evidence_class')
    return x


def valid_scope(value, path):
    scope=obj(value,path);fu=obj(scope.get('functional_unit'),path+'.functional_unit')
    if set(scope)!=set(SCOPE_FIELDS)|{'functional_unit'}:
        raise ValueError(path+': scope must contain exactly the documented comparison fields')
    if set(fu)!={'description','amount','unit'}:
        raise ValueError(path+'.functional_unit: expected exactly description, amount and unit')
    result={'functional_unit': {'description': text(fu.get('description'),path+'.functional_unit.description'),
             'amount': num(fu.get('amount'),path+'.functional_unit.amount'),
             'unit': text(fu.get('unit'),path+'.functional_unit.unit')}}
    if result['functional_unit']['amount']<=0:raise ValueError(path+': functional-unit amount must be positive')
    for field in SCOPE_FIELDS:result[field]=text(scope.get(field),path+'.'+field)
    return result


def validate(data):
    data=obj(data,'input');description=text(data.get('description'),'description')
    raw_routes=data.get('routes')
    if not isinstance(raw_routes,list) or len(raw_routes)<2:raise ValueError('routes: at least two routes required')
    routes={};canonical_scope=None;canonical_units=None
    for i,raw in enumerate(raw_routes):
        r=obj(raw,f'routes[{i}]');rid=text(r.get('id'),f'routes[{i}].id')
        if rid in routes:raise ValueError(f'duplicate route: {rid}')
        if r.get('result_basis')!='absolute':raise ValueError(f'route {rid}: result_basis must be absolute')
        scope=valid_scope(r.get('scope'),f'route {rid}.scope')
        if canonical_scope is None:canonical_scope=scope
        elif scope != canonical_scope:raise ValueError(f'route {rid}: incompatible comparison scope')
        cats=obj(r.get('impact_categories'),f'route {rid}.impact_categories')
        if not cats:raise ValueError(f'route {rid}: no impact categories')
        units={};totals={};sources={}
        for cat,value in cats.items():
            text(cat,'impact category id');v=obj(value,f'{rid}.{cat}')
            units[cat]=text(v.get('unit'),f'{rid}.{cat}.unit')
            totals[cat]=num(v.get('total'),f'{rid}.{cat}.total')
            sources[cat]={'source':text(v.get('source'),f'{rid}.{cat}.source'),
                          'evidence_class':evidence(v.get('evidence_class'),f'{rid}.{cat}')}
        if canonical_units is None:canonical_units=units
        elif units!=canonical_units:raise ValueError(f'route {rid}: incompatible impact categories or units')
        raw_components=r.get('components')
        if r.get('components_are_non_overlapping') is not True:
            raise ValueError(f'route {rid}: components_are_non_overlapping must be explicitly true')
        if not isinstance(raw_components,list) or not raw_components:raise ValueError(f'route {rid}: components required')
        components={}
        for j,raw_comp in enumerate(raw_components):
            comp=obj(raw_comp,f'{rid}.components[{j}]');cid=text(comp.get('id'),f'{rid}.components[{j}].id')
            if cid in components:raise ValueError(f'route {rid}: duplicate component {cid}')
            impacts=obj(comp.get('impacts'),f'{rid}.{cid}.impacts')
            if set(impacts)!=set(units):raise ValueError(f'route {rid} component {cid}: impact categories incomplete')
            components[cid]={'source':text(comp.get('source'),f'{rid}.{cid}.source'),
                             'evidence_class':evidence(comp.get('evidence_class'),f'{rid}.{cid}'),
                             'impacts':{c:num(impacts[c],f'{rid}.{cid}.{c}') for c in units}}
        for cat,total in totals.items():
            actual=math.fsum(comp['impacts'][cat] for comp in components.values())
            if not math.isfinite(actual) or not math.isclose(actual,total,rel_tol=1e-9,abs_tol=0.0):
                raise ValueError(f'route {rid} category {cat}: components do not reconcile with absolute total')
        routes[rid]={'scope':scope,'totals':totals,'total_sources':sources,'components':components}
    scenarios=data.get('scenarios')
    if not isinstance(scenarios,list) or not scenarios:raise ValueError('scenarios: nonempty list required')
    seen={'baseline'};clean=[]
    for i,raw in enumerate(scenarios):
        sc=obj(raw,f'scenarios[{i}]');sid=text(sc.get('id'),f'scenarios[{i}].id')
        if sid in seen:raise ValueError(f'duplicate/reserved scenario: {sid}')
        seen.add(sid);variable=text(sc.get('variable'),sid+'.variable');unit=text(sc.get('unit'),sid+'.unit')
        source=text(sc.get('source'),sid+'.source');classification=evidence(sc.get('evidence_class'),sid)
        old,new=sc.get('baseline'),sc.get('value')
        if isinstance(old,str) and isinstance(new,str):old=text(old,sid+'.baseline');new=text(new,sid+'.value')
        else:old=num(old,sid+'.baseline');new=num(new,sid+'.value')
        if old==new:raise ValueError(f'{sid}: baseline and alternative must differ')
        if unit=='fraction' and (isinstance(old,str) or isinstance(new,str) or not 0<=old<=1 or not 0<=new<=1):
            raise ValueError(f'{sid}: fraction must be between 0 and 1')
        if unit=='uses' and (isinstance(old,str) or isinstance(new,str) or old<1 or new<1):
            raise ValueError(f'{sid}: effective uses must be at least 1')
        changes=sc.get('adjustments')
        if not isinstance(changes,list) or not changes:raise ValueError(f'{sid}: adjustments required')
        checks=set();adjustments=[]
        for j,item in enumerate(changes):
            a=obj(item,f'{sid}.adjustments[{j}]');route=text(a.get('route'),sid+'.route');component=text(a.get('component'),sid+'.component')
            if route not in routes or component not in routes[route]['components']:raise ValueError(f'{sid}: unknown route/component {route}/{component}')
            if (route,component) in checks:raise ValueError(f'{sid}: duplicate route/component adjustment')
            checks.add((route,component));op=a.get('operator')
            if op not in ('linear','inverse','replace'):raise ValueError(f'{sid}: invalid operator')
            adj={'route':route,'component':component,'operator':op}
            if op in ('linear','inverse'):
                if isinstance(old,str) or isinstance(new,str) or old<=0 or new<0 or (op=='inverse' and new==0):
                    raise ValueError(f'{sid}: ratio operators require positive baseline and valid alternative')
                multiplier=new/old if op=='linear' else old/new
                if not math.isfinite(multiplier) or (multiplier==0 and new!=0):raise ValueError(f'{sid}: non-finite or underflowed multiplier')
                adj['multiplier']=multiplier
            else:
                impacts=obj(a.get('replacement_impacts'),sid+'.replacement_impacts')
                if set(impacts)!=set(canonical_units):raise ValueError(f'{sid}: replacement impacts incomplete')
                adj['replacement_source']=text(a.get('replacement_source'),sid+'.replacement_source')
                adj['replacement_evidence_class']=evidence(a.get('replacement_evidence_class'),sid+'.replacement_evidence_class')
                adj['replacement_impacts']={c:num(impacts[c],sid+'.'+c) for c in canonical_units}
            adjustments.append(adj)
        clean.append({'id':sid,'variable':variable,'baseline':old,'value':new,'unit':unit,'evidence_class':classification,'source':source,'adjustments':adjustments})
    return description,routes,canonical_units,clean


def rank(results,cat):
    order=sorted(results,key=lambda rid:(results[rid][cat]['absolute'],rid));groups=[]
    for rid in order:
        if not groups or results[groups[-1][0]][cat]['absolute'] != results[rid][cat]['absolute']:groups.append([rid])
        else:groups[-1].append(rid)
    return groups


def build(data):
    description,routes,units,scenarios=validate(data)
    cases=[];base_ranks={}
    for sc in [None,*scenarios]:
        components={rid:copy.deepcopy(r['components']) for rid,r in routes.items()}
        if sc:
            for a in sc['adjustments']:
                comp=components[a['route']][a['component']]
                comp['baseline_source']=comp['source']
                comp['baseline_evidence_class']=comp['evidence_class']
                comp['scenario_evidence_class']=sc['evidence_class']
                if a['operator']=='replace':
                    comp['impacts']=a['replacement_impacts'].copy();comp['source']=a['replacement_source'];comp['evidence_class']=a['replacement_evidence_class']
                else:
                    scaled={}
                    for c,v in comp['impacts'].items():
                        scaled[c]=num(v*a['multiplier'],sc['id']+'.scaled.'+c)
                        if v!=0 and a['multiplier']!=0 and scaled[c]==0:raise ValueError(sc['id']+': scaled impact underflow')
                    comp['impacts']=scaled
                    comp['source']=comp['source']+'; scaled under '+sc['id']+' ('+sc['source']+')'
                    comp['evidence_class']='calculated'
        results={}
        for rid,r in routes.items():
            results[rid]={}
            for cat,unit in units.items():
                value=num(math.fsum(c['impacts'][cat] for c in components[rid].values()),rid+'.'+cat+'.absolute')
                base=r['totals'][cat];delta=num(value-base,rid+'.'+cat+'.delta')
                pct=None if base==0 else delta/abs(base)*100
                if pct is not None and not math.isfinite(pct):pct=None
                results[rid][cat]={'absolute':value,'unit':unit,'baseline':base,'delta':delta,'change_percent':pct}
        rankings={}
        for cat in units:
            groups=rank(results,cat)
            if sc is None:base_ranks[cat]=groups
            rankings[cat]={'groups':groups,'changed_from_baseline':groups!=base_ranks[cat]}
        cases.append({'id':sc['id'] if sc else 'baseline','change':sc,'results':results,'rankings':rankings,'components':components})
    return {'description':description,'input_result_basis':'absolute','components_non_overlapping_user_asserted':True,
            'scope_user_asserted':next(iter(routes.values()))['scope'],
            'baseline_total_sources':{rid:r['total_sources'] for rid,r in routes.items()},'cases':cases,
            'limitations':['Absolute impacts and additive decomposition are user supplied; no LCA engine is run.',
                'Compatible metadata are user asserted, not scientifically verified.',
                'Each case changes only the explicitly identified variable and components; all other inputs are held fixed.',
                'Linear/inverse scaling must be justified; nonlinear recovery or proxy changes require explicit replacement impacts.',
                'A null percent means a zero baseline or a non-finite percentage; ranking uses exact numeric ties.']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('--csv',type=Path,help='new file for absolute results; existing files are never replaced');args=p.parse_args()
    try:
        def bad_constant(x):raise ValueError('non-standard JSON constant: '+x)
        data=json.loads(args.input.read_text(encoding='utf8'),parse_constant=bad_constant)
        report=build(data);output=json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)
        if args.csv:
            with args.csv.open('x',encoding='utf8',newline='') as stream:
                writer=csv.writer(stream,lineterminator='\n');writer.writerow(['case','route','category','unit','absolute','baseline','delta','change_percent'])
                for case in report['cases']:
                    for rid,values in case['results'].items():
                        for cat,item in values.items():
                            cells=[case['id'],rid,cat,item['unit'],item['absolute'],item['baseline'],item['delta'],'' if item['change_percent'] is None else item['change_percent']]
                            writer.writerow(["'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v for v in cells])
        print(output);return 0
    except (OSError,UnicodeError,ValueError,OverflowError,ZeroDivisionError,TypeError) as exc:
        print(f'ERROR: {exc}',file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
