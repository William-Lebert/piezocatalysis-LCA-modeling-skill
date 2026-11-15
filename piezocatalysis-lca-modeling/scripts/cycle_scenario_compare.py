#!/usr/bin/env python3
"""Compare independently built cyclic scenarios and a linear background contribution estimate."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

from cyclic_foreground import build
from openlca_readonly import IPCError, numeric
from parameter_sensitivity import compare_impacts
from scenario_comparability import assess


def activity_rows(source):
    result=build(source)
    return result,{x['activity_id']:x for x in result['functional_unit_flows'] if x['included']}


def demands(plan, baseline_rows, scenario_rows):
    planned={r['activity_id']:r for r in plan['rows'] if r['status']!='excluded'}
    if planned.keys()!=baseline_rows.keys() or planned.keys()!=scenario_rows.keys():
        raise ValueError('scenario activities differ from the reviewed baseline mapping; update the mapping first')
    base={}; alternate={}; unresolved=[]; detailed=[]
    for aid,p in planned.items():
        a,b=baseline_rows[aid],scenario_rows[aid]
        for field,source_field in [('flow_name','flow_name'),('unit','unit'),('direction','direction'),('stage','stage'),('cycle_id','cycle')]:
            if p[field]!=a[source_field] or a[source_field]!=b[source_field]:
                raise ValueError(aid+': activity identity, unit, direction, stage or cycle changed')
        x=numeric(a['amount'],aid+' baseline amount');y=numeric(b['amount'],aid+' scenario amount')
        if not math.isclose(x,numeric(p['amount_per_functional_unit'],aid+' plan amount'),rel_tol=1e-10,abs_tol=1e-15):
            raise ValueError(aid+': baseline input differs from checked plan')
        if p['status']=='unresolved':
            unresolved.append(aid);detailed.append({'activity_id':aid,'baseline':x,'scenario':y,'unit':a['unit'],'status':'unresolved'});continue
        if p['status']!='preflight_matches_review_still_required' or p['issues']:
            raise ValueError(aid+': mapping is not ready for preflight')
        factor=float(p['mapping_user_asserted']['conversion_factor'])
        if not math.isfinite(factor) or factor<=0:raise ValueError(aid+': invalid conversion factor')
        x2=x*factor;y2=y*factor
        if not math.isclose(x2,numeric(p['dataset_amount_per_functional_unit'],aid+' plan dataset amount'),rel_tol=1e-9,abs_tol=1e-15):
            raise ValueError(aid+': conversion differs from checked plan')
        provider=p['actual_reference']['process_uuid']
        base[provider]=base.get(provider,0)+x2;alternate[provider]=alternate.get(provider,0)+y2
        detailed.append({'activity_id':aid,'baseline':x,'scenario':y,'unit':a['unit'],
                         'provider_uuid':provider,'dataset_unit':p['actual_reference']['unit_name'],
                         'dataset_baseline':x2,'dataset_scenario':y2,'mapping_type':p['mapping_type'],
                         'baseline_source':a['source'],'scenario_source':b['source'],
                         'baseline_evidence_class':a['evidence_class'],'scenario_evidence_class':b['evidence_class'],
                         'baseline_derivation':a['derivation'],'scenario_derivation':b['derivation'],'status':'mapped_candidate'})
    return base,alternate,unresolved,detailed


def compare(baseline_source, scenario_source, plan, baseline_calc, scenario_calc, contexts):
    left,a=activity_rows(baseline_source);right,b=activity_rows(scenario_source)
    if plan.get('amount_basis')!='per_functional_unit':raise ValueError('plan must use per-functional-unit amounts')
    context=assess(contexts); issues=list(context['issues'])
    if left['functional_unit'].get('unit')!=right['functional_unit'].get('unit') or left['functional_unit'].get('value')!=right['functional_unit'].get('value'):
        issues.append({'field':'actual_functional_unit','status':'mismatch'})
    if left['boundary']!=right['boundary']:issues.append({'field':'actual_boundary','status':'mismatch'})
    left_method=(baseline_calc.get('impact_method') or {}).get('@id');right_method=(scenario_calc.get('impact_method') or {}).get('@id')
    if not left_method or not right_method or left_method!=right_method:
        issues.append({'field':'calculated_method','status':'missing_or_mismatch'})
    for key in ('name','version','system_model'):
        x=(baseline_calc.get('database') or {}).get(key);y=(scenario_calc.get('database') or {}).get(key)
        if not x or not y or x!=y:issues.append({'field':'calculation_database_'+key,'status':'missing_or_mismatch'})
    if baseline_calc.get('functional_unit_user_asserted')!=scenario_calc.get('functional_unit_user_asserted'):
        issues.append({'field':'calculated_functional_unit_label','status':'mismatch'})
    if baseline_calc.get('setup',{}).get('amount')!=scenario_calc.get('setup',{}).get('amount'):
        issues.append({'field':'calculation_amount','status':'mismatch'})
    bg,sg,unresolved,rows=demands(plan,a,b)
    proxies=[x['activity_id'] for x in rows if x.get('mapping_type') in ('proxy','constructed')]
    try:
        impacts=compare_impacts(baseline_calc['impacts'],scenario_calc['impacts'])
    except ValueError as exc:
        issues.append({'field':'impact_categories','status':'not_comparable','detail':str(exc)})
        impacts=[]
    base_impacts={x['category']['@id']:x for x in baseline_calc['impacts']}
    for impact in impacts:
        source=base_impacts[impact['category']['@id']];contrib={}
        for c in source['contributions']:
            pid=(c.get('techFlow',{}).get('provider') or {}).get('@id')
            if pid in contrib:raise ValueError('multiple technical flows share provider; linear estimate is ambiguous')
            contrib[pid]=numeric(c['amount'],'contribution')
        if any(p not in contrib or bg[p]==0 for p in bg):
            estimate=None
        else:estimate=math.fsum(contrib[p]*(sg[p]/bg[p]-1) for p in bg)
        impact['linear_delta_estimate']=estimate
        impact['actual_minus_linear']=None if estimate is None else impact['delta']-estimate
    return {'schema_version':'piezolca.cycle-scenario-comparison/1',
            'context_check':{'status':'not_comparable' if issues else 'declared_contexts_match',
                             'issues':issues,'note':'User declarations and simple direct checks, not independent proof of equivalence.'},
            'ranking_permitted':False,
            'ranking_review_note':'Automatic checks do not establish equivalent pollutant identity, performance or scientific comparability; independent review is required.',
            'baseline_campaign':left['campaign'],'scenario_campaign':right['campaign'],
            'provenance':{'baseline_mapping_sha256':plan.get('mapping_sha256'),'baseline_assignments_sha256':plan.get('assignments_sha256'),
                          'baseline_inventory_sha256':plan.get('inventory_sha256'),'baseline_database_user_asserted':baseline_calc.get('database'),
                          'scenario_database_user_asserted':scenario_calc.get('database'),
                          'baseline_calculation_setup':baseline_calc.get('setup'),'scenario_calculation_setup':scenario_calc.get('setup'),
                          'software_user_asserted':baseline_calc.get('software')},
            'activities':rows,'baseline_provider_demands':bg,'scenario_provider_demands':sg,
            'unresolved_activity_ids':unresolved,'proxy_activity_ids':proxies,
            'baseline_warnings':left['warnings'],'scenario_warnings':right['warnings'],
            'impacts':impacts,'note':'Actual calculations are supplied separately; verify each scenario model exchanges and links. Linear estimate rescales baseline provider contributions and excludes unresolved exchanges; nonlinear or changed background effects require real recalculation.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('baseline-input','scenario-input','baseline-plan','baseline-result','scenario-result','contexts'):p.add_argument('--'+arg,type=Path,required=True)
    args=p.parse_args()
    try:
        paths={k:getattr(args,k.replace('-','_')) for k in ('baseline-input','scenario-input','baseline-plan','baseline-result','scenario-result','contexts')}
        raw={k:v.read_bytes() for k,v in paths.items()}
        data={k:json.loads(v,parse_constant=lambda x: (_ for _ in ()).throw(ValueError('invalid JSON number '+x))) for k,v in raw.items()}
        report=compare(data['baseline-input'],data['scenario-input'],data['baseline-plan'],data['baseline-result'],data['scenario-result'],data['contexts'])
        report['input_sha256']={k:hashlib.sha256(v).hexdigest() for k,v in raw.items()}
        report['code_sha256']={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ('cycle_scenario_compare.py','cyclic_foreground.py','scenario_comparability.py','parameter_sensitivity.py')}
        print(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False));return 0
    except (OSError,ValueError,TypeError,KeyError,OverflowError,IPCError) as exc:
        print('ERROR:',exc,file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
