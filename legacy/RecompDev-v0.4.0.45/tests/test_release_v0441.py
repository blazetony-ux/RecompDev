"""v0441 release-boundary checks: runtime semantics and owner command wiring."""
import unittest
from pathlib import Path
from tooling.release_contract import assert_entrypoints,version
R=Path(__file__).resolve().parents[1]
class Release441Tests(unittest.TestCase):
 def test_release_entrypoints(self):
  self.assertEqual(version(R),(R/'RELEASE_VERSION').read_text().strip())
  self.assertEqual(assert_entrypoints(R),version(R))
  self.assertTrue((R/'Verify-v0441.ps1').is_file())
 def test_owner_tests_preserve_existing_shared_db(self):
  script=(R/'tools/Test-Native-Interaction-v0441.py').read_text()
  for key in ('generation.json','translated.cpp','original_source_sha256','native_app_sha256',
              'nmi_events','EVIDENCE_ZIP=','SHA','start_timeline','--button'):
   if key=='SHA':key='sha256'
   self.assertIn(key,script)
  self.assertNotIn('catalogue.sqlite',script)
 def test_full_campaign_is_versioned_and_compares_against_040(self):
  script=(R/'tools/Run-SMS-Campaign-v0441.py').read_text()
  for term in ('RecompDev-v0.4.0.41','Run-Continuous-Recovery-v0441.py',
               'baselines','sms-seven-v0440.json','v0440-comparison.json','EVIDENCE_ZIP='):
   self.assertIn(term,script)
  self.assertTrue((R/'baselines/sms-seven-v0440.json').is_file())
 def test_compiled_verification_runs_new_semantic_gates(self):
  script=(R/'Verify-v0441.ps1').read_text()
  for term in ('FILE_SHA256_v0441.json','test_generated_start_replay_v0441.py',
               'test_sms_pause_nmi_v0441.py','test_native_interaction_v0441.py',
               'test_interaction_refresh_v0441.py','Validate-Native-Outputs-v0437.py'):
   self.assertIn(term,script)
 def test_generic_host_has_no_rom_title_case(self):
  for path in ('systems/mastersystem/runtime.cpp','nativepilot/live_sms.hpp',
               'nativepilot/interactive.cpp'):
   source=(R/path).read_text().lower()
   for name in ('r-type','shinobi','wonder boy','bank panic'):
    self.assertNotIn(name,source)
if __name__=='__main__':unittest.main()
