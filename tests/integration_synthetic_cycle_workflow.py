"""Real openLCA integration: cycle input -> inventory -> mapping -> model -> scenarios -> checks.

Creates only a temporary fictional database. Characterization factors are deliberately
arbitrary test coefficients; this is an integration test, not a research LCA.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1];SKILL=ROOT/'piezocatalysis-lca-modeling';SCRIPTS=SKILL/'scripts'
sys.path.insert(0,str(SCRIPTS))
from cyclic_foreground import build
from inventory_handoff import load_handoff
from audit_and_scale_inventory import audit as legacy_audit
from integration_openlca_guard import fingerprint
from mapping_coverage import audit
from openlca_local_launch import launch
from openlca_readonly import Client
from parameter_sensitivity import run
from scenario_comparability import assess as assess_comparability, FIELDS
from synthetic_joint_uncertainty import run as sample_joint
from uncertainty_readiness import assess as assess_readiness


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',choices=('constant','variable-exact'),default='constant');case_name=parser.parse_args().case
    app=Path('/Applications/openLCA.app');java=app/'Contents/Eclipse/jre/Contents/Home/bin/java';libs=app/'Contents/Eclipse/plugins/olca-app_2.7.0/libs'
    with tempfile.TemporaryDirectory(prefix='piezolca-cycle-e2e-') as tmp:
        folder=Path(tmp);workspace=folder/'workspace';db=workspace/'databases/synthetic_cycle';inventory=folder/'inventory.csv'
        case=SKILL/'assets/examples/synthetic-cycles'/f'{case_name}.json'; source=json.loads(case.read_text());foreground=build(source)
        assert foreground['campaign']['campaigns_per_functional_unit']==(5 if case_name=='constant' else 2)
        proc=subprocess.run([sys.executable,str(SCRIPTS/'cyclic_foreground.py'),str(case),'--inventory-csv',str(inventory)],capture_output=True,text=True,timeout=30)
        if proc.returncode:raise RuntimeError(proc.stderr)
        validation=subprocess.run([sys.executable,str(SCRIPTS/'validate_inventory.py'),str(inventory)],capture_output=True,text=True)
        if validation.returncode:raise RuntimeError(validation.stdout+validation.stderr)
        handoff=load_handoff(inventory,inventory.with_name(inventory.name+'.manifest.json'))
        assert handoff['amount_basis']=='per_functional_unit' and handoff['summary']['status']=='needs_review'
        try:
            legacy_audit(inventory,folder/'unused_mapping.csv',folder/'unused_parameters.json',source['system'],'dry catalyst')
            raise AssertionError('already scaled inventory was accepted for a second scaling')
        except ValueError as exc:
            assert 'already scaled per functional unit' in str(exc)
        p=subprocess.run([str(java),'-Xmx1024M','-cp',str(libs/'*'),'org.python.util.jython',str(ROOT/'tests/fixtures/create_cycle_workflow.py'),str(db),str(inventory)],capture_output=True,text=True,timeout=90)
        if p.returncode:raise RuntimeError('fixture creation failed: '+p.stderr[-1500:])
        ids=json.loads(next(x[len('RESULT_JSON='):] for x in p.stdout.splitlines() if x.startswith('RESULT_JSON=')))
        before=fingerprint(db)
        with launch(app,workspace,'synthetic_cycle') as port:
            c=Client(port,timeout=120)
            process=c.call('data/get',{'@type':'Process','@id':ids['provider']});ref=next(e for e in process['exchanges'] if e.get('isQuantitativeReference'))
            method=c.call('data/get',{'@type':'ImpactMethod','@id':ids['method']});cat=c.call('data/get',{'@type':'ImpactCategory','@id':ids['category']});factor=cat['impactFactors'][0]
            consumer=c.call('data/get',{'@type':'Process','@id':ids['process']})
            exchange=next(e for e in consumer['exchanges'] if e.get('isInput') and e.get('flow',{}).get('@id')==ref['flow']['@id'])
            req={'database':{'name':'synthetic_cycle'},'process':{'process_uuid':process['@id'],'name':process['name'],'process_version':process.get('version'),
                'reference_flow_uuid':ref['flow']['@id'],'reference_product':ref['flow']['name'],'flow_property_uuid':ref['flowProperty']['@id'],
                'unit_uuid':ref['unit']['@id'],'reference_is_input':False,'foreground_unit':'kWh','conversion_factor':1},
                'method':{'method_uuid':method['@id'],'method_name':method['name'],'method_version':method.get('version'),
                'categories':[{'category_uuid':cat['@id'],'category_name':cat['name'],'category_version':cat.get('version'),
                'flows':[{'flow_uuid':factor['flow']['@id'],'flow_property_uuid':factor['flowProperty']['@id'],'unit_uuid':factor['unit']['@id']}]}]},
                'link':{'system_uuid':ids['system'],'consumer_uuid':ids['process'],'flow_uuid':ref['flow']['@id'],
                        'exchange_internal_id':exchange['internalId'],'is_input':True}}
            mapping=audit(c,req)
            assert mapping['process']['actual_reference']['reference_flow_uuid']==ref['flow']['@id']
            assert mapping['method']['categories'][0]['flows'][0]['status']=='factor_present'
            assert mapping['link']['status']=='linked_to_selected_provider'
            model={'system_id':ids['system'],'method_id':ids['method'],'unit_id':ids['unit'],'flow_property_id':ids['property'],'amount':1}
            context={'software_version':'2.7.0','database_label':'synthetic_cycle','database_version':'synthetic','system_model':'synthetic',
                'functional_unit':f"{source['treatment_target']['value']} mg synthetic apparent removal",'unit_label':'service','system_boundary':'fictional functional-unit inventory',
                'mapping_notes':'fictional supply and elementary waste factors','lcia_method_label':'synthetic cycle method','lcia_version':'synthetic'}
            scenario={'id':'double_ultrasound','name':'ultrasound_scale','context_id':ids['process'],'value':2,'unit':'factor',
                      'minimum':0,'source':'fictional scenario','evidence_class':'scenario'}
            report=run(c,{'model':model,'context':context,'scenarios':[scenario]},'synthetic-input',{'mode':'guarded clone'})
            baseline=report['baseline']['impacts'][0]['amount'];alternative=report['cases'][0]['calculation']['impacts'][0]['amount']
            assert abs(baseline-ids['expected_baseline'])<1e-8,(baseline,ids)
            assert abs(alternative-baseline-ids['expected_power_delta'])<1e-8,(baseline,alternative,ids)
        assert fingerprint(db)==before
        declaration={k:'synthetic same' for k in FIELDS};declaration['lcia_method_uuid']=ids['method']
        assert assess_comparability({'cases':[dict(declaration,id='baseline'),dict(declaration,id='scenario')]})['ranking_permitted_by_context_check']
        different=dict(declaration,id='different');different['functional_unit']='different service'
        assert not assess_comparability({'cases':[dict(declaration,id='baseline'),different]})['ranking_permitted_by_context_check']
        readiness=json.loads((SKILL/'assets/examples/synthetic-uncertainty/readiness-demo.json').read_text());assert not assess_readiness(readiness)['issues']
        demo=json.loads((SKILL/'assets/examples/synthetic-uncertainty/joint-demo.json').read_text());assert sample_joint(demo)==sample_joint(demo)
        print('PASS: '+case_name+' cyclic foreground -> validated CSV -> synthetic providers/LCIA -> mapping -> openLCA baseline and parameter recalculation')
        print('PASS: synthetic expected baseline='+str(baseline)+'; doubling ultrasound delta='+str(alternative-baseline)+'; links='+str(ids['links']))
        print('PASS: comparability, uncertainty readiness, seeded joint example and source synthetic DB unchanged')

if __name__=='__main__':main()
