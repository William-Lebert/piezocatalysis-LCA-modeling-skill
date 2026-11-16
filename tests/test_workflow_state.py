import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'piezocatalysis-lca-modeling' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from workflow_state import check, record


class WorkflowStateTests(unittest.TestCase):
    def test_upstream_input_change_blocks_downstream_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, inventory, result = (root / n for n in ('source', 'inventory', 'result'))
            source.write_text('original'); inventory.write_text('inventory'); result.write_text('result')
            foreground, downstream = root / 'foreground.json', root / 'result.json'
            record('foreground', [source], [inventory], [], foreground)
            record('execution', [inventory], [result], [foreground], downstream)
            self.assertEqual(check(downstream)['file_integrity'], 'PASS')
            self.assertEqual(check(downstream)['scientific_review'], 'NOT_EVALUATED')
            source.write_text('changed')
            self.assertEqual(check(downstream)['file_integrity'], 'BLOCKED')
            with self.assertRaisesRegex(ValueError, 'upstream state is stale'):
                record('reporting', [], [result], [downstream], root / 'new.json')

    def test_missing_outputs_and_existing_state_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); output = root / 'result'; output.write_text('result'); state = root / 'state.json'
            with self.assertRaisesRegex(ValueError, 'output file'):
                record('intake', [], [], [], state)
            record('intake', [], [output], [], state); original = state.read_bytes()
            with self.assertRaises(FileExistsError):
                record('intake', [], [output], [], state)
            self.assertEqual(state.read_bytes(), original)
            output.unlink()
            self.assertEqual(check(state)['file_integrity'], 'BLOCKED')

    def test_cli_status_does_not_imply_scientific_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); out = root / 'result'; out.write_text('synthetic')
            p = subprocess.run([sys.executable, str(SCRIPTS / 'workflow_state.py'), 'record', '--stage', 'foreground', '--output', str(out), '--state', str(root / 'state.json')], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(json.loads(p.stdout)['scientific_review'], 'NOT_EVALUATED')


if __name__ == '__main__':
    unittest.main()
