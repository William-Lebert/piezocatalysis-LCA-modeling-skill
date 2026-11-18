#!/usr/bin/env python3
"""Capture a cyclic scenario's preflight, actual exchanges and calculation from one read-only session."""
import argparse
from contextlib import ExitStack
import hashlib
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace
from cyclic_foreground import build
from inventory_handoff import load_handoff
from cycle_model_plan import preflight
from openlca_readonly import Client,IPCError,calculate,numeric
from mapping_coverage import ident,read_entity
from result_coverage import analyze
from parameter_sensitivity import compare_impacts
from cycle_scenario_compare import compare


def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def same(a,b):return math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-14)


def check_plan_source(plan,source):
    model=build(source);expected={x['activity_id']:x for x in model['functional_unit_flows']};rows=plan.get('rows')
    if not isinstance(rows,list) or plan.get('functional_unit')!=model['functional_unit'] or plan.get('boundary')!=model['boundary']:raise ValueError('plan functional unit or boundary differs from foreground')
    actual={x['activity_id']:x for x in rows}
    if len(actual)!=len(rows) or actual.keys()!=expected.keys():raise ValueError('plan activities differ from foreground')
    for aid,x in expected.items():
        r=actual[aid]
        if not x['included']:
            if r.get('status')!='excluded':raise ValueError(aid+': excluded activity differs')
            continue
        amount=x['amount'];planned=r.get('amount_per_functional_unit')
        if r.get('status')=='excluded' or any(x[k]!=r.get(t) for k,t in [('unit','unit'),('stage','stage'),('cycle','cycle_id'),('direction','direction'),('flow_name','flow_name')]) or (amount is None)!=(planned is None) or (amount is not None and not same(amount,planned)):raise ValueError(aid+': plan differs from scenario foreground')


def check_parameter_overrides(overrides,available):
    if not isinstance(overrides,list):raise ValueError('parameter overrides must be a list')
    seen=set()
    for override in overrides:
        if not isinstance(override,dict) or not isinstance(override.get('name'),str) or not override['name'].strip():raise ValueError('parameter override requires a name')
        ctx=override.get('context') or {};key=(override['name'],ctx.get('@id'))
        if key in seen:raise ValueError('duplicate parameter override')
        seen.add(key)
        try:numeric(override.get('value'),'parameter override')
        except IPCError as exc:raise ValueError(str(exc)) from exc
        matches=[x for x in available if x.get('name')==key[0] and (x.get('context') or {}).get('@id')==key[1]]
        if len(matches)!=1 or matches[0].get('isProtected') is True:raise ValueError('parameter override is missing, ambiguous or protected: '+key[0])
        if key[1] is not None and ctx.get('@type')!=(matches[0].get('context') or {}).get('@type'):raise ValueError('parameter override context type differs')


def check_system_reference(system,root_process,binding):
    if ident(system.get('refProcess'))!=binding.get('root_uuid'):raise ValueError('binding root is not the product-system reference process')
    if ident(system.get('targetUnit'))!=binding.get('unit_uuid') or ident(system.get('targetFlowProperty'))!=binding.get('property_uuid'):raise ValueError('binding unit or flow property differs from product system')
    ref=system.get('refExchange') or {};rid=ref.get('internalId');flow=ident(ref.get('flow'))
    if not isinstance(root_process,dict) or ident(root_process)!=binding.get('root_uuid') or rid is None or not flow:raise ValueError('product-system reference exchange is unavailable')
    matches=[x for x in root_process.get('exchanges',[]) if x.get('internalId')==rid and x.get('isQuantitativeReference') is True and ident(x.get('flow'))==flow]
    if len(matches)!=1:raise ValueError('product-system reference exchange differs from root process')
    return {'ref_process':binding['root_uuid'],'reference_exchange_id':rid,'reference_flow':flow,'target_unit':binding['unit_uuid'],'target_flow_property':binding['property_uuid']}


