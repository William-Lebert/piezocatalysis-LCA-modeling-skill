"""Exercise the benchmark CLI with deterministic stand-ins for the openLCA rerun."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'tests/benchmark_scenario_suite.py'
RERUN = """
import json
import sys
from pathlib import Path

assert sys.argv[1] == 'rerun'
payload = json.loads(Path(sys.argv[2]).read_bytes())
capture = payload['cases'][0]['capture']
calc = capture['coverage']['calculation']
# The values and their derived digests naturally differ between executions.
role = Path(__file__).parents[1].name
calc.update(calculated_at_utc=role, result_id=role)
capture.update(coverage_sha256=role, calculation_sha256=role)
if role == 'bad':
    capture['snapshot_sha256'] = 'changed'
Path(sys.argv[sys.argv.index('--output') + 1]).write_text(json.dumps(payload), encoding='utf-8')
"""


class BenchmarkScenarioSuiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for role in ('baseline', 'candidate', 'bad'):
            scripts = self.root / role / 'scripts'
            scripts.mkdir(parents=True)
            (scripts / 'scenario_suite.py').write_text(RERUN, encoding='utf-8')
        capture = dict.fromkeys(('system_reference', 'snapshot_sha256', 'provider_snapshot_hashes',
                                 'provider_snapshots_sha256', 'method_snapshot_sha256',
                                 'category_snapshot_sha256', 'parameters_sha256'), 'stable')
        capture['coverage'] = {'calculation': {'impacts': [{'amount': 3.2, 'contributions': [{}]}],
                                               'total_flows': [{}]}}
        self.archive = self.root / 'archived suite.json'
        self.archive.write_text(json.dumps({'cases': [{'capture': capture}]}), encoding='utf-8')

    def invoke(self, role, output, *extra):
        command = [sys.executable, str(RUNNER), '--baseline-skill', str(self.root / 'baseline'),
                   '--candidate-skill', str(self.root / role), '--suite', 'synthetic', str(self.archive),
                   '--workspace', str(self.root), '--output', str(output), *extra]
        return subprocess.run(command, capture_output=True, text=True, timeout=20)

    def test_alternates_version_order_and_writes_one_summary(self):
        output = self.root / 'run results'
        result = self.invoke('candidate', output, '--suite', 'other', str(self.archive))
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads((output / 'summary.json').read_bytes())
        self.assertEqual([(r['suite'], r['round'], r['version']) for r in summary['runs']], [
            ('synthetic', 1, 'baseline'), ('synthetic', 1, 'candidate'),
            ('other', 1, 'baseline'), ('other', 1, 'candidate'),
            ('other', 2, 'candidate'), ('other', 2, 'baseline'),
            ('synthetic', 2, 'candidate'), ('synthetic', 2, 'baseline'),
        ])
        synthetic = summary['suites']['synthetic']
        self.assertEqual((synthetic['exact_lcia_amounts'], synthetic['exact_contributions'],
                          synthetic['exact_inventory_rows']), (1, 1, 1))
        self.assertEqual(len(synthetic['reference_sha256']), 64)
        duplicate = self.invoke('candidate', output)
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertEqual(json.loads((output / 'summary.json').read_bytes()), summary)

    def test_snapshot_mismatch_fails_without_success_summary(self):
        output = self.root / 'mismatch'
        result = self.invoke('bad', output, '--rounds', '1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('synthetic-r1-candidate: LCIA, snapshot or other stable capture fields differ', result.stderr)
        self.assertTrue((output / 'manifest.json').is_file())
        self.assertTrue((output / 'synthetic-r1-candidate.json').is_file())
        self.assertFalse((output / 'summary.json').exists())
