#!/usr/bin/env python3
"""Audit explicit CSV-to-foreground evidence links and per-functional-unit inventory handoff."""
import argparse,csv,hashlib,io,json,math,sys
from pathlib import Path
from cyclic_foreground import build
from inventory_handoff import load_handoff
from audit_and_scale_inventory import UNITS
from experimental_foreground import CONCENTRATION, POWER, TIME

EVIDENCE={'measured','reported','calculated','proxy','scenario'}
COLUMNS={'value','unit','qualifier','limit','evidence_class','basis'}

def digest(raw): return hashlib.sha256(raw).hexdigest()
def read_json(path):
    raw=path.read_bytes();return json.loads(raw,parse_constant=lambda v: (_ for _ in ()).throw(ValueError('invalid number '+v))),digest(raw)
def text(value,name):
    if not isinstance(value,str) or not value.strip():raise ValueError(name+' must be nonempty')
    return value.strip()
def finite(value,name):
    if isinstance(value,bool):raise ValueError(name+' is invalid')
    try:v=float(value)
    except (TypeError,ValueError,OverflowError):raise ValueError(name+' is invalid') from None
    if not math.isfinite(v):raise ValueError(name+' must be finite')
    return v

def conversion(source,target):
    lookup={u:(d,float(f)) for u,(d,f) in UNITS.items()}
    lookup.update({u:('concentration',f) for u,f in CONCENTRATION.items()})
    lookup.update({u:('power',f) for u,f in POWER.items()})
    lookup.update({u:('time',f) for u,f in TIME.items()})
    if source not in lookup or target not in lookup or lookup[source][0]!=lookup[target][0]:
        raise ValueError('incompatible or unsupported unit conversion: '+str(source)+' -> '+str(target))
    return lookup[source][1]/lookup[target][1]

def pointer(value,path):
    if not isinstance(path,str) or not path.startswith('/'):raise ValueError('target must be a JSON pointer')
    for part in path[1:].split('/'):
        part=part.replace('~1','/').replace('~0','~')
        if isinstance(value,list):
            if not part.isdigit() or (len(part)>1 and part.startswith('0')):raise ValueError('invalid array index')
            value=value[int(part)]
        else:value=value[part]
    return value

def quantities(obj,path=''):
    if isinstance(obj,dict):
        if {'value','unit','evidence_class'}.issubset(obj):yield path,obj
        else:
            for k,v in obj.items():yield from quantities(v,path+'/'+str(k).replace('~','~0').replace('/','~1'))
    elif isinstance(obj,list):
        for i,v in enumerate(obj):yield from quantities(v,path+'/'+str(i))

