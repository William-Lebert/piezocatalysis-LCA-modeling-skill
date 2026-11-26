"""Check the same fictional openLCA 2.7.0 database via an already running local IPC."""
import argparse
import json
import math
import platform
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from integration_openlca_descriptor_fallback import read_fixture_snapshot
from openlca_readonly import Client, IPCError, RESULT_WAIT_TIMEOUT, calculate, valid_uuid
from scenario_binding import digest


class TracedClient(Client):
    def __init__(self, port):
        super().__init__(port, timeout=30)
        self.allocation = None
        self.disposal = None

    def call(self, method, params):
        result = super().call(method, params)
        if method == 'result/calculate':
            self.allocation = result
            self.disposal = None
        elif method == 'result/dispose':
            self.disposal = result
        return result


def require_released(client, result_id):
    state = client.call('result/state', {'@id': result_id})
    if state != {'error': 'does not exist'}:
        client.call('result/dispose', {'@id': result_id})
        raise ValueError(f'result {result_id} is still available after disposal')


def run_case(client, arguments, ids, snapshot_sha256, amount):
    args = SimpleNamespace(**vars(arguments), amount=amount, wait_seconds=30,
                           functional_unit=f'{amount} kg synthetic service')
    result = calculate(client, args)
    result_id = result.pop('result_id')
    result.pop('calculated_at_utc')
    if client.disposal != {'@id': result_id}:
        raise ValueError('disposal acknowledgement did not match the completed calculation')
    require_released(client, result_id)
    impacts = result['impacts']
    if (len(impacts) != 1 or impacts[0]['category']['@id'] != ids['CATEGORY']
            or not math.isclose(impacts[0]['amount'], amount * 56.0, rel_tol=1e-12)):
        raise ValueError(f'unexpected synthetic LCIA for amount {amount}')
    if digest(read_fixture_snapshot(client, ids)) != snapshot_sha256:
        raise ValueError('fixture snapshot changed across calculation')
    return result


def verify(port, ids):
    for key in ('SYSTEM', 'METHOD', 'CATEGORY', 'UNIT', 'PROPERTY'):
        valid_uuid(ids[key])
    client = TracedClient(port)
    snapshot = read_fixture_snapshot(client, ids)
    if len({link['provider']['@id'] for link in snapshot['system']['processLinks']}) != 33:
        raise ValueError('expected the fictional system with 33 distinct supply processes')
    snapshot_sha256 = digest(snapshot)
    arguments = SimpleNamespace(system_id=ids['SYSTEM'], method_id=ids['METHOD'], unit_id=ids['UNIT'],
                                flow_property_id=ids['PROPERTY'], software_version='2.7.0',
                                database_label='manual_ipc_synthetic', database_version='synthetic',
                                system_model='synthetic', unit_label='kg', include_total_flows=True)
    cases = [run_case(client, arguments, ids, snapshot_sha256, amount) for amount in (1, 2)]
    args = SimpleNamespace(**vars(arguments), amount=1, wait_seconds=0.001,
                           functional_unit='1 kg synthetic service')
    started = time.perf_counter()
    try:
        calculate(client, args)
    except IPCError as exc:
        if str(exc) != RESULT_WAIT_TIMEOUT:
            raise
    else:
        raise ValueError('the 1 ms test budget did not exercise the timeout path')
    timeout_elapsed_seconds = time.perf_counter() - started
    result_id = client.allocation['@id']
    if client.allocation.get('isScheduled') is not True or client.disposal != {'@id': result_id}:
        raise ValueError('timeout did not dispose the scheduled calculation')
    require_released(client, result_id)
    recovery = run_case(client, arguments, ids, snapshot_sha256, 1)
    if digest(recovery) != digest(cases[0]):
        raise ValueError('the first case changed after timeout recovery')
    require_released(client, result_id)
    return {'platform': platform.system(), 'platform_release': platform.release(),
            'python': platform.python_version(), 'software_version_user_asserted': '2.7.0',
            'port': port, 'snapshot': snapshot, 'snapshot_sha256': snapshot_sha256,
            'cases': cases, 'cases_sha256': digest(cases),
            'timeout': {'seconds': args.wait_seconds, 'elapsed_with_cleanup_seconds': timeout_elapsed_seconds,
                        'result_id': result_id, 'released_after_timeout_and_after_recovery': True}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--fixture', type=Path, required=True, help='IDs from the shared 33-provider database')
    parser.add_argument('--compare', type=Path, help='successful report for the same database on another host')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError('choose a new output file')
        ids = json.loads(args.fixture.read_bytes())
        reference = json.loads(args.compare.read_bytes()) if args.compare else None
        report = verify(args.port, ids)
        if reference is not None:
            for payload in ('snapshot', 'cases'):
                key = f'{payload}_sha256'
                if reference[key] != digest(reference[payload]) or reference[key] != report[key]:
                    raise ValueError(f'{payload} differs from the reference report')
            report['matched_reference_platform'] = reference['platform']
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
        print(f"PASS: {report['platform']} LCIA 56.0, 112.0; snapshots stable; timed-out result released after recovery")
        return 0
    except (OSError, ValueError, TypeError, KeyError, IPCError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
