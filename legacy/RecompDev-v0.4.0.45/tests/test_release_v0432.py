"""Consolidated release qualification does not equate compiled subsets with games."""
import json,unittest
from pathlib import Path
import sys
from tooling.release_contract import version
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tooling.gates_v0432 import run
class Release432(unittest.TestCase):
 def test_active_release_and_previous_catalogue_preserved(self):
  self.assertIn('VERSION '+version(ROOT),(ROOT/'nativepilot/CMakeLists.txt').read_text())
  self.assertIn('catalogue.v0435-working.sqlite',(ROOT/'Run-Workbench.ps1').read_text())
  self.assertIn('RecompDev-v0.4.0.31',(ROOT/'Run-Workbench.ps1').read_text())
  self.assertIn('FILE_SHA256_v0433.json',(ROOT/'Verify-v0433.ps1').read_text())
  self.assertIn('BUILD_VALIDATION_v0435.json',(ROOT/'workbench.py').read_text())
 def test_generic_engine_native_only_with_boundary(self):
  src=(ROOT/'multisa/native.py').read_text()
  self.assertIn('UNSUPPORTED_TRANSLATION',src)
  self.assertIn('source SHA-256 mismatch',src)
  self.assertIn('generated translation changed',src)
  self.assertIn('MIPS delay slot unsupported',src)
  gate=run(run_tests=False)
  self.assertEqual(gate['release'],'0.4.0.32')
  self.assertFalse(gate['native_qualified'])
  self.assertEqual(gate['milestones']['AUTHENTIC_NONZ80_NATIVE_COMPILATION'],'NOT_ESTABLISHED')
 def test_common_tooling_does_not_contain_game_specific_repair(self):
  for name in ('multisa/native.py','multisa/campaign.py','multisa/checkpoints.py','multisa/triage.py'):
   text=(ROOT/name).read_text().lower()
   for game in ('shinobi','sonic','ridge racer','streets of rage'):
    self.assertNotIn(game,text)
  self.assertIn('compare-checkpoints',(ROOT/'recomp.py').read_text())
  self.assertIn('universal-campaign',(ROOT/'recomp.py').read_text())

if __name__=='__main__':unittest.main()
