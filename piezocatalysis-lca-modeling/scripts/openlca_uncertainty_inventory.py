#!/usr/bin/env python3
"""Read uncertainty fields of a selected product system and impact category."""
import argparse
from contextlib import ExitStack
import hashlib,json,sys
from pathlib import Path
from mapping_coverage import ident,read_entity
from openlca_readonly import Client, IPCError, valid_uuid


def count_uncertainty(items):
    return {'count':len(items),'uncertainty_nonempty_count':sum(bool(x.get('uncertainty')) for x in items),
            'scope':'Nonempty uncertainty field in IPC response; absent does not mean zero uncertainty.'}


def inspect(client,system_id,category_id):
    system=read_entity(client,'ProductSystem',system_id);cat=read_entity(client,'ImpactCategory',category_id)
    if system is None or cat is None:raise IPCError('selected system or category not found')
    if not isinstance(system.get('processes'),list) or not isinstance(cat.get('impactFactors'),list):raise IPCError('process list or factor data unavailable')
    processes=[]
    for ref in system['processes']:
        p=read_entity(client,'Process',ident(ref))
        if p is None or not isinstance(p.get('exchanges'),list):raise IPCError('process exchanges unavailable')
        exchanges=[x for x in p['exchanges'] if x.get('isQuantitativeReference') is not True]
        params=p.get('parameters') or []
        if not isinstance(params,list):raise IPCError('invalid process parameters')
        processes.append({'process':ref,'process_type':p.get('processType'),
                          'exchanges':count_uncertainty(exchanges),'parameters':count_uncertainty(params)})
    return {'schema_version':'piezolca.openlca-uncertainty-inventory/1','system':system_id,'category':category_id,
            'processes':processes,'selected_category_factors':count_uncertainty(cat['impactFactors']),
            'note':'Only selected system processes and one impact category; IPC fields may not represent all uncertainty or other available datasets. No distributions are inferred.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True);g.add_argument('--port',type=int);g.add_argument('--start-local',action='store_true')
    p.add_argument('--workspace',type=Path);p.add_argument('--database',required=True);p.add_argument('--openlca-app',type=Path,default=Path('/Applications/openLCA.app'))
    p.add_argument('--system-id',type=valid_uuid,required=True);p.add_argument('--category-id',type=valid_uuid,required=True);a=p.parse_args()
    if a.start_local != (a.workspace is not None):p.error('--workspace required only with --start-local')
    try:
        with ExitStack() as stack:
            if a.start_local:
                from openlca_local_launch import launch
                port=stack.enter_context(launch(a.openlca_app,a.workspace,a.database))
            else:port=a.port
            report=inspect(Client(port,120),a.system_id,a.category_id)
        report['database_user_asserted']=a.database;report['code_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        print(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False));return 0
    except (OSError,ValueError,TypeError,KeyError,IPCError) as e:
        print('ERROR:',e,file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
