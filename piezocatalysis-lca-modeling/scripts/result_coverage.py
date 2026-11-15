#!/usr/bin/env python3
"""Interpret an openLCA calculation and inspect selected system links and LCIA factors (read-only)."""
import argparse
from contextlib import ExitStack
import hashlib
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace

from mapping_coverage import ident, read_entity
from openlca_readonly import Client, IPCError, calculate, numeric, positive, valid_uuid


def contribution_summary(impact):
    total = numeric(impact['amount'], 'impact total')
    contributions = impact['contributions']
    values = [numeric(c['amount'], 'contribution') for c in contributions]
    magnitude = math.fsum(abs(v) for v in values)
    has_positive = any(v > 0 for v in values)
    has_negative = any(v < 0 for v in values)
    cancelled = has_positive and has_negative
    reconciles = bool(contributions) and math.isclose(math.fsum(values), total, rel_tol=1e-6, abs_tol=1e-15)
    usable = reconciles and not cancelled and abs(total) > max(1e-15, magnitude * 1e-9)
    rows = []
    for c, value in zip(contributions, values):
        rows.append({'tech_flow':c['techFlow'], 'amount':value,
                     'share_percent':100.0 * value / total if usable else None})
    rows.sort(key=lambda x: abs(x['amount']), reverse=True)
    return {'total':total, 'absolute_contribution_sum':magnitude,
            'has_positive_and_negative':cancelled, 'contribution_sum_matches_total':reconciles, 'shares_available':usable,
            'shares_reason': 'same_sign_nonzero_total' if usable else 'empty_near_zero_offsetting_or_unreconciled_contributions',
            'contributions_by_absolute_amount':rows,
            'reconciliation':impact.get('reconciliation')}


def link_review(system, processes):
    if not isinstance(system.get('processLinks'), list) or not isinstance(system.get('processes'), list):
        raise IPCError('product system has no process list or process links')
    links = system['processLinks']; indexed = {}
    for link in links:
        key=(ident(link.get('process')), (link.get('exchange') or {}).get('internalId'))
        indexed.setdefault(key, []).append(link)
    rows=[]
    for ref in system['processes']:
        pid=ident(ref); process=processes.get(pid)
        if process is None: raise IPCError('process missing from link review: '+str(pid))
        exchanges=process.get('exchanges')
        if not isinstance(exchanges,list): raise IPCError('process exchanges unavailable: '+str(pid))
        for e in exchanges:
            flow=e.get('flow') or {}; flow_type=flow.get('flowType')
            if flow_type not in ('PRODUCT_FLOW','WASTE_FLOW') or e.get('isQuantitativeReference') is True: continue
            match=indexed.get((pid,e.get('internalId')),[])
            rows.append({'process':ref, 'exchange_internal_id':e.get('internalId'), 'flow':flow,
                         'is_input':e.get('isInput'), 'amount':e.get('amount'), 'unit':e.get('unit'),
                         'links':match, 'status':'unlinked_candidate' if not match else 'linked' if len(match)==1 and ident(match[0].get('flow'))==ident(flow) else 'link_requires_review'})
    return {'system_link_count':len(links),'process_count':len(processes),'technical_exchanges':rows,
            'scope':'Non-reference product/waste exchanges in listed system processes; linked means one matching link record only, not provider/reference compatibility. Unlinked candidates include intended co-products or cutoffs; review their role.'}


def factors_for_selected(category, flow_ids):
    factors=category.get('impactFactors')
    if not isinstance(factors,list): raise IPCError('selected category factor data unavailable')
    result=[]
    for fid in flow_ids:
        matches=[f for f in factors if ident(f.get('flow'))==fid]
        if not matches: status='no_factor_for_flow_uuid'
        elif len(matches)>1: status='multiple_factors_review_required'
        elif matches[0].get('formula'): status='formula_requires_evaluation'
        else:
            value=matches[0].get('value')
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value): status='factor_value_unavailable'
            elif value==0: status='explicit_zero_factor'
            else: status='factor_value_present'
        result.append({'flow_uuid':fid,'status':status,'matching_factors':matches,
                       'scope':'Flow UUID only; compartment, geography, direction, property, unit and applicability require review.'})
    return result


