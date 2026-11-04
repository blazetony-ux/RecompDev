"""v0442 release contract preserves v0441 native interaction and fixes Windows verification discovery."""
import unittest
from pathlib import Path
from tooling.release_contract import assert_entrypoints,version
R=Path(__file__).resolve().parents[1]
class Release442Tests(unittest.TestCase):
 def test_release_entrypoints(self):
  self.assertEqual(version(R),'0.4.0.42')
  self.assertEqual(assert_entrypoints(R),'0.4.0.42')
  for path in ('Verify-v0442.ps1','tools/Run-SMS-Campaign-v0442.py','tools/Run-Continuous-Recovery-v0442.py','tools/Test-Native-Interaction-v0442.py'):
   self.assertTrue((R/path).is_file(),path)
 def test_stack_and_replay_brought_forward(self):
  src=(R/'nativepilot/CMakeLists.txt').read_text()
  self.assertIn('target_link_options(RecompDevNativeApp PRIVATE /STACK:8388608)',src)
  runner=(R/'tools/Test-Native-Interaction-v0442.py').read_text()
  for phrase in ('native-interaction-v0442','recomp-native-interaction-v0442','service_pending_console_nmi','GUEST_CLOCK'):
   if phrase=='service_pending_console_nmi':
    self.assertIn(phrase,(R/'systems/mastersystem/runtime.cpp').read_text())
   else:self.assertIn(phrase,runner)
if __name__=='__main__':unittest.main()
