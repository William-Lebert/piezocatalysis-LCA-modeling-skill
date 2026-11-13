"""Optional real-engine parameter regression on a temporary synthetic database."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'piezocatalysis-lca-modeling/scripts'
sys.path.insert(0,str(SCRIPTS))
from openlca_local_launch import launch, copy_runtime_bundle, LaunchError
from openlca_readonly import Client
from parameter_sensitivity import run, redacted_summary
from sensitivity_report import build as additive_report
from integration_openlca_guard import fingerprint, rpc


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--openlca-app',type=Path,default=Path('/Applications/openLCA.app'))
    args=parser.parse_args(); app=args.openlca_app
    java=app/'Contents/Eclipse/jre/Contents/Home/bin/java'
    libs=app/'Contents/Eclipse/plugins/olca-app_2.7.0/libs'
    with tempfile.TemporaryDirectory(prefix='piezolca-param-integration-') as temp:
        workspace=Path(temp)/'workspace'; db=workspace/'databases/synthetic_params'
        p=subprocess.run([str(java),'-Xmx1024M','-cp',str(libs/'*'),'org.python.util.jython',
                          str(ROOT/'tests/fixtures/create_openlca_parameterized.py'),str(db)],capture_output=True,text=True,timeout=90)
        if p.returncode: raise RuntimeError('fixture failed: '+p.stderr[-1000:])
        ids=dict(line.split('=',1) for line in p.stdout.splitlines() if line.startswith(('SYSTEM=','PROCESS=','METHOD=','UNIT=','PROPERTY=')))
        before=fingerprint(db)
        model=dict(system_id=ids['SYSTEM'],method_id=ids['METHOD'],unit_id=ids['UNIT'],flow_property_id=ids['PROPERTY'],amount=1)
        context=dict(software_version='2.7.0',database_label='synthetic_params',database_version='synthetic',
            system_model='synthetic',functional_unit='1 kg synthetic service',unit_label='kg',system_boundary='synthetic',
            mapping_notes='synthetic only',lcia_method_label='synthetic method',lcia_version='synthetic')
        scenarios=[dict(id=key,name=key,context_id=ids['PROCESS'],value=value,unit=unit,minimum=minimum,
                        source='synthetic',evidence_class='scenario') for key,value,unit,minimum in
                        [('power',4,'kW',0),('hours',2,'h',0),('reuse',4,'uses',1)]]
        spec=dict(model=model,context=context,scenarios=scenarios)
        with launch(app,workspace,'synthetic_params') as port:
            c=Client(port,timeout=30)
            params=c.call('data/get/parameters',{'@type':'ProductSystem','@id':ids['SYSTEM']})
            assert {p['name'] for p in params}=={'power','hours','reuse'}
            assert rpc(port,'data/put',{'@type':'Flow','name':'denied'})['error']['code']==-32601
            one=run(c,spec,'synthetic-input',{'mode':'guarded_temporary_clone'})
            two=run(c,spec,'synthetic-input',{'mode':'guarded_temporary_clone'})
            def values(report):return [report['baseline']['impacts'][0]['amount']]+[x['calculation']['impacts'][0]['amount'] for x in report['cases']]
            v=values(one)
            assert all(abs(a-b)<1e-10 for a,b in zip(v,[4.8,8.0,8.0,4.0])),v
            assert v==values(two)
            assert redacted_summary(one)['scenario_count']==3
            source=json.loads((ROOT/'piezocatalysis-lca-modeling/assets/examples/synthetic-sensitivity/scenarios.json').read_text())
            routes=[]
            for name in ('A','B'):
                r=copy.deepcopy(source['routes'][0]); r['id']=name
                r['impact_categories']={'synthetic':{'unit':'synthetic impact unit','total':4.8,
                    'source':'synthetic algebra','evidence_class':'scenario'}}
                r['components']=[{'id':'electricity','source':'synthetic formula','evidence_class':'scenario','impacts':{'synthetic':3.2}},
                                 {'id':'preparation','source':'synthetic formula','evidence_class':'scenario','impacts':{'synthetic':1.6}}]
                routes.append(r)
            alternatives=[]
            for sid,old,new,unit,component,operation in [('power',2,4,'kW','electricity','linear'),
                    ('hours',1,2,'h','electricity','linear'),('reuse',2,4,'uses','preparation','inverse')]:
                alternatives.append({'id':sid,'variable':sid,'baseline':old,'value':new,'unit':unit,
                    'source':'synthetic scenario','evidence_class':'scenario','adjustments':[{'route':'A',
                    'component':component,'operator':operation}]})
            approx=additive_report({'description':'synthetic additive check','routes':routes,'scenarios':alternatives})
            additive=[case['results']['A']['synthetic']['absolute'] for case in approx['cases']]
            assert all(abs(a-b)<1e-10 for a,b in zip(v,additive)),(v,additive)
        assert fingerprint(db)==before,'synthetic source database changed'
        tampered=Path(temp)/'tampered.app'
        copy_runtime_bundle(app,tampered)
        signed_resource=tampered/'Contents/Eclipse/about.html'
        with signed_resource.open('ab') as stream: stream.write(b'\nmodified synthetic test\n')
        try:
            with launch(tampered,workspace,'synthetic_params'):
                raise AssertionError('modified signed application unexpectedly launched')
        except LaunchError as exc:
            assert 'signature verification failed' in str(exc),str(exc)
        print('PASS: actual openLCA parameter scenarios baseline=4.8, power=8, hours=8, reuse=4')
        print('PASS: repeat values match; writes rejected; source synthetic database unchanged')
        print('PASS: additive approximation matches the explicitly additive synthetic formula')
        print('PASS: modified signed app is rejected after cache cleanup')

if __name__=='__main__':main()
