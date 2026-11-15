#!/usr/bin/env python3
"""Review declared piezocatalysis service, boundary and evidence without inventing values."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

from inventory_handoff import load_handoff

EVIDENCE={'measured','reported','calculated','proxy','scenario'}
SERVICE_UNITS={'treated_water':{'L':1,'mL':.001,'m3':1000},
 'apparent_pollutant_removal':{'mg':1,'g':1000,'kg':1e6},
 'h2o2_product':{'mg':1,'g':1000,'kg':1e6},'catalyst_production':{'mg':1,'g':1000,'kg':1e6}}
PRODUCT_BASES={'net_accumulated','gross_generated','recovered_product','in_situ_consumed'}
COMMON={'system_boundary':'text','reaction_mode':'text','energy_metering':'text','electricity_geography':'text',
 'external_oxidants':'text','external_oxidant_dose':'text','catalyst_fresh':'mass','catalyst_recovered':'mass','catalyst_loss':'mass',
 'catalyst_destination':'text','catalyst_mass_balance':'text','wastewater_destination':'text','background_mapping':'text',
 'coproduct_allocation':'text','sampling_protocol':'text','replication_design':'text','calibration':'text'}
WATER={'pollutant_identity':'text','influent_volume':'volume','influent_concentration':'concentration',
 'effluent_volume':'volume','effluent_concentration':'concentration','sampling_losses':'text','performance_criteria':'text'}
EXTRA={'treated_water':WATER,'apparent_pollutant_removal':WATER,
       'h2o2_product':{'product_measurement':'text','product_quality':'text','external_product_adjustment':'text','in_situ_consumption':'text'},
       'catalyst_production':{'catalyst_identity':'text','dry_yield':'mass'}}
UNITS={'mass':{'mg':1,'g':1000,'kg':1e6},'volume':{'mL':.001,'L':1,'m3':1000},
       'concentration':{'ug/L':.001,'µg/L':.001,'μg/L':.001,'mg/L':1,'g/L':1000}}


def text(x):return isinstance(x,str) and bool(x.strip()) and 'replace-me' not in x.lower()


def quantity(item,kind,label,issues,positive=False):
    units=SERVICE_UNITS.get(kind,UNITS.get(kind))
    if not isinstance(item,dict):issues.append({'field':label,'status':'missing'});return None
    unit=item.get('unit');qualifier=item.get('qualifier','exact')
    if unit not in units:issues.append({'field':label,'status':'unit_invalid','unit':unit});return None
    if qualifier not in ('exact','below_lod','below_loq','missing'):
        issues.append({'field':label,'status':'qualifier_invalid'});return None
    val=item.get('value')
    if qualifier in ('below_lod','below_loq'):
        limit=item.get('limit')
        if isinstance(limit,bool) or not isinstance(limit,(int,float)) or not math.isfinite(limit) or limit<=0:
            issues.append({'field':label,'status':'detection_limit_missing_or_invalid'})
        else:issues.append({'field':label,'status':'censored_not_imputed','limit':limit,'unit':unit})
        if val is not None:issues.append({'field':label,'status':'censored_value_must_be_null'})
        return None
    if qualifier=='missing' or val is None:
        issues.append({'field':label,'status':'value_missing'})
        if qualifier=='missing' and val is not None:issues.append({'field':label,'status':'missing_value_must_be_null'})
        return None
    if isinstance(val,bool) or not isinstance(val,(int,float)) or not math.isfinite(val) or val<0 or (positive and val<=0):
        issues.append({'field':label,'status':'numeric_value_invalid'});return None
    converted=val*units[unit]
    if not math.isfinite(converted) or (val and converted==0):issues.append({'field':label,'status':'conversion_out_of_range'});return None
    return converted


def field_check(name,item,kind,issues):
    if not isinstance(item,dict):issues.append({'field':name,'status':'missing_declaration'});return
    status=item.get('status')
    if status=='missing':issues.append({'field':name,'status':'missing'});return
    if status=='not_applicable':
        if not text(item.get('reason')):issues.append({'field':name,'status':'exclusion_reason_missing'})
        return
    if status!='provided':issues.append({'field':name,'status':'invalid_status'});return
    if not text(item.get('source')):issues.append({'field':name,'status':'source_missing'})
    if item.get('evidence_class') not in EVIDENCE:issues.append({'field':name,'status':'evidence_missing_or_invalid'})
    if kind=='text':
        if not text(item.get('value')):issues.append({'field':name,'status':'value_missing'})
    else:
        if not text(item.get('basis')):issues.append({'field':name,'status':'measurement_basis_missing'})
        quantity(item,kind,name,issues)


def assess(data,handoff=None,source_input_sha256=None):
    if not isinstance(data,dict) or not isinstance(data.get('service'),dict) or not isinstance(data.get('fields'),dict):
        raise ValueError('service and fields objects are required')
    service=data['service'];kind=service.get('kind')
    if kind not in SERVICE_UNITS:raise ValueError('unsupported service kind')
    issues=[];warnings=[]
    amount=quantity(service.get('functional_unit'),kind,'service.functional_unit',issues,positive=True)
    for key in ('definition','source'):
        if not text(service.get(key)):issues.append({'field':'service.'+key,'status':'missing'})
    if service.get('evidence_class') not in EVIDENCE:issues.append({'field':'service.evidence_class','status':'missing_or_invalid'})
    if kind=='h2o2_product':
        if service.get('product_basis') not in PRODUCT_BASES:issues.append({'field':'service.product_basis','status':'missing_or_invalid'})
        if service.get('product_basis') in ('gross_generated','in_situ_consumed'):
            warnings.append('This is a service declaration only; the H2O2 foreground calculator does not infer gross generation or in-situ consumption.')
    if kind=='catalyst_production' and service.get('catalyst_basis')!='dry':
        issues.append({'field':'service.catalyst_basis','status':'dry_basis_not_confirmed'})
    requested={**COMMON,**EXTRA[kind]};fields=data['fields']
    for name,dimension in requested.items():field_check(name,fields.get(name),dimension,issues)
    for name in ('catalyst_fresh','catalyst_recovered','catalyst_loss'):
        if (fields.get(name) or {}).get('status')=='not_applicable':warnings.append(name+' excluded by user declaration; review system boundary.')
    observed=None
    if kind in ('treated_water','apparent_pollutant_removal'):
        def field_number(name,dimension):
            item=fields.get(name) or {}; ignored=[]
            return quantity(item,dimension,name,ignored) if item.get('status')=='provided' else None
        sample_fields=('influent_volume','influent_concentration','effluent_volume','effluent_concentration')
        bases=[(fields.get(n) or {}).get('basis') for n in sample_fields]
        aligned=all(text(v) for v in bases) and len(set(bases))==1
        if not aligned:issues.append({'field':'water_sample_basis','status':'missing_or_mismatch'})
        vin=field_number('influent_volume','volume') if aligned else None;cin=field_number('influent_concentration','concentration') if aligned else None
        vout=field_number('effluent_volume','volume') if aligned else None;cout=field_number('effluent_concentration','concentration') if aligned else None
        incoming=None if vin is None or cin is None else vin*cin
        outgoing=None if vout is None or cout is None else vout*cout
        net=None if incoming is None or outgoing is None else incoming-outgoing
        interval=None
        eff=fields.get('effluent_concentration') or {}; lim=eff.get('limit');u=eff.get('unit')
        if incoming is not None and vout is not None and eff.get('status')=='provided' and eff.get('value') is None and eff.get('qualifier') in ('below_lod','below_loq') and u in UNITS['concentration'] and isinstance(lim,(int,float)) and not isinstance(lim,bool) and math.isfinite(lim) and lim>0:
            interval=[incoming-vout*lim*UNITS['concentration'][u],incoming]
        if net is not None and net<0:warnings.append('Calculated outgoing pollutant mass exceeds incoming mass; review sampling and flows.')
        observed={'influent_mass_mg':incoming,'effluent_mass_mg':outgoing,'apparent_mass_difference_mg':net,
                  'censored_apparent_difference_interval_mg':interval,
                  'note':'Water-phase mass difference only; not proof of mineralization or a closed mass balance. The censored interval assumes concentration is nonnegative and below the stated limit.'}
    source_check='not_checked'
    if handoff is not None:
        if source_input_sha256 is not None:
            source_check='matches_manifest' if source_input_sha256==handoff.get('input_sha256') else 'mismatch_or_missing'
            if source_check!='matches_manifest':issues.append({'field':'handoff.source_input_sha256','status':source_check})
        if handoff.get('amount_basis')!='per_functional_unit':issues.append({'field':'handoff.amount_basis','status':'not_per_functional_unit'})
        actual=handoff.get('functional_unit_type')
        if actual!=kind:issues.append({'field':'handoff.functional_unit_type','status':'mismatch_or_unavailable','declared':kind,'manifest':actual})
        fu=handoff.get('functional_unit') or {};temp=[]
        normalized=quantity({'value':fu.get('value'),'unit':fu.get('unit')},kind,'manifest.functional_unit',temp,positive=True)
        if amount is None or normalized is None or not math.isclose(amount,normalized,rel_tol=1e-10,abs_tol=0):
            issues.append({'field':'handoff.functional_unit','status':'mismatch_or_unavailable'})
        if kind=='h2o2_product' and handoff.get('product_basis')!=service.get('product_basis'):
            issues.append({'field':'handoff.product_basis','status':'mismatch_or_unavailable'})
        if kind=='h2o2_product' and handoff.get('product_definition')!=service.get('definition'):
            issues.append({'field':'handoff.product_definition','status':'mismatch_or_unavailable'})
        if handoff.get('boundary')!=(fields.get('system_boundary') or {}).get('value'):
            issues.append({'field':'handoff.system_boundary','status':'mismatch_or_unavailable'})
        for row in handoff.get('rows',[]):
            if row.get('included') and row.get('issues'):
                issues.append({'field':'mapping.'+row['activity_id'],'status':'requires_review','issues':row['issues']})
            if row.get('included') and row.get('mapping_type') in ('proxy','constructed'):
                warnings.append('Mapping '+row['activity_id']+' uses '+row['mapping_type']+'; suitability requires review.')
        warnings.extend(handoff.get('model_warnings',[]))
    else:issues.append({'field':'handoff','status':'not_checked'})
    return {'schema_version':'piezolca.domain-review/1','service':service,'fields':fields,'required_fields':requested,
            'water_phase_observation':observed,
            'source_input_sha256_check':source_check,
            'observation_binding':'Domain declarations are user supplied; numerical observations are not automatically reconciled with source input or model exchanges.',
            'handoff':None if handoff is None else {'inventory_sha256':handoff.get('inventory_sha256'),'manifest_sha256':handoff.get('manifest_sha256'),
              'mapping_sha256':handoff.get('mapping_sha256'),'assignments_sha256':handoff.get('assignments_sha256'),
              'functional_unit_type':handoff.get('functional_unit_type'),'product_basis':handoff.get('product_basis')},
            'issues':issues,'warnings':warnings,'status':'needs_review' if issues or warnings else 'declarations_complete_review_required',
            'note':'Checks declarations and linked inventory basis; it does not independently verify sampling, mass balance, database identity, impact coverage, proxy suitability, mineralization or scientific equivalence.'}


def compare_services(a,b):
    issues=[]
    if a.get('kind')!=b.get('kind'):issues.append('service_kind_mismatch')
    kind=a.get('kind')
    if kind not in SERVICE_UNITS:return {'comparable':False,'issues':issues+['service_kind_invalid']}
    for x in (a,b):
        tmp=[];quantity(x.get('functional_unit'),kind,'functional_unit',tmp,positive=True)
        if tmp:issues.append('functional_unit_invalid_or_missing')
        if not text(x.get('definition')):issues.append('service_definition_missing')
    if not issues:
        def amount(x):q=x['functional_unit'];return q['value']*SERVICE_UNITS[kind][q['unit']]
        if not math.isclose(amount(a),amount(b),rel_tol=1e-10,abs_tol=0):issues.append('functional_unit_mismatch')
        if a['definition'].strip()!=b['definition'].strip():issues.append('service_definition_mismatch')
    if kind=='h2o2_product' and (a.get('product_basis') not in PRODUCT_BASES or a.get('product_basis')!=b.get('product_basis')):
        issues.append('product_basis_missing_or_mismatch')
    if kind=='catalyst_production' and (a.get('catalyst_basis')!='dry' or b.get('catalyst_basis')!='dry'):
        issues.append('dry_catalyst_basis_not_confirmed')
    return {'comparable':not issues,'issues':issues,'note':'Only service declarations compared; review boundary, performance, method, geography and data quality separately.'}


def compare_declarations(left,right):
    service=compare_services(left.get('service',{}),right.get('service',{}));issues=list(service['issues'])
    kind=left.get('service',{}).get('kind')
    fields=['system_boundary','electricity_geography','coproduct_allocation']
    if kind in ('treated_water','apparent_pollutant_removal'):fields+=['pollutant_identity','performance_criteria']
    elif kind=='h2o2_product':fields+=['product_quality']
    elif kind=='catalyst_production':fields+=['catalyst_identity']
    for name in fields:
        a=left.get('fields',{}).get(name) or {};b=right.get('fields',{}).get(name) or {}
        if a.get('status')!='provided' or b.get('status')!='provided' or not text(a.get('value')) or not text(b.get('value')):
            issues.append(name+'_not_verified')
        elif a['value'].strip()!=b['value'].strip():issues.append(name+'_mismatch')
    return {'declarations_match':not issues,'issues':issues,'ranking_permitted':False,
            'note':'Selected declarations only; LCIA method, database, mappings, data quality and scientific suitability still require independent review before ranking.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path)
    p.add_argument('--inventory',type=Path);p.add_argument('--manifest',type=Path);p.add_argument('--mapping',type=Path);p.add_argument('--assignments',type=Path)
    p.add_argument('--compare',type=Path,help='optional second service declaration to compare')
    p.add_argument('--source-input',type=Path,help='optional original foreground input checked against the manifest hash')
    a=p.parse_args()
    if bool(a.inventory)!=bool(a.manifest) or (a.mapping and not a.inventory) or (a.assignments and not a.mapping) or (a.source_input and not a.inventory):p.error('inventory and manifest are paired; source input requires them; assignments require mapping')
    try:
        raw=a.input.read_bytes();data=json.loads(raw,parse_constant=lambda x: (_ for _ in ()).throw(ValueError('invalid number '+x)))
        h=load_handoff(a.inventory,a.manifest,a.mapping,a.assignments) if a.inventory else None
        source_hash=hashlib.sha256(a.source_input.read_bytes()).hexdigest() if a.source_input else None
        out=assess(data,h,source_hash)
        if a.compare:
            compare_raw=a.compare.read_bytes();other=json.loads(compare_raw,parse_constant=lambda x: (_ for _ in ()).throw(ValueError('invalid number '+x)))
            out['service_comparison']=compare_declarations(data,other);out['comparison_input_sha256']=hashlib.sha256(compare_raw).hexdigest()
        out['input_sha256']=hashlib.sha256(raw).hexdigest();out['code_sha256']={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in ('domain_review.py','inventory_handoff.py','audit_and_scale_inventory.py')}
        print(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False));return 0
    except (OSError,ValueError,TypeError,KeyError,OverflowError) as e:print('ERROR:',e,file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
