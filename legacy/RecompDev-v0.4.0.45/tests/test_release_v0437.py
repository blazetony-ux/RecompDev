"""v0437 release integrity contracts remain reusable by later releases."""
import unittest
from pathlib import Path
from tooling.release_contract import assert_entrypoints,version
ROOT=Path(__file__).resolve().parents[1]
class Release437(unittest.TestCase):
 def test_current_release_matches_entrypoints(self):
  self.assertEqual(assert_entrypoints(ROOT),version(ROOT))
 def test_verification_has_four_required_gates(self):
  s=(ROOT/'Verify-v0437.ps1').read_text()
  for x in ('FILE_SHA256_v0437.json','Validate-v0437.py','test_*.py','bridge/tests'):
   self.assertIn(x,s)
 def test_catalogue_preserved(self):
  s=(ROOT/'Run-Workbench.ps1').read_text()
  self.assertIn('catalogue.v0437-working.sqlite',s)
  self.assertIn('RecompDev-v0.4.0.36',s)
 def test_new_compiled_selftest_and_reference_qualification(self):
  for path in ('hardware/tests/output_probe_v0437/main.cpp',
               'nativecore/reference_parity_v0437.py',
               'tools/Run-Shinobi-Reference-v0437.py',
               'tools/Validate-Native-Outputs-v0437.py'):
   self.assertTrue((ROOT/path).is_file())
  s=(ROOT/'nativecore/reference_parity_v0437.py').read_text()
  self.assertIn("'cpu_parity':'NOT_ESTABLISHED'",s)
 def test_no_shinobi_hacks_in_shared_renderer_or_oracle(self):
  for name in ('hardware/image_io.hpp','hardware/adapters/sms.hpp',
               'nativecore/reference_parity_v0437.py','nativecore/output_qualification_v0437.py'):
   self.assertNotIn('shinobi',(ROOT/name).read_text().lower())
if __name__=='__main__':unittest.main()
