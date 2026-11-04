import unittest
from pathlib import Path
from tooling.release_contract import assert_entrypoints,version
R=Path(__file__).resolve().parents[1]
class Release438(unittest.TestCase):
 def test_active_entrypoints(self):self.assertEqual(assert_entrypoints(R),version(R))
 def test_four_verification_gates_and_compiled_conditional(self):
  s=(R/'Verify-v0438.ps1').read_text()
  for term in ('FILE_SHA256_v0438.json','Validate-v0438.py','test_*.py','bridge/tests'):
   self.assertIn(term,s)
  compiled=(R/'tools/Validate-v0438.py').read_text()
  for x in ('test_conditional_control_dev.py','test_sms_th_feedback_dev.py','Validate-v0437.py'):
   self.assertIn(x,compiled)
 def test_catalogue_and_seven_game_campaign(self):
  launch=(R/'Run-Workbench.ps1').read_text()
  for x in ('catalogue.v0438-working.sqlite','RecompDev-v0.4.0.37'):
   self.assertIn(x,launch)
  s=(R/'tools/Run-SMS-Campaign-v0438.py').read_text()
  for x in ('sms-seven-v0436.json','baseline-comparison.json','EVIDENCE_ZIP=','shinobi','r-type','Run-Continuous-Recovery-v0436.py'):
   self.assertIn(x,s)
 def test_no_rom_specific_translation_guard(self):
  s=(R/'nativepilot/generator.py').read_text().lower()
  for name in ('shinobi','alex kidd','bank panic','wonder boy','fantasy zone'):
   self.assertNotIn(name,s)
if __name__=='__main__':unittest.main()
