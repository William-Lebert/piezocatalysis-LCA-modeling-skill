#!/usr/bin/env python3
"""Compare recorded cyclic foregrounds and explicitly sourced scale-up assumptions."""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from cyclic_foreground import build

SCHEMA='piezolca.engineering-scenarios/1'
CATEGORIES={'catalyst_lifetime','ultrasound_power','treatment_time','water_exchange',
            'cleaning_regeneration','oxidant','electricity_grid','engineering_scale','other'}

def digest(raw): return hashlib.sha256(raw).hexdigest()
def read(path):
    raw=path.read_bytes()
    return json.loads(raw,parse_constant=lambda x: (_ for _ in ()).throw(ValueError('invalid number '+x))),digest(raw)
def text(value,label):
    if not isinstance(value,str) or not value.strip(): raise ValueError(label+' requires text')
    return value.strip()
def number(value,label):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value): raise ValueError(label+' must be finite')
    return value

def pointer(obj,path):
    if not isinstance(path,str) or not path.startswith('/'): raise ValueError('input_pointer must be a JSON pointer')
    for segment in path[1:].split('/'):
        segment=segment.replace('~1','/').replace('~0','~')
        obj=obj[int(segment)] if isinstance(obj,list) else obj[segment]
    return obj

def validate_parameters(params,source):
    if not isinstance(params,list): raise ValueError('parameters must be a list')
    seen=set(); out=[]; warnings=[]
    for p in params:
        name=text(p.get('name'),'parameter name')
        if name in seen: raise ValueError('duplicate parameter name: '+name)
        seen.add(name)
        category=p.get('category')
        if category not in CATEGORIES: raise ValueError(name+': unsupported parameter category')
        kind=p.get('basis')
        if kind not in ('experimental_measurement','engineering_assumption','synthetic_test'):
            raise ValueError(name+': invalid evidence basis')
        value=number(p.get('value'),name);unit=text(p.get('unit'),name+' unit');text(p.get('source'),name+' source')
        bound=p.get('input_pointer')
        if bound:
            target=pointer(source,bound)
            if isinstance(target,dict):
                if target.get('unit')!=unit: raise ValueError(name+': input unit mismatch')
                actual=target.get('value')
            elif isinstance(target,list):
                if unit!='cycles': raise ValueError(name+': list length requires cycles unit')
                actual=len(target)
            else: raise ValueError(name+': pointer must address a quantity or cycles list')
            if number(actual,name+' input')!=value: raise ValueError(name+': value differs from input')
        else:
            warnings.append(name+': design declaration not bound to a foreground input; no automatic effect on inventory')
        interval=p.get('measured_range')
        outside=None
        if interval is not None:
            if not isinstance(interval,dict):raise ValueError(name+': measured_range must be object')
            lo=number(interval.get('min'),name+' minimum');hi=number(interval.get('max'),name+' maximum')
            if lo>hi or interval.get('unit')!=unit:raise ValueError(name+': invalid range or unit')
            text(interval.get('source'),name+' range source')
            outside=not lo<=value<=hi
            if outside:warnings.append(name+': outside declared measured range; extrapolation not validated')
        else:warnings.append(name+': measured range not supplied')
        out.append({**p,'outside_measured_range':outside,'bound_to_input':bool(bound)})
    return out,warnings

def row_index(rows):
    return {r['activity_id']:r for r in rows if r['included']}

def compare_foreground(a,b):
    left,right=row_index(a['functional_unit_flows']),row_index(b['functional_unit_flows']);rows=[]
    for key in sorted(left.keys() | right.keys()):
        x,y=left.get(key),right.get(key)
        identity=('flow_name','unit','direction','stage','cycle')
        compatible=bool(x and y and all(x.get(k)==y.get(k) for k in identity))
        av=x.get('amount') if x else None;bv=y.get('amount') if y else None
        delta=bv-av if compatible and av is not None and bv is not None else None
        rows.append({'activity_id':key,'baseline':av,'scenario':bv,'unit':x.get('unit') if compatible else None,
                     'delta':delta,'status':'matched' if compatible else 'new_removed_or_changed_identity'})
    return rows

def input_changes(a,b,path=''):
    if isinstance(a,dict) and isinstance(b,dict):
        out=[]
        for key in sorted(a.keys() | b.keys()):
            p=path+'/'+str(key).replace('~','~0').replace('/','~1')
            if key not in a or key not in b:out.append({'path':p,'baseline':a.get(key),'scenario':b.get(key),'status':'added_or_removed'})
            else:out.extend(input_changes(a[key],b[key],p))
        return out
    if isinstance(a,list) and isinstance(b,list):
        out=[]
        for i in range(max(len(a),len(b))):
            p=path+'/'+str(i)
            if i>=len(a) or i>=len(b):out.append({'path':p,'baseline':a[i] if i<len(a) else None,'scenario':b[i] if i<len(b) else None,'status':'added_or_removed'})
            else:out.extend(input_changes(a[i],b[i],p))
        return out
    return [] if type(a)==type(b) and a==b else [{'path':path,'baseline':a,'scenario':b,'status':'changed'}]

