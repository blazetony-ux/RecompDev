"""v0436 release contracts survive future versions; no hard-pinned active version."""
import unittest
from pathlib import Path
from tooling.release_contract import assert_entrypoints,version
ROOT=Path(__file__).resolve().parents[1]
class Release436(unittest.TestCase):
 def test_release_version_and_entrypoints(self):
  self.assertEqual(assert_entrypoints(ROOT),version(ROOT))
 def test_verification_retains_four_gates(self):
  script=(ROOT/'Verify-v0436.ps1').read_text()
  for name in ('FILE_SHA256_v0436.json','Validate-v0436.py','test_*.py','bridge/tests'):
   self.assertIn(name,script)
 def test_catalogue_migrates_0435(self):
  launch=(ROOT/'Run-Workbench.ps1').read_text()
  self.assertIn('catalogue.v0436-working.sqlite',launch)
  self.assertIn('RecompDev-v0.4.0.35',launch)
 def test_campaign_starts_with_shinobi_and_continues(self):
  campaign=(ROOT/'tools/Run-SMS-Campaign-v0436.py').read_text()
  for name in ('shinobi','bank-panic','alex-kidd','fantasy-zone','r-type','sonic-sms','wonder-boy'):
   self.assertIn(name,campaign)
  self.assertIn('compile-timeout',campaign)
  self.assertIn('EVIDENCE_ZIP=',campaign)
 def test_no_game_hacks_or_false_alignment(self):
  for file in ('nativecore/continuous_recovery_v0436.py','nativecore/session_triage_v0436.py'):
   data=(ROOT/file).read_text().lower()
   for game in ('shinobi','sonic','alex kidd','bank panic'):
    self.assertNotIn(game,data)
  self.assertIn("'root_cause':'NOT_ESTABLISHED'",(ROOT/'nativecore/session_triage_v0436.py').read_text())
if __name__=='__main__':unittest.main()
