"""Current version is single-sourced; inherited release tests are not hard-pinned."""
import unittest
from pathlib import Path
from tooling.release_contract import version,assert_entrypoints
ROOT=Path(__file__).resolve().parents[1]
class Release435(unittest.TestCase):
 def test_active_version_and_manifest_verifier(self):
  self.assertEqual(assert_entrypoints(ROOT),version(ROOT))
  self.assertRegex(version(ROOT),r'^0\.4\.0\.[0-9]+$')
  verify=(ROOT/'Verify-v0435.ps1').read_text()
  for name in ('FILE_SHA256_v0435.json','Validate-v0435.py',"test_*.py",'bridge/tests'):
   self.assertIn(name,verify)
  self.assertIn('Run-Workbench.ps1',(ROOT/'README-v0435.md').read_text())
 def test_catalogue_migration_includes_previous_installations(self):
  launcher=(ROOT/'Run-Workbench.ps1').read_text()
  self.assertIn('catalogue.v0435-working.sqlite',launcher)
  self.assertIn('RecompDev-v0.4.0.34',launcher)
  self.assertIn('RecompDev-v0.4.0.33',launcher)
 def test_generic_recovery_and_guarded_parity(self):
  code=(ROOT/'nativecore/continuous_recovery_v0435.py').read_text().lower()
  for game in ('shinobi','bank panic','alex kidd','sonic'):
   self.assertNotIn(game,code)
  self.assertIn('verify_export',code)
  self.assertIn('recoveryplanner',code)
  self.assertIn('not_tested',code)
  triage=(ROOT/'nativecore/hardware_triage_v0435.py').read_text()
  self.assertIn("'root_cause':'NOT_ESTABLISHED'",triage)
if __name__=='__main__':unittest.main()
