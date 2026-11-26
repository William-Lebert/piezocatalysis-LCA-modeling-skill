"""Measure and compare archived openLCA scenario reruns across two Skill copies."""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'piezocatalysis-lca-modeling'
sys.path.insert(0, str(SKILL / 'scripts'))
from openlca_local_launch import digest as file_digest
from scenario_binding import digest as result_digest

SNAPSHOTS = ('system_reference', 'snapshot_sha256', 'provider_snapshot_hashes',
             'provider_snapshots_sha256', 'method_snapshot_sha256',
             'category_snapshot_sha256', 'parameters_sha256')


def write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def run_rerun(script, archive, workspace, app, output, timeout):
    command = [sys.executable, str(script), 'rerun', str(archive), '--workspace',
               str(workspace), '--openlca-app', str(app), '--output', str(output)]
    start = time.perf_counter()
    # Keep the command's errors with the run rather than including raw case data in the summary.
    with output.with_suffix('.log').open('x', encoding='utf-8') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
    elapsed = time.perf_counter() - start
    if result.returncode:
        raise ValueError(f'rerun failed with exit code {result.returncode}; see {log.name}')
    return elapsed


def observe_output(path):
    suite = json.loads(path.read_bytes())
    counts = dict(scenarios=len(suite['cases']), exact_lcia_amounts=0,
                  exact_contributions=0, exact_inventory_rows=0, exact_snapshot_fields=SNAPSHOTS)
    for case in suite['cases']:
        capture = case['capture']
        if any(key not in capture for key in SNAPSHOTS):
            raise ValueError(f'snapshot fields missing in {path.name}')
        calc = capture['coverage']['calculation']
        counts['exact_lcia_amounts'] += len(calc['impacts'])
        counts['exact_contributions'] += sum(len(row['contributions']) for row in calc['impacts'])
        counts['exact_inventory_rows'] += len(calc['total_flows'])
        for key in ('calculated_at_utc', 'result_id'):
            del calc[key]
        for key in ('coverage_sha256', 'calculation_sha256'):
            del capture[key]
    return result_digest(suite), counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-skill', required=True, type=Path, help='baseline installable Skill directory')
    parser.add_argument('--candidate-skill', type=Path, default=SKILL, help='candidate installable Skill directory')
    parser.add_argument('--suite', nargs=2, action='append', required=True, metavar=('NAME', 'ARCHIVE'),
                        help='named suite archive produced by scenario_suite.py; repeat for more suites')
    parser.add_argument('--workspace', type=Path, required=True, help='local openLCA data workspace')
    parser.add_argument('--openlca-app', type=Path, default=Path('/Applications/openLCA.app'))
    parser.add_argument('--rounds', type=int, default=2)
    parser.add_argument('--timeout', type=int, default=180, help='seconds allowed for each rerun')
    parser.add_argument('--output', type=Path, required=True, help='new directory for local benchmark evidence')
    args = parser.parse_args()
    if args.rounds < 1 or args.timeout < 1:
        parser.error('--rounds and --timeout must be positive')
    suites = {}
    for name, path in args.suite:
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', name) or name.lower() in suites:
            parser.error('suite names must be distinct and use letters, digits, hyphens or underscores')
        suites[name.lower()] = Path(path).resolve()
    skills = {'baseline': args.baseline_skill.resolve(), 'candidate': args.candidate_skill.resolve()}
    scripts = {version: root / 'scripts/scenario_suite.py' for version, root in skills.items()}
    try:
        reference_hashes = {name: file_digest(path) for name, path in suites.items()}
        fingerprints = {version: {'path': str(skills[version]), 'scenario_suite_sha256': file_digest(script)}
                        for version, script in scripts.items()}
        for version, root in skills.items():
            guard = root / 'scripts/openlca_guard/localhost-agent.jar'
            if guard.is_file():
                fingerprints[version]['guard_sha256'] = file_digest(guard)
        summary = {'skills': fingerprints, 'workspace': str(args.workspace.resolve()),
                   'openlca_app': str(args.openlca_app.resolve()), 'rounds': args.rounds,
                   'timeout_seconds': args.timeout, 'suites': {
                       name: {'archive': str(path), 'reference_sha256': reference_hashes[name]}
                       for name, path in suites.items()},
                   'runs': []}
        args.output.mkdir()
        write_json(args.output / 'manifest.json', summary)
        checksums = {}
        times = {name: {version: [] for version in skills} for name in suites}
        for number in range(1, args.rounds + 1):
            order = tuple(skills) if number % 2 else tuple(reversed(skills))
            cases = tuple(suites) if number % 2 else tuple(reversed(suites))
            for name in cases:
                for version in order:
                    label = f'{name}-r{number}-{version}'
                    output = args.output / (label + '.json')
                    elapsed = run_rerun(scripts[version], suites[name], args.workspace.resolve(),
                                        args.openlca_app.resolve(), output, args.timeout)
                    if file_digest(suites[name]) != reference_hashes[name]:
                        raise ValueError(f'{name}: reference archive changed during benchmarking')
                    observed, counts = observe_output(output)
                    if checksums.setdefault(name, observed) != observed:
                        raise ValueError(f'{label}: LCIA, snapshot or other stable capture fields differ')
                    summary['suites'][name].update(counts, stable_capture_sha256=observed)
                    times[name][version].append(elapsed)
                    summary['runs'].append(dict(suite=name, round=number, version=version,
                                                end_to_end_seconds=elapsed, output=output.name))
                    print(f'{label} {elapsed:.3f}s', flush=True)
        for name, measurements in times.items():
            row = summary['suites'][name]
            for version, values in measurements.items():
                row[version] = dict(runs_seconds=values, mean_seconds=mean(values))
            row['change_percent'] = 100 * (row['candidate']['mean_seconds'] / row['baseline']['mean_seconds'] - 1)
        report = args.output / 'summary.json'
        write_json(report, summary)
        print(report)
        return 0
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
