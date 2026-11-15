#!/usr/bin/env python3
"""Read-only preflight of reviewed cycle inventory mappings for an existing openLCA database."""
import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import sys

from inventory_handoff import load_handoff, sha
from openlca_readonly import Client, IPCError, descriptors
from mapping_coverage import read_entity


def preflight(handoff, client, database_name):
    if not isinstance(handoff, dict) or handoff.get('schema_version') != 'piezolca.handoff/1':
        raise ValueError('unsupported handoff report')
    available = {x.get('@id'):x for x in descriptors(client, 'Process')}
    cache = {}; rows = []
    for row in handoff['rows']:
        if not row['included']:
            rows.append({'activity_id':row['activity_id'],'status':'excluded','note':row['note']});continue
        issues = list(row['issues']); m = row.get('mapping_user_asserted'); actual = None
        if not isinstance(m,dict):
            issues.append('mapping_unavailable')
        elif not issues:
            uid = m['process_uuid']
            if m['database'] != database_name:
                issues.append('database_name_mismatch')
            elif uid not in available:
                issues.append('process_uuid_not_found')
            else:
                if uid not in cache: cache[uid] = read_entity(client, 'Process', uid)
                process = cache[uid]
                if process is None:
                    issues.append('process_not_found')
                else:
                    refs = [e for e in process.get('exchanges', []) if e.get('isQuantitativeReference') is True]
                    if len(refs) != 1:
                        issues.append('reference_exchange_invalid')
                    else:
                        e=refs[0];d=available[uid]
                        actual={'process_uuid':uid,'name':process.get('name'),'process_version':process.get('version'),
                                'process_type':process.get('processType'),'geography':d.get('location'),
                                'reference_flow_uuid':(e.get('flow') or {}).get('@id'),
                                'reference_product':(e.get('flow') or {}).get('name'),
                                'flow_property_uuid':(e.get('flowProperty') or {}).get('@id'),
                                'unit_uuid':(e.get('unit') or {}).get('@id'),
                                'unit_name':(e.get('unit') or {}).get('name'),'reference_is_input':e.get('isInput')}
                        for key,field in [('dataset_name','name'),('geography','geography'),('reference_flow_uuid','reference_flow_uuid'),
                                          ('reference_product','reference_product'),('flow_property_uuid','flow_property_uuid'),
                                          ('unit_uuid','unit_uuid'),('dataset_unit','unit_name')]:
                            if m.get(key) != actual[field]: issues.append(key+'_database_mismatch')
                        if m.get('process_version') and m['process_version'] != actual['process_version']:
                            issues.append('process_version_database_mismatch')
                        expected_input=m.get('reference_is_input','').lower() in ('true','1','yes')
                        if not isinstance(actual['reference_is_input'],bool) or expected_input != actual['reference_is_input']:
                            issues.append('reference_direction_database_mismatch')
        rows.append({'activity_id':row['activity_id'],'stage':row['stage'],'cycle_id':row['cycle_id'],
                     'flow_name':row['flow_name'],'direction':row['direction'],'amount_per_functional_unit':row['amount_per_functional_unit'],
                     'unit':row['unit'],'mapping_id':row['mapping_id'],'mapping_type':row['mapping_type'],
                     'dataset_amount_per_functional_unit':row['dataset_amount_per_functional_unit'] if not issues else None,
                     'mapping_user_asserted':m,'actual_reference':actual,'issues':issues,
                     'status':'unresolved' if issues else 'preflight_matches_review_still_required'})
    included=[x for x in rows if x['status']!='excluded'];unresolved=[x for x in included if x['status']=='unresolved']
    return {'report_type':'cycle_model_plan','schema_version':'piezolca.cycle-model-plan/1',
            'system':handoff['system'],'boundary':handoff['boundary'],'functional_unit':handoff['functional_unit'],
            'functional_unit_type':handoff.get('functional_unit_type'),'product_basis':handoff.get('product_basis'),
            'product_definition':handoff.get('product_definition'),
            'amount_basis':handoff['amount_basis'],'database_name_user_asserted':database_name,
            'inventory_sha256':handoff['inventory_sha256'],'manifest_sha256':handoff['manifest_sha256'],
            'mapping_sha256':handoff['mapping_sha256'],'assignments_sha256':handoff['assignments_sha256'],
            'handoff_code_sha256':handoff['handoff_code_sha256'],'plan_code_sha256':sha(Path(__file__)),
            'model_warnings':handoff['model_warnings'],'campaign':handoff['campaign'],'rows':rows,
            'summary':{'included_rows':len(included),'matched_rows':len(included)-len(unresolved),
                       'unresolved_rows':len(unresolved),'status':'partial' if unresolved or handoff['model_warnings'] else 'declarations_match_review_required'},
            'note':'Read-only preflight; does not create or modify product systems. Database version, proxies and scientific suitability require review. Unresolved and uncharacterized items are not zero.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inventory',required=True,type=Path);p.add_argument('--manifest',type=Path)
    p.add_argument('--mapping',required=True,type=Path);p.add_argument('--assignments',required=True,type=Path)
    conn=p.add_mutually_exclusive_group(required=True);conn.add_argument('--port',type=int);conn.add_argument('--start-local',action='store_true')
    p.add_argument('--workspace',type=Path);p.add_argument('--database',required=True);p.add_argument('--openlca-app',type=Path,default=Path('/Applications/openLCA.app'))
    a=p.parse_args()
    if a.start_local != (a.workspace is not None):p.error('--workspace is required only with --start-local')
    try:
        handoff=load_handoff(a.inventory,a.manifest or a.inventory.with_name(a.inventory.name+'.manifest.json'),a.mapping,a.assignments)
        with ExitStack() as stack:
            if a.start_local:
                from openlca_local_launch import launch
                port=stack.enter_context(launch(a.openlca_app,a.workspace,a.database))
            else:port=a.port
            result=preflight(handoff,Client(port,timeout=120),a.database)
        print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False));return 0
    except (OSError,UnicodeError,ValueError,TypeError,KeyError,OverflowError,IPCError) as e:
        print('ERROR:',e,file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
