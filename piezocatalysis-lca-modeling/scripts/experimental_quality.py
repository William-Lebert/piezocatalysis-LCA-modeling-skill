#!/usr/bin/env python3
"""Inventory quality of cyclic experiment records before considering distributions."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

from cyclic_foreground import build


def present(value):
    return isinstance(value,str) and bool(value.strip()) and 'replace-me' not in value.lower()


def audit(data):
    if not isinstance(data,dict) or not isinstance(data.get('campaigns'),list) or not data['campaigns']:
        raise ValueError('campaigns must be a nonempty list')
    names=set();observations={};pairs={};campaign_results=[];issues=[]
    def add(batch,key,quantity):
        if not isinstance(quantity,dict):
            issues.append({'campaign':batch,'field':key,'status':'quantity_missing'});return
        value=quantity.get('value');qualifier=quantity.get('qualifier','exact' if value is not None else 'missing')
        if qualifier not in ('exact','missing','below_lod','below_loq'):raise ValueError(key+': invalid qualifier')
        if qualifier=='exact' and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value)):
            raise ValueError(key+': exact observation requires a finite number')
        if qualifier!='exact' and value is not None:raise ValueError(key+': censored or missing observation must have null value')
        lim=quantity.get('limit')
        if qualifier in ('below_lod','below_loq') and (isinstance(lim,bool) or not isinstance(lim,(int,float)) or not math.isfinite(lim) or lim<=0):
            issues.append({'campaign':batch,'field':key,'status':'detection_limit_missing_or_invalid'})
        for f in ('unit','source','evidence_class'):
            if not present(quantity.get(f)):issues.append({'campaign':batch,'field':key+'.'+f,'status':'missing'})
        observations.setdefault(key,[]).append({'campaign':batch,'value':value,'qualifier':qualifier,'limit':lim,
            'unit':quantity.get('unit'),'source':quantity.get('source'),'evidence_class':quantity.get('evidence_class')})
    for c in data['campaigns']:
        if not isinstance(c,dict) or not present(c.get('id')) or c['id'] in names:raise ValueError('campaign IDs must be unique and nonempty')
        name=c['id'];names.add(name);record=c.get('record')
        if not isinstance(record,dict):raise ValueError('campaign record must be an object')
        try:result=build(record)
        except (ValueError,TypeError,KeyError) as exc:
            result=None;issues.append({'campaign':name,'field':'cyclic_foreground','status':'invalid_or_incomplete','detail':str(exc)})
        for field in ('geography','time_scope','calibration'):
            if not present(c.get(field)):issues.append({'campaign':name,'field':field,'status':'missing'})
        if c.get('calibration_status')!='verified':
            issues.append({'campaign':name,'field':'calibration_status','status':'not_verified'})
        if record.get('final_recovered_destination')=='disposed' and not present(c.get('disposal_mapping')):
            issues.append({'campaign':name,'field':'disposal_mapping','status':'final_catalyst_route_unconfirmed'})
        elif record.get('final_recovered_destination')=='unknown':
            issues.append({'campaign':name,'field':'final_recovered_destination','status':'unknown'})
        add(name,'dry_yield',record.get('dry_yield'));add(name,'initial_catalyst',record.get('initial_catalyst'))
        for cycle in record['cycles']:
            prefix='cycle/'+cycle['cycle_id']+'/'
            for field in ('catalyst_added','catalyst_loaded','catalyst_recovered','influent_volume','influent_concentration','effluent_volume','effluent_concentration'):
                add(name,prefix+field,cycle.get(field))
            for act in cycle['activities']:
                for field in ('power','duration','quantity'):
                    if field in act:add(name,prefix+'activity/'+act['activity_id']+'/'+field,act[field])
                if 'power' in act and 'duration' in act:
                    p,t=act['power'].get('value'),act['duration'].get('value')
                    if all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in (p,t)):
                        pairs.setdefault(prefix+'activity/'+act['activity_id'],[]).append({'campaign':name,'power':p,'duration':t,'power_unit':act['power'].get('unit'),'duration_unit':act['duration'].get('unit')})
        for act in record['preparation_activities']:
            for field in ('power','duration','quantity'):
                if field in act:add(name,'preparation/'+act['activity_id']+'/'+field,act[field])
        campaign_results.append({'id':name,'geography':c.get('geography'),'time_scope':c.get('time_scope'),
                                 'calibration':c.get('calibration'),'calibration_status_user_asserted':c.get('calibration_status'),'disposal_mapping_user_asserted':c.get('disposal_mapping'),'campaign':result['campaign'] if result else None,'warnings':result['warnings'] if result else []})
    summaries=[]
    for key,items in sorted(observations.items()):
        units={x['unit'] for x in items}; evidence={x['evidence_class'] for x in items if x['qualifier']=='exact'};exact=[x['value'] for x in items if x['qualifier']=='exact']
        if len(units)!=1:issues.append({'field':key,'status':'unit_mismatch_no_aggregation'})
        if len(evidence)>1:issues.append({'field':key,'status':'mixed_evidence_no_aggregation'})
        if len(items)!=len(names):issues.append({'field':key,'status':'missing_in_some_campaigns'})
        censored=sum(x['qualifier'] in ('below_lod','below_loq') for x in items)
        missing=sum(x['qualifier']=='missing' for x in items)+len(names)-len(items)
        if censored:issues.append({'field':key,'status':'censored_observation_not_imputed','count':censored})
        if missing:issues.append({'field':key,'status':'missing_observation','count':missing})
        if len(exact)<2:issues.append({'field':key,'status':'insufficient_exact_repeats','exact_count':len(exact)})
        comparable=len(units)==1 and len(evidence)<=1 and len(exact)>=2
        summaries.append({'field':key,'observations':items,'exact_count':len(exact),'censored_count':censored,'missing_count':missing,
            'measured_count':sum(x['evidence_class']=='measured' and x['qualifier']=='exact' for x in items),
            'minimum':min(exact) if comparable else None,'maximum':max(exact) if comparable else None,
            'sample_standard_deviation':statistics.stdev(exact) if comparable else None,
            'note':'Descriptive only; campaigns are not assumed independent or representative.'})
    pair_summaries=[]
    for key,rows in sorted(pairs.items()):
        units={(r['power_unit'],r['duration_unit']) for r in rows};correlation=None
        if len(rows)>=3 and len(units)==1:
            a=[r['power'] for r in rows];b=[r['duration'] for r in rows]
            if statistics.stdev(a)>0 and statistics.stdev(b)>0:
                ma=statistics.mean(a);mb=statistics.mean(b)
                correlation=math.fsum((x-ma)*(y-mb) for x,y in zip(a,b))/math.sqrt(math.fsum((x-ma)**2 for x in a)*math.fsum((y-mb)**2 for y in b))
        pair_summaries.append({'activity':key,'pairs':rows,'pair_count':len(rows),'pearson_descriptive':correlation,
                               'note':'Paired settings are retained; this is not proof of independence or a probability model.'})
        if len(rows)<3:issues.append({'field':key,'status':'insufficient_paired_records','pair_count':len(rows)})
    if data.get('dependency_reviewed') is not True:issues.append({'field':'dependency_reviewed','status':'not_confirmed'})
    if data.get('distribution_basis_reviewed') is not True:issues.append({'field':'distribution_basis_reviewed','status':'not_confirmed'})
    return {'schema_version':'piezolca.experimental-quality/1','campaigns':campaign_results,'variables':summaries,'paired_power_duration':pair_summaries,
            'issues':issues,'status':'evidence_gaps' if issues else 'descriptive_checks_complete_review_still_required',
            'note':'No probability distribution is fitted. Source, calibration, replication, boundary and dependencies need expert review; censored and missing values are never replaced with zero.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);args=p.parse_args()
    try:
        raw=args.input.read_bytes();d=json.loads(raw,parse_constant=lambda x: (_ for _ in ()).throw(ValueError('invalid number '+x)))
        report=audit(d);report['input_sha256']=hashlib.sha256(raw).hexdigest()
        report['code_sha256']={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in ('experimental_quality.py','cyclic_foreground.py','experimental_foreground.py')}
        print(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False));return 0
    except (OSError,ValueError,TypeError,KeyError,OverflowError) as e:
        print('ERROR:',e,file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
