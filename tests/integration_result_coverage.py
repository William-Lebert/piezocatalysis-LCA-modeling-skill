"""Optional end-to-end real openLCA test on a temporary fictional database."""
import json,subprocess,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'piezocatalysis-lca-modeling/scripts'))
from openlca_local_launch import launch
from openlca_readonly import Client,calculate
from mapping_coverage import ident,read_entity
from result_coverage import analyze
APP=Path('/Applications/openLCA.app');LIBS=APP/'Contents/Eclipse/plugins/olca-app_2.7.0/libs';JAVA=APP/'Contents/Eclipse/jre/Contents/Home/bin/java'
with tempfile.TemporaryDirectory(prefix='piezolca-coverage-') as tmp:
 workspace=Path(tmp);database=workspace/'databases'/'synthetic'
 p=subprocess.run([str(JAVA),'-cp',str(LIBS/'*'),'org.python.util.jython',str(ROOT/'tests/fixtures/create_result_coverage_synthetic.py'),str(database)],capture_output=True,text=True,timeout=90)
 if p.returncode:raise RuntimeError(p.stderr[-2000:])
 keys={'SYSTEM','METHOD','UNIT','PROPERTY','CANCEL','ZERO','EMISSION','MISSING'}
 ids=dict(line.split('=',1) for line in p.stdout.splitlines() if line.split('=',1)[0] in keys)
 assert set(ids)==keys,ids
 with launch(APP,workspace,'synthetic') as port:
  c=Client(port,120);args=SimpleNamespace(system_id=ids['SYSTEM'],method_id=ids['METHOD'],unit_id=ids['UNIT'],flow_property_id=ids['PROPERTY'],amount=1,wait_seconds=60,software_version='2.7',database_label='synthetic',database_version='synthetic',system_model='fictional',functional_unit='1 synthetic service',unit_label='kg',include_total_flows=True)
  result=calculate(c,args);system=read_entity(c,'ProductSystem',ids['SYSTEM']);procs={ident(x):read_entity(c,'Process',ident(x)) for x in system['processes']}
  category=read_entity(c,'ImpactCategory',ids['CANCEL']);report=analyze(result,system,procs,category,[ids['EMISSION'],ids['MISSING']])
  assert abs(report['hotspots']['total'])<1e-12 and report['hotspots']['has_positive_and_negative'] and not report['hotspots']['shares_available']
  assert [x['status'] for x in report['selected_factor_checks']]==['factor_value_present','no_factor_for_flow_uuid']
  assert any(x['status']=='unlinked_candidate' and x['flow']['flowType']=='WASTE_FLOW' for x in report['link_review']['technical_exchanges'])
  zero=read_entity(c,'ImpactCategory',ids['ZERO']);z=analyze(result,system,procs,zero,[ids['EMISSION']])
  assert z['hotspots']['total']==0 and not z['hotspots']['shares_available']
  assert z['selected_factor_checks'][0]['status']=='explicit_zero_factor'
  print('PASS: real openLCA zero factor, absent factor, unlinked waste and cancelling contributions')
