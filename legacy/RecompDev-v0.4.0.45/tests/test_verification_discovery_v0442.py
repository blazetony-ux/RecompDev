"""Regression: 'Ran 0 tests ... OK' must always be a verification failure."""
import importlib.util
import re
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('verify_discovery',ROOT/'tools/Verify-Test-Discovery-v0442.py')
gate=importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

class DiscoveryGateTests(unittest.TestCase):
    def test_missing_pattern_is_fatal(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'Missing regression file'):
                gate.count_discovered(d,'test_does_not_exist.py')
    def test_empty_test_module_is_fatal(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'test_empty.py').write_text('import unittest\n')
            with self.assertRaisesRegex(ValueError,'Zero tests discovered'):
                gate.count_discovered(d,'test_empty.py')
    def test_import_failure_is_fatal(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'test_broken.py').write_text('import definitely_missing_module_v0442\n')
            with self.assertRaisesRegex(ValueError,'Import or discovery errors'):
                gate.count_discovered(d,'test_broken.py')
    def test_nonempty_module_is_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'test_positive_v0442.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_ok(self): pass\n')
            self.assertEqual(gate.count_discovered(d,'test_positive_v0442.py'),1)
    def test_release_verifier_references_real_test_files(self):
        text=(ROOT/'Verify-v0442.ps1').read_text()
        patterns=set(re.findall(r"test_[a-z_0-9]+\.py",text))
        self.assertIn('test_windows_native_stack_v0440.py',patterns)
        self.assertIn('test_native_process_exit_v0440.py',patterns)
        self.assertIn('test_staged_recovery_v0440.py',patterns)
        self.assertIn('Verify-Test-Discovery-v0442.py',text)
        for pat in patterns:self.assertTrue((ROOT/'tests'/pat).is_file(),pat)
if __name__=='__main__':unittest.main()
