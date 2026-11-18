#!/usr/bin/env python3
"""Assemble and verify a local, traceable research delivery from existing artifacts."""
import argparse,copy,csv,hashlib,io,json,math,sys
from pathlib import Path
from inventory_handoff import load_handoff
from mapping_review import finalize,DECISION_FIELDS
from plot_data import stage_contributions,cycles,scenarios,sensitivity
from result_coverage import contribution_summary

SCHEMA='piezolca.research-delivery/1'
ROLES={'foreground','evidence_spec','evidence_report','domain_protocol','domain_input','domain_report','inventory','inventory_manifest','mapping','assignments',
       'candidate_review','candidate_decisions','candidate_record','model_plan','calculation','coverage','binding','plot_data','plot_dir','cycle_plot_data','cycle_plot_dir','cycle_service_spec','cycle_service_report','scenario_baseline_bound','scenario_bound','scenario_source','scenario_contexts','scenario_comparison','scenario_plot_data','scenario_plot_dir','sensitivity_spec','sensitivity_report','sensitivity_plot_data','sensitivity_plot_dir'}
REQUIRED=('foreground','inventory','inventory_manifest')

def sha(raw):return hashlib.sha256(raw).hexdigest()
def json_read(path):
 raw=path.read_bytes();return json.loads(raw,parse_constant=lambda v: (_ for _ in ()).throw(ValueError('invalid JSON number '+v)))
def resolve(root,value):
 if not isinstance(value,str) or not value.strip():raise ValueError('artifact path must be a nonempty string')
 return (root/Path(value)).resolve()
