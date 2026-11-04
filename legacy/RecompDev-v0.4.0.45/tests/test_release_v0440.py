"""Active release and reusable v0440 acceptance contracts."""
import json,unittest
from pathlib import Path
from tooling.release_contract import assert_entrypoints,version
R=Path(__file__).resolve().parents[1]
class Release440(unittest.TestCase):
 def test_version_and_active_entrypoints(self):
  self.assertEqual(version(R),(R/'RELEASE_VERSION').read_text().strip())
  self.assertEqual(assert_entrypoints(R),version(R))
 def test_owner_scripts_and_real_previous_campaign(self):
  for p in ('Verify-v0440.ps1','Run-Workbench.ps1','tools/Run-SMS-Campaign-v0440.py',
      'tools/Run-Continuous-Recovery-v0440.py','tools/View-Native-Output-v0440.py',
      'baselines/sms-seven-v0439.json'):
   self.assertTrue((R/p).is_file(),p)
  baseline=json.loads((R/'baselines/sms-seven-v0439.json').read_text())
  self.assertEqual(baseline['release'],'0.4.0.39')
  self.assertEqual(len(baseline['games']),7)
  self.assertEqual({g['slug'] for g in baseline['games']},
                   {'shinobi','bank-panic','alex-kidd','fantasy-zone','r-type','sonic-sms','wonder-boy'})
 def test_owner_campaign_is_bounded_and_labeled(self):
  text=(R/'tools/Run-SMS-Campaign-v0440.py').read_text()
  for token in ('default=600','default=12','--extended','--max-recoveries',
                'v0439-comparison.json','frame-checkpoints.json','EVIDENCE_ZIP='):
   self.assertIn(token,text)
  self.assertIn('0.4.0.40',text)
 def test_no_game_specific_recovery_rules(self):
  for p in ('nativecore/continuous_recovery_v0436.py','nativecore/recovery.py','nativepilot/generator.py'):
   code=(R/p).read_text().lower()
   for name in ('sonic the hedgehog','shinobi','fantasy zone','bank panic'):
    self.assertNotIn(name,code,p)
 def test_windows_stack_is_in_generated_project_template(self):
  cmake=(R/'nativepilot/CMakeLists.txt').read_text()
  self.assertIn('VERSION '+version(R),cmake)
  self.assertIn('target_link_options(RecompDevNativeApp PRIVATE /STACK:8388608)',cmake)
if __name__=='__main__':unittest.main()
