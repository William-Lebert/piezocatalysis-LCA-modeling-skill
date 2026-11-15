#!/usr/bin/env python3
"""Collect read-only openLCA mapping alternatives and record explicit review decisions."""
import argparse,csv,hashlib,io,json,math,sys,uuid
from contextlib import ExitStack
from datetime import date
from pathlib import Path
from audit_and_scale_inventory import unit_factor
from inventory_handoff import load_handoff
from mapping_coverage import read_entity
from openlca_readonly import Client,IPCError,descriptors
from validate_inventory import EVIDENCE

SCHEMA='piezolca.mapping-review/1'
DECISION_FIELDS=['activity_id','process_uuid','candidate_name','process_version','process_type','geography','geography_name','location_code','location_verification','reference_product','dataset_unit','reference_is_input','candidate_issues',
 'decision','match_type','rationale','expected_bias','geography_rationale','technology_rationale','reviewer','review_date',
 'conversion_type','density_kg_per_l','density_source','density_evidence_class']
MAPPING_FIELDS=['mapping_id','foreground_flow','foreground_unit','database','database_version','system_model','dataset_name','reference_product',
 'dataset_unit','geography','match_type','conversion_factor','rationale','expected_bias','alternative_dataset','review_status','process_uuid',
 'reference_flow_uuid','flow_property_uuid','unit_uuid','mapping_source','verified_at','reference_is_input','process_version','conversion_type',
 'density_kg_per_l','density_source','density_evidence_class','geography_rationale','technology_rationale','candidate_reviewer','candidate_review_date']

def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(path):
 raw=path.read_bytes();return json.loads(raw,parse_constant=lambda x: (_ for _ in ()).throw(ValueError('invalid number '+x))),sha(raw)
def txt(value,label):
 if not isinstance(value,str) or not value.strip() or 'replace-me' in value.lower():raise ValueError(label+' is required')
 return value.strip()
def canonical_id(value):
 try:return str(uuid.UUID(value))
 except (ValueError,TypeError,AttributeError):raise ValueError('invalid process UUID') from None