def json_bytes(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def valid_text(value,label):
 if not isinstance(value,str) or not value.strip() or 'replace-me' in value.lower():raise ValueError(label+' is required')
 return value.strip()

def declaration(value):
 if not isinstance(value,dict) or not value:return '未提供'
 labels={'value':'内容','source':'来源','status':'状态','energy_basis':'计量基准','mode':'模式','activity_ids':'活动编号','reason':'说明',
         'treatment_mapping':'处置映射','claim':'声明','measurement':'测量方式'}
 parts=[]
 for key,label in labels.items():
  item=value.get(key)
  if item is None or item=='' or item==[]:continue
  parts.append(label+'：'+('、'.join(map(str,item)) if isinstance(item,list) else str(item)))
 return '；'.join(parts) if parts else '未提供'

def verify_plot_files(directory,plot):
 valid_text(plot.get('license_note'),'plot license_note')
 manifest=json_read(directory/'manifest.json')
 if manifest.get('schema_version')!='piezolca.plot-manifest/1' or manifest.get('input_plot_data_sha256')!=sha(json_bytes(plot)) or manifest.get('license_note')!=plot['license_note']:raise ValueError('plot manifest input or license mismatch')
 if set(manifest.get('outputs',{}))!={'plot-data.json','table.csv','chart.svg','chart.png'}:raise ValueError('plot manifest output list mismatch')
 for name,h in manifest['outputs'].items():
  if sha((directory/name).read_bytes())!=h:raise ValueError('plot output hash mismatch: '+name)
 if json_read(directory/'plot-data.json')!=plot:raise ValueError('rendered plot data differs')

def candidate_matches_plan(candidate,actual):
 fields=('process_uuid','name','process_version','process_type','geography','reference_flow_uuid','reference_product','flow_property_uuid','unit_uuid','reference_is_input')
 return all(candidate.get(k)==actual.get(k) for k in fields) and candidate.get('dataset_unit')==actual.get('unit_name')

def assemble(spec,root,outdir,spec_raw=None):
 if spec.get('schema_version')!=SCHEMA:raise ValueError('unsupported delivery schema')
 title=valid_text(spec.get('title'),'title');license_note=valid_text(spec.get('license_note'),'license_note')
 files=spec.get('artifacts')
 if not isinstance(files,dict) or set(files)-ROLES:raise ValueError('unsupported or missing artifacts object')
 paths={k:resolve(root,v) for k,v in files.items()}
 for role in REQUIRED:
  if role not in paths:raise ValueError('required artifact missing: '+role)
 for k,p in paths.items():
  if k in ('plot_dir','cycle_plot_dir','scenario_plot_dir','sensitivity_plot_dir'):
   if not p.is_dir():raise ValueError('plot_dir must be a directory')
  elif not p.is_file():raise ValueError(k+' must be a file')
 if ('mapping' in paths)!=('assignments' in paths):raise ValueError('mapping and assignments must be supplied together')
 if any(k in paths for k in ('candidate_review','candidate_decisions','candidate_record')) and not all(k in paths for k in ('candidate_review','candidate_decisions','candidate_record')):
  raise ValueError('candidate review, decisions and record must be supplied together')
 if ('coverage' in paths)!=('calculation' in paths):raise ValueError('coverage and calculation must be supplied together')
 if any(k in paths for k in ('plot_data','plot_dir','binding')) and not all(k in paths for k in ('plot_data','plot_dir','binding','coverage','model_plan')):
  raise ValueError('stage plot requires plot_data, plot_dir, binding, coverage and model_plan')
 if ('cycle_plot_data' in paths)!=('cycle_plot_dir' in paths):raise ValueError('cycle plot data and directory must be supplied together')
 for group in (('scenario_baseline_bound','scenario_bound','scenario_source','scenario_contexts','scenario_comparison','scenario_plot_data','scenario_plot_dir'),('sensitivity_spec','sensitivity_report','sensitivity_plot_data','sensitivity_plot_dir')):
  if any(k in paths for k in group) and not all(k in paths for k in group):raise ValueError('analysis artifact group is incomplete: '+', '.join(group))
 if ('cycle_service_spec' in paths)!=('cycle_service_report' in paths) or ('cycle_service_report' in paths and 'evidence_report' not in paths):raise ValueError('cycle service review requires spec, report and evidence report')
 handoff=load_handoff(paths['inventory'],paths['inventory_manifest'],paths.get('mapping'),paths.get('assignments'))
 fg_raw=paths['foreground'].read_bytes();fg_hash=sha(fg_raw)
 if handoff.get('input_sha256')!=fg_hash:raise ValueError('foreground differs from inventory manifest')
 from evidence_chain import build_foreground
 fg=json.loads(fg_raw,parse_constant=lambda v: (_ for _ in ()).throw(ValueError('invalid JSON number '+v)));model,service=build_foreground(fg)
 if handoff.get('functional_unit')!=model['functional_unit'] or handoff.get('boundary')!=model['boundary'] or handoff.get('functional_unit_type')!=service:raise ValueError('manifest service or boundary differs from foreground')
 if service=='h2o2_product' and any(handoff.get(k)!=model[k] for k in ('product_basis','product_definition')):raise ValueError('manifest product basis or definition differs from foreground')
 if service=='h2o2_product' and any(k in paths for k in ('domain_protocol','domain_input','domain_report','cycle_plot_data','cycle_plot_dir')):raise ValueError('cyclic domain review and cycle plots do not support H2O2 product foreground')
 invrows={x['activity_id']:x for x in handoff['rows']};flows={x['activity_id']:x for x in model['functional_unit_flows']}
 if invrows.keys()!=flows.keys():raise ValueError('inventory activities differ from rebuilt foreground')
 for aid,x in invrows.items():
  f=flows[aid];a=x['amount_per_functional_unit'];b=f['amount']
  if x['unit']!=f['unit'] or x['direction']!=f['direction'] or x['stage']!=f['stage'] or x['cycle_id']!=f['cycle'] or x['flow_name']!=f['flow_name'] or x['included']!=f['included'] or (a is None)!=(b is None) or (a is not None and not math.isclose(a,b,rel_tol=1e-10,abs_tol=0)):raise ValueError('inventory differs from rebuilt foreground: '+aid)
  if x['evidence_class']!=f['evidence_class'] or x['source']!=f['source'].strip():raise ValueError('inventory evidence class or source differs from rebuilt foreground: '+aid)
 warnings=[];checks=[]
 if handoff['summary']['included_needing_review']:warnings.append('Inventory mappings or exchanges require review: '+str(handoff['summary']['included_needing_review']))
 for row in handoff['rows']:
  if row['included'] and row['mapping_type'] in ('proxy','constructed'):warnings.append('Proxy or constructed mapping: '+row['activity_id'])
 warnings.extend(handoff.get('model_warnings',[]))
 checks.append('Foreground, functional unit, boundary and per-functional-unit inventory rebuilt and checked.')
 data={k:json_read(p) for k,p in paths.items() if k in ('evidence_spec','evidence_report','domain_protocol','domain_input','domain_report','candidate_review','candidate_record','model_plan','calculation','coverage','binding','plot_data','cycle_plot_data','cycle_service_spec','cycle_service_report','scenario_baseline_bound','scenario_bound','scenario_source','scenario_contexts','scenario_comparison','scenario_plot_data','sensitivity_spec','sensitivity_report','sensitivity_plot_data')}
 for role,value in data.items():
  if not isinstance(value,dict) or not value:raise ValueError(role+' must be a nonempty JSON object')
 sources=spec.get('evidence_sources',{})
 if not isinstance(sources,dict):raise ValueError('evidence_sources must be an object')
 source_paths={k:resolve(root,v) for k,v in sources.items()}
 for sid in source_paths:
  if not sid or any(ch not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for ch in sid):raise ValueError('evidence source id must be safe for a filename')
 if ('evidence_spec' in paths)!=('evidence_report' in paths):raise ValueError('evidence_spec and evidence_report must be supplied together')
 if 'evidence_report' in data:
  ev=data['evidence_report'];es=data['evidence_spec']
  if ev.get('schema_version')!='piezolca.evidence-audit/1' or ev.get('foreground_sha256')!=fg_hash or ev.get('spec_sha256')!=sha(paths['evidence_spec'].read_bytes()):raise ValueError('evidence report does not match foreground or evidence spec')
  if service=='h2o2_product' and (ev.get('functional_unit_type')!=service or ev.get('product_basis')!=model['product_basis'] or ev.get('product_definition_user_asserted')!=model['product_definition']):raise ValueError('evidence product function differs from foreground')
  if (ev.get('inventory_rebuilt_and_verified') or {}).get('inventory_sha256')!=handoff['inventory_sha256'] or (ev.get('inventory_rebuilt_and_verified') or {}).get('manifest_sha256')!=handoff['manifest_sha256']:raise ValueError('evidence report is not bound to this inventory and manifest')
  declared={x['id']:x for x in es.get('sources',[])}
  if set(source_paths)-set(declared):raise ValueError('unknown evidence source id')
  for sid,p in source_paths.items():
   if not p.is_file() or sha(p.read_bytes())!=declared[sid]['sha256']:raise ValueError('evidence source hash mismatch: '+sid)
  missing=set(declared)-set(source_paths)
  if missing:warnings.append('Evidence source files omitted: '+', '.join(sorted(missing)))
  if es.get('originals'):warnings.append('Original files are not automatically included; declared original locations need independent verification.')
  if not missing and not es.get('originals'):
   from evidence_chain import audit as evidence_audit
   replay=copy.deepcopy(es)
   for entry in replay['sources']:entry['path']=str(source_paths[entry['id']])
   rebuilt=evidence_audit(replay,root,fg,fg_hash,paths['inventory'],paths['inventory_manifest'])
   for key in ('coverage','links','inventory_rebuilt_and_verified','campaign','functional_unit_flows','inventory_traces','issues','status'):
    if rebuilt[key]!=ev.get(key):raise ValueError('evidence audit differs from rebuilt sources: '+key)
   if service=='h2o2_product' and any(rebuilt.get(k)!=ev.get(k) for k in ('functional_unit_type','product_basis','product_definition_user_asserted')):raise ValueError('evidence product function differs from rebuilt sources')
   checks.append('Evidence links and per-functional-unit provenance rebuilt from supplied CSV sources.')
  for issue in ev.get('issues',[]):warnings.append('Evidence '+str(issue.get('target','unknown'))+': '+str(issue.get('status','unknown')))
  checks.append('Evidence report hashes and supplied normalized sources checked; original measurement authenticity is not established.')
 else:warnings.append('Evidence audit not supplied.')
 if 'cycle_service_report' in data:
  if service!='apparent_pollutant_removal':raise ValueError('cycle service review requires a cyclic foreground')
  sr=data['cycle_service_report']
  if sr.get('spec_sha256')!=sha(paths['cycle_service_spec'].read_bytes()) or sr.get('evidence_report_sha256')!=sha(paths['evidence_report'].read_bytes()):raise ValueError('cycle service report input hash mismatch')
  from cycle_service_review import review as cycle_service_review
  rebuilt=cycle_service_review(data['cycle_service_spec'],fg,fg_hash,data['evidence_report'])
  if any(sr.get(k)!=v for k,v in rebuilt.items()):raise ValueError('cycle service report differs from rebuilt declarations')
  warnings.append('Cycle service thresholds and sample identities are user assertions; independently review service comparability, samples and catalyst fate.')
  for issue in sr['issues']:warnings.append('Cycle service '+str(issue.get('field'))+': '+str(issue.get('status')))
  checks.append('Cycle service declarations and sample links rebuilt; this does not convert the LCI to treated-water service.')
 if any(k in paths for k in ('domain_protocol','domain_input','domain_report')) and not all(k in paths for k in ('domain_protocol','domain_input','domain_report','evidence_report')):
  raise ValueError('domain report requires protocol, domain input and evidence report')
 if 'domain_report' in data:
  dr=data['domain_report']
  if dr.get('schema_version')!='piezolca.piezo-boundary-review/1' or dr.get('foreground_sha256')!=fg_hash:raise ValueError('domain report does not match foreground')
  if 'evidence_report' in paths and dr.get('evidence_report_sha256')!=sha(paths['evidence_report'].read_bytes()):raise ValueError('domain report refers to a different evidence report')
  if dr.get('protocol_sha256')!=sha(paths['domain_protocol'].read_bytes()) or dr.get('domain_sha256')!=sha(paths['domain_input'].read_bytes()):raise ValueError('domain inputs do not match report')
  from piezocatalysis_checks import audit as domain_audit
  rebuilt=domain_audit(data['domain_protocol'],fg,fg_hash,data['evidence_report'],data['domain_input'])
  if any(dr.get(k)!=v for k,v in rebuilt.items()):raise ValueError('domain report differs from rebuilt declarations')
  for issue in dr.get('issues',[]):warnings.append('Domain '+str(issue.get('field','unknown'))+': '+str(issue.get('status','unknown')))
  warnings.extend(dr.get('warnings',[]))
 else:warnings.append('Piezocatalysis boundary review not supplied.' if service!='h2o2_product' else 'H2O2 product definition and experimental boundary require independent review; cyclic domain review is not applicable.')
 plan=data.get('model_plan')
 if plan:
  if plan.get('schema_version')!='piezolca.cycle-model-plan/1' or plan.get('inventory_sha256')!=handoff['inventory_sha256'] or plan.get('manifest_sha256')!=handoff['manifest_sha256'] or plan.get('mapping_sha256')!=handoff['mapping_sha256'] or plan.get('assignments_sha256')!=handoff['assignments_sha256']:raise ValueError('model plan differs from inventory or mapping handoff')
  if service=='h2o2_product' and any(plan.get(k)!=handoff.get(k) for k in ('functional_unit_type','product_basis','product_definition','functional_unit','boundary')):raise ValueError('model plan product function differs from handoff')
  planrows={r['activity_id']:r for r in plan['rows']}
  if len(planrows)!=len(plan['rows']) or planrows.keys()!=invrows.keys():raise ValueError('model plan activities differ from inventory')
  for aid,x in invrows.items():
   r=planrows[aid]
   if x['included'] and (r.get('flow_name')!=x['flow_name'] or r.get('unit')!=x['unit'] or r.get('direction')!=x['direction'] or r.get('amount_per_functional_unit')!=x['amount_per_functional_unit']):raise ValueError('model plan row differs from inventory: '+aid)
   if x['included'] and (r.get('mapping_id')!=x['mapping_id'] or r.get('mapping_type')!=x['mapping_type'] or r.get('mapping_user_asserted')!=x['mapping_user_asserted']):raise ValueError('model plan mapping differs from handoff: '+aid)
   if x['included'] and r.get('status')=='preflight_matches_review_still_required' and (x['issues'] or r.get('issues') or r.get('dataset_amount_per_functional_unit')!=x['dataset_amount_per_functional_unit']):raise ValueError('model plan incorrectly marks mapping as matched: '+aid)
  if plan.get('summary',{}).get('unresolved_rows',0):warnings.append('Model plan contains unresolved exchanges.')
  checks.append('Model plan tied to the supplied inventory, manifest and mapping hashes.')
 else:warnings.append('Read-only mapping preflight not supplied.')
 if 'candidate_record' in data:
  rev=data['candidate_review'];record=data['candidate_record'];raw=paths['candidate_decisions'].read_bytes();reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig'),newline=''))
  if set(reader.fieldnames or [])!=set(DECISION_FIELDS) or len(reader.fieldnames)!=len(set(reader.fieldnames)):raise ValueError('invalid candidate decisions columns')
  decisions=list(reader);bare=load_handoff(paths['inventory'],paths['inventory_manifest'])
  rebuilt,_,_=finalize(rev,decisions,bare,sha(raw),sha(paths['candidate_review'].read_bytes()))
  for key in ('schema_version','review_sha256','decisions_sha256','inventory_sha256','manifest_sha256','records','selected_count','activities_without_selection'):
   if rebuilt[key]!=record.get(key):raise ValueError('candidate record differs from reviewed inputs: '+key)
  if plan:
   for item in rebuilt['records']:
    if item['decision']=='selected':
     p=planrows.get(item['activity_id']) or {};actual=p.get('actual_reference') or {}
     if p.get('status')!='preflight_matches_review_still_required' or actual.get('process_uuid')!=item['process_uuid']:
      raise ValueError('candidate selection does not match verified model plan: '+item['activity_id'])
     observed=next(c['actual_reference'] for row in rev['rows'] if row['activity_id']==item['activity_id'] for c in row['candidates'] if c['actual_reference']['process_uuid']==item['process_uuid'])
     if not candidate_matches_plan(observed,actual):raise ValueError('candidate reference details differ from model plan: '+item['activity_id'])
  warnings.append('Candidate selections are pending independent review; selection is not scientific approval.')
  if rebuilt['activities_without_selection']:warnings.append('Candidate review does not select every included activity: '+', '.join(rebuilt['activities_without_selection']))
  checks.append('Candidate decisions replayed against the original inventory and collected references.')
 else:warnings.append('Candidate review and decisions not supplied.')
 calc=data.get('calculation');coverage=data.get('coverage');plot=data.get('plot_data')
 if calc:
  if service=='h2o2_product' and model['campaign']['campaigns_per_functional_unit'] is None:raise ValueError('H2O2 product amount is unavailable; cannot attach a per-functional-unit calculation')
  if coverage.get('schema_version')!='piezolca.result-coverage/1' or coverage.get('calculation')!=calc:raise ValueError('coverage does not contain the supplied calculation')
  setup=calc.get('setup') or {};amount=setup.get('amount')
  if isinstance(amount,bool) or amount!=1:raise ValueError('calculation must use exactly one declared functional unit')
  target=(calc.get('target') or {}).get('@id');method=(calc.get('impact_method') or {}).get('@id')
  if not target or target!=(setup.get('target') or {}).get('@id') or not method or method!=(setup.get('impactMethod') or {}).get('@id'):
   raise ValueError('calculation target or impact method differs from its setup')
  if not isinstance(calc.get('impacts'),list) or not calc['impacts']:raise ValueError('calculation contains no impact categories')
  ids=set()
  for row in calc['impacts']:
   cat=row.get('category') or {};cid=cat.get('@id');value=row.get('amount')
   if not cid or cid in ids or not cat.get('name') or not cat.get('refUnit') or isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError('invalid calculation category or amount')
   ids.add(cid)
  selected=coverage.get('selected_category') or {};matches=[x for x in calc['impacts'] if x['category']['@id']==selected.get('@id')]
  if len(matches)!=1 or any(selected.get(k)!=matches[0]['category'].get(k) for k in ('name','refUnit')) or coverage.get('hotspots')!=contribution_summary(matches[0]):
   raise ValueError('coverage category or contributions differ from calculation')
  valid_text(calc.get('functional_unit_user_asserted'),'calculation functional unit declaration')
  if not all((calc.get('database') or {}).get(k) for k in ('name','version','system_model')):warnings.append('Database identity, version or system model declaration is incomplete.')
  if not plot:warnings.append('No stage binding supplied: calculation-to-inventory model exchanges have not been independently checked by this bundle.')
  warnings.extend(calc.get('warnings',[]));checks.append('Selected coverage embeds the supplied calculation; database and functional-unit labels remain user asserted.')
 else:warnings.append('openLCA calculation and coverage not supplied.')
 if plot:
  if plot.get('schema_version')!='piezolca.plot-data/1' or plot.get('kind')!='stages':raise ValueError('only versioned stage plot data supported')
  expected=stage_contributions(coverage,plan,data['binding'])
  if any(plot.get(k)!=v for k,v in expected.items()):raise ValueError('stage plot data differs from recomputed coverage and model plan')
  provenance=(plot.get('provenance') or {}).get('inputs') or {}
  for role,key in (('coverage','report'),('model_plan','plan'),('binding','binding')):
   if (provenance.get(key) or {}).get('sha256')!=sha(paths[role].read_bytes()):raise ValueError('stage plot source hash mismatch: '+role)
  verify_plot_files(paths['plot_dir'],plot)
  warnings.extend(plot.get('warnings',[]));checks.append('Stage plot data recomputed from supplied coverage, verified plan and binding; rendering files checked by hash.')
 else:warnings.append('Stage plot not supplied.')
 if 'cycle_plot_data' in data:
  cp=data['cycle_plot_data']
  if cp.get('schema_version')!='piezolca.plot-data/1' or cp.get('kind')!='cycles':raise ValueError('invalid cyclic plot data')
  expected=cycles(fg)
  if any(cp.get(k)!=v for k,v in expected.items()):raise ValueError('cyclic plot data differs from foreground')
  if ((cp.get('provenance') or {}).get('inputs',{}).get('report') or {}).get('sha256')!=fg_hash:raise ValueError('cyclic plot source hash mismatch')
  verify_plot_files(paths['cycle_plot_dir'],cp);warnings.extend(cp.get('warnings',[]))
  checks.append('Cyclic plot data recomputed from supplied foreground; rendering files checked by hash.')
 elif service!='h2o2_product':warnings.append('Cyclic plot not supplied.')
 if 'scenario_comparison' in data:
  if service!='apparent_pollutant_removal':raise ValueError('bound cyclic scenarios require a cyclic foreground')
  from scenario_binding import compare_bound,digest
  base=data['scenario_baseline_bound'];alt=data['scenario_bound'];comparison=data['scenario_comparison'];sp=data['scenario_plot_data']
  if base.get('foreground_sha256')!=fg_hash or base.get('inventory_sha256')!=handoff['inventory_sha256'] or base.get('manifest_sha256')!=handoff['manifest_sha256']:raise ValueError('bound scenario baseline differs from delivery foreground or inventory')
  if handoff['mapping_sha256'] is not None and (base.get('mapping_sha256')!=handoff['mapping_sha256'] or base.get('assignments_sha256')!=handoff['assignments_sha256']):raise ValueError('bound scenario mapping differs from delivery')
  if calc and base['coverage']['calculation']!=calc:raise ValueError('bound baseline calculation differs from delivery calculation')
  rebuilt=compare_bound(base,alt,fg,data['scenario_source'],data['scenario_contexts'])
  if any(comparison.get(k)!=v for k,v in rebuilt.items()):raise ValueError('bound scenario comparison differs from rebuilt records')
  refs={'baseline':'scenario_baseline_bound','scenario':'scenario_bound','baseline-input':'foreground','scenario-input':'scenario_source','contexts':'scenario_contexts'}
  if any((comparison.get('input_sha256') or {}).get(k)!=sha(paths[v].read_bytes()) for k,v in refs.items()):raise ValueError('bound scenario comparison input hash mismatch')
  if sp.get('schema_version')!='piezolca.plot-data/1' or sp.get('kind')!='scenarios':raise ValueError('invalid scenario plot data')
  expected=scenarios(comparison,fg,data['scenario_source'],(sp.get('category') or {}).get('id'))
  if any(sp.get(k)!=v for k,v in expected.items()):raise ValueError('scenario plot differs from bound comparison')
  refs={'report':'scenario_comparison','baseline_input':'foreground','scenario_input':'scenario_source'}
  if any(((sp.get('provenance') or {}).get('inputs',{}).get(k) or {}).get('sha256')!=sha(paths[v].read_bytes()) for k,v in refs.items()):raise ValueError('scenario plot input hash mismatch')
  verify_plot_files(paths['scenario_plot_dir'],sp);warnings.extend(sp.get('warnings',[]));warnings.append('Scenario comparisons use captured models; scientific comparability and omitted background remain subject to review.')
  checks.append('Bound scenario comparison and plot data recomputed; rendered files checked by hash. Neither openLCA nor rendering is rerun.')
 if 'sensitivity_report' in data:
  from sensitivity_report import build as sensitivity_build
  report=data['sensitivity_report'];rebuilt=sensitivity_build(data['sensitivity_spec'])
  if any(report.get(k)!=v for k,v in rebuilt.items()):raise ValueError('sensitivity report differs from source specification')
  scope=report['scope_user_asserted'];fu=scope['functional_unit']
  if scope['system_boundary']!=model['boundary'] or fu['amount']!=model['functional_unit']['value'] or fu['unit']!=model['functional_unit']['unit']:raise ValueError('sensitivity scope or functional unit differs from delivery')
  sp=data['sensitivity_plot_data']
  if sp.get('schema_version')!='piezolca.plot-data/1' or sp.get('kind')!='sensitivity':raise ValueError('invalid sensitivity plot data')
  expected=sensitivity(report,sp.get('route'),(sp.get('category') or {}).get('id'))
  if any(sp.get(k)!=v for k,v in expected.items()):raise ValueError('sensitivity plot differs from rebuilt report')
  if (((sp.get('provenance') or {}).get('inputs') or {}).get('report') or {}).get('sha256')!=sha(paths['sensitivity_report'].read_bytes()):raise ValueError('sensitivity plot input hash mismatch')
  verify_plot_files(paths['sensitivity_plot_dir'],sp);warnings.extend(sp.get('warnings',[]));warnings.append('Sensitivity is a user-supplied additive approximation, not an openLCA recalculation or verified link to this calculation.')
  checks.append('Sensitivity report and plot data rebuilt from supplied additive inputs; rendered files checked by hash, not rerendered. Scientific assumptions remain user asserted.')
 warnings=list(dict.fromkeys(str(x) for x in warnings))
 # Only explicitly supplied inputs are copied, and no database is copied or queried.
 outdir.mkdir(parents=True,exist_ok=False);(outdir/'artifacts').mkdir();items=[]
 for role,p in paths.items():
  if role in ('plot_dir','cycle_plot_dir','scenario_plot_dir','sensitivity_plot_dir'):
   folder={'plot_dir':'figure','cycle_plot_dir':'figure-cycles','scenario_plot_dir':'figure-scenarios','sensitivity_plot_dir':'figure-sensitivity'}[role];dest=outdir/'artifacts'/folder;dest.mkdir()
   for name in ('manifest.json','plot-data.json','table.csv','chart.svg','chart.png'):
    raw=(p/name).read_bytes();(dest/name).write_bytes(raw);items.append({'role':folder+'_'+name,'path':'artifacts/'+folder+'/'+name,'sha256':sha(raw)})
  else:
   ext=p.suffix.lower() or '.dat';name=role+ext;raw=p.read_bytes();(outdir/'artifacts'/name).write_bytes(raw);items.append({'role':role,'path':'artifacts/'+name,'sha256':sha(raw)})
 for sid,p in source_paths.items():
  raw=p.read_bytes();name='evidence-source-'+sid+'.csv';(outdir/'artifacts'/name).write_bytes(raw);items.append({'role':'evidence_source:'+sid,'path':'artifacts/'+name,'sha256':sha(raw)})
 original=spec_raw if spec_raw is not None else json.dumps(spec,ensure_ascii=False,indent=2).encode()
 (outdir/'source-spec.json').write_bytes(original)
 replay=copy.deepcopy(spec);replay['artifacts']={k:('artifacts/'+{'plot_dir':'figure','cycle_plot_dir':'figure-cycles','scenario_plot_dir':'figure-scenarios','sensitivity_plot_dir':'figure-sensitivity'}[k] if k in ('plot_dir','cycle_plot_dir','scenario_plot_dir','sensitivity_plot_dir') else 'artifacts/'+k+(p.suffix.lower() or '.dat')) for k,p in paths.items()}
 replay['evidence_sources']={k:'artifacts/evidence-source-'+k+'.csv' for k in source_paths}
 (outdir/'replay-spec.json').write_text(json.dumps(replay,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 if calc:
  with (outdir/'lcia-results.csv').open('x',encoding='utf-8-sig',newline='') as f:
   w=csv.DictWriter(f,fieldnames=['category_id','category_name','amount','unit','functional_unit_user_asserted','calculation_amount']);w.writeheader()
   for x in calc['impacts']:
    c=x['category'];row={'category_id':c['@id'],'category_name':c['name'],'amount':x['amount'],'unit':c['refUnit'],
                         'functional_unit_user_asserted':calc['functional_unit_user_asserted'],'calculation_amount':calc['setup']['amount']}
    w.writerow({k:("'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v) for k,v in row.items()})
 fu=model['functional_unit']
 if service=='h2o2_product':
  basis={'net_accumulated':'净积累','recovered_product':'回收产品'}[model['product_basis']]
  service_text='H₂O₂ '+basis
  foreground_text='前景按声明的 H₂O₂ 产品量及催化剂分摊计算每功能单位清单；净积累、回收产品、原位消耗与总生成不能自动等同。每功能单位清单不应重复缩放。'
 else:
  service_text='水相表观污染物去除'
  foreground_text='逐循环前景按输入记录计算水相表观去除及每功能单位清单；表观去除不证明矿化。每功能单位清单不应重复缩放。'
 methods=['# 研究方法与结果说明（待研究者审核）','', '## 研究范围','', '研究标题：'+title,'', '功能单位：'+str(fu.get('value','未提供'))+' '+str(fu.get('unit',''))+' '+service_text+'（来源：'+str(fu.get('source','未提供'))+'；证据类别：'+str(fu.get('evidence_class','未提供'))+'）','', '系统边界：'+model['boundary'], '',
  '## 前景与数据','', foreground_text,
  '证据、代理和未链接项以交付文件及审查记录为准。','']
 if service=='h2o2_product':
  methods+=['产品定义（用户声明）：'+model['product_definition'], '催化剂去向：'+model['campaign']['catalyst_destination']+'；产品测量、外加量修正及催化剂处置均须研究者核实。','']
 if 'cycle_service_report' in data:
  sr=data['cycle_service_report'];methods+=['## 逐循环服务条件（待复核）','', '服务类型：'+str(sr['service']['kind'])+'；阈值、样品和寿命为用户声明，数值检查不构成法规达标或服务等价证明。']
  methods+=['- 循环 '+str(row['cycle_id'])+'：'+row['criterion_status']+'；样品关联声明完整：'+str(row['sample_links_complete_user_asserted']) for row in sr['cycles']]
  methods+=['','清单仍按表观去除功能单位生成，不自动转换为处理水量功能单位。','']
 if data.get('evidence_report'):
  counts=data['evidence_report'].get('coverage') or {}
  methods+=['数值证据链接：'+str(counts.get('linked_count','未知'))+'/'+str(counts.get('quantity_count','未知'))+'；来源记录、计算依赖和缺口见 artifacts/evidence_report.json。','']
 if 'scenario_comparison' in data:methods+=['## 情景比较','','情景图与记录基于已捕获的 openLCA 计算及绑定；每个功能和背景声明、未连接项与代理需独立复核，不自动排名。','']
 if 'sensitivity_report' in data:methods+=['## 单因素敏感性','','此图基于用户提供的加和近似，不是 openLCA 重新计算；输入、范围和适用性需复核。','']
 if data.get('domain_protocol'):
  protocol=data['domain_protocol']
  methods+=['## 实验边界声明','']
  for key,label in (('reactor_configuration','反应器'),('mechanical_coupling','机械耦合'),('pollutant_identity','污染物'),('ultrasound','超声能耗'),('auxiliary_energy','辅助能耗'),('illumination','光照'),('external_oxidant','外加氧化剂'),('ph_adjustment','pH 调节'),('catalyst_destination','催化剂去向'),('byproducts_and_toxicity','副产物与毒性'),('mineralization','矿化声明')):
   methods.append('- '+label+'：'+declaration(protocol.get(key)))
  methods+=['','以上是提供的实验边界声明，是否符合原始记录和实际实验需独立确认。','']
 if handoff.get('mapping_sha256'):
  methods+=['## 数据集映射','', '各活动的数据集、地域、参考产品、代理理由及未决项见 artifacts/mapping.csv 与相关候选审查记录；映射声明不等于实际供应方连接或工艺适用性证明。','']
 if calc:
  db=calc.get('database') or {};software=calc.get('software') or {};method=calc.get('impact_method') or {};target=calc.get('target') or {}
  methods+=['## 背景与计算','', '数据库声明：'+str(db.get('name','未提供'))+'；版本：'+str(db.get('version','未提供'))+'；系统模型：'+str(db.get('system_model','未提供')),
   '软件声明：'+str(software.get('name','未提供'))+' '+str(software.get('version_user_asserted','未提供')),
   '影响方法：'+str(method.get('name','未提供'))+'（ID：'+str(method.get('@id','未提供'))+'）',
   '产品系统：'+str(target.get('name','未提供'))+'（ID：'+str(target.get('@id','未提供'))+'）；计算量：一个声明功能单位。',
   '计算结果功能单位（用户声明）：'+calc['functional_unit_user_asserted']+'。',
   '数据库身份及模型与实验的等价性需要独立确认。','']
 elif 'scenario_comparison' in data:methods+=['## 背景与计算','','未单独提供主模型计算表；已捕获的情景计算结果见相关记录，仍须独立核对。','']
 else:methods+=['## 背景与计算','','未提供可核对的计算结果；不报告影响结果。','']
 methods+=['## 缺口与解释','']+['- '+x for x in warnings]+['','不得由本报告自动推断方案排名、矿化程度或未提供的不确定性。','', '许可说明：'+license_note,'']
 (outdir/'methods.md').write_text('\n'.join(methods),encoding='utf-8')
 readme=['# '+title,'','本地科研交付：清单、审查、计算与图表按提供的文件整理。','',
  '查看 `methods.md`、`delivery-manifest.json` 和 `artifacts/`。图表存在时分别位于 `figure/`、`figure-cycles/`、`figure-scenarios/`、`figure-sensitivity/`。',
  '原始 CSV 仅在明确提供时复制；原始 Excel/PDF 和数据库不会自动复制。source-spec.json 可能含原本机路径，分享前须检查。',
  'Agent 可用 `scripts/research_delivery.py verify <本目录>` 检查文件摘要，并使用 `replay-spec.json` 重新整理到新的目录；这不会重新运行 openLCA，验证不证明测量真实或结果科学适用。',
  '本交付可能包含商业数据库衍生信息，仅按许可使用；不要在未经审查时对外分享。','']
 (outdir/'README.md').write_text('\n'.join(readme),encoding='utf-8')
 for name in ('methods.md','README.md','source-spec.json','replay-spec.json')+ (('lcia-results.csv',) if calc else ()):
  items.append({'role':'generated_'+name,'path':name,'sha256':sha((outdir/name).read_bytes())})
 manifest={'schema_version':SCHEMA,'title':title,'status':'review_required' if warnings else 'checks_passed_review_still_required','license_note':license_note,
           'functional_unit':model['functional_unit'],'functional_unit_type':service,'product_basis':model.get('product_basis'),'product_definition':model.get('product_definition'),'calculation_functional_unit_user_asserted':calc.get('functional_unit_user_asserted') if calc else None,
           'boundary':model['boundary'],'checks':checks,'warnings':warnings,'files':items,'python_version':sys.version.split()[0],
           'generator_sha256':{n:sha(Path(__file__).with_name(n).read_bytes()) for n in ('research_delivery.py','cyclic_foreground.py','h2o2_foreground.py','experimental_foreground.py','audit_and_scale_inventory.py','inventory_handoff.py','mapping_review.py','mapping_coverage.py','openlca_readonly.py','result_coverage.py','plot_data.py','evidence_chain.py','piezocatalysis_checks.py','cycle_service_review.py','scenario_binding.py','sensitivity_report.py')}}
 (outdir/'delivery-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
 return manifest

def verify(directory):
 manifest=json_read(directory/'delivery-manifest.json')
 if manifest.get('schema_version')!=SCHEMA or not isinstance(manifest.get('files'),list):raise ValueError('unsupported delivery manifest')
 required={'foreground','inventory','inventory_manifest','generated_methods.md','generated_README.md','generated_source-spec.json','generated_replay-spec.json'}
 roles=[item.get('role') for item in manifest['files'] if isinstance(item,dict)]
 if len(roles)!=len(manifest['files']) or len(roles)!=len(set(roles)) or not required.issubset(roles):raise ValueError('delivery manifest has missing or duplicate artifact roles')
 seen=set()
 for item in manifest['files']:
  rel=item.get('path');path=Path(rel) if isinstance(rel,str) else None
  if path is None or path.is_absolute() or '..' in path.parts or rel in seen:raise ValueError('invalid or duplicate delivery path')
  seen.add(rel);p=(directory/path).resolve()
  if not p.is_relative_to(directory.resolve()) or not p.is_file() or sha(p.read_bytes())!=item.get('sha256'):raise ValueError('delivery file missing or changed: '+rel)
 return {'verified_files':len(seen),'status':'hashes_match','note':'Hash consistency is not a digital signature or proof of scientific validity.'}

def main():
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
 a=sub.add_parser('assemble');a.add_argument('spec',type=Path);a.add_argument('--output-dir',type=Path,required=True)
 v=sub.add_parser('verify');v.add_argument('directory',type=Path);args=p.parse_args()
 try:
  if args.command=='assemble':
   raw=args.spec.read_bytes();spec=json.loads(raw,parse_constant=lambda v: (_ for _ in ()).throw(ValueError('invalid JSON number '+v)))
   report=assemble(spec,args.spec.resolve().parent,args.output_dir,raw);print(json.dumps({'output':str(args.output_dir),'status':report['status'],'warnings':len(report['warnings'])},ensure_ascii=False))
  else:print(json.dumps(verify(args.directory),ensure_ascii=False))
  return 0
 except (OSError,UnicodeError,ValueError,KeyError,TypeError,OverflowError,csv.Error) as exc:print('ERROR:',exc,file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
