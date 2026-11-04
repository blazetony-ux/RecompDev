"""Release-specific smoke tests for portable v0.4.0.27 batch verification."""
import sys,unittest
from pathlib import Path
from tooling.release_contract import version
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
class VersionContract(unittest.TestCase):
 def test_all_release_entrypoints_updated(self):
  self.assertRegex((ROOT/'nativepilot/CMakeLists.txt').read_text(),'VERSION '+version(ROOT))
  self.assertRegex((ROOT/'static/tooling.html').read_text(),'v'+version(ROOT))
  script=(ROOT/'Run-Workbench.ps1').read_text()
  self.assertRegex(script,r'catalogue\.v04[0-9]{2}-working\.sqlite')
  self.assertIn('RecompDev-v0.4.0.26',script)
  self.assertIn('FILE_SHA256_v0427.json',(ROOT/'Verify-v0427.ps1').read_text())
  self.assertRegex((ROOT/'workbench.py').read_text(),r'BUILD_VALIDATION_v04[0-9]{2}\.json')
  self.assertRegex((ROOT/'workbench.py').read_text(),"'release':'"+version(ROOT)+"'")
 def test_go_backend_test_avoids_posix_shell_dependency(self):
  test=(ROOT/'tests/test_batch_campaign.py').read_text()
  self.assertNotIn('#!/bin/sh',test)
  self.assertIn("patch('native_batch.subprocess.run'",test)
  self.assertIn('chqdev-windows-amd64.exe',test)
  self.assertIn('BACKEND_IDENTITY_MISMATCH',test)
 def test_nativeprep_python_fixture_runs_using_interpreter_on_windows(self):
  source=(ROOT/'tests/test_native_preparation_v0403.py').read_text()
  self.assertIn("patch('nativeprep.engine.subprocess.run'",source)
  self.assertIn('sys.executable,*argv',source)
 def test_missing_external_go_backend_never_promotes_native_parity(self):
  from tooling.gates_v0427 import run
  result=run(run_tests=False)
  self.assertEqual(result['native_qualified'],False)
  self.assertEqual(result['milestones']['REAL_GO_BACKEND'],'EXTERNAL_OPTIONAL_NOT_BUNDLED')
  self.assertEqual(result['milestones']['SHINOBI_PLAYABLE'],'NOT_ESTABLISHED')
if __name__=='__main__':unittest.main()
