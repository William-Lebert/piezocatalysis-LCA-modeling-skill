#!/usr/bin/env python3
"""Prepare traceable chart data from project reports; no database writes."""
import argparse,hashlib,json,math,sys
from pathlib import Path
from cyclic_foreground import build
from audit_and_scale_inventory import unit_factor

SCHEMA='piezolca.plot-data/1'


def num(x,label):
    if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x):raise ValueError(label+': finite number required')
    return float(x)


def same(a,b):
    scale=max(abs(a),abs(b),1e-300)
    return abs(a-b)<=1e-9*scale


def cycles(source):
    d=build(source);rows=[]
    for c in d['cycles']:
        energies=[x for x in d['functional_unit_flows'] if x['stage']=='treatment' and x['cycle']==c['cycle_id'] and x['included'] and x['kind']=='energy']
        if not energies or any(x['campaign_value'] is None for x in energies):energy=None
        else:energy=math.fsum(num(x['campaign_value'],'energy')*unit_factor(x['campaign_unit'],'kWh') for x in energies)
        v=c['apparent_removal_mg']; interval=c['apparent_removal_interval_mg']
        rows.append({'cycle':c['cycle_id'],'apparent_removal_mg':v,'removal_lower_mg':interval[0] if interval else None,
                     'removal_upper_mg':interval[1] if interval else None,'treatment_energy_kwh':energy,
                     'energy_activity_count':len(energies),'effluent_qualifier':c['effluent_qualifier']})
    return {'kind':'cycles','title_zh':'逐循环表观去除与处理能耗','title_en':'Cycle apparent removal and energy',
            'functional_unit':{**d['functional_unit'],'description':d['functional_unit'].get('description') or 'water-phase apparent pollutant removal'},'data_basis':'per campaign cycle, not per functional unit',
            'rows':rows,'warnings':d['warnings']+['Water-phase apparent removal is not proof of mineralization. Missing energy is not zero.']}


