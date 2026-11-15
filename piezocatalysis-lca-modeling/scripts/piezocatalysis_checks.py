#!/usr/bin/env python3
"""Review piezocatalytic experimental boundaries against a cyclic foreground."""
import argparse,hashlib,json,math,sys
from pathlib import Path
from cyclic_foreground import build
from evidence_chain import conversion


def read(path):
 raw=path.read_bytes();return json.loads(raw,parse_constant=lambda v: (_ for _ in ()).throw(ValueError('invalid number '+v))),hashlib.sha256(raw).hexdigest()
def text(value):return isinstance(value,str) and bool(value.strip()) and 'replace-me' not in value.lower()

def audit(protocol,source,source_hash,evidence=None,domain=None):
 if protocol.get('schema_version')!='piezolca.piezo-boundary/1':raise ValueError('unsupported protocol schema')
 if protocol.get('foreground_sha256')!=source_hash:raise ValueError('protocol foreground hash differs')
 model=build(source);issues=[];warnings=[]
 acts={x['activity_id']:x for c in source['cycles'] for x in c['activities']}
 def issue(field,status):issues.append({'field':field,'status':status})
 for key in ('reactor_configuration','mechanical_coupling','pollutant_identity','service_performance','sampling_and_losses'):
  entry=protocol.get(key)
  if not isinstance(entry,dict) or not text(entry.get('value')) or not text(entry.get('source')):issue(key,'missing_value_or_source')
 energy=protocol.get('ultrasound') or {};method=energy.get('energy_basis')
 if method not in ('wall_metered','device_metered','rated_power_estimate','unknown'):raise ValueError('invalid ultrasound energy_basis')
 if not text(energy.get('source')):issue('ultrasound.source','missing')
 if method=='unknown':issue('ultrasound.energy_basis','unknown')
 if method=='rated_power_estimate':warnings.append('Rated power × time is an estimate, not a measured wall-energy consumption.')
 ids=energy.get('activity_ids')
 if not isinstance(ids,list) or not ids or len(ids)!=len(set(ids)):issue('ultrasound.activity_ids','missing_or_duplicate');ids=[]
 for aid in ids:
  a=acts.get(aid)
  if not a or a.get('kind')!='energy' or a.get('included',True) is not True:issue('ultrasound.'+str(aid),'missing_excluded_or_not_energy');continue
  if method in ('wall_metered','device_metered') and 'quantity' not in a:issue('ultrasound.'+aid,'metered_basis_not_supported_by_power_time_input')
  if method in ('wall_metered','device_metered') and 'quantity' in a and a['quantity'].get('evidence_class') not in ('measured','reported'):
   issue('ultrasound.'+aid,'metered_basis_not_backed_by_measured_or_reported_quantity')
  if method=='rated_power_estimate' and not ('power' in a and 'duration' in a):issue('ultrasound.'+aid,'rated_basis_not_supported_by_power_time_input')
 for cycle in source['cycles']:
  if not any(a.get('activity_id') in ids and a.get('included',True) is True for a in cycle['activities']):
   issue('ultrasound.cycle.'+cycle['cycle_id'],'no_listed_ultrasound_activity_review_required')
 aux=protocol.get('auxiliary_energy') or {};aux_status=aux.get('status')
 if aux_status not in ('separately_included','included_in_total','excluded','unknown'):raise ValueError('invalid auxiliary energy status')
 if not text(aux.get('source')):issue('auxiliary_energy.source','missing')
 if aux_status=='unknown':issue('auxiliary_energy','coverage_unknown')
 if aux_status=='excluded' and not text(aux.get('reason')):issue('auxiliary_energy.reason','exclusion_reason_missing')
 auxids=aux.get('activity_ids',[])
 if not isinstance(auxids,list) or len(auxids)!=len(set(auxids)):raise ValueError('auxiliary activity_ids must be unique list')
 if aux_status=='separately_included' and not auxids:issue('auxiliary_energy','no_activity_declared')
 for aid in auxids:
  if aid in ids:issue('auxiliary_energy.'+str(aid),'same_activity_as_ultrasound')
  a=acts.get(aid)
  if not a or a.get('kind')!='energy' or a.get('included',True) is not True:issue('auxiliary_energy.'+str(aid),'missing_excluded_or_not_energy')
 if aux_status=='included_in_total' and auxids:issue('auxiliary_energy','potential_double_counting')
 if aux_status=='excluded' and auxids:issue('auxiliary_energy','excluded_but_activities_listed')
 oxidant=protocol.get('external_oxidant') or {};status=oxidant.get('status')
 if status not in ('added','not_added','unknown'):raise ValueError('invalid oxidant status')
 if not text(oxidant.get('source')):issue('external_oxidant.source','missing')
 oxids=oxidant.get('activity_ids',[])
 if not isinstance(oxids,list) or len(oxids)!=len(set(oxids)):raise ValueError('oxidant activity_ids must be unique list')
 if status=='unknown':issue('external_oxidant','unknown')
 if status=='added' and not oxids:issue('external_oxidant','added_without_inventory_activity')
 if status=='not_added' and oxids:issue('external_oxidant','contradictory_activity_list')
 for aid in oxids:
  a=acts.get(aid)
  if not a or a.get('kind')!='material' or a.get('direction')!='input' or a.get('included',True) is not True:issue('external_oxidant.'+str(aid),'missing_excluded_or_not_material_input')
 ph=protocol.get('ph_adjustment') or {};ph_status=ph.get('status')
 if ph_status not in ('added','not_added','unknown'):raise ValueError('invalid pH adjustment status')
 if not text(ph.get('source')):issue('ph_adjustment.source','missing')
 phids=ph.get('activity_ids',[])
 if not isinstance(phids,list) or len(phids)!=len(set(phids)):raise ValueError('pH activity_ids must be unique list')
 if ph_status=='unknown':issue('ph_adjustment','unknown')
 if ph_status=='added' and not phids:issue('ph_adjustment','added_without_inventory_activity')
 if ph_status=='not_added' and phids:issue('ph_adjustment','contradictory_activity_list')
 for aid in phids:
  a=acts.get(aid)
  if not a or a.get('kind')!='material' or a.get('direction')!='input' or a.get('included',True) is not True:issue('ph_adjustment.'+str(aid),'missing_excluded_or_not_material_input')
 light=protocol.get('illumination') or {};light_mode=light.get('mode')
 if light_mode not in ('dark','illuminated','unknown'):raise ValueError('invalid illumination mode')
 if not text(light.get('source')):issue('illumination.source','missing')
 lightids=light.get('activity_ids',[])
 if not isinstance(lightids,list) or len(lightids)!=len(set(lightids)):raise ValueError('illumination activity_ids must be unique list')
 if light_mode=='unknown':issue('illumination','unknown')
 if light_mode=='illuminated' and not lightids:issue('illumination','energy_activity_not_declared')
 if light_mode=='dark' and lightids:issue('illumination','dark_mode_has_light_activity')
 for aid in lightids:
  a=acts.get(aid)
  if not a or a.get('kind')!='energy' or a.get('included',True) is not True:issue('illumination.'+str(aid),'missing_excluded_or_not_energy')
  if aid in ids or aid in auxids:issue('illumination.'+str(aid),'overlapping_energy_activity')
 byproducts=protocol.get('byproducts_and_toxicity') or {}
 if not text(byproducts.get('value')) or not text(byproducts.get('source')):issue('byproducts_and_toxicity','missing_value_or_source')
 fate=protocol.get('catalyst_destination') or {}
 if fate.get('status') not in ('disposed','retained','unknown'):raise ValueError('invalid catalyst destination')
 if fate['status']!=source.get('final_recovered_destination'):issue('catalyst_destination','foreground_mismatch')
 if not text(fate.get('source')):issue('catalyst_destination.source','missing')
 if fate['status']=='unknown':issue('catalyst_destination','unknown')
 if fate['status']=='disposed' and not text(fate.get('treatment_mapping')):issue('catalyst_destination','disposal_mapping_missing')
 mineral=protocol.get('mineralization') or {};claim=mineral.get('claim')
 if claim not in ('not_claimed','claimed','unknown'):raise ValueError('invalid mineralization claim')
 if claim=='unknown':issue('mineralization','claim_unknown')
 if claim=='claimed':
  if not text(mineral.get('measurement')) or not text(mineral.get('source')):issue('mineralization','independent_measurement_and_source_missing')
  warnings.append('A declared mineralization measurement still requires scientific review; apparent aqueous removal is not proof.')
 if evidence is not None:
  if evidence.get('schema_version')!='piezolca.evidence-audit/1' or evidence.get('foreground_sha256')!=source_hash:raise ValueError('evidence report does not match foreground')
  if evidence.get('status')!='links_match_review_still_required':issue('evidence','unresolved_source_links')
 else:issue('evidence','not_checked')
 sample_checks=[]
 if domain is None:
  issue('domain_sample','not_checked')
 else:
  fields=domain.get('fields') or {};service=domain.get('service') or {}
  domain_boundary=fields.get('system_boundary') or {}
  if domain_boundary.get('status')!='provided' or not text(domain_boundary.get('value')):
   issue('domain.system_boundary','missing_or_unverified')
  elif domain_boundary['value'].strip()!=source['boundary'].strip():issue('domain.system_boundary','foreground_mismatch')
  kind=service.get('kind');fu=service.get('functional_unit') or {};target=source.get('treatment_target') or {}
  try:
   x=fu.get('value');y=target.get('value')
   if kind!='apparent_pollutant_removal' or fu.get('qualifier','exact')!='exact' or isinstance(x,bool) or not isinstance(x,(int,float)) or isinstance(y,bool) or not isinstance(y,(int,float)) or not math.isfinite(x) or not math.isfinite(y) or x<=0 or y<=0 or not math.isclose(x*conversion(fu.get('unit'),target.get('unit')),y,rel_tol=1e-10,abs_tol=0):
    raise ValueError('service or functional unit mismatch')
  except (ValueError,TypeError):issue('domain.functional_unit','mismatch_or_unverified')
  for protocol_key,domain_key in (('pollutant_identity','pollutant_identity'),('service_performance','performance_criteria')):
   left=protocol.get(protocol_key) or {};right=fields.get(domain_key) or {}
   if not text(left.get('value')) or right.get('status')!='provided' or not text(right.get('value')):
    issue('domain.'+domain_key,'missing_or_unverified')
   elif left['value'].strip().casefold()!=right['value'].strip().casefold():
    issue('domain.'+domain_key,'declaration_mismatch')
  sample=protocol.get('domain_sample_cycle_id')
  found=[(i,c) for i,c in enumerate(source['cycles']) if c.get('cycle_id')==sample]
  if len(found)!=1:issue('domain_sample_cycle_id','missing_or_not_unique')
  else:
   idx,cycle=found[0];linked={x['target']:x for x in (evidence or {}).get('links',[])}
   for key in ('influent_volume','influent_concentration','effluent_volume','effluent_concentration'):
    path='/cycles/'+str(idx)+'/'+key;decl=(domain.get('fields') or {}).get(key) or {};item=cycle.get(key) or {}
    check={'field':key,'foreground_pointer':path,'status':'matches'}
    try:
     if decl.get('status')!='provided':raise ValueError('domain field not provided')
     q1=decl.get('qualifier','exact' if decl.get('value') is not None else 'missing');q2=item.get('qualifier','exact' if item.get('value') is not None else 'missing')
     if q1!=q2:raise ValueError('qualifier mismatch')
     if q1 not in ('exact','below_lod','below_loq'):raise ValueError('invalid or missing observation')
     val='limit' if q1 in ('below_lod','below_loq') else 'value';x=decl.get(val);y=item.get(val)
     if isinstance(x,bool) or not isinstance(x,(int,float)) or isinstance(y,bool) or not isinstance(y,(int,float)) or not math.isfinite(x) or not math.isfinite(y) or not math.isclose(x*conversion(decl.get('unit'),item.get('unit')),y,rel_tol=1e-10,abs_tol=0):raise ValueError('value, limit or unit mismatch')
     if q1!='exact' and (decl.get('value') is not None or item.get('value') is not None or x<=0 or y<=0):raise ValueError('invalid censored value or limit')
     if decl.get('evidence_class')!=item.get('evidence_class'):raise ValueError('evidence class mismatch')
     if path not in linked or linked[path].get('basis')!=decl.get('basis'):raise ValueError('source link or sample basis mismatch')
    except (ValueError,TypeError,KeyError) as exc:
     check['status']='mismatch_or_unverified';check['detail']=str(exc);issue('domain_sample.'+key,'mismatch_or_unverified')
    sample_checks.append(check)
 warnings.extend(model['warnings'])
 return {'schema_version':'piezolca.piezo-boundary-review/1','foreground_sha256':source_hash,'protocol':protocol,'domain_sample_checks':sample_checks,'issues':issues,'warnings':warnings,
         'status':'needs_review' if issues or warnings else 'declarations_complete_review_required',
         'note':'Checks declarations against listed foreground activities; it cannot prove measurement provenance, completeness of unlisted equipment or reagents, chemical identity, mineralization, database suitability or scientific equivalence.'}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('protocol',type=Path);p.add_argument('--foreground',type=Path,required=True);p.add_argument('--evidence',type=Path);p.add_argument('--domain',type=Path);a=p.parse_args()
 try:
  protocol,ph=read(a.protocol);source,sh=read(a.foreground);ev,eh=read(a.evidence) if a.evidence else (None,None)
  domain,dh=read(a.domain) if a.domain else (None,None)
  r=audit(protocol,source,sh,ev,domain);r['protocol_sha256']=ph;r['evidence_report_sha256']=eh;r['domain_sha256']=dh
  r['code_sha256']={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in ('piezocatalysis_checks.py','cyclic_foreground.py','experimental_foreground.py','evidence_chain.py')}
  print(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False));return 0
 except (OSError,UnicodeError,ValueError,TypeError,KeyError,OverflowError) as exc:print('ERROR:',exc,file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
