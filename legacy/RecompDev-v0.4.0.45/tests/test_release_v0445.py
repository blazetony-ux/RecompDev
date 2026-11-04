"""v0.4.0.45 distribution contract: Windows CMake/PSG compiler portability and immutable release."""
import unittest
from pathlib import Path
from tooling.release_contract import version,assert_entrypoints

ROOT=Path(__file__).resolve().parents[1]

class Release445Tests(unittest.TestCase):
    def test_release_identity(self):
        self.assertEqual(version(ROOT),'0.4.0.45')
        self.assertEqual(assert_entrypoints(ROOT),'0.4.0.45')
    def test_current_versioned_entrypoints_present(self):
        for rel in ('Verify-v0445.ps1','tools/Run-SMS-Campaign-v0445.py',
                    'tools/Run-Continuous-Recovery-v0445.py',
                    'tools/View-Native-Output-v0445.py','tools/Test-Native-Interaction-v0445.py',
                    'tools/Verify-SQLite-Lifecycle-v0445.py'):
            self.assertTrue((ROOT/rel).is_file(),rel)
    def test_recovery_uses_explicit_close_and_persistent_cache(self):
        src=(ROOT/'tools/Run-Continuous-Recovery-v0445.py').read_text()
        self.assertIn('with closing(sqlite3.connect(str(db))) as con:',src)
        self.assertIn('coverage_path(root,a.coverage_cache)',src)
        self.assertIn('RecompDev v0.4.0.45 - seven-game authentic ROM campaign',(ROOT/'tools/Run-SMS-Campaign-v0445.py').read_text())
        self.assertIn("'verified-coverage-v0443.sqlite'",(ROOT/'nativecore/verified_coverage_v0443.py').read_text())
    def test_compiler_portability_gate(self):
        fixture=(ROOT/'tests/test_sms_psg_v0443.py').read_text()
        self.assertIn('run_cpp_fixture(SOURCE,ROOT,Path(d))',fixture)
        self.assertNotIn("compiler or 'cl'",fixture)
        s=(ROOT/'Verify-v0445.ps1').read_text()
        self.assertIn('test_compiler_portability_v0445.py',s)
    def test_new_verifier_fails_closed_for_sqlite_leaks(self):
        s=(ROOT/'Verify-v0445.ps1').read_text()
        self.assertIn('Verify-SQLite-Lifecycle-v0445.py',s)
        self.assertIn('test_sqlite_lifecycle_v0444.py',s)
        self.assertIn('test_verified_coverage_v0443.py',s)

if __name__=='__main__':unittest.main()