def collect(handoff,queries,client,context):
 if handoff.get('schema_version')!='piezolca.handoff/1':raise ValueError('unsupported handoff')
 for key in ('database','database_version','system_model'):txt(context.get(key),key)
 requests=queries.get('queries')
 if not isinstance(requests,list) or not requests:raise ValueError('queries must be a nonempty list')
 rows={r['activity_id']:r for r in handoff['rows'] if r['included']};available=descriptors(client,'Process');by_id={}
 for item in available:
  uid=item.get('@id')
  if uid:
   if uid in by_id:raise ValueError('duplicate process descriptor UUID')
   by_id[uid]=item
 seen=set();cache={};location_cache={};results=[]
 for query in requests:
  aid=txt(query.get('activity_id'),'activity_id')
  if aid in seen or aid not in rows:raise ValueError('unknown or duplicate activity_id: '+aid)
  seen.add(aid);row=rows[aid];ids=query.get('process_uuids',[]);term=query.get('name_contains','');geo=query.get('geography','')
  if not isinstance(ids,list) or len(ids)>20 or not isinstance(term,str) or not isinstance(geo,str):raise ValueError(aid+': invalid query')
  if not ids and not term.strip():raise ValueError(aid+': supply process UUIDs or a name search')
  if 'replace-me' in term.lower() or 'replace-me' in geo.lower():raise ValueError(aid+': replace placeholder query values')
  missing=[]
  if ids:
   ids=[canonical_id(x) for x in ids]
   if len(ids)!=len(set(ids)):raise ValueError(aid+': duplicate process UUID')
   matches=[by_id[x] for x in ids if x in by_id];missing=[x for x in ids if x not in by_id];total=len(matches);truncated=False
  else:
   matches=[d for d in available if term.strip().casefold() in (d.get('name') or '').casefold() and (not geo.strip() or geo.strip().casefold()==(d.get('location') or '').casefold())]
   matches.sort(key=lambda x:((x.get('name') or ''),(x.get('location') or ''),(x.get('@id') or '')))
   total=len(matches);truncated=total>20;matches=matches[:20]
  candidates=[]
  for desc in matches:
   uid=desc.get('@id')
   if not uid:continue
   if uid not in cache:cache[uid]=read_entity(client,'Process',uid)
   process=cache[uid];issues=[];ref=None
   if not process:issues.append('process_not_found')
   else:
    refs=[e for e in process.get('exchanges',[]) if e.get('isQuantitativeReference') is True]
    if len(refs)!=1:issues.append('reference_exchange_invalid')
    else:ref=refs[0]
   ref=ref or {};flow=ref.get('flow') or {};prop=ref.get('flowProperty') or {};unit=ref.get('unit') or {}
   actual={'process_uuid':uid,'name':(process or {}).get('name'),'process_version':(process or {}).get('version'),
           'process_type':(process or {}).get('processType'),'geography':desc.get('location'),'reference_flow_uuid':flow.get('@id'),
           'reference_product':flow.get('name'),'flow_type':flow.get('flowType'),'flow_property_uuid':prop.get('@id'),
           'unit_uuid':unit.get('@id'),'dataset_unit':unit.get('name'),'reference_is_input':ref.get('isInput')}
   loc=(process or {}).get('location') or {};entity_geo=loc.get('name') if isinstance(loc,dict) else loc
   loc_id=loc.get('@id') if isinstance(loc,dict) else None;location=None
   if loc_id:
    if loc_id not in location_cache:location_cache[loc_id]=read_entity(client,'Location',loc_id)
    location=location_cache[loc_id]
   code=(location or {}).get('code');descriptor_geo=actual['geography']
   actual['geography_name']=entity_geo;actual['location_uuid']=loc_id;actual['location_code']=code
   actual['location_verification']=('code_matches' if code and descriptor_geo and code==descriptor_geo else
                                   'code_mismatch' if code and descriptor_geo else 'code_not_verified')
   if actual['location_verification']=='code_mismatch':issues.append('geography_descriptor_code_mismatch')
   if ids and term.strip() and term.strip().casefold() not in (actual['name'] or '').casefold():issues.append('query_name_mismatch')
   if ids and geo.strip() and geo.strip().casefold()!=(actual['geography'] or '').casefold():issues.append('query_geography_mismatch')
   for key in ('name','geography','reference_flow_uuid','reference_product','flow_property_uuid','unit_uuid','dataset_unit'):
    if not actual.get(key):issues.append(key+'_missing')
   if not isinstance(actual['reference_is_input'],bool):issues.append('reference_direction_missing')
   elif actual['reference_is_input']!=(row['direction']=='output'):issues.append('reference_direction_mismatch')
   try:factor=unit_factor(row['unit'],actual['dataset_unit'])
   except (ValueError,KeyError,TypeError):factor=None;issues.append('direct_unit_conversion_unavailable')
   candidates.append({'actual_reference':actual,'direct_conversion_factor':factor,'issues':issues})
  results.append({'activity_id':aid,'foreground_flow':row['flow_name'],'foreground_unit':row['unit'],'direction':row['direction'],
                  'stage':row.get('stage'),'cycle_id':row.get('cycle_id'),'foreground_source':row.get('source'),'foreground_evidence_class':row.get('evidence_class'),
                  'existing_mapping_id':row.get('mapping_id'),
                  'amount_per_functional_unit':row['amount_per_functional_unit'],'query':query,'matched_count':total,
                  'truncated':truncated,'missing_requested_uuids':missing,'candidates':candidates})
 return {'schema_version':SCHEMA,'database_user_asserted':context,'database_identity_verification':'user_asserted_not_verified',
         'inventory_sha256':handoff['inventory_sha256'],'manifest_sha256':handoff['manifest_sha256'],'amount_basis':handoff['amount_basis'],
         'included_activity_ids':list(rows),'unqueried_activity_ids':[aid for aid in rows if aid not in seen],
         'rows':results,'note':'Candidates are read-only observations, not selections or scientific approvals. The 20-item search limit, database identity, relevance and provider links need independent review.'}

def decision_rows(report):
 for row in report['rows']:
  for cand in row['candidates']:
   a=cand['actual_reference']
   yield {'activity_id':row['activity_id'],'process_uuid':a['process_uuid'],'candidate_name':a['name'] or '',
          'process_version':a['process_version'] or '', 'process_type':a['process_type'] or '',
          'geography':a['geography'] or '', 'geography_name':a['geography_name'] or '', 'location_code':a['location_code'] or '',
          'location_verification':a['location_verification'], 'reference_product':a['reference_product'] or '', 'dataset_unit':a['dataset_unit'] or '',
          'reference_is_input':str(a['reference_is_input']).lower() if isinstance(a['reference_is_input'],bool) else '',
          'candidate_issues':'; '.join(cand['issues']),
          'decision':'pending','match_type':'','rationale':'','expected_bias':'','geography_rationale':'','technology_rationale':'',
          'reviewer':'','review_date':'','conversion_type':'unit','density_kg_per_l':'','density_source':'','density_evidence_class':''}

def write_csv(path,fields,rows):
 with path.open('x',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='raise');w.writeheader();w.writerows(rows)