def stage_contributions(report,plan,binding):
    if report.get('schema_version')!='piezolca.result-coverage/1' or plan.get('schema_version')!='piezolca.cycle-model-plan/1':raise ValueError('unsupported report or plan schema')
    if plan.get('amount_basis')!='per_functional_unit':raise ValueError('plan is not per functional unit')
    calc=report['calculation'];target=(calc.get('target') or {}).get('@id')
    if not target or target!=binding.get('system_uuid'):raise ValueError('model binding and calculated product system differ')
    if num((calc.get('setup') or {}).get('amount'),'functional unit amount')!=1:raise ValueError('stage allocation requires a calculation of exactly one declared functional unit')
    ref_rows=report['link_review']['technical_exchanges'];used=set();demands={};counts={};unresolved=[];stage_processes={}
    stage_ids=binding.get('stages')
    if not isinstance(stage_ids,list) or not stage_ids or len(stage_ids)!=len(set(stage_ids)):raise ValueError('binding requires unique foreground stage identifiers')
    root=binding.get('root_uuid');root_rows=[x for x in ref_rows if (x.get('process') or {}).get('@id')==root]
    if not root or len(root_rows)!=len(stage_ids):raise ValueError('root must contain exactly one link to each stage')
    root_providers=[];root_flows={}
    for x in root_rows:
        links=x.get('links') or []
        if x.get('is_input') is not True or num(x.get('amount'),'root stage demand')!=1 or x.get('status')!='linked' or len(links)!=1:
            raise ValueError('root stage link must be an input of one service')
        provider_id=(links[0].get('provider') or {}).get('@id');root_providers.append(provider_id);root_flows[provider_id]=(x.get('flow') or {}).get('@id')
    if len(root_providers)!=len(set(root_providers)) or set(root_providers)!=set(stage_ids):raise ValueError('root stage providers differ from binding')
    for row in plan['rows']:
        if row['status']=='excluded':continue
        if row['status']=='unresolved':
            unresolved.append(row['activity_id'])
            bound=[x for x in binding['activities'] if x['activity_id']==row['activity_id']]
            if len(bound)!=1 or bound[0].get('provider_uuid') is not None:raise ValueError('unresolved activity binding missing or linked')
            rec=bound[0]
            if rec['process_uuid'] not in stage_ids or rec['is_input']!=(row['direction']=='input'):raise ValueError('unresolved stage or direction mismatch')
            prior_stage=stage_processes.setdefault(rec['process_uuid'],row['stage'])
            if prior_stage!=row['stage']:raise ValueError('a foreground process mixes declared stages')
            expected=num(row['amount_per_functional_unit'],'unresolved amount')*unit_factor(row['unit'],rec['unit'])
            if not same(num(rec['amount'],'unresolved bound amount'),expected):raise ValueError('unresolved activity quantity mismatch')
            found=[x for x in ref_rows if (x.get('process') or {}).get('@id')==rec['process_uuid'] and (x.get('flow') or {}).get('@id')==rec['flow_uuid'] and x.get('is_input')==rec['is_input'] and (x.get('unit') or {}).get('name')==rec['unit'] and same(num(x.get('amount'),'unresolved exchange amount'),expected) and x.get('status')=='unlinked_candidate' and (rec['process_uuid'],x['exchange_internal_id']) not in used]
            if len(found)!=1:raise ValueError('unresolved exchange not uniquely verified')
            used.add((rec['process_uuid'],found[0]['exchange_internal_id']));continue
        if row['status']!='preflight_matches_review_still_required' or row['issues']:raise ValueError('unreviewed mapping')
        matches=[x for x in binding['activities'] if x['activity_id']==row['activity_id']]
        if len(matches)!=1:raise ValueError('binding activity is missing or duplicated')
        rec=matches[0]
        if rec['process_uuid'] not in stage_ids or rec['is_input']!=(row['direction']=='input'):raise ValueError('bound stage or direction mismatch')
        if row['actual_reference']['reference_is_input']==rec['is_input']:raise ValueError('provider reference direction mismatch')
        prior_stage=stage_processes.setdefault(rec['process_uuid'],row['stage'])
        if prior_stage!=row['stage']:raise ValueError('a foreground process mixes declared stages')
        amount=num(row['dataset_amount_per_functional_unit'],'dataset demand');provider=row['actual_reference']['process_uuid']
        if rec['provider_uuid']!=provider or rec['flow_uuid']!=row['actual_reference']['reference_flow_uuid'] or rec['unit']!=row['actual_reference']['unit_name'] or not same(num(rec['amount'],'bound demand'),amount):
            raise ValueError('binding does not match selected mapping and amount')
        found=[]
        for x in ref_rows:
            if (x.get('process') or {}).get('@id')!=rec['process_uuid'] or (x.get('flow') or {}).get('@id')!=rec['flow_uuid'] or x.get('is_input')!=rec['is_input'] or (x.get('unit') or {}).get('name')!=rec['unit'] or not same(num(x.get('amount'),'exchange amount'),amount):continue
            ls=x.get('links') or []
            if x.get('status')=='linked' and len(ls)==1 and (ls[0].get('provider') or {}).get('@id')==provider and (rec['process_uuid'],x['exchange_internal_id']) not in used:found.append(x)
        if len(found)!=1:raise ValueError('exchange/link not uniquely verified for '+row['activity_id'])
        used.add((rec['process_uuid'],found[0]['exchange_internal_id']))
        stage=row['stage'];
        if stage not in ('preparation','treatment'):raise ValueError('unknown stage')
        demands.setdefault(provider,{});demands[provider][stage]=demands[provider].get(stage,0)+amount
        counts[stage]=counts.get(stage,0)+1
    for x in ref_rows:
        if (x.get('process') or {}).get('@id') in stage_ids and ((x.get('process') or {}).get('@id'),x.get('exchange_internal_id')) not in used:
            raise ValueError('unaccounted technical exchange in a foreground stage')
    contribs=report['hotspots']['contributions_by_absolute_amount'];total=num(report['hotspots']['total'],'impact total');actual=math.fsum(num(x['amount'],'contribution') for x in contribs)
    if abs(total-actual)>1e-9*max(abs(total),math.fsum(abs(num(x['amount'],'contribution')) for x in contribs),1e-300):raise ValueError('process contributions do not reconcile with impact total')
    provider_ids=[(x['tech_flow'].get('provider') or {}).get('@id') for x in contribs]
    if len(provider_ids)!=len(set(provider_ids)) or not set(demands).issubset(provider_ids):raise ValueError('provider contribution list is missing or ambiguous')
    for stage_id in stage_ids:
        matches=[x for x in contribs if (x['tech_flow'].get('provider') or {}).get('@id')==stage_id]
        if len(matches)!=1 or not root_flows.get(stage_id) or (matches[0]['tech_flow'].get('flow') or {}).get('@id')!=root_flows[stage_id]:
            raise ValueError('root link flow does not match stage reference flow')
    proxies=[r['activity_id'] for r in plan['rows'] if r.get('status')=='preflight_matches_review_still_required' and r.get('mapping_type') in ('proxy','constructed')]
    stages={'preparation':0.0,'treatment':0.0};provider_seen=set()
    for x in contribs:
        val=num(x['amount'],'contribution');ref=(x['tech_flow'].get('provider') or {});pid=ref.get('@id')
        if val==0:continue
        if pid in provider_seen:raise ValueError('multiple technical flows per provider are not supported')
        provider_seen.add(pid)
        if pid not in demands or ref.get('processType')!='LCI_RESULT':raise ValueError('nonzero contribution is not an allocated LCI_RESULT provider')
        denom=math.fsum(demands[pid].values())
        if denom<=0:raise ValueError('invalid total provider demand')
        for stage,amount in demands[pid].items():stages[stage]+=val*amount/denom
    cat=report['selected_category']
    if not cat.get('@id') or not cat.get('name') or not cat.get('refUnit'):raise ValueError('impact category identity or unit missing')
    return {'kind':'stages','title_zh':'单一影响类别的阶段贡献','title_en':'Stage contributions to one impact category',
            'category':{'id':cat['@id'],'name':cat['name'],'unit':cat['refUnit']},'functional_unit':calc['functional_unit_user_asserted'],
            'database':calc['database'],'method':calc['impact_method'],'total':total,
            'rows':[{'stage':s,'contribution':stages[s],'unit':cat['refUnit'],'activity_count':counts.get(s,0)} for s in ('preparation','treatment')],
            'warnings':list(calc.get('warnings',[]))+list(plan.get('model_warnings',[]))+(['Unresolved activities: '+', '.join(unresolved)] if unresolved else [])+(['Proxy activities: '+', '.join(proxies)] if proxies else [])+
              ['Stage allocation distributes each LCI_RESULT direct contribution in proportion to linked reference demand; fixed background and linearity assumed. This is not a full UPR supply-chain decomposition.']}