def audit(spec,root,foreground,foreground_hash,inventory=None,manifest=None):
    if spec.get('schema_version')!='piezolca.evidence-chain/1':raise ValueError('unsupported evidence schema')
    declared=text(spec.get('foreground_sha256'),'foreground_sha256')
    if declared!=foreground_hash:raise ValueError('foreground SHA-256 differs from evidence manifest')
    source_rows={};sources=[];originals={}
    for original in spec.get('originals',[]):
        oid=text(original.get('id'),'original id')
        if oid in originals:raise ValueError('duplicate original id')
        path=(root/text(original.get('path'),'original path')).resolve();sha=digest(path.read_bytes())
        if sha!=text(original.get('sha256'),'original sha256'):raise ValueError(oid+': original source SHA-256 mismatch')
        originals[oid]={'id':oid,'name':path.name,'sha256':sha}
    for src in spec.get('sources',[]):
        sid=text(src.get('id'),'source id')
        if sid in source_rows:raise ValueError('duplicate source id')
        path=(root/text(src.get('path'),'source path')).resolve();raw=path.read_bytes();sha=digest(raw)
        if sha!=text(src.get('sha256'),'source sha256'):raise ValueError(sid+': raw source SHA-256 mismatch')
        reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig'),newline=''))
        fields=reader.fieldnames or []
        if len(fields)!=len(set(fields)) or not COLUMNS.issubset(fields):raise ValueError(sid+': duplicate or missing CSV columns')
        rows=list(reader)
        if any(None in r or any(v is None for v in r.values()) for r in rows):raise ValueError(sid+': malformed CSV row')
        source_rows[sid]=rows;sources.append({'id':sid,'name':path.name,'sha256':sha,'record_count':len(rows)})
    if not source_rows:raise ValueError('at least one CSV source required')
    result=[];issues=[];seen=set();used_records=set()
    for link in spec.get('links',[]):
        target=text(link.get('target'),'link target')
        if target in seen:raise ValueError('duplicate target: '+target)
        seen.add(target);sid=text(link.get('source'),'link source');index=link.get('record')
        if sid not in source_rows or isinstance(index,bool) or not isinstance(index,int) or index<1 or index>len(source_rows[sid]):raise ValueError(target+': invalid source record')
        if (sid,index) in used_records:issues.append({'target':target,'status':'source_record_reused_review_required'})
        used_records.add((sid,index))
        row=source_rows[sid][index-1];q=pointer(foreground,target)
        if not isinstance(q,dict) or not {'value','unit','evidence_class'}.issubset(q):raise ValueError(target+': not a quantity object')
        basis=text(link.get('basis'),'link basis')
        if basis!=text(row['basis'],'CSV basis'):raise ValueError(target+': basis mismatch')
        oid=(row.get('original_id') or '').strip();locator=(row.get('original_locator') or '').strip();origin=None
        if oid or locator:
            if oid not in originals or not locator:raise ValueError(target+': original id or locator is invalid')
            origin={**originals[oid],'locator_user_asserted':locator,'verification':'file_hash_only_not_original_cell'}
            issues.append({'target':target,'status':'original_locator_requires_review'})
        source_class=text(row['evidence_class'],'CSV evidence class')
        if source_class not in EVIDENCE or q['evidence_class']!=source_class:raise ValueError(target+': evidence class mismatch')
        source_qualifier=text(row['qualifier'],'CSV qualifier');target_qualifier=q.get('qualifier','exact' if q.get('value') is not None else 'missing')
        if source_qualifier not in ('exact','missing','below_lod','below_loq') or source_qualifier!=target_qualifier:raise ValueError(target+': qualifier mismatch')
        factor=conversion(text(row['unit'],'CSV unit'),text(q['unit'],'target unit'));measured=None;converted=None
        if source_qualifier=='exact':
            measured=finite(row['value'],'CSV value');converted=measured*factor;value=finite(q.get('value'),'target value')
            if not math.isfinite(converted) or not math.isclose(value,converted,rel_tol=1e-10,abs_tol=0):raise ValueError(target+': source value differs from foreground')
            if row['limit'].strip():raise ValueError(target+': exact source must not include limit')
        elif source_qualifier in ('below_lod','below_loq'):
            if row['value'].strip() or q.get('value') is not None:raise ValueError(target+': censored value must be missing')
            measured=finite(row['limit'],'CSV limit');converted=measured*factor;value=finite(q.get('limit'),'target limit')
            if measured<=0 or not math.isclose(value,converted,rel_tol=1e-10,abs_tol=0):raise ValueError(target+': detection limit mismatch')
            issues.append({'target':target,'status':'censored_not_imputed'})
        else:
            if row['value'].strip() or row['limit'].strip() or q.get('value') is not None:raise ValueError(target+': missing source must remain missing')
            issues.append({'target':target,'status':'missing_not_imputed'})
        column='value' if source_qualifier=='exact' else 'limit' if source_qualifier!='missing' else None
        result.append({'target':target,'source_id':sid,'record':index,'value_column':column,'source_cell_text':row[column] if column else None,
                       'source_value':measured,'source_unit':row['unit'],'target_unit':q['unit'],'conversion_factor':factor,
                       'target_value_or_limit':converted,'qualifier':source_qualifier,'evidence_class':source_class,'basis':basis,'original':origin,'status':'source_matches_declaration'})
    all_quantities=dict(quantities(foreground))
    if any(target not in all_quantities for target in seen):raise ValueError('link target is not an enumerated quantity')
    for path,q in all_quantities.items():
        if path not in seen:issues.append({'target':path,'status':'source_not_linked','evidence_class':q.get('evidence_class')})
    model=build(foreground);handoff=None
    if bool(inventory)!=bool(manifest):raise ValueError('inventory and manifest must be provided together')
    if inventory:
        handoff=load_handoff(inventory,manifest)
        if handoff.get('input_sha256')!=foreground_hash:raise ValueError('inventory manifest references a different foreground')
        if handoff.get('functional_unit')!=model['functional_unit'] or handoff.get('boundary')!=model['boundary'] or handoff.get('functional_unit_type')!='apparent_pollutant_removal':
            raise ValueError('inventory manifest service or boundary differs from foreground')
        expected={r['activity_id']:r for r in model['functional_unit_flows']}
        rows={r['activity_id']:r for r in handoff['rows']}
        if rows.keys()!=expected.keys():raise ValueError('inventory activity IDs differ from rebuilt foreground')
        for aid,e in expected.items():
            r=rows[aid];x=e['amount'];y=r['amount_per_functional_unit']
            if e['unit']!=r['unit'] or e['direction']!=r['direction'] or e['stage']!=r['stage'] or e['cycle']!=r['cycle_id'] or e['included']!=r['included'] or e['flow_name']!=r['flow_name'] or (x is None)!=(y is None) or (x is not None and not math.isclose(x,y,rel_tol=1e-10,abs_tol=0)):
                raise ValueError(aid+': inventory differs from rebuilt per-functional-unit foreground')
        handoff={'inventory_sha256':handoff['inventory_sha256'],'manifest_sha256':handoff['manifest_sha256'],'amount_basis':handoff['amount_basis'],'activity_count':len(rows)}
    # Separate direct activity inputs from allocation dependencies; quantities are already per FU.
    scaling=['/treatment_target']
    for i,_ in enumerate(foreground['cycles']):
        scaling.extend('/cycles/'+str(i)+'/'+k for k in ('influent_volume','influent_concentration','effluent_volume','effluent_concentration'))
    prep_scaling=scaling+['/dry_yield','/initial_catalyst']+['/cycles/'+str(i)+'/catalyst_added' for i in range(len(foreground['cycles']))]
    activity_paths={}
    for i,entry in enumerate(foreground['preparation_activities']):activity_paths[entry['activity_id']]='/preparation_activities/'+str(i)
    for i,cycle in enumerate(foreground['cycles']):
        for j,entry in enumerate(cycle['activities']):activity_paths[entry['activity_id']]='/cycles/'+str(i)+'/activities/'+str(j)
    traces=[]
    for flow in model['functional_unit_flows']:
        aid=flow['activity_id'];base=activity_paths.get(aid)
        if base:
            item=pointer(foreground,base);direct=[base+'/'+k for k in ('quantity','power','duration') if k in item]
        else:
            direct=['/cycles/'+str(len(foreground['cycles'])-1)+'/catalyst_recovered']
        dependencies=list(dict.fromkeys(direct+(prep_scaling if flow['stage']=='preparation' else scaling)))
        campaigns=model['campaign']['campaigns_per_functional_unit'];prep_batches=model['campaign']['preparation_batches']
        factor=campaigns if flow['stage']!='preparation' else (campaigns*prep_batches if campaigns is not None and prep_batches is not None else None)
        formula=('power converted to kW × duration converted to h' if base and 'power' in item else 'declared quantity converted to inventory unit')
        formula+=(' × preparation batches per campaign × campaigns per functional unit' if flow['stage']=='preparation' else ' × campaigns per functional unit')
        traces.append({'activity_id':aid,'amount_per_functional_unit':flow['amount'],'unit':flow['unit'],
                       'campaign_amount':flow['campaign_value'],'campaign_unit':flow['campaign_unit'],
                       'functional_unit_allocation_factor':factor,'formula':formula,
                       'direct_input_pointers':direct,'allocation_input_pointers':[x for x in dependencies if x not in direct],
                       'unlinked_input_pointers':[x for x in dependencies if x not in seen]})
    return {'schema_version':'piezolca.evidence-audit/1','foreground_sha256':foreground_hash,'sources':sources,'links':result,
            'coverage':{'quantity_count':len(all_quantities),'linked_count':len(seen),'unlinked_count':len(all_quantities)-len(seen)},
            'inventory_rebuilt_and_verified':handoff,'campaign':model['campaign'],
            'functional_unit_flows':model['functional_unit_flows'],'inventory_traces':traces,'issues':issues,'status':'evidence_gaps' if issues else 'links_match_review_still_required',
            'limitations':['A matching cell and hash do not prove measurement authenticity, experimental relevance, sample identity, or source metadata.',
             'Basis and evidence classes are user declarations; CSV record number counts data records, not physical file lines.',
             'Only direct CSV numeric/unit or detection-limit links are checked. Optional original files are hash-checked, but their cited cell/page is not automatically verified.',
             'Derived formulas require their inputs and calculation to be reviewed.',
             'Cyclic model generates per-functional-unit amounts; matching the inventory does not validate its database mapping or LCIA results.']}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('spec',type=Path);p.add_argument('--foreground',type=Path,required=True);p.add_argument('--inventory',type=Path);p.add_argument('--manifest',type=Path);a=p.parse_args()
    try:
        spec,sh=read_json(a.spec);foreground,fh=read_json(a.foreground);r=audit(spec,a.spec.resolve().parent,foreground,fh,a.inventory,a.manifest)
        r['spec_sha256']=sh;r['code_sha256']={n:digest(Path(__file__).with_name(n).read_bytes()) for n in ('evidence_chain.py','cyclic_foreground.py','experimental_foreground.py','inventory_handoff.py')}
        print(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False));return 0
    except (OSError,UnicodeError,ValueError,TypeError,KeyError,IndexError,OverflowError,csv.Error) as exc:print('ERROR:',exc,file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
