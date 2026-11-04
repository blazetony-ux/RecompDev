"""Release identity and no-game-specific-promotion contract."""
import unittest
from pathlib import Path
import sys
from tooling.release_contract import version
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tooling.gates_v0431 import run

class Release431(unittest.TestCase):
 def test_new_version_is_distinct(self):
  self.assertIn('VERSION '+version(ROOT),(ROOT/'nativepilot/CMakeLists.txt').read_text())
  self.assertIn('v'+version(ROOT),(ROOT/'static/tooling.html').read_text())
  self.assertIn('catalogue.v0435-working.sqlite',(ROOT/'Run-Workbench.ps1').read_text())
  self.assertIn('FILE_SHA256_v0431.json',(ROOT/'Verify-v0431.ps1').read_text())
  self.assertIn('BUILD_VALIDATION_v0435.json',(ROOT/'workbench.py').read_text())
  self.assertIn("'release':'"+version(ROOT)+"'",(ROOT/'workbench.py').read_text())
 def test_history_gate_maintains_qualification_boundaries(self):
  g=run(run_tests=False)
  self.assertEqual(g['release'],'0.4.0.31')
  self.assertFalse(g['native_qualified'])
  self.assertEqual(g['milestones']['INDEPENDENT_MAME_PARITY'],'NOT_ESTABLISHED')
 def test_registered_graph_sha_is_history_lookup_key(self):
  source=(ROOT/'workbench.py').read_text()
  self.assertIn('t.source_sha256',source)
  self.assertIn('DISCOVERY_SOURCE_ID_NOT_FULL_SHA256',source)
  self.assertIn('identity_issues',source)
  self.assertIn('native_history_issues',source)

if __name__=='__main__':unittest.main()
