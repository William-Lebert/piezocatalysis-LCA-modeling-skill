"""JSON-RPC integration checks with an invented loopback server; no openLCA data."""
import importlib.util
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import threading
import socket
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'piezocatalysis-lca-modeling/scripts/openlca_readonly.py'
SYSTEM = '11111111-1111-4111-8111-111111111111'
METHOD = '22222222-2222-4222-8222-222222222222'
UNIT = '33333333-3333-4333-8333-333333333333'
PROPERTY = '44444444-4444-4444-8444-444444444444'
CAT = {'@type': 'ImpactCategory', '@id': '55555555-5555-4555-8555-555555555555', 'name': 'synthetic climate', 'refUnit': 'kg CO2-eq'}

class FakeServer(ThreadingHTTPServer):
    def __init__(self):
        super().__init__(('127.0.0.1', 0), Handler); self.calls=[]; self.fail=''; self.states=0

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_POST(self):
        req=json.loads(self.rfile.read(int(self.headers['Content-Length']))); self.server.calls.append(req)
        method=req['method']; params=req.get('params', {}); result=None
        if self.server.fail == method:
            response={'jsonrpc':'2.0','id':req['id'],'error':{'code':-32000,'message':'synthetic error'}}
        else:
            if method == 'data/get/descriptors':
                typ=params['@type']; ident={'ProductSystem':SYSTEM,'ImpactMethod':METHOD}.get(typ)
                result=[{'@type':typ,'@id':ident,'name':'synthetic '+typ}] if ident else []
            elif method == 'data/get/parameters': result=[{'name':'power','value':2.0}]
            elif method == 'result/calculate': result={'@id':'result-synthetic','isReady':False}
            elif method == 'result/state':
                self.server.states += 1
                result={'@id':'result-synthetic','isReady':self.server.fail != 'never-ready'}
                if self.server.fail == 'state-error': result['error']='synthetic calculation failed'
            elif method == 'result/total-impacts': result=[] if self.server.fail == 'empty-impacts' else [{'impactCategory':CAT,'amount':1e-13 if self.server.fail == 'tiny-mismatch' else 3.2}]
            elif method == 'result/impact-contributions-of':
                result=[] if self.server.fail == 'empty-contributions' else [{'techFlow':{'provider':{'name':'A'}},'amount':0.0 if self.server.fail == 'tiny-mismatch' else 1.2}, {'techFlow':{'provider':{'name':'B'}},'amount':0.0 if self.server.fail == 'tiny-mismatch' else (1.0 if self.server.fail == 'mismatch' else 2.0)}]
            elif method == 'result/dispose': result='ok'
            else: raise AssertionError(method)
            response={'jsonrpc':'2.0','id':req['id'],'result':result}
        raw=json.dumps(response).encode(); self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)

class ReadOnlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=FakeServer(); cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls): cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def setUp(self): self.server.calls=[];self.server.fail='';self.server.states=0
    def invoke(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), '--port', str(self.server.server_port), *args],text=True,capture_output=True)
    def calc(self):
        return self.invoke('calculate','--system-id',SYSTEM,'--method-id',METHOD,'--amount','1',
            '--unit-id',UNIT,'--flow-property-id',PROPERTY,'--unit-label','kg', '--database-label','synthetic DB',
            '--database-version','synthetic 1','--system-model','synthetic','--software-version','synthetic 2.7',
            '--functional-unit','1 kg synthetic service')
    def test_list_is_only_read_descriptor(self):
        r=self.invoke('list','--type','ProductSystem');self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(json.loads(r.stdout)['descriptors'][0]['@id'], SYSTEM)
        self.assertEqual([x['method'] for x in self.server.calls], ['data/get/descriptors'])
    def test_synthetic_calculation_and_cleanup(self):
        r=self.calc();self.assertEqual(r.returncode,0,r.stderr); x=json.loads(r.stdout)
        self.assertEqual(x['impacts'][0]['amount'],3.2);self.assertTrue(x['impacts'][0]['reconciliation']['within_tolerance'])
        self.assertEqual(x['database']['identity_verification'], 'user_asserted_not_verified')
        self.assertEqual([c['method'] for c in self.server.calls],['data/get/descriptors','data/get/descriptors','result/calculate','result/state','result/total-impacts','result/impact-contributions-of','result/dispose'])
        setup=self.server.calls[2]['params'];self.assertEqual(setup['unit']['@id'],UNIT);self.assertEqual(setup['flowProperty']['@id'],PROPERTY)
    def test_rpc_failure_is_error_and_disposes(self):
        self.server.fail='result/total-impacts'; r=self.calc()
        self.assertNotEqual(r.returncode,0);self.assertEqual(r.stdout,'');self.assertIn('synthetic error',r.stderr)
        self.assertEqual(self.server.calls[-1]['method'],'result/dispose')
    def test_cleanup_failure_is_error(self):
        self.server.fail='result/dispose';r=self.calc();self.assertNotEqual(r.returncode,0);self.assertEqual(r.stdout,'')
    def test_empty_impacts_and_failed_calculation_stop_and_dispose(self):
        for failure in ('empty-impacts', 'state-error'):
            with self.subTest(failure=failure):
                self.server.calls=[]; self.server.fail=failure; r=self.calc()
                self.assertNotEqual(r.returncode,0); self.assertEqual(r.stdout,'')
                self.assertEqual(self.server.calls[-1]['method'],'result/dispose')
    def test_empty_contributions_are_not_zero_filled(self):
        self.server.fail='empty-contributions';r=self.calc();self.assertEqual(r.returncode,0,r.stderr)
        result=json.loads(r.stdout)
        self.assertIsNone(result['impacts'][0]['reconciliation']['sum'])
        self.assertTrue(any('reconciliation unavailable' in x for x in result['warnings']))
    def test_nonreconciling_contributions_are_flagged(self):
        self.server.fail='mismatch'; r=self.calc(); self.assertEqual(r.returncode,0,r.stderr)
        result=json.loads(r.stdout)
        self.assertFalse(result['impacts'][0]['reconciliation']['within_tolerance'])
        self.assertTrue(any('do not reconcile' in x for x in result['warnings']))
    def test_small_impact_is_not_reconciled_to_zero(self):
        self.server.fail='tiny-mismatch';r=self.calc();self.assertEqual(r.returncode,0,r.stderr)
        result=json.loads(r.stdout)
        self.assertFalse(result['impacts'][0]['reconciliation']['within_tolerance'])
    def test_timeout_disposes_result(self):
        self.server.fail='never-ready'
        r=self.invoke('calculate','--system-id',SYSTEM,'--method-id',METHOD,'--amount','1',
            '--unit-id',UNIT,'--flow-property-id',PROPERTY,'--unit-label','kg','--database-label','test',
            '--database-version','1','--system-model','test','--software-version','2.7',
            '--functional-unit','test','--wait-seconds','0.05')
        self.assertNotEqual(r.returncode,0);self.assertIn('timed out',r.stderr)
        self.assertEqual(self.server.calls[-1]['method'],'result/dispose')
    def test_missing_system_stops_before_calculation(self):
        r=self.invoke('calculate','--system-id','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','--method-id',METHOD,'--amount','1','--unit-id',UNIT,'--flow-property-id',PROPERTY,'--unit-label','kg','--database-label','test','--database-version','1','--system-model','test','--software-version','2.7','--functional-unit','test')
        self.assertNotEqual(r.returncode,0);self.assertNotIn('result/calculate',[c['method'] for c in self.server.calls])
    def test_client_rejects_write_methods(self):
        spec=importlib.util.spec_from_file_location('olca_readonly', SCRIPT);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        client=mod.Client(self.server.server_port)
        with self.assertRaises(ValueError):client.call('data/put',{})
        self.assertEqual(self.server.calls,[])

    def test_product_system_parameters_are_readable(self):
        spec=importlib.util.spec_from_file_location('olca_readonly', SCRIPT);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        client=mod.Client(self.server.server_port)
        values=client.call('data/get/parameters',{'@type':'ProductSystem','@id':SYSTEM})
        self.assertEqual(values[0]['name'],'power')
        self.assertEqual(self.server.calls[-1]['method'],'data/get/parameters')

    def test_cli_lists_parameters_for_existing_product_system(self):
        result=self.invoke('parameters','--system-id',SYSTEM)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['parameters'][0]['name'],'power')
        self.assertEqual([x['method'] for x in self.server.calls],['data/get/descriptors','data/get/parameters'])

    def test_auto_connect_finds_local_service_using_read_only_probe(self):
        r=subprocess.run([sys.executable,str(SCRIPT),'--candidate-ports',str(self.server.server_port),
                          'list','--type','ProductSystem'],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        result=json.loads(r.stdout)
        self.assertEqual(result['connection']['port'],self.server.server_port)
        self.assertEqual(result['connection']['mode'],'automatic')
        self.assertEqual([c['method'] for c in self.server.calls],['data/get/descriptors']*2)
        self.assertEqual(self.server.calls[0]['params']['@type'],'FlowProperty')

    def test_auto_connect_rejects_ambiguous_services(self):
        other=FakeServer();thread=threading.Thread(target=other.serve_forever,daemon=True);thread.start()
        try:
            ports=f'{self.server.server_port},{other.server_port}'
            r=subprocess.run([sys.executable,str(SCRIPT),'--candidate-ports',ports,
                              'list','--type','ProductSystem'],capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0)
            self.assertIn('multiple',r.stderr)
            self.assertEqual([c['method'] for c in other.calls],['data/get/descriptors'])
        finally:
            other.shutdown();other.server_close();thread.join()

    def test_auto_connect_reports_absent_service(self):
        with socket.socket() as reserved:
            reserved.bind(('127.0.0.1',0))
            port=reserved.getsockname()[1]
            r=subprocess.run([sys.executable,str(SCRIPT),'--candidate-ports',str(port),
                              'list','--type','ProductSystem'],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0)
        self.assertIn('no compatible',r.stderr)

    def test_auto_connect_calculates_and_disposes(self):
        r=subprocess.run([sys.executable,str(SCRIPT),'--candidate-ports',str(self.server.server_port),
            'calculate','--system-id',SYSTEM,'--method-id',METHOD,'--amount','1',
            '--unit-id',UNIT,'--flow-property-id',PROPERTY,'--unit-label','kg',
            '--database-label','synthetic DB','--database-version','1','--system-model','synthetic',
            '--software-version','2.7','--functional-unit','1 synthetic unit'],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(json.loads(r.stdout)['impacts'][0]['amount'],3.2)
        self.assertEqual(self.server.calls[-1]['method'],'result/dispose')

    def test_candidate_ports_reject_duplicates_and_out_of_range(self):
        for ports in ('0', '65536', '8080,8080', '8080,invalid'):
            r=subprocess.run([sys.executable,str(SCRIPT),'--candidate-ports',ports,
                              'list','--type','ProductSystem'],capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0)
        self.assertEqual(self.server.calls,[])

    def test_autostart_requires_a_database_and_does_not_change_input_when_app_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace=Path(temp)
            original=workspace/'databases'/'example'
            original.mkdir(parents=True)
            sentinel=original/'service.properties';sentinel.write_text('preserve me')
            missing=workspace/'missing-openLCA.app'
            r=subprocess.run([sys.executable,str(SCRIPT),'--start-local','--workspace',str(workspace),
                              '--database','example','--openlca-app',str(missing),
                              'list','--type','ProductSystem'],capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0)
            self.assertEqual(sentinel.read_text(),'preserve me')
        r=subprocess.run([sys.executable,str(SCRIPT),'--start-local',
                          'list','--type','ProductSystem'],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0)
        self.assertIn('requires --workspace and --database',r.stderr)

if __name__=='__main__': unittest.main()
