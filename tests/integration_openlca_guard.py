"""Optional real openLCA 2.7.0 test; creates and deletes only a synthetic DB."""
import hashlib
import argparse
import csv
import http.client
import json
import socket
import subprocess
import sys
import tempfile
import os
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'piezocatalysis-lca-modeling/scripts'
sys.path.insert(0, str(SCRIPTS))
from openlca_local_launch import launch
from openlca_readonly import Client, calculate, discover_local

APP = Path('/Applications/openLCA.app')
JAVA = APP / 'Contents/Eclipse/jre/Contents/Home/bin/java'
LIBS = APP / 'Contents/Eclipse/plugins/olca-app_2.7.0/libs'


def fingerprint(folder):
    digest = hashlib.sha256()
    for path in sorted(p for p in folder.rglob('*') if p.is_file()):
        digest.update(str(path.relative_to(folder)).encode())
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
    return digest.hexdigest()


def rpc(port, method, params):
    body = json.dumps({'jsonrpc': '2.0', 'id': 97, 'method': method, 'params': params})
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
    try:
        c.request('POST', '/', body, {'Content-Type': 'application/json'})
        return json.loads(c.getresponse().read())
    finally:
        c.close()


def main():
    global APP, JAVA, LIBS
    parser = argparse.ArgumentParser()
    parser.add_argument('--openlca-app', type=Path, default=APP)
    APP = parser.parse_args().openlca_app
    JAVA = APP / 'Contents/Eclipse/jre/Contents/Home/bin/java'
    LIBS = APP / 'Contents/Eclipse/plugins/olca-app_2.7.0/libs'
    with tempfile.TemporaryDirectory(prefix='piezolca-real-integration-') as temp:
        workspace = Path(temp) / 'workspace'
        database = workspace / 'databases' / 'synthetic_case'
        p = subprocess.run([str(JAVA), '-Xmx1024M', '-cp', str(LIBS / '*'), 'org.python.util.jython',
                            str(ROOT / 'tests/fixtures/create_openlca_synthetic.py'), str(database)],
                           capture_output=True, text=True, timeout=90)
        if p.returncode:
            raise RuntimeError('synthetic fixture creation failed: ' + p.stderr[-500:])
        ids = dict(line.split('=', 1) for line in p.stdout.splitlines() if line.startswith(('SYSTEM=', 'METHOD=', 'UNIT=', 'PROPERTY=')))
        before = fingerprint(database)
        with launch(APP, workspace, 'synthetic_case') as port:
            assert discover_local((port,)).port == port
            for method, data in [('data/put', {'@type': 'Flow', 'name': 'forbidden synthetic write'}),
                                 ('data/delete', {'@type': 'Flow', '@id': '00000000-0000-4000-8000-000000000001'}),
                                 ('data/get/all', {'@type': 'Flow'})]:
                answer = rpc(port, method, data)
                assert answer.get('error', {}).get('code') == -32601, (method, answer)
            for interface in ('en0', 'en1'):
                result = subprocess.run(['ipconfig', 'getifaddr', interface], capture_output=True, text=True)
                address = result.stdout.strip()
                if result.returncode == 0 and address:
                    with socket.socket() as conn:
                        conn.settimeout(1)
                        assert conn.connect_ex((address, port)) != 0, 'non-loopback address unexpectedly reachable'
            args = SimpleNamespace(system_id=ids['SYSTEM'], method_id=ids['METHOD'], unit_id=ids['UNIT'],
                flow_property_id=ids['PROPERTY'], amount=1, wait_seconds=30, software_version='2.7.0',
                database_label='synthetic_case', database_version='synthetic', system_model='synthetic',
                functional_unit='1 kg synthetic service', unit_label='kg')
            result = calculate(Client(port), args)
            assert abs(result['impacts'][0]['amount'] - 3.2) < 1e-8
            assert result['impacts'][0]['reconciliation']['within_tolerance'] is True
        with socket.socket() as conn:
            conn.settimeout(1)
            assert conn.connect_ex(('127.0.0.1', port)) != 0, 'server did not stop'
        assert fingerprint(database) == before, 'original synthetic DB changed'
        command = [sys.executable, str(SCRIPTS / 'openlca_readonly.py'), '--start-local', '--workspace', str(workspace),
                   '--database', 'synthetic_case', '--openlca-app', str(APP), 'list', '--type', 'ProductSystem']
        p = subprocess.run(command, capture_output=True, text=True, timeout=90)
        if p.returncode: raise RuntimeError('automatic CLI failed: ' + p.stderr)
        result = json.loads(p.stdout)
        assert result['connection']['mode'] == 'guarded-autostart'
        assert any(item.get('@id') == ids['SYSTEM'] for item in result['descriptors'])
        assert fingerprint(database) == before, 'original synthetic DB changed after CLI'
        inventory = Path(temp) / 'inventory.csv'
        mapping = Path(temp) / 'mapping.csv'
        inventory_fields = ['system', 'stage', 'flow_name', 'amount', 'unit', 'direction', 'evidence_class',
                            'source', 'dataset_mapping', 'included', 'note']
        with inventory.open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=inventory_fields); writer.writeheader()
            writer.writerow(dict(system='synthetic', stage='treatment', flow_name='synthetic service', amount='1',
                                 unit='kg', direction='input', evidence_class='scenario', source='synthetic',
                                 dataset_mapping='map-service', included='true', note=''))
        from audit_and_scale_inventory import MAPPING_FIELDS
        m = dict.fromkeys(MAPPING_FIELDS, '')
        m.update(mapping_id='map-service', foreground_flow='synthetic service', foreground_unit='kg',
                 database='synthetic_case', database_version='synthetic', system_model='synthetic',
                 dataset_name='Synthetic treatment process', reference_product='Synthetic treatment service',
                 dataset_unit='kg', match_type='exact', conversion_factor='1', review_status='pending')
        with mapping.open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=sorted(MAPPING_FIELDS)); writer.writeheader(); writer.writerow(m)
        command = [sys.executable, str(SCRIPTS/'dataset_candidates.py'), '--inventory', str(inventory),
                   '--mapping', str(mapping), '--database', 'synthetic_case', '--database-version', 'synthetic',
                   '--system-model', 'synthetic', '--start-local', '--workspace', str(workspace), '--openlca-app', str(APP)]
        p = subprocess.run(command, capture_output=True, text=True, timeout=90)
        if p.returncode: raise RuntimeError('candidate query failed: ' + p.stderr)
        candidate = json.loads(p.stdout)['rows'][0]
        assert candidate['status'] == 'needs_review' and candidate['candidate_count'] == 1
        assert candidate['selected_process_uuid'] is None
        assert fingerprint(database) == before, 'original synthetic DB changed after candidate lookup'
        command = [sys.executable, str(SCRIPTS / 'openlca_readonly.py'), '--start-local', '--workspace', str(workspace),
            '--database', 'synthetic_case', '--openlca-app', str(APP), 'calculate', '--system-id', ids['SYSTEM'], '--method-id', ids['METHOD'],
            '--unit-id', ids['UNIT'], '--flow-property-id', ids['PROPERTY'], '--amount', '1', '--unit-label', 'kg',
            '--database-label', 'synthetic_case', '--database-version', 'synthetic', '--system-model', 'synthetic',
            '--software-version', '2.7.0', '--functional-unit', '1 kg synthetic service']
        p = subprocess.run(command, capture_output=True, text=True, timeout=90)
        if p.returncode: raise RuntimeError('automatic CLI calculation failed: ' + p.stderr)
        result = json.loads(p.stdout)
        assert result['connection']['mode'] == 'guarded-autostart'
        assert abs(result['impacts'][0]['amount'] - 3.2) < 1e-8
        assert result['impacts'][0]['reconciliation']['within_tolerance'] is True
        assert fingerprint(database) == before, 'original synthetic DB changed after CLI calculation'
        command[command.index('--amount') + 1] = '2'
        command[command.index('--functional-unit') + 1] = '2 kg synthetic service'
        p = subprocess.run(command, capture_output=True, text=True, timeout=90)
        if p.returncode: raise RuntimeError('second automatic CLI calculation failed: ' + p.stderr)
        second = json.loads(p.stdout)
        assert abs(second['impacts'][0]['amount'] - 6.4) < 1e-8
        assert second['impacts'][0]['reconciliation']['within_tolerance'] is True
        assert fingerprint(database) == before, 'original synthetic DB changed after second CLI calculation'
        crash_temp = Path(temp) / 'parent_crash'
        crash_temp.mkdir()
        child_code = ('import sys,time; from pathlib import Path; '
            'sys.path.insert(0,sys.argv[1]); from openlca_local_launch import launch; '
            'ctx=launch(Path(sys.argv[2]),Path(sys.argv[3]),"synthetic_case"); '
            'port=ctx.__enter__(); print(port,flush=True); time.sleep(120)')
        env = dict(os.environ, TMPDIR=str(crash_temp))
        parent = subprocess.Popen([sys.executable, '-u', '-c', child_code, str(SCRIPTS), str(APP), str(workspace)],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        try:
            line = parent.stdout.readline()
            if not line:
                raise RuntimeError('crash-test parent failed: ' + parent.stderr.read()[-500:])
            crash_port = int(line.strip())
        finally:
            parent.kill()
            parent.wait(timeout=5)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with socket.socket() as conn:
                conn.settimeout(0.5)
                if conn.connect_ex(('127.0.0.1', crash_port)) != 0:
                    break
            time.sleep(0.1)
        else:
            raise AssertionError('guarded server survived a killed parent')
        assert fingerprint(database) == before, 'original synthetic DB changed after interrupted run'
        print('PASS: real openLCA synthetic calculations=3.2 and 6.4; source DB unchanged')
        print('PASS: local-only listener; write methods rejected; process stopped; CLI autostart succeeded')
        print('PASS: guarded server stopped after parent was killed')
        print('PASS: candidate lookup against real synthetic openLCA process')


if __name__ == '__main__':
    main()
