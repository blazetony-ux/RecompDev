"""New release must be numbered, generic, and continue to fail closed on parity."""
import unittest
from pathlib import Path
from tooling.gates_v0433 import run
from tooling.release_contract import version
ROOT=Path(__file__).resolve().parents[1]
class Release433(unittest.TestCase):
 def test_release_versions_and_catalogue_migration(self):
  self.assertIn('VERSION '+version(ROOT),(ROOT/'nativepilot/CMakeLists.txt').read_text())
  self.assertIn('catalogue.v0435-working.sqlite',(ROOT/'Run-Workbench.ps1').read_text())
  self.assertIn('RecompDev-v0.4.0.32',(ROOT/'Run-Workbench.ps1').read_text())
  self.assertIn('FILE_SHA256_v0433.json',(ROOT/'Verify-v0433.ps1').read_text())
  self.assertIn('BUILD_VALIDATION_v0435.json',(ROOT/'workbench.py').read_text())
  info=run(run_tests=False)
  self.assertEqual(info['release'],'0.4.0.33');self.assertFalse(info['native_qualified'])
 def test_cpu_and_hardware_fixes_are_not_game_overrides(self):
  for name in ('nativepilot/z80_cycles.hpp','systems/mastersystem/counters.hpp',
               'systems/mastersystem/runtime.cpp','nativecore/sms_startup_v0433.py'):
   data=(ROOT/name).read_text().lower()
   for word in ('shinobi','sonic','ridge racer','streets of rage'):
    self.assertNotIn(word,data)
  self.assertEqual(run(run_tests=False)['milestones']['Z80_INDEPENDENT_INSTRUCTION_PARITY'],'NOT_ESTABLISHED')
if __name__=='__main__':unittest.main()