def validate_grid(grid):
    if not isinstance(grid,dict): raise ValueError('background_electricity must be an object')
    for key in ('database','dataset_id','geography','reference_unit','source'):
        text(grid.get(key),'background_electricity '+key)
    return grid

def build_report(spec,root):
    if spec.get('schema_version')!=SCHEMA:raise ValueError('unsupported scenario schema')
    baseline_path=(root/Path(text(spec.get('baseline_input'),'baseline_input'))).resolve()
    baseline,base_hash=read(baseline_path);base=build(baseline)
    grid=validate_grid(spec.get('background_electricity'))
    cases=spec.get('scenarios')
    if not isinstance(cases,list) or not cases:raise ValueError('at least one scenario required')
    ids=set();output=[]
    for case in cases:
        sid=text(case.get('id'),'scenario id')
        if sid in ids:raise ValueError('duplicate scenario id: '+sid)
        ids.add(sid);path=(root/Path(text(case.get('input'),'input'))).resolve()
        source,source_hash=read(path);result=build(source)
        params,warnings=validate_parameters(case.get('parameters'),source)
        scenario_grid=validate_grid(case.get('background_electricity',grid))
        grid_changed=any(grid[k]!=scenario_grid[k] for k in ('database','dataset_id','geography','reference_unit'))
        if grid_changed: warnings.append('Electricity dataset changed: check mapping and recalculate independently; previous background results are not reusable.')
        compatible=(base['functional_unit'].get('value')==result['functional_unit'].get('value') and
                    base['functional_unit'].get('unit')==result['functional_unit'].get('unit') and base['boundary']==result['boundary'])
        if not compatible:warnings.append('Functional unit or boundary differs; do not compare impacts.')
        warnings.extend(base['warnings']);warnings.extend(result['warnings'])
        changes=compare_foreground(base,result)
        if not compatible:
            for row in changes: row['delta']=None
        if any(x['status']!='matched' for x in changes):warnings.append('Inventory activity identity differs; update mapping and recalculate independently.')
        actual=None
        if case.get('comparison'):
            cp=(root/Path(case['comparison'])).resolve();actual,ch=read(cp)
            if actual.get('schema_version')!='piezolca.cycle-scenario-comparison/1':raise ValueError(sid+': unsupported comparison report')
            hashes=actual.get('input_sha256') or {}
            if hashes.get('baseline-input')!=base_hash or hashes.get('scenario-input')!=source_hash:
                raise ValueError(sid+': comparison inputs do not match scenario files')
            if grid_changed or not compatible or (actual.get('context_check') or {}).get('status')!='declared_contexts_match':
                warnings.append('Actual comparison has unmatched service or context; no impact comparison is accepted.')
                actual=None
            else:
                impacts=actual.get('impacts')
                if not isinstance(impacts,list) or not impacts: raise ValueError(sid+': comparison has no impacts')
                seen_categories=set()
                for row in impacts:
                    cat=row.get('category') or {}; cid=text(cat.get('@id'),'impact category ID')
                    if cid in seen_categories: raise ValueError(sid+': duplicate impact category')
                    seen_categories.add(cid);text(cat.get('name'),'impact category name');text(row.get('unit'),'impact unit')
                    if cat.get('refUnit')!=row['unit']: raise ValueError(sid+': impact unit mismatch')
                    a=number(row.get('baseline'),'baseline impact');b=number(row.get('amount'),'scenario impact');d=number(row.get('delta'),'impact delta')
                    if not math.isclose(b-a,d,rel_tol=1e-9,abs_tol=1e-12): raise ValueError(sid+': impact delta mismatch')
                if actual.get('unresolved_activity_ids'): warnings.append('Unresolved model activities: '+', '.join(actual['unresolved_activity_ids']))
                if actual.get('proxy_activity_ids'): warnings.append('Proxy or constructed activities: '+', '.join(actual['proxy_activity_ids']))
                actual={'report_file':cp.name,'report_sha256':ch,'impacts':actual.get('impacts'),
                        'ranking_permitted':actual.get('ranking_permitted') is True,
                        'unresolved_activity_ids':actual.get('unresolved_activity_ids'),
                        'proxy_activity_ids':actual.get('proxy_activity_ids'),
                        'note':'Calculation inputs are matched by hash; model exchanges, providers and database identity still require independent verification.'}
        if actual is None: warnings.append('No verified impact calculation: mapping, background coverage and model completeness remain unconfirmed.')
        output.append({'id':sid,'label':text(case.get('label'),'label'),'input_file':path.name,'input_sha256':source_hash,
                       'parameters':params,'background_electricity':scenario_grid,'electricity_grid_changed':grid_changed,'functional_unit_and_boundary_match':compatible,
                       'campaign':result['campaign'],'input_changes':input_changes(baseline,source),'inventory_comparison':changes,'actual_openlca_comparison':actual,
                       'warnings':list(dict.fromkeys(warnings)), 'ranking_permitted':False})
    return {'schema_version':SCHEMA,'baseline':{'file':baseline_path.name,'sha256':base_hash,'functional_unit':base['functional_unit'],
            'boundary':base['boundary'],'campaign':base['campaign'],'background_electricity':grid},'scenarios':output,
            'limitations':['Scenario inputs and evidence are user declarations; inspect all differences and validate the experimental service.',
            'No automatic scale-up, transfer efficiency, grid change, model fitting, probability distributions or confidence intervals are inferred.',
            'Actual impacts require separately verified model links and calculations. No impact ranking is enabled by this report.']}

