"""Structural validation and CLI failure behavior for model specifications."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'piezocatalysis-lca-modeling/scripts/validate_model_spec.py'
TEMPLATE = ROOT / 'piezocatalysis-lca-modeling/assets/templates/model_spec.template.json'
spec = importlib.util.spec_from_file_location('model_spec', SCRIPT)
validator = importlib.util.module_from_spec(spec); spec.loader.exec_module(validator)

class ModelSpecTests(unittest.TestCase):
    def setUp(self): self.data = json.loads(TEMPLATE.read_text())
    def test_template_is_structurally_valid(self): self.assertEqual(validator.validate(self.data), [])
    def test_bad_types_do_not_crash_and_are_rejected(self):
        for key in ('study', 'functional_unit', 'system_boundary', 'lcia', 'data_policy'):
            data = copy.deepcopy(self.data); data[key] = []
            with self.subTest(key=key): self.assertTrue(validator.validate(data))
        self.assertTrue(validator.validate([]))
        for field in ('mode',):
            data = copy.deepcopy(self.data); data['systems'][0][field] = []
            self.assertTrue(validator.validate(data))
        data = copy.deepcopy(self.data); data['systems'][0]['foreground_inventory'][0]['evidence_class'] = []
        self.assertTrue(validator.validate(data))
    def test_invalid_amounts(self):
        for value in [float('nan'), float('inf'), -1, 0, True, '1', None]:
            data = copy.deepcopy(self.data); data['functional_unit']['amount'] = value
            with self.subTest(value=value): self.assertTrue(validator.validate(data))
    def test_bad_foreground_fields(self):
        for key, value in [('value', float('nan')), ('value', '1'), ('unit', ''), ('source', ''),
                           ('stage', ''), ('direction', 'sideways'), ('evidence_class', 'unknown')]:
            data = copy.deepcopy(self.data); data['systems'][0]['foreground_inventory'][0][key] = value
            with self.subTest(key=key): self.assertTrue(validator.validate(data))
    def test_invalid_json_cli_has_no_traceback(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'bad.json'; p.write_text('{bad')
            result = subprocess.run([sys.executable, str(SCRIPT), str(p)], text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0); self.assertNotIn('Traceback', result.stderr)
    def test_nonstandard_json_constant_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'bad.json'; p.write_text('{"extra": NaN}')
            result = subprocess.run([sys.executable, str(SCRIPT), str(p)], text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0); self.assertIn('non-standard', result.stderr)
    def test_template_placeholder_warning_and_strict_mode(self):
        normal = subprocess.run([sys.executable, str(SCRIPT), str(TEMPLATE)], text=True, capture_output=True)
        strict = subprocess.run([sys.executable, str(SCRIPT), str(TEMPLATE), '--reject-placeholders'], text=True, capture_output=True)
        self.assertEqual(normal.returncode, 0); self.assertIn('WARNING', normal.stdout)
        self.assertNotEqual(strict.returncode, 0)
    def test_strict_mode_accepts_structurally_valid_synthetic_data(self):
        def replace(value):
            if isinstance(value, dict): return {k: replace(v) for k, v in value.items()}
            if isinstance(value, list): return [replace(v) for v in value]
            if isinstance(value, str): return value.replace('replace-me', 'synthetic example')
            return value
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'synthetic.json'; p.write_text(json.dumps(replace(self.data)))
            result = subprocess.run([sys.executable, str(SCRIPT), str(p), '--reject-placeholders'], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('scientific completeness is not assessed', result.stdout)

if __name__ == '__main__': unittest.main()