def analyze(report,system,processes,category,flow_ids):
    if ident(system)!=ident(report.get('target')): raise IPCError('calculation and system identity differ')
    cid=ident(category)
    matches=[x for x in report['impacts'] if ident(x.get('category'))==cid]
    if len(matches)!=1: raise IPCError('selected category not uniquely present in calculated method')
    inventory=report.get('total_flows')
    if not isinstance(inventory,list):raise IPCError('calculation has no total inventory')
    counts={}
    for entry in inventory:
        f=(entry.get('enviFlow') or {}).get('flow') or {}
        kind=f.get('flowType') or 'UNKNOWN';counts[kind]=counts.get(kind,0)+1
    return {'schema_version':'piezolca.result-coverage/1','calculation':report,
            'link_review':link_review(system,processes),
            'inventory':{'counts_by_flow_type':counts,'rows':inventory,
                         'scope':'Intervention flow totals can include unconnected product and waste flows; they are not all elementary emissions.'},
            'selected_category':matches[0]['category'],
            'hotspots':contribution_summary(matches[0]),
            'selected_factor_checks':[{**r, 'inventory_occurrences':[v for v in inventory if ident((v.get('enviFlow') or {}).get('flow')) == r['flow_uuid']]} for r in factors_for_selected(category,flow_ids)],
            'scope':'Factor checks cover only requested flow UUIDs and one selected category; no factor is not proof of no impact. Zero results do not prove completeness.'}


def redacted_summary(report):
    rows = report['link_review']['technical_exchanges']
    return {'schema_version': 'piezolca.result-coverage-summary/1',
            'functional_unit_user_asserted': report['calculation']['functional_unit_user_asserted'],
            'inventory_counts_by_flow_type': report['inventory']['counts_by_flow_type'],
            'system_link_count': report['link_review']['system_link_count'],
            'unlinked_exchange_candidates': sum(r['status'] == 'unlinked_candidate' for r in rows),
            'links_requiring_review': sum(r['status'] == 'link_requires_review' for r in rows),
            'selected_category': report['selected_category'].get('name'),
            'category_unit': report['selected_category'].get('refUnit'),
            'total': report['hotspots']['total'],
            'has_offsetting_contributions': report['hotspots']['has_positive_and_negative'],
            'factor_statuses': [r['status'] for r in report['selected_factor_checks']],
            'warning': 'Process and flow names omitted; data and results may still be subject to license restrictions.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    c=p.add_mutually_exclusive_group(required=True);c.add_argument('--port',type=int);c.add_argument('--start-local',action='store_true')
    p.add_argument('--workspace',type=Path);p.add_argument('--database',required=True);p.add_argument('--openlca-app',type=Path,default=Path('/Applications/openLCA.app'))
    for key in ('system-id','method-id','unit-id','flow-property-id','category-id'):p.add_argument('--'+key,type=valid_uuid,required=True)
    p.add_argument('--flow-id',type=valid_uuid,action='append',required=True,help='selected elementary flow UUID; repeat as needed')
    p.add_argument('--amount',type=positive,required=True);p.add_argument('--functional-unit',required=True)
    p.add_argument('--summary-output',type=Path,help='new path for reduced summary; license restrictions may still apply')
    p.add_argument('--database-version',required=True);p.add_argument('--system-model',required=True);p.add_argument('--software-version',default='2.7.0');p.add_argument('--unit-label',required=True)
    args=p.parse_args()
    if args.start_local != (args.workspace is not None):p.error('--workspace is required only with --start-local')
    try:
        with ExitStack() as stack:
            if args.start_local:
                from openlca_local_launch import launch
                port=stack.enter_context(launch(args.openlca_app,args.workspace,args.database))
            else:port=args.port
            client=Client(port,timeout=120)
            setup=SimpleNamespace(system_id=args.system_id,method_id=args.method_id,unit_id=args.unit_id,
                  flow_property_id=args.flow_property_id,amount=args.amount,wait_seconds=120,
                  software_version=args.software_version,database_label=args.database,database_version=args.database_version,
                  system_model=args.system_model,functional_unit=args.functional_unit,unit_label=args.unit_label,include_total_flows=True)
            calc=calculate(client,setup)
            system=read_entity(client,'ProductSystem',args.system_id)
            if system is None:raise IPCError('product system not found')
            procs={ident(r):read_entity(client,'Process',ident(r)) for r in system.get('processes',[])}
            cat=read_entity(client,'ImpactCategory',args.category_id)
            if cat is None:raise IPCError('impact category not found')
            result=analyze(calc,system,procs,cat,args.flow_id)
        result['code_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        if args.summary_output:
            with args.summary_output.open('x',encoding='utf-8') as f:
                json.dump(redacted_summary(result),f,ensure_ascii=False,indent=2,allow_nan=False)
        print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False));return 0
    except (OSError,ValueError,TypeError,KeyError,IPCError) as exc:
        print('ERROR:',exc,file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
