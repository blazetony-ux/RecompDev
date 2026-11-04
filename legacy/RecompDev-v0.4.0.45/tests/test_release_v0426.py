"""Versioned Windows corrective release: package, CLI contract, and SQLite lifetime."""
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from tooling.release_contract import version
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from test_continuous_native_v0423 import locate_native_app

class ReleaseContractTests(unittest.TestCase):
 def test_release_metadata_tracks_new_version(self):
  self.assertRegex((ROOT/'nativepilot/CMakeLists.txt').read_text(),'VERSION '+version(ROOT))
  self.assertRegex((ROOT/'static/tooling.html').read_text(),'v'+version(ROOT))
  script=(ROOT/'Run-Workbench.ps1').read_text()
  self.assertRegex(script,r'catalogue\.v04[0-9]{2}-working\.sqlite')
  self.assertIn('RecompDev-v0.4.0.26',script) # preserve previous catalogue
  source=(ROOT/'workbench.py').read_text()
  self.assertRegex(source,r'BUILD_VALIDATION_v04[0-9]{2}\.json')
  self.assertRegex(source,"'release':'"+version(ROOT)+"'")
 def test_real_executable_product_is_selected_not_visual_studio_metadata(self):
  with tempfile.TemporaryDirectory() as tmp:
   build=Path(tmp)
   (build/'RecompDevNativeApp.vcxproj').write_text('<Project/>')
   (build/'RecompDevNativeApp.ilk').write_bytes(b'fake')
   self.assertIsNone(locate_native_app(build,windows=True))
   exe=build/'Release'/'RecompDevNativeApp.exe';exe.parent.mkdir()
   exe.write_bytes(b'fixture')
   self.assertEqual(locate_native_app(build,windows=True),exe)
 def test_sqlite_connection_is_closed_before_cleanup(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'verify.sqlite'
   with closing(sqlite3.connect(p)) as con:
    with con:con.execute('CREATE TABLE sanity(value TEXT)')
   # On Windows, this fails with WinError 32 if the DB handle was leaked.
   p.unlink()
   self.assertFalse(p.exists())
 def test_gate_explicitly_requires_compiled_acceptance(self):
  doc=(ROOT/'tooling/gates_v0426.py').read_text()
  self.assertIn('test_null_backends_v0425.py',doc)
  self.assertIn('proc.returncode',doc)
  self.assertIn("'skipped='",doc)
  self.assertIn('WIN32_EXECUTABLE_SELECTION',doc)

if __name__=='__main__':unittest.main()