def finalize(report,decisions,handoff,decision_hash,review_hash):
 if report.get('schema_version')!=SCHEMA:raise ValueError('unsupported mapping review')
 if (report.get('inventory_sha256')!=handoff.get('inventory_sha256') or report.get('manifest_sha256')!=handoff.get('manifest_sha256') or handoff.get('amount_basis')!='per_functional_unit'):
  raise ValueError('inventory or manifest differs from the collected review')
 original={r['activity_id']:r for r in handoff['rows'] if r['included']}
 if report.get('included_activity_ids')!=list(original):raise ValueError('included activity inventory differs from collected review')
 activity_ids=[r['activity_id'] for r in report['rows']]
 if len(activity_ids)!=len(set(activity_ids)):raise ValueError('duplicate activity in collected review')
 for r in report['rows']:
  a=original.get(r['activity_id'])
  if not a or any(r[k]!=a[k] for k in ('direction','amount_per_functional_unit')) or r['foreground_flow']!=a['flow_name'] or r['foreground_unit']!=a['unit'] or any(r.get(k)!=a.get(source) for k,source in (('stage','stage'),('cycle_id','cycle_id'),('foreground_source','source'),('foreground_evidence_class','evidence_class'),('existing_mapping_id','mapping_id'))):
   raise ValueError('collected foreground metadata differs from inventory')
 reference={(x['activity_id'],x['process_uuid']):x for x in decision_rows(report)}
 if len(reference)!=sum(len(x['candidates']) for x in report['rows']):raise ValueError('duplicate candidate key')
 rows={x['activity_id']:x for x in report['rows']};selected={};seen=set();records=[]
 for d in decisions:
  key=(d.get('activity_id',''),d.get('process_uuid',''))
  if key in seen or key not in reference:raise ValueError('duplicate or unknown decision candidate')
  seen.add(key);snapshot=reference[key]
  for field in ('candidate_name','process_version','process_type','geography','geography_name','location_code','location_verification','reference_product','dataset_unit','reference_is_input','candidate_issues'):
   if d.get(field,'')!=snapshot[field]:raise ValueError('candidate metadata differs from collected review: '+field)
  state=d.get('decision','').strip()
  if state not in ('pending','selected','rejected'):raise ValueError('decision must be pending, selected or rejected')
  record={k:d.get(k,'').strip() for k in DECISION_FIELDS}
  if state in ('selected','rejected'):
   for f in ('rationale','reviewer','review_date'):txt(d.get(f),f)
   try:date.fromisoformat(d['review_date'].strip())
   except ValueError:raise ValueError('review_date must be an ISO date') from None
  if state=='selected':
   if key[0] in selected:raise ValueError('more than one selected candidate for '+key[0])
   for f in ('expected_bias','geography_rationale','technology_rationale'):txt(d.get(f),f)
   if d.get('match_type') not in ('exact','proxy','constructed'):raise ValueError('invalid match_type')
   row=rows[key[0]];cand=next(x for x in row['candidates'] if x['actual_reference']['process_uuid']==key[1]);a=cand['actual_reference']
   issues=[i for i in cand['issues'] if i!='direct_unit_conversion_unavailable']
   if issues:raise ValueError('selected candidate reference cannot be handed off: '+', '.join(issues))
   kind=d.get('conversion_type','').strip() or 'unit';density=None
   if kind=='unit':
    factor=unit_factor(row['foreground_unit'],a['dataset_unit'])
   elif kind=='density':
    try:density=float(d.get('density_kg_per_l',''))
    except ValueError:raise ValueError('density must be a positive finite number') from None
    if not math.isfinite(density) or density<=0:raise ValueError('density must be a positive finite number')
    txt(d.get('density_source'),'density_source')
    if d.get('density_evidence_class') not in EVIDENCE:raise ValueError('density evidence class is required')
    factor=unit_factor(row['foreground_unit'],'L')*density*unit_factor('kg',a['dataset_unit'])
   else:raise ValueError('unsupported conversion type')
   selected[key[0]]=(d,a,kind,density,factor)
  records.append(record)
 if seen!=set(reference):raise ValueError('decision table must retain all collected candidates')
 context=report['database_user_asserted'];mapping=[];assignments=[]
 for aid,(d,a,kind,density,factor) in selected.items():
  row=rows[aid];mid=original[aid].get('mapping_id') or 'review-'+aid
  if any(other!=aid and value.get('mapping_id')==mid for other,value in original.items()):
   raise ValueError('mapping ID is shared or conflicts with another activity: '+mid)
  alternatives=['{} | {} [{}] ({})'.format(r['candidate_name'],r['geography'],r['process_uuid'],r['decision'])
                for r in records if r['activity_id']==aid and r['process_uuid']!=a['process_uuid']]
  mapping.append({'mapping_id':mid,'foreground_flow':row['foreground_flow'],'foreground_unit':row['foreground_unit'],**context,
   'dataset_name':a['name'],'reference_product':a['reference_product'],'dataset_unit':a['dataset_unit'],'geography':a['geography'],
   'match_type':d['match_type'],'conversion_factor':factor,'rationale':d['rationale'],'expected_bias':d['expected_bias'],
   'alternative_dataset':'; '.join(alternatives),'review_status':'pending','process_uuid':a['process_uuid'],'reference_flow_uuid':a['reference_flow_uuid'],
   'flow_property_uuid':a['flow_property_uuid'],'unit_uuid':a['unit_uuid'],'mapping_source':'candidate selection; independent review pending',
   'verified_at':'','reference_is_input':str(a['reference_is_input']).lower(),'process_version':a['process_version'] or '',
   'conversion_type':kind,'density_kg_per_l':density if density is not None else '', 'density_source':d.get('density_source',''),
   'density_evidence_class':d.get('density_evidence_class',''),'geography_rationale':d['geography_rationale'],
   'technology_rationale':d['technology_rationale'],'candidate_reviewer':d['reviewer'],'candidate_review_date':d['review_date']})
  assignments.append({'activity_id':aid,'mapping_id':mid})
 unresolved=[aid for aid in original if aid not in selected]
 return {'schema_version':'piezolca.mapping-decision/1','review_sha256':review_hash,'decisions_sha256':decision_hash,
         'inventory_sha256':report['inventory_sha256'],'manifest_sha256':report['manifest_sha256'],'database_user_asserted':context,
         'records':records,'selected_count':len(mapping),'activities_without_selection':unresolved,
         'note':'Explicit candidate selections are not independent approvals. Exported mappings are pending; missing activities remain unmapped. Provider links and scientific suitability are not verified.'},mapping,assignments