def check_links(plan,coverage,binding):
    calc=coverage['calculation'];target=(calc.get('target') or {}).get('@id')
    if not target or target!=binding.get('system_uuid') or target!=(calc['setup'].get('target') or {}).get('@id'):raise ValueError('calculation system differs from binding')
    if isinstance(calc['setup'].get('amount'),bool) or calc['setup'].get('amount')!=1:raise ValueError('exactly one declared functional unit required')
    if not binding.get('unit_uuid') or binding['unit_uuid']!=(calc['setup'].get('unit') or {}).get('@id') or not binding.get('property_uuid') or binding['property_uuid']!=(calc['setup'].get('flowProperty') or {}).get('@id'):raise ValueError('calculation unit or flow property differs from binding')
    ids=binding.get('stages');root=binding.get('root_uuid');rows=coverage['link_review']['technical_exchanges']
    if not isinstance(ids,list) or not ids or len(ids)!=len(set(ids)):raise ValueError('invalid foreground stage list')
    root_rows=[x for x in rows if ident(x.get('process'))==root]
    if len(root_rows)!=len(ids):raise ValueError('root stage exchanges do not match declared stages')
    providers=[]
    for x in root_rows:
        ls=x.get('links') or []
        if x.get('is_input') is not True or not same(x.get('amount'),1) or x.get('status')!='linked' or len(ls)!=1:raise ValueError('root stage link is invalid')
        providers.append(ident(ls[0].get('provider')))
    if len(set(providers))!=len(providers) or set(providers)!=set(ids):raise ValueError('root stage providers differ')
    used=set();stage_map={};unresolved=[]
    for row in plan['rows']:
        if row['status']=='excluded':continue
        found=[x for x in binding.get('activities',[]) if x.get('activity_id')==row['activity_id']]
        if len(found)!=1:raise ValueError(row['activity_id']+': missing or duplicate binding')
        rec=found[0];pid=rec.get('process_uuid')
        if pid not in ids or rec.get('is_input')!=(row['direction']=='input'):raise ValueError(row['activity_id']+': stage or direction differs')
        if stage_map.setdefault(pid,row['stage'])!=row['stage']:raise ValueError('foreground process mixes declared stages')
        if row['status']=='unresolved':
            unresolved.append(row['activity_id'])
            if rec.get('provider_uuid') is not None:raise ValueError(row['activity_id']+': unresolved activity must not have provider')
            from audit_and_scale_inventory import unit_factor
            expected=row['amount_per_functional_unit']*unit_factor(row['unit'],rec['unit'])
            state='unlinked_candidate'
        elif row['status']=='preflight_matches_review_still_required' and not row['issues']:
            expected=row['dataset_amount_per_functional_unit'];actual=row['actual_reference']
            if rec.get('provider_uuid')!=actual['process_uuid'] or rec.get('flow_uuid')!=actual['reference_flow_uuid'] or rec.get('unit')!=actual['unit_name'] or actual['reference_is_input']==rec['is_input']:raise ValueError(row['activity_id']+': provider reference differs')
            state='linked'
        else:raise ValueError(row['activity_id']+': invalid preflight status')
        if expected is None or not same(rec['amount'],expected):raise ValueError(row['activity_id']+': amount differs from plan')
        matches=[]
        for x in rows:
            key=(ident(x.get('process')),x.get('exchange_internal_id'))
            if key in used or key[0]!=pid or ident(x.get('flow'))!=rec['flow_uuid'] or x.get('is_input')!=rec['is_input'] or (x.get('unit') or {}).get('name')!=rec['unit'] or not same(x.get('amount'),expected) or x.get('status')!=state:continue
            ls=x.get('links') or []
            if state=='linked' and (len(ls)!=1 or ident(ls[0].get('provider'))!=rec['provider_uuid']):continue
            matches.append(key)
        if len(matches)!=1:raise ValueError(row['activity_id']+': actual exchange or provider is missing/ambiguous')
        used.add(matches[0])
    extras=[x for x in rows if ident(x.get('process')) in ids and (ident(x.get('process')),x.get('exchange_internal_id')) not in used]
    if extras:raise ValueError('unaccounted foreground technical exchanges')
    if len(binding.get('activities',[]))!=len(used):raise ValueError('binding contains unused or duplicate activities')
    return {'checked_activities':len(used),'unresolved_activity_ids':unresolved}


