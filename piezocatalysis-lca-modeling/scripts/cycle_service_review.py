#!/usr/bin/env python3
"""Review declared per-cycle service and sample links without changing the LCI."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

from cyclic_foreground import build
from evidence_chain import conversion, EVIDENCE


def present(value):
    return isinstance(value,str) and bool(value.strip()) and 'replace-me' not in value.lower()


def review(spec,foreground,foreground_hash,evidence=None):
    if not isinstance(spec,dict) or spec.get('schema_version')!='piezolca.cycle-service-review/1':raise ValueError('unsupported service review schema')
    if spec.get('foreground_sha256')!=foreground_hash:raise ValueError('service review foreground hash differs')
    model=build(foreground);service=spec.get('service') or {};kind=service.get('kind')
    if kind not in ('apparent_pollutant_removal','treated_water_to_threshold'):raise ValueError('unsupported service kind')
    issues=[]
    for field in ('campaign_id','pollutant','source'):
        if not present(spec.get(field)):issues.append({'field':field,'status':'missing_or_unverified'})
    if not present(service.get('source')):issues.append({'field':'service.source','status':'missing_or_unverified'})
    if service.get('evidence_class') not in EVIDENCE:issues.append({'field':'service.evidence_class','status':'missing_or_invalid'})
    criterion=service.get('criterion');threshold=None
    if not isinstance(criterion,dict) or not present(criterion.get('source')):
        issues.append({'field':'service.criterion','status':'missing_or_unverified'})
    else:
        if criterion.get('evidence_class') not in EVIDENCE:issues.append({'field':'service.criterion.evidence_class','status':'missing_or_invalid'})
        v=criterion.get('value')
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0:raise ValueError('criterion value must be finite and non-negative')
        target='mg/L' if kind=='treated_water_to_threshold' else 'mg'
        threshold=v*conversion(criterion.get('unit'),target)
        if not math.isfinite(threshold):raise ValueError('criterion conversion is nonfinite')
    if evidence is not None and (not isinstance(evidence,dict) or evidence.get('schema_version')!='piezolca.evidence-audit/1' or evidence.get('foreground_sha256')!=foreground_hash):raise ValueError('evidence report does not match foreground')
    if evidence is None:issues.append({'field':'evidence','status':'not_supplied'})
    elif evidence.get('status')!='links_match_review_still_required':issues.append({'field':'evidence','status':'source_links_need_review'})
    links={x['target']:x for x in (evidence or {}).get('links',[])}
    if len(links)!=len((evidence or {}).get('links',[])):raise ValueError('duplicate evidence target')
    rows=[];seen_samples={}
    for index,(cycle,result) in enumerate(zip(foreground['cycles'],model['cycles'])):
        cid=cycle['cycle_id'];sample_pairs={};sample_issues=[]
        for role in ('influent','effluent'):
            identities=[]
            for field in ('volume','concentration'):
                pointer=f'/cycles/{index}/{role}_{field}';link=links.get(pointer) or {};sample=link.get('sample_user_asserted')
                if not isinstance(sample,dict) or not all(present(sample.get(k)) for k in ('campaign_id','cycle_id','sample_id','sample_role')):
                    sample_issues.append(pointer+': sample identity not declared');continue
                if sample['campaign_id']!=spec.get('campaign_id') or sample['cycle_id']!=cid or sample['sample_role']!=role:
                    sample_issues.append(pointer+': sample campaign/cycle/role mismatch');continue
                identities.append(sample['sample_id'])
            if len(identities)==2 and identities[0]!=identities[1]:sample_issues.append(role+': volume and concentration sample IDs differ')
            if len(identities)==2 and identities[0]==identities[1]:
                sample_pairs[role]=identities[0];key=(spec.get('campaign_id'),identities[0]);prior=seen_samples.get(key)
                if prior is not None and prior!=(cid,role):sample_issues.append(role+': sample ID reused across cycles or roles')
                seen_samples[key]=(cid,role)
        sample_ok=not sample_issues and len(sample_pairs)==2
        if sample_pairs.get('influent') and sample_pairs.get('influent')==sample_pairs.get('effluent'):
            sample_issues.append('influent and effluent have the same sample ID');sample_ok=False
        if sample_issues:issues.extend({'field':'cycle.'+cid+'.sample','status':'review_required','detail':x} for x in sample_issues)
        outcome='not_evaluated';reason='criterion not supplied'
        if threshold is not None:
            if kind=='apparent_pollutant_removal':
                interval=result['apparent_removal_interval_mg']
                if interval is None:reason='apparent removal unavailable'
                elif interval[0]>=threshold:outcome='meets_declared_criterion';reason='removal lower bound meets criterion'
                elif interval[1]<threshold:outcome='does_not_meet_declared_criterion';reason='removal upper bound below criterion'
                else:reason='censored removal interval crosses criterion'
            else:
                q=cycle['effluent_concentration'];qual=q.get('qualifier','exact' if q.get('value') is not None else 'missing')
                if qual=='exact' and q.get('value') is not None:
                    v=q['value']*conversion(q['unit'],'mg/L');outcome='meets_declared_criterion' if v<=threshold else 'does_not_meet_declared_criterion';reason='exact effluent concentration compared with declared threshold'
                elif qual in ('below_lod','below_loq') and q.get('limit') is not None:
                    lim=q['limit']*conversion(q['unit'],'mg/L')
                    if lim<=threshold:outcome='meets_declared_criterion';reason='censoring limit at or below threshold'
                    else:reason='censoring limit above threshold'
                else:reason='effluent concentration missing'
        if outcome=='not_evaluated':issues.append({'field':'cycle.'+cid+'.service','status':'not_evaluated','detail':reason})
        elif outcome=='does_not_meet_declared_criterion':issues.append({'field':'cycle.'+cid+'.service','status':'criterion_not_met'})
        energy=[x for x in model['functional_unit_flows'] if x['cycle']==cid and x['kind']=='energy' and x['included']]
        energy_kwh=None if not energy or any(x['campaign_value'] is None for x in energy) else math.fsum(x['campaign_value']*conversion(x['campaign_unit'],'kWh') for x in energy)
        if energy_kwh is None:issues.append({'field':'cycle.'+cid+'.energy','status':'missing_or_unknown'})
        loss=result['catalyst_unaccounted_g']
        if loss is None or loss>0:issues.append({'field':'cycle.'+cid+'.catalyst_loss','status':'unknown_or_unaccounted'})
        if result['influent_mass_mg'] is None or result['effluent_mass_mg'] is None:issues.append({'field':'cycle.'+cid+'.water_mass','status':'missing_or_censored'})
        vin=cycle['influent_volume'];vout=cycle['effluent_volume']
        vi=vin.get('value');vo=vout.get('value')
        vi_l=None if vi is None else vi*conversion(vin['unit'],'L');vo_l=None if vo is None else vo*conversion(vout['unit'],'L')
        if vi_l is None or vo_l is None or not math.isclose(vi_l,vo_l,rel_tol=1e-9,abs_tol=1e-12):issues.append({'field':'cycle.'+cid+'.volume','status':'sampling_or_volume_change_requires_review'})
        rows.append({'cycle_id':cid,'criterion_status':outcome,'reason':reason,'sample_links_complete_user_asserted':sample_ok,'sample_ids_user_asserted':sample_pairs,'sample_issues':sample_issues,'influent_volume_l':vi_l,'effluent_volume_l':vo_l,'apparent_removal_mg':result['apparent_removal_mg'],'apparent_removal_interval_mg':result['apparent_removal_interval_mg'],'energy_kwh':energy_kwh,'catalyst_unaccounted_g':loss})
    life=spec.get('lifetime') or {};life_kind=life.get('kind')
    if life_kind not in ('observed','assumed','extrapolated') or not present(life.get('source')):
        issues.append({'field':'lifetime','status':'kind_or_source_missing'})
    if life.get('evidence_class') not in EVIDENCE:issues.append({'field':'lifetime.evidence_class','status':'missing_or_invalid'})
    life_cycles=life.get('cycles')
    if life_cycles is not None and (isinstance(life_cycles,bool) or not isinstance(life_cycles,int) or life_cycles<=0):raise ValueError('lifetime cycles must be a positive integer')
    if life_kind=='observed' and life_cycles!=len(rows):issues.append({'field':'lifetime.cycles','status':'observed_count_mismatch'})
    if life_kind in ('assumed','extrapolated'):issues.append({'field':'lifetime','status':'not_observed_lifetime_requires_review'})
    return {'schema_version':'piezolca.cycle-service-result/1','foreground_sha256':foreground_hash,'campaign_id_user_asserted':spec.get('campaign_id'),'pollutant_user_asserted':spec.get('pollutant'),'service':service,'criterion_canonical':{'value':threshold,'unit':'mg/L' if kind=='treated_water_to_threshold' else 'mg'},'observed_cycle_count':len(rows),'lifetime_user_asserted':life,'cycles':rows,'issues':issues,'status':'review_required','ranking_permitted':False,'note':'Criterion outcomes are provisional numerical checks, not regulatory compliance, sample identity verification, delivered-water totals, or scientific approval. Existing LCI remains based on apparent removal; no treatment-volume functional-unit scaling is performed.'}


def read(path):
    raw=path.read_bytes();return json.loads(raw,parse_constant=lambda v: (_ for _ in ()).throw(ValueError('invalid JSON number '+v))),hashlib.sha256(raw).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('spec',type=Path);p.add_argument('--foreground',type=Path,required=True);p.add_argument('--evidence',type=Path);a=p.parse_args()
    try:
        spec,sh=read(a.spec);fg,fh=read(a.foreground);ev,eh=read(a.evidence) if a.evidence else (None,None)
        result=review(spec,fg,fh,ev);result.update(spec_sha256=sh,evidence_report_sha256=eh)
        result['code_sha256']={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in ('cycle_service_review.py','cyclic_foreground.py','evidence_chain.py')}
        print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False));return 0
    except (OSError,UnicodeError,ValueError,TypeError,KeyError,OverflowError) as exc:print('ERROR:',exc,file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
