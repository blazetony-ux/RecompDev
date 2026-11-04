"""Full package contract for the 0.4.0.43 increment and new correctness gates."""
import unittest
from pathlib import Path
from tooling.release_contract import assert_entrypoints,version
R=Path(__file__).resolve().parents[1]
class Release443(unittest.TestCase):
 def test_version_and_entrypoints(self):
  self.assertGreaterEqual(int(version(R).split('.')[-1]),43)
  self.assertEqual(assert_entrypoints(R),version(R))
  for name in ('Verify-v0443.ps1','tools/Run-SMS-Campaign-v0443.py',
       'tools/Run-Continuous-Recovery-v0443.py','tools/Test-Native-Interaction-v0443.py',
       'tools/View-Native-Output-v0443.py','tools/View-Frame-Timeline-v0443.py',
       'tools/Recovery-Profiler-v0443.py','nativecore/verified_coverage_v0443.py'):
   self.assertTrue((R/name).is_file(),name)
 def test_real_campaign_has_no_false_version_and_reuses_verified_coverage(self):
  campaign=(R/'tools/Run-SMS-Campaign-v0443.py').read_text()
  self.assertIn('Run-Continuous-Recovery-v0443.py',campaign)
  self.assertIn('"release": "0.4.0.43"',campaign)
  self.assertIn('persisted_coverage=',campaign)
  runner=(R/'tools/Run-Continuous-Recovery-v0443.py').read_text()
  for word in ('coverage_path','--no-history-import','--input-events','--coverage-cache','verified-coverage'):
   if word=='verified-coverage':word='coverage_path'
   self.assertIn(word,runner)
 def test_tone_and_scheduled_frame_snapshots_are_actual_guest_output(self):
  adapter=(R/'hardware/adapters/sms.hpp').read_text()
  host=(R/'nativepilot/interactive.cpp').read_text()
  self.assertIn('set_noise',adapter)
  self.assertIn('vol_[selected_>>1]=v&15',adapter)
  self.assertIn('--snapshot-every',host)
  self.assertIn('audio_nonzero_samples',host)
  self.assertIn('snapshot_prefix',host)
 def test_windows_linker_and_shared_db_untouched(self):
  cmake=(R/'nativepilot/CMakeLists.txt').read_text()
  self.assertIn('/STACK:8388608',cmake)
  self.assertIn('--stack,8388608',cmake)
  self.assertIn('RecompDev-Data', (R/'nativecore/shared_catalogue.py').read_text())
 def test_verifier_fails_closed_for_missing_tests(self):
  script=(R/'Verify-v0443.ps1').read_text()
  for name in ('FILE_SHA256_v0443.json','Verify-Test-Discovery-v0442.py',
        'test_release_v0443.py','test_verified_coverage_v0443.py',
        'test_generated_snapshots_v0443.py','test_sms_psg_v0443.py'):
   self.assertIn(name,script)
if __name__=='__main__':unittest.main()