def capture(client,source_path,inventory,manifest,mapping,assignments,binding,args,category_id,flow_ids):
    raw=source_path.read_bytes();source=json.loads(raw,parse_constant=lambda x: (_ for _ in ()).throw(ValueError('invalid JSON number '+x)));model=build(source)
    h=load_handoff(inventory,manifest,mapping,assignments)
    if h['input_sha256']!=hashlib.sha256(raw).hexdigest() or h['functional_unit']!=model['functional_unit'] or h['boundary']!=model['boundary'] or h['functional_unit_type']!='apparent_pollutant_removal':raise ValueError('inventory manifest differs from foreground')
    expected={x['activity_id']:x for x in model['functional_unit_flows']};actual={x['activity_id']:x for x in h['rows']}
    if expected.keys()!=actual.keys():raise ValueError('inventory activities differ from foreground')
    for aid,x in expected.items():
        y=actual[aid];a=x['amount'];b=y['amount_per_functional_unit']
        if any(x[k]!=y[t] for k,t in [('unit','unit'),('stage','stage'),('cycle','cycle_id'),('direction','direction'),('flow_name','flow_name'),('included','included'),('evidence_class','evidence_class')]) or x['source'].strip()!=y['source'] or (a is None)!=(b is None) or (a is not None and not same(a,b)):raise ValueError(aid+': inventory differs from rebuilt foreground')
    if isinstance(args.amount,bool) or args.amount!=1:raise ValueError('calculation amount must equal one functional unit')
    plan=preflight(h,client,args.mapping_database)
    check_plan_source(plan,source)
    def snapshot():
        system=read_entity(client,'ProductSystem',args.system_id)
        if not system or not isinstance(system.get('processes'),list):raise ValueError('product system or process list unavailable')
        processes={ident(ref):read_entity(client,'Process',ident(ref)) for ref in system['processes']}
        if any(not v for v in processes.values()):raise ValueError('system process unavailable')
        method=read_entity(client,'ImpactMethod',args.method_id);category=read_entity(client,'ImpactCategory',category_id)
        params=client.call('data/get/parameters',{'@type':'ProductSystem','@id':args.system_id})
        if not isinstance(params,list) or not isinstance(method,dict) or not isinstance(category,dict):raise ValueError('method, category or parameter snapshot unavailable')
        return {'system':system,'processes':processes,'method':method,'category':category,'parameters':params}
    before=snapshot();reference=check_system_reference(before['system'],before['processes'].get(binding.get('root_uuid')),binding);check_parameter_overrides(getattr(args,'parameters',[]),before['parameters']);args.include_total_flows=True;calc=calculate(client,args);after=snapshot()
    if digest(before)!=digest(after):raise ValueError('system, processes, method, selected category or parameters changed during calculation')
    if preflight(h,client,args.mapping_database)!=plan:raise ValueError('mapping preflight changed during calculation')
    coverage=analyze(calc,before['system'],before['processes'],before['category'],flow_ids)
    links=check_links(plan,coverage,binding)
    provider_ids={r['actual_reference']['process_uuid'] for r in plan['rows'] if r.get('actual_reference')}
    providers={pid:before['processes'].get(pid) for pid in provider_ids}
    if any(v is None for v in providers.values()):raise ValueError('mapped provider missing from system snapshot')
    return {'schema_version':'piezolca.bound-scenario/2','foreground_sha256':hashlib.sha256(raw).hexdigest(),'foreground_semantic_sha256':digest(source),'inventory_sha256':h['inventory_sha256'],'manifest_sha256':h['manifest_sha256'],'mapping_sha256':h['mapping_sha256'],'assignments_sha256':h['assignments_sha256'],'binding':binding,'binding_sha256':digest(binding),'system_reference':reference,'snapshot_sha256':digest(before),'provider_snapshots_sha256':digest(providers),'parameters_at_calculation':before['parameters'],'parameters_sha256':digest(before['parameters']),'parameter_overrides':calc['setup'].get('parameters',[]),'plan':plan,'plan_sha256':digest(plan),'coverage':coverage,'coverage_sha256':digest(coverage),'calculation_sha256':digest(calc),'link_check':links,'status':'observed_in_session_review_required','note':'Snapshot comparison covers the listed system/processes, method, selected category and parameters, not every LCIA category or licensed database file. Database and functional-unit labels are user assertions; human scientific review remains required.'}