def markdown(r):
    lines=['# 压电催化情景与工程放大报告','', '基准输入 SHA-256：`'+r['baseline']['sha256']+'`', '', '功能单位：`'+json.dumps(r['baseline']['functional_unit'],ensure_ascii=False)+'`',
           '', '边界：'+r['baseline']['boundary'], '', '所有输入、参数和来源均由使用者提供；情景结果不自动证明工程性能。','']
    for c in r['scenarios']:
        lines += ['## '+c['label']+' ('+c['id']+')','', '循环数：'+str(c['campaign']['cycle_count'])+'；每功能单位批次数：'+str(c['campaign']['campaigns_per_functional_unit']), '', '| 参数 | 值 | 单位 | 依据 | 测量范围 | 来源 |','|---|---:|---|---|---|---|']
        for p in c['parameters']:
            interval=p.get('measured_range');rng=(str(interval['min'])+'–'+str(interval['max'])+' '+interval['unit']+'；'+interval['source']) if interval else '未提供'
            cells=[p['name'],str(p['value']),p['unit'],p['basis'],rng,p['source']]
            lines.append('| '+' | '.join(x.replace('|','\\|').replace('\n',' ') for x in cells)+' |')
        lines+=['','功能单位与边界声明一致：'+str(c['functional_unit_and_boundary_match']),
                '实际 openLCA 比较：'+('已附（详见 JSON）' if c['actual_openlca_comparison'] else '未提供 / 不可比'),
                '允许排名：否', '电网：'+c['background_electricity']['database']+' / '+c['background_electricity']['dataset_id']+' / '+c['background_electricity']['geography'], '', '提示：']
        lines += ['- '+x for x in c['warnings']] or ['- 仍需人工审核模型和数据。']
        lines+=['']
        actual=c['actual_openlca_comparison']
        if actual:
            lines+=['### 实际 openLCA 计算结果','', '背景结果仅用于本地验证；代理与未连接项须审核。', '', '| 影响类别 | 基准 | 情景 | 差值 | 单位 |','|---|---:|---:|---:|---|']
            for row in actual['impacts']:
                name=str(row['category']['name']).replace('|','\\|').replace('\n',' ')
                lines.append('| '+name+' | '+str(row['baseline'])+' | '+str(row['amount'])+' | '+str(row['delta'])+' | '+str(row['unit'])+' |')
            lines+=['','来源比较 SHA-256：`'+actual['report_sha256']+'`','']
    lines+=['## 解释边界','']+['- '+x for x in r['limitations']]
    return '\n'.join(lines)+'\n'

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('spec',type=Path);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
    try:
        spec,h=read(a.spec);report=build_report(spec,a.spec.resolve().parent)
        report['spec_sha256']=h;report['code_sha256']={name:digest(Path(__file__).with_name(name).read_bytes()) for name in ('engineering_scenarios.py','cyclic_foreground.py','experimental_foreground.py')}
        a.output_dir.mkdir(parents=True,exist_ok=False)
        (a.output_dir/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        (a.output_dir/'report.md').write_text(markdown(report),encoding='utf-8')
        print('Prepared',a.output_dir);return 0
    except (OSError,ValueError,TypeError,KeyError,IndexError,OverflowError) as e:print('ERROR:',e,file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
