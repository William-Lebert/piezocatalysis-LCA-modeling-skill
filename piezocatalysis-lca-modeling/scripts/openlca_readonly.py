#!/usr/bin/env python3
"""Read descriptors and calculate existing openLCA systems over local JSON-RPC.

No database entity creation, editing, import or deletion is implemented.
Calculations allocate transient result resources which are disposed afterwards.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import http.client
import json
import math
import sys
import time
import uuid
from pathlib import Path


ALLOWED_METHODS = frozenset({'data/get/descriptors', 'data/get/parameters', 'result/calculate', 'result/state',
                             'result/total-impacts', 'result/impact-contributions-of', 'result/dispose'})
KINDS = ('ProductSystem', 'ImpactMethod', 'Process', 'Flow', 'FlowProperty')
MAX_RESPONSE = 32 * 1024 * 1024
DEFAULT_CANDIDATE_PORTS = (8080, 18808)


class IPCError(Exception):
    pass


class Client:
    def __init__(self, port: int, timeout: float = 10):
        if not 1 <= port <= 65535 or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('invalid port or timeout')
        self.port, self.timeout, self.next_id = port, timeout, 1

    def call(self, method: str, params: dict):
        if method not in ALLOWED_METHODS:
            raise ValueError(f'method is not allowed by read-only client: {method}')
        request_id = self.next_id
        self.next_id += 1
        data = json.dumps({'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params}, allow_nan=False).encode()
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=self.timeout)
        try:
            connection.request('POST', '/', body=data, headers={'Content-Type': 'application/json'})
            response = connection.getresponse()
            if response.status != 200:
                raise IPCError(f'{method}: HTTP {response.status}; redirects are not followed')
            raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise IPCError(f'{method}: response exceeds size limit')
            def bad_constant(value):
                raise ValueError(f'invalid JSON number {value}')
            payload = json.loads(raw, parse_constant=bad_constant)
        except (OSError, http.client.HTTPException, ValueError, UnicodeError) as exc:
            raise IPCError(f'{method}: connection or JSON error: {exc}') from exc
        finally:
            connection.close()
        if not isinstance(payload, dict) or payload.get('id') != request_id or payload.get('jsonrpc') != '2.0':
            raise IPCError(f'{method}: invalid JSON-RPC response or mismatched request ID')
        if payload.get('error') is not None:
            raise IPCError(f'{method}: server error: {payload["error"]}')
        if 'result' not in payload:
            raise IPCError(f'{method}: missing result')
        return payload['result']


def descriptors(client: Client, kind: str) -> list:
    if kind not in KINDS:
        raise ValueError('unsupported descriptor type')
    result = client.call('data/get/descriptors', {'@type': kind})
    if not isinstance(result, list) or any(not isinstance(item, dict) for item in result):
        raise IPCError(f'{kind}: invalid descriptor list')
    return result


def candidate_ports(value: str) -> tuple:
    try:
        parts = value.split(',')
        ports = tuple(int(part.strip()) for part in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('use comma-separated port numbers') from exc
    if not 1 <= len(ports) <= 16 or len(set(ports)) != len(ports) or any(not 1 <= p <= 65535 for p in ports):
        raise argparse.ArgumentTypeError('provide 1–16 distinct ports from 1 to 65535')
    return ports


def discover_local(ports: tuple) -> Client:
    matches = []
    for port in ports:
        try:
            descriptors(Client(port, timeout=1.0), 'FlowProperty')
        except IPCError:
            continue
        matches.append(port)
    if not matches:
        raise IPCError('no compatible local IPC service found on candidate ports; start openLCA or supply --port')
    if len(matches) > 1:
        raise IPCError('multiple compatible local IPC services found; select one explicitly with --port: ' + ', '.join(map(str, matches)))
    return Client(matches[0])


def known_ref(client: Client, kind: str, identifier: str) -> dict:
    matches = [r for r in descriptors(client, kind) if r.get('@id') == identifier]
    if len(matches) != 1:
        raise IPCError(f'{kind} UUID not uniquely found in active database: {identifier}')
    return matches[0]


def numeric(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise IPCError(f'{label}: missing or invalid numeric amount')
    try:
        amount = float(value)
    except OverflowError as exc:
        raise IPCError(f'{label}: non-finite amount') from exc
    if not math.isfinite(amount):
        raise IPCError(f'{label}: non-finite amount')
    return amount


def get_impacts(client: Client, result_id: str) -> tuple[list, list]:
    raw = client.call('result/total-impacts', {'@id': result_id})
    if not isinstance(raw, list) or not raw:
        raise IPCError('result/total-impacts: no impact results returned; inspect method and model')
    impacts, warnings = [], []
    for row in raw:
        if not isinstance(row, dict) or not isinstance(row.get('impactCategory'), dict):
            raise IPCError('invalid impact result')
        category = row['impactCategory']
        if not isinstance(category.get('@id'), str) or not category['@id']:
            raise IPCError('impact category has no stable identifier')
        amount = numeric(row.get('amount'), 'impact')
        contributions = client.call('result/impact-contributions-of', {'@id': result_id, 'impactCategory': category})
        if not isinstance(contributions, list):
            raise IPCError('invalid contribution list')
        for item in contributions:
            if not isinstance(item, dict) or not isinstance(item.get('techFlow'), dict):
                raise IPCError('invalid contribution entry')
            numeric(item.get('amount'), 'contribution')
        reconciliation = {'sum': None, 'difference': None, 'within_tolerance': None,
                          'relative_tolerance': 1e-6, 'absolute_tolerance': 0.0}
        if contributions:
            total = numeric(math.fsum(numeric(item['amount'], 'contribution') for item in contributions), 'contribution sum')
            reconciliation.update({'sum': total, 'difference': total - amount,
                                   'within_tolerance': math.isclose(total, amount, rel_tol=1e-6, abs_tol=0.0)})
            if not reconciliation['within_tolerance']:
                warnings.append(f'contributions do not reconcile for category {category["@id"]}')
        else:
            warnings.append(f'no contributions returned for category {category["@id"]}; reconciliation unavailable')
        if not category.get('refUnit'):
            warnings.append(f'category {category["@id"]} has no refUnit in response; verify unit')
        impacts.append({'category': category, 'amount': amount, 'contributions': contributions, 'reconciliation': reconciliation})
    return impacts, warnings


def calculate(client: Client, args) -> dict:
    system = known_ref(client, 'ProductSystem', args.system_id)
    method = known_ref(client, 'ImpactMethod', args.method_id)
    setup = {'target': {'@type': 'ProductSystem', '@id': args.system_id},
             'impactMethod': {'@type': 'ImpactMethod', '@id': args.method_id},
             'amount': args.amount, 'unit': {'@type': 'Unit', '@id': args.unit_id},
             'flowProperty': {'@type': 'FlowProperty', '@id': args.flow_property_id}}
    if getattr(args, 'parameters', None):
        setup['parameters'] = args.parameters
    state = client.call('result/calculate', setup)
    if not isinstance(state, dict) or not isinstance(state.get('@id'), str) or not state['@id']:
        raise IPCError('calculation returned no result ID; no result can be retrieved or disposed')
    result_id = state['@id']
    failure = None
    report = None
    try:
        deadline = time.monotonic() + args.wait_seconds
        while True:
            if state.get('error'):
                raise IPCError(f'calculation failed: {state["error"]}')
            if state.get('isReady') is True:
                break
            if time.monotonic() >= deadline:
                raise IPCError('calculation timed out while waiting for result')
            time.sleep(min(0.2, max(0, deadline - time.monotonic())))
            state = client.call('result/state', {'@id': result_id})
            if not isinstance(state, dict) or state.get('@id') != result_id:
                raise IPCError('result/state: invalid or mismatched result ID')
        impacts, warnings = get_impacts(client, result_id)
        warnings.append('Database identity, software and unit labels are user supplied and not independently verified by IPC.')
        report = {'calculated_at_utc': datetime.now(timezone.utc).isoformat(),
                  'software': {'name': 'openLCA', 'version_user_asserted': args.software_version},
                  'database': {'name': args.database_label, 'version': args.database_version,
                               'system_model': args.system_model, 'identity_verification': 'user_asserted_not_verified'},
                  'functional_unit_user_asserted': args.functional_unit,
                  'target': system, 'impact_method': method, 'setup': setup,
                  'unit_label_user_asserted': args.unit_label, 'result_id': result_id,
                  'impacts': impacts, 'warnings': warnings}
    except (IPCError, ValueError, OverflowError) as exc:
        failure = exc
    try:
        client.call('result/dispose', {'@id': result_id})
    except (IPCError, ValueError) as exc:
        if failure is not None:
            raise IPCError(f'{failure}; additionally failed to dispose result {result_id}: {exc}') from exc
        raise IPCError(f'failed to dispose result {result_id}: {exc}') from exc
    if failure is not None:
        raise failure
    return report


def valid_uuid(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise argparse.ArgumentTypeError('must be a UUID') from exc


def positive(value: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('must be a positive finite number') from exc
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError('must be a positive finite number')
    return result


def nonempty(value: str) -> str:
    if not value.strip() or 'replace-me' in value.lower():
        raise argparse.ArgumentTypeError('must be nonempty and not a placeholder')
    return value.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    connection = parser.add_mutually_exclusive_group()
    connection.add_argument('--port', type=int, help='explicit local IPC server port')
    connection.add_argument('--candidate-ports', type=candidate_ports, help='comma-separated local ports to probe (default: 8080,18808)')
    connection.add_argument('--start-local', action='store_true', help='start guarded openLCA on a temporary clone of an existing database (verified macOS 2.7.0 only)')
    parser.add_argument('--workspace', type=Path, help='openLCA data workspace for --start-local')
    parser.add_argument('--database', help='existing database name for --start-local')
    parser.add_argument('--openlca-app', type=Path, default=Path('/Applications/openLCA.app'), help='verified openLCA 2.7.0 app path')
    sub = parser.add_subparsers(dest='command', required=True)
    listing = sub.add_parser('list'); listing.add_argument('--type', choices=KINDS, required=True)
    parameters = sub.add_parser('parameters'); parameters.add_argument('--system-id', type=valid_uuid, required=True)
    run = sub.add_parser('calculate')
    for arg in ('system-id', 'method-id', 'unit-id', 'flow-property-id'):
        run.add_argument('--' + arg, type=valid_uuid, required=True)
    for arg in ('unit-label', 'database-label', 'database-version', 'system-model', 'software-version', 'functional-unit'):
        run.add_argument('--' + arg, type=nonempty, required=True)
    run.add_argument('--amount', type=positive, required=True)
    run.add_argument('--wait-seconds', type=positive, default=30)
    args = parser.parse_args()
    if args.start_local and (args.workspace is None or not args.database):
        parser.error('--start-local requires --workspace and --database')
    if not args.start_local and (args.workspace is not None or args.database):
        parser.error('--workspace and --database require --start-local')
    try:
        with ExitStack() as stack:
            automatic = args.port is None and not args.start_local
            if args.start_local:
                from openlca_local_launch import launch
                port = stack.enter_context(launch(args.openlca_app, args.workspace, args.database))
                client = Client(port)
            else:
                client = discover_local(args.candidate_ports or DEFAULT_CANDIDATE_PORTS) if automatic else Client(args.port)
            if args.command == 'list':
                output = {'type': args.type, 'descriptors': descriptors(client, args.type),
                          'warning': 'Active database identity is not verified; confirm in openLCA.'}
            elif args.command == 'parameters':
                system = known_ref(client, 'ProductSystem', args.system_id)
                values = client.call('data/get/parameters', {'@type': 'ProductSystem', '@id': args.system_id})
                if not isinstance(values, list) or any(not isinstance(x, dict) for x in values):
                    raise IPCError('invalid parameter list')
                output = {'target': system, 'parameters': values,
                          'warning': 'Active database identity and parameter units require user confirmation.'}
            else:
                output = calculate(client, args)
            if automatic or args.start_local:
                output['connection'] = {'mode': 'guarded-autostart' if args.start_local else 'automatic',
                    'host': '127.0.0.1', 'port': client.port,
                    'identity_verification': 'guarded_temporary_clone' if args.start_local else 'protocol_probe_only_not_authenticated'}
                if args.start_local:
                    output['connection']['database_name'] = args.database
        print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (IPCError, OSError, ValueError, OverflowError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
