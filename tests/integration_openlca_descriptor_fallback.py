"""Compare optimized and upstream lookups on real openLCA with 33 fictional suppliers."""
import argparse
import math
import re
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from integration_openlca_guard import APP, ROOT, fingerprint
from openlca_local_launch import launch, snapshot_agent_argument
from openlca_readonly import Client, calculate
from scenario_binding import digest


def process_queries(trace):
    statements = re.findall(r'Executing (?:prepared )?statement:\s*(.*?)(?=\s*:End|\n[^\n]*Thread\[|\Z)',
                            trace, re.DOTALL | re.IGNORECASE)
    statements = [' '.join(sql.lower().split()) for sql in statements]
    descriptors = [sql for sql in statements
                   if sql.startswith('select d.id,') and 'from tbl_processes d left join tbl_exchanges e' in sql]
    return sum('where d.id = ?' in sql for sql in descriptors), sum(' where ' not in sql for sql in descriptors)


def read_fixture_snapshot(client, ids):
    def entity(kind, uid):
        return client.call('data/get', {'@type': kind, '@id': uid})

    system = entity('ProductSystem', ids['SYSTEM'])
    return {'system': system,
            'processes': {ref['@id']: entity('Process', ref['@id']) for ref in system['processes']},
            'method': entity('ImpactMethod', ids['METHOD']),
            'category': entity('ImpactCategory', ids['CATEGORY']),
            'parameters': client.call('data/get/parameters', {'@type': 'ProductSystem', '@id': ids['SYSTEM']})}


def observe(app, workspace, ids, trace, agent_option):
    spawn = subprocess.Popen

    def traced_spawn(command, *args, **kwargs):
        if 'org.openlca.ipc.Server' in command:
            command = [command[0], '-Dderby.language.logStatementText=true',
                       '-Dderby.stream.error.file=' + str(trace), *command[1:]]
        return spawn(command, *args, **kwargs)

    with patch('openlca_local_launch.subprocess.Popen', side_effect=traced_spawn), \
         patch('openlca_local_launch.snapshot_agent_argument', return_value=agent_option):
        with launch(app, workspace, 'descriptor_fallback') as port:
            client = Client(port, timeout=30)

            args = SimpleNamespace(system_id=ids['SYSTEM'], method_id=ids['METHOD'], unit_id=ids['UNIT'],
                                   flow_property_id=ids['PROPERTY'], amount=1, wait_seconds=30,
                                   software_version='2.7.0', database_label='descriptor_fallback',
                                   database_version='synthetic', system_model='synthetic', unit_label='kg',
                                   functional_unit='1 kg synthetic service', include_total_flows=True)
            before = read_fixture_snapshot(client, ids)
            assert len({link['provider']['@id'] for link in before['system']['processLinks']}) == 33
            assert len(before['processes']) == 34
            offset = trace.stat().st_size
            result = calculate(client, args)
            with trace.open('rb') as stream:
                stream.seek(offset)
                queries = process_queries(stream.read().decode())
            after = read_fixture_snapshot(client, ids)
            assert before == after and digest(before) == digest(after)
    for key in ('calculated_at_utc', 'result_id'):
        del result[key]
    return before, result, queries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--openlca-app', type=Path, default=APP)
    app = parser.parse_args().openlca_app.resolve()
    eclipse = app / 'Contents/Eclipse'
    java = eclipse / 'jre/Contents/Home/bin/java'
    libs = eclipse / 'plugins/olca-app_2.7.0/libs'
    agent_option = snapshot_agent_argument(libs)
    if not agent_option:
        parser.error('the descriptor fallback test requires the verified openLCA 2.7.0 core and Trove JARs')
    with tempfile.TemporaryDirectory(prefix='piezolca-descriptor-fallback-') as tmp:
        root = Path(tmp)
        database = root / 'workspace/databases/descriptor_fallback'
        created = subprocess.run([str(java), '-Xmx1024M', '-cp', str(libs / '*'), 'org.python.util.jython',
                                  str(ROOT / 'tests/fixtures/create_openlca_synthetic.py'), str(database), '33'],
                                 cwd=root, capture_output=True, text=True, timeout=90)
        if created.returncode:
            raise RuntimeError('synthetic fixture creation failed: ' + created.stderr[-1500:])
        ids = dict(line.split('=', 1) for line in created.stdout.splitlines()
                   if line.startswith(('SYSTEM=', 'METHOD=', 'CATEGORY=', 'UNIT=', 'PROPERTY=')))
        source_hash = fingerprint(database)
        baseline, original, original_queries = observe(app, root / 'workspace', ids, root / 'original.log', '')
        optimized, fallback, fallback_queries = observe(app, root / 'workspace', ids, root / 'fallback.log', agent_option)
        assert baseline == optimized and digest(baseline) == digest(optimized)
        assert original == fallback, 'LCIA results, contributions or inventory differ'
        assert math.isclose(fallback['impacts'][0]['amount'], 56.0, rel_tol=1e-12)
        assert fingerprint(database) == source_hash
        assert original_queries == (0, 1), original_queries
        assert fallback_queries == (32, 1), fallback_queries
        print(f'PASS: 33 linked providers, 56.0 LCIA, exact result and snapshot {digest(optimized)}')
        print(f'PASS: original point/full process queries={original_queries}, fallback={fallback_queries}')


if __name__ == '__main__':
    main()
