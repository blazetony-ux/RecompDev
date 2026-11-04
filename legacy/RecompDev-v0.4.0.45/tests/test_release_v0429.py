"""v0.4.0.29 regression: synthetic preparation without host-installed Ghidra."""
import unittest
from pathlib import Path
from discovery.workbench_jobs import DiscoveryController
from tooling.gates_v0429 import run
from tooling.release_contract import version
ROOT=Path(__file__).resolve().parents[1]

class WorkerLifetimeReleaseTests(unittest.TestCase):
 def test_release_and_default_real_analysis(self):
  self.assertIn('VERSION '+version(ROOT),(ROOT/'nativepilot/CMakeLists.txt').read_text())
  self.assertIn('catalogue.v0432-working.sqlite',(ROOT/'Run-Workbench.ps1').read_text())
  self.assertIn('FILE_SHA256_v0429.json',(ROOT/'Verify-v0429.ps1').read_text())
  self.assertIn('BUILD_VALIDATION_v0435.json',(ROOT/'workbench.py').read_text())
  self.assertTrue(DiscoveryController(ROOT,ROOT/'catalogue.sqlite',[]).native_prepare_analysis)
  self.assertFalse(DiscoveryController(ROOT,ROOT/'catalogue.sqlite',[],False).native_prepare_analysis)
 def test_browser_fixture_explicitly_isolates_ghidra(self):
  t=(ROOT/'tests/test_native_preparation_v0403.py').read_text()
  self.assertIn("'--native-prepare-register-only'",t)
  self.assertIn('native-prepare-cancel',t)
  self.assertIn('time.monotonic()+45',t)
  c=(ROOT/'discovery/workbench_jobs.py').read_text()
  self.assertIn("argv.append('--no-analysis')",c)
  self.assertIn('proc.wait(timeout=5)',c)
  e=(ROOT/'nativeprep/engine.py').read_text()
  self.assertIn("p.add_argument('--no-analysis'",e)
 def test_truthful_gate(self):
  result=run(run_tests=False)
  self.assertFalse(result['native_qualified'])
  self.assertEqual(result['milestones']['SHINOBI_GAMEPLAY'],'NOT_ESTABLISHED')
  self.assertEqual(result['release'],'0.4.0.29')
if __name__=='__main__':unittest.main()