def compare_bound(left,right,left_source,right_source,contexts):
    if any(x.get('schema_version')!='piezolca.bound-scenario/2' or x.get('status')!='observed_in_session_review_required' for x in (left,right)):raise ValueError('two version 2 captured scenario records are required; recapture older records')
    if not isinstance(contexts.get('cases'),list) or len(contexts['cases'])!=2:raise ValueError('exactly two ordered scenario contexts are required')
    for record,source in ((left,left_source),(right,right_source)):
        if digest(record['binding'])!=record['binding_sha256'] or any(record['plan'].get(k)!=record.get(k) for k in ('inventory_sha256','manifest_sha256','mapping_sha256','assignments_sha256')):raise ValueError('captured binding or plan hashes differ')
        ref=record.get('system_reference') or {};binding=record['binding']
        if ref.get('ref_process')!=binding.get('root_uuid') or ref.get('target_unit')!=binding.get('unit_uuid') or ref.get('target_flow_property')!=binding.get('property_uuid') or ref.get('reference_exchange_id') is None or not ref.get('reference_flow'):raise ValueError('captured product-system reference differs from binding')
        if digest(record['plan'])!=record.get('plan_sha256') or digest(record['coverage'])!=record.get('coverage_sha256') or digest(record['coverage']['calculation'])!=record.get('calculation_sha256') or digest(record['parameters_at_calculation'])!=record.get('parameters_sha256'):raise ValueError('captured plan, result, coverage or parameters have changed')
        check_plan_source(record['plan'],source)
        if check_links(record['plan'],record['coverage'],record['binding'])!=record['link_check']:raise ValueError('captured exchange checks differ')
    if digest(left_source)!=left.get('foreground_semantic_sha256') or digest(right_source)!=right.get('foreground_semantic_sha256'):raise ValueError('scenario foreground does not match captured record')
    if left.get('mapping_sha256')!=right.get('mapping_sha256') or left.get('assignments_sha256')!=right.get('assignments_sha256'):raise ValueError('scenario mappings or assignments differ; compare only after independent review')
    if left.get('provider_snapshots_sha256')!=right.get('provider_snapshots_sha256'):raise ValueError('background provider snapshots differ')
    a=left['coverage']['calculation'];b=right['coverage']['calculation']
    if (a.get('setup') or {}).get('parameters',[])!=left['parameter_overrides'] or (b.get('setup') or {}).get('parameters',[])!=right['parameter_overrides']:raise ValueError('calculation parameter overrides differ from capture')
    result=compare(left_source,right_source,left['plan'],a,b,contexts)
    if result['context_check']['issues']:raise ValueError('declared or calculated scenario contexts are not comparable')
    if any(c.get('lcia_method_uuid')!=(calc.get('impact_method') or {}).get('@id') or c.get('system_boundary')!=src.get('boundary') for c,calc,src in zip(contexts['cases'],(a,b),(left_source,right_source))):raise ValueError('declared method or boundary differs from captured model')
    unavailable=[]
    if left['link_check']['unresolved_activity_ids'] or right['link_check']['unresolved_activity_ids']:unavailable.append('unresolved_foreground_exchanges')
    if left['parameters_at_calculation'] or right['parameters_at_calculation'] or left['parameter_overrides'] or right['parameter_overrides']:unavailable.append('parameters_require_independent_linearity_review')
    base_providers=set(result['baseline_provider_demands'])
    for impact in a['impacts']:
        values=[x['amount'] for x in impact['contributions']]
        if any(v<0 for v in values) and any(v>0 for v in values):unavailable.append('offsetting_contributions')
        if any(x['amount']!=0 and ((x.get('techFlow') or {}).get('provider') or {}).get('@id') not in base_providers for x in impact['contributions']):unavailable.append('unaccounted_contribution')
        if impact['amount']==0:unavailable.append('zero_baseline_requires_review')
    unavailable=list(dict.fromkeys(unavailable))
    if unavailable:
        for row in result['impacts']:row['linear_delta_estimate']=None;row['actual_minus_linear']=None
    result['bound_scenario_comparison']={'baseline_capture_sha256':digest(left),'scenario_capture_sha256':digest(right),'linear_estimate_unavailable_reasons':unavailable,'note':'Bound snapshots support a scoped exchange check, not proof of complete background or scientific equivalence.'}
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    c=sub.add_parser('capture');c.add_argument('spec',type=Path);c.add_argument('--output',type=Path,required=True)
    a=sub.add_parser('compare');a.add_argument('--baseline',type=Path,required=True);a.add_argument('--scenario',type=Path,required=True);a.add_argument('--baseline-input',type=Path,required=True);a.add_argument('--scenario-input',type=Path,required=True);a.add_argument('--contexts',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    opt=p.parse_args()
    try:
        def read(path):return json.loads(Path(path).read_text(encoding='utf-8'),parse_constant=lambda x: (_ for _ in ()).throw(ValueError('invalid JSON number '+x)))
        if opt.command=='capture':
            spec=read(opt.spec);base=opt.spec.resolve().parent
            def path(key):return (base/Path(spec[key])).resolve()
            config=spec['calculation'];args=SimpleNamespace(**config);args.mapping_database=spec['mapping_database'];args.parameters=config.get('parameters',[])
            if isinstance(args.amount,bool) or args.amount!=1:raise ValueError('calculation amount must equal one functional unit')
            with ExitStack() as stack:
                if 'start_local' in spec:
                    from openlca_local_launch import launch
                    lc=spec['start_local'];port=stack.enter_context(launch(Path(lc['app']),Path(lc['workspace']),lc['database']))
                else:port=spec['port']
                result=capture(Client(port,120),path('foreground'),path('inventory'),path('manifest'),path('mapping'),path('assignments'),read(path('binding')),args,spec['category_id'],spec.get('flow_ids',[]))
            result['foreground_semantic_sha256']=digest(read(path('foreground')))
        else:
            result=compare_bound(read(opt.baseline),read(opt.scenario),read(opt.baseline_input),read(opt.scenario_input),read(opt.contexts))
            result['input_sha256']={key:hashlib.sha256(path.read_bytes()).hexdigest() for key,path in [('baseline',opt.baseline),('scenario',opt.scenario),('baseline-input',opt.baseline_input),('scenario-input',opt.scenario_input),('contexts',opt.contexts)]}
        with opt.output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
        print(json.dumps({'output':str(opt.output),'status':result.get('status',result.get('context_check',{}).get('status'))},ensure_ascii=False));return 0
    except (OSError,ValueError,TypeError,KeyError,AttributeError,OverflowError,IPCError) as exc:print('ERROR:',exc,file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