def scenarios(report,base_source,alt_source,category_id):
    if report.get('schema_version')!='piezolca.cycle-scenario-comparison/1':raise ValueError('unsupported scenario report')
    if not isinstance(report.get('ranking_permitted'),bool):raise ValueError('ranking status missing')
    if report.get('context_check',{}).get('status')!='declared_contexts_match':raise ValueError('scenarios have incompatible or incomplete declared contexts')
    a=build(base_source);b=build(alt_source)
    if a['functional_unit']!=b['functional_unit'] or a['boundary']!=b['boundary']:raise ValueError('scenario functional units or boundaries differ')
    matches=[x for x in report['impacts'] if x['category']['@id']==category_id]
    if len(matches)!=1:raise ValueError('category not uniquely present')
    x=matches[0];c=x['category'];unit=x['unit']
    if not c.get('name') or not unit or unit!=c.get('refUnit'):raise ValueError('category units differ or are missing')
    base=num(x['baseline'],'baseline');alt=num(x['amount'],'scenario')
    if not same(alt-base,num(x['delta'],'delta')):raise ValueError('scenario delta does not reconcile')
    warning=['Automatic checks do not establish scientific comparability: do not rank or claim a preferred alternative without independent review.']
    if not report.get('ranking_permitted'):warning.append('Model may be incomplete or contain unresolved evidence.')
    changes=[r for r in report.get('activities',[]) if r.get('baseline') is not None and r.get('scenario') is not None and not same(num(r['baseline'],'activity baseline'),num(r['scenario'],'activity scenario'))]
    if changes:warning.append('Changed per-FU activities: '+ '; '.join(str(r['activity_id'])+': '+str(r['baseline'])+' -> '+str(r['scenario'])+' '+str(r['unit']) for r in changes))
    warning+=['Context declarations match; independent scientific comparability and actual exchange bindings require review.']
    warning+=report.get('baseline_warnings',[])+report.get('scenario_warnings',[])
    if report.get('unresolved_activity_ids'):warning.append('Unresolved activities: '+', '.join(report['unresolved_activity_ids']))
    if report.get('proxy_activity_ids'):warning.append('Proxy activities: '+', '.join(report['proxy_activity_ids']))
    return {'kind':'scenarios','title_zh':'同功能单位的情景结果','title_en':'Scenario results for one declared function',
            'category':{'id':category_id,'name':c['name'],'unit':unit},'functional_unit':{**a['functional_unit'],'description':a['functional_unit'].get('description') or 'water-phase apparent pollutant removal'},
            'boundary':a['boundary'],'ranking_permitted':False,'source_report_ranking_permitted':report['ranking_permitted'],'changed_activities':changes,
            'database':report.get('provenance',{}).get('baseline_database_user_asserted'),
            'method':{'id':(report.get('provenance',{}).get('baseline_calculation_setup',{}).get('impactMethod') or {}).get('@id'),'name':c.get('category')},
            'rows':[{'case':'baseline','amount':base,'unit':unit},{'case':'scenario','amount':alt,'unit':unit}],
            'warnings':warning}


