"""v0.4.0.44 distribution contract: Windows SQLite handles and immutable release."""
import unittest
from pathlib import Path
from tooling.release_contract import version,assert_entrypoints

ROOT=Path(__file__).resolve().parents[1]

class Release444Tests(unittest.TestCase):
    def test_release_identity(self):
        self.assertGreaterEqual(int(version(ROOT).split('.')[-1]),44)
        self.assertEqual(assert_entrypoints(ROOT),version(ROOT))
    def test_current_versioned_entrypoints_present(self):
        for rel in ('Verify-v0444.ps1','tools/Run-SMS-Campaign-v0444.py',
                    'tools/Run-Continuous-Recovery-v0444.py',
                    'tools/View-Native-Output-v0444.py','tools/Test-Native-Interaction-v0444.py',
                    'tools/Verify-SQLite-Lifecycle-v0444.py'):
            self.assertTrue((ROOT/rel).is_file(),rel)
    def test_recovery_uses_explicit_close_and_persistent_cache(self):
        src=(ROOT/'tools/Run-Continuous-Recovery-v0444.py').read_text()
        self.assertIn('with closing(sqlite3.connect(str(db))) as con:',src)
        self.assertIn('coverage_path(root,a.coverage_cache)',src)
        self.assertIn('RecompDev v0.4.0.44 - seven-game authentic ROM campaign',(ROOT/'tools/Run-SMS-Campaign-v0444.py').read_text())
        self.assertIn("'verified-coverage-v0443.sqlite'",(ROOT/'nativecore/verified_coverage_v0443.py').read_text())
    def test_new_verifier_fails_closed_for_sqlite_leaks(self):
        s=(ROOT/'Verify-v0444.ps1').read_text()
        self.assertIn('Verify-SQLite-Lifecycle-v0444.py',s)
        self.assertIn('test_sqlite_lifecycle_v0444.py',s)
        self.assertIn('test_verified_coverage_v0443.py',s)

if __name__=='__main__':unittest.main()
