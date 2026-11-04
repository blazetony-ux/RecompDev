"""v0.4.0.30 independent-version and cross-ISA qualification contracts."""
import unittest
from pathlib import Path
import sys
from tooling.release_contract import version
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tooling.gates_v0430 import run

class Release430(unittest.TestCase):
 def test_current_release_versioned_entrypoints(self):
  self.assertIn('VERSION '+version(ROOT),(ROOT/'nativepilot/CMakeLists.txt').read_text())
  self.assertIn('v'+version(ROOT),(ROOT/'static/tooling.html').read_text())
  self.assertIn('catalogue.v0435-working.sqlite',(ROOT/'Run-Workbench.ps1').read_text())
  self.assertIn('FILE_SHA256_v0430.json',(ROOT/'Verify-v0430.ps1').read_text())
  self.assertIn('BUILD_VALIDATION_v0435.json',(ROOT/'workbench.py').read_text())
  self.assertIn("'release':'"+version(ROOT)+"'",(ROOT/'workbench.py').read_text())
 def test_real_game_baseline_not_claimed(self):
  gate=run(run_tests=False)
  self.assertFalse(gate['native_qualified'])
  self.assertEqual(gate['release'],'0.4.0.30')
  self.assertEqual(gate['milestones']['SONIC_AUTHENTIC_BEFORE_AFTER'],'OWNER_ROM_BENCHMARK_PENDING')
  self.assertEqual(gate['milestones']['NONZ80_NATIVE_GAME_COMPILATION'],'NOT_ESTABLISHED')
 def test_recovery_provenance_visible(self):
  self.assertIn('recovered_local_constant',(ROOT/'graph_store.py').read_text())
  self.assertIn('--recover-indirect',(ROOT/'recomp.py').read_text())
  self.assertIn('benchmark-discovery',(ROOT/'recomp.py').read_text())
  self.assertIn('native_history',(ROOT/'static/app.js').read_text())

if __name__=='__main__':unittest.main()