def sensitivity(report,route,category):
    if report.get('input_result_basis')!='absolute' or not isinstance(report.get('cases'),list):raise ValueError('unsupported sensitivity report')
    cases=report['cases'];baseline=[c for c in cases if c.get('id')=='baseline']
    if len(baseline)!=1:raise ValueError('baseline is missing or duplicated')
    base=baseline[0]['results'][route][category];unit=base['unit'];base_amount=num(base['absolute'],'baseline')
    rows=[]
    for c in cases:
        if c.get('id')=='baseline':continue
        v=c['results'][route][category];change=c.get('change') or {};amount=num(v['absolute'],'scenario')
        if v.get('unit')!=unit or not same(num(v['baseline'],'baseline'),base_amount) or not same(amount-base_amount,num(v['delta'],'delta')):raise ValueError('sensitivity unit or baseline mismatch')
        if not change.get('variable') or not change.get('source'):raise ValueError('sensitivity variable or source missing')
        rows.append({'case':c['id'],'variable':change['variable'],'setting':str(change.get('value'))+' '+str(change.get('unit','')),
                     'delta':num(v['delta'],'delta'),'unit':unit,'source':change['source']})
    if not rows:raise ValueError('no sensitivity cases')
    rows.sort(key=lambda x:abs(x['delta']),reverse=True)
    return {'kind':'sensitivity','title_zh':'单因素情景影响变化','title_en':'One-at-a-time scenario impact changes',
            'category':{'id':category,'name':category,'unit':unit},'functional_unit':report['scope_user_asserted']['functional_unit'],
            'route':route,'baseline':base_amount,'scope_user_asserted':report['scope_user_asserted'],'rows':rows,
            'warnings':list(report.get('limitations',[]))+['Each bar shows one stated setting, not an inferred low/high interval or probability distribution.']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kind',choices=('cycles','stages','scenarios','sensitivity'),required=True)
    p.add_argument('--report',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--plan',type=Path);p.add_argument('--binding',type=Path);p.add_argument('--baseline-input',type=Path);p.add_argument('--scenario-input',type=Path)
    p.add_argument('--category');p.add_argument('--route');p.add_argument('--license-note',required=True)
    a=p.parse_args()
    if not a.license_note.strip():p.error('--license-note is required')
    try:
        paths={'report':a.report};read=lambda p:json.loads(p.read_bytes(),parse_constant=lambda x: (_ for _ in ()).throw(ValueError('invalid number '+x)))
        data=read(a.report)
        if a.kind=='cycles':out=cycles(data)
        elif a.kind=='stages':
            if not a.plan or not a.binding:raise ValueError('stages require --plan and --binding')
            paths.update(plan=a.plan,binding=a.binding);out=stage_contributions(data,read(a.plan),read(a.binding))
        elif a.kind=='scenarios':
            if not a.baseline_input or not a.scenario_input or not a.category:raise ValueError('scenarios require baseline input, scenario input and category')
            paths.update(baseline_input=a.baseline_input,scenario_input=a.scenario_input)
            hashes=data.get('input_sha256') or {}
            for name,path in [('baseline-input',a.baseline_input),('scenario-input',a.scenario_input)]:
                if hashlib.sha256(path.read_bytes()).hexdigest()!=hashes.get(name):raise ValueError(name+' hash differs from comparison report')
            out=scenarios(data,read(a.baseline_input),read(a.scenario_input),a.category)
        else:
            if not a.category or not a.route:raise ValueError('sensitivity requires --route and --category')
            out=sensitivity(data,a.route,a.category)
        out['schema_version']=SCHEMA;out['license_note']=a.license_note
        out['provenance']={'inputs':{k:{'name':v.name,'sha256':hashlib.sha256(v.read_bytes()).hexdigest()} for k,v in paths.items()},
                           'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                           'dependency_code_sha256':{n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in ('cyclic_foreground.py','experimental_foreground.py','audit_and_scale_inventory.py')}}
        with a.output.open('x',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
        print('Prepared',a.output);return 0
    except (OSError,ValueError,KeyError,TypeError,OverflowError) as e:print('ERROR:',e,file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