def main():
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
 c=sub.add_parser('collect');c.add_argument('--inventory',type=Path,required=True);c.add_argument('--manifest',type=Path,required=True);c.add_argument('--queries',type=Path,required=True)
 for k in ('database','database-version','system-model'):c.add_argument('--'+k,required=True)
 src=c.add_mutually_exclusive_group(required=True);src.add_argument('--port',type=int);src.add_argument('--start-local',action='store_true')
 c.add_argument('--workspace',type=Path);c.add_argument('--openlca-app',type=Path,default=Path('/Applications/openLCA.app'));c.add_argument('--output-dir',type=Path,required=True)
 f=sub.add_parser('finalize');f.add_argument('--inventory',type=Path,required=True);f.add_argument('--manifest',type=Path,required=True);f.add_argument('--review',type=Path,required=True);f.add_argument('--decisions',type=Path,required=True);f.add_argument('--output-dir',type=Path,required=True)
 a=p.parse_args()
 try:
  handoff=load_handoff(a.inventory,a.manifest)
  if a.command=='collect':
   if a.start_local != (a.workspace is not None):raise ValueError('--workspace is required only for --start-local')
   queries,qh=read(a.queries);ctx={'database':a.database,'database_version':a.database_version,'system_model':a.system_model}
   with ExitStack() as stack:
    if a.start_local:
     from openlca_local_launch import launch
     port=stack.enter_context(launch(a.openlca_app,a.workspace,a.database))
    else:port=a.port
    report=collect(handoff,queries,Client(port,timeout=120),ctx)
   report['query_sha256']=qh;report['code_sha256']={n:sha(Path(__file__).with_name(n).read_bytes()) for n in ('mapping_review.py','mapping_coverage.py','inventory_handoff.py','openlca_readonly.py')}
   a.output_dir.mkdir(parents=True,exist_ok=False)
   (a.output_dir/'review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
   write_csv(a.output_dir/'decisions.csv',DECISION_FIELDS,decision_rows(report))
  else:
   report,rh=read(a.review);raw=a.decisions.read_bytes();reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig'),newline=''));fields=reader.fieldnames or []
   if len(fields)!=len(set(fields)) or set(fields)!=set(DECISION_FIELDS):raise ValueError('decision CSV columns differ from template')
   decisions=list(reader)
   if any(None in r or any(v is None for v in r.values()) for r in decisions):raise ValueError('malformed decision CSV')
   out,mapping,assignments=finalize(report,decisions,handoff,sha(raw),rh)
   out['finalizer_code_sha256']={n:sha(Path(__file__).with_name(n).read_bytes()) for n in ('mapping_review.py','inventory_handoff.py','audit_and_scale_inventory.py')}
   out['collect_code_matches_finalizer']=(report.get('code_sha256') or {}).get('mapping_review.py')==out['finalizer_code_sha256']['mapping_review.py']
   a.output_dir.mkdir(parents=True,exist_ok=False)
   (a.output_dir/'review-record.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
   write_csv(a.output_dir/'mapping.csv',MAPPING_FIELDS,mapping);write_csv(a.output_dir/'assignments.csv',['activity_id','mapping_id'],assignments)
  print('Prepared',a.output_dir);return 0
 except (OSError,UnicodeError,ValueError,TypeError,KeyError,OverflowError,csv.Error,IPCError) as exc:print('ERROR:',exc,file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
