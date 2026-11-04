"""Guard compiled release tests against assumptions about Windows compilers."""
import tempfile,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
from tooling.compiled_fixture_v0445 import executable_in_build,run_cpp_fixture

ROOT=Path(__file__).resolve().parents[1]
class CompilerPortability445(unittest.TestCase):
 def test_find_msvc_multiconfig_executable(self):
  with tempfile.TemporaryDirectory() as tmp:
   release=Path(tmp)/"build"/"Debug";release.mkdir(parents=True)
   exe=release/"RecompDevPsgFixture.exe";exe.write_bytes(b"MZfixture")
   self.assertEqual(executable_in_build(Path(tmp)/"build","RecompDevPsgFixture"),exe)
 def test_missing_and_duplicate_executables_fail_closed(self):
  with tempfile.TemporaryDirectory() as tmp:
   build=Path(tmp)
   with self.assertRaisesRegex(RuntimeError,"exactly one"):executable_in_build(build,"RecompDevPsgFixture")
   (build/"RecompDevPsgFixture").write_bytes(b"mock")
   (build/"RecompDevPsgFixture.exe").write_bytes(b"mock")
   with self.assertRaisesRegex(RuntimeError,"exactly one"):executable_in_build(build,"RecompDevPsgFixture")
 def test_msvc_style_cmake_build_never_invokes_cl_or_gcc_flags(self):
  with tempfile.TemporaryDirectory() as tmp:
   calls=[]
   def fake_run(command,**kwargs):
    calls.append(list(command))
    if len(calls)==2:
     out=Path(tmp)/"build"/"Debug"/"RecompDevPsgFixture.exe"
     out.parent.mkdir(parents=True,exist_ok=True)
     out.write_bytes(b"MZ simulated binary")
    return subprocess.CompletedProcess(command,0,stdout="",stderr="")
   with patch('tooling.compiled_fixture_v0445.shutil.which',return_value='C:/Program Files/CMake/bin/cmake.exe'):
    with patch('tooling.compiled_fixture_v0445.subprocess.run',side_effect=fake_run):
     run_cpp_fixture('int main(){return 0;}',ROOT,Path(tmp))
   self.assertEqual(len(calls),3)
   self.assertEqual(calls[0][0],"cmake")
   self.assertEqual(calls[1][:2],["cmake","--build"])
   self.assertTrue(calls[2][0].endswith(".exe"))
   self.assertNotIn("cl", " ".join(" ".join(cmd) for cmd in calls))
   self.assertNotIn("-std=c++17", " ".join(" ".join(cmd) for cmd in calls))
 def test_mandatory_toolchain_error_is_explicit(self):
  with tempfile.TemporaryDirectory() as tmp:
   with patch('tooling.compiled_fixture_v0445.shutil.which',return_value=None):
    with self.assertRaisesRegex(RuntimeError,'requires CMake'):
     run_cpp_fixture('int main(){return 0;}',ROOT,Path(tmp))
 def test_psg_uses_cmake_not_direct_cl_or_gcc_flags(self):
  psg=(ROOT/'tests/test_sms_psg_v0443.py').read_text()
  self.assertIn('run_cpp_fixture',psg)
  self.assertNotIn("compiler or 'cl'",psg)
  helper=(ROOT/'tooling/compiled_fixture_v0445.py').read_text()
  self.assertIn('cmake',helper)
  self.assertIn('cxx_std_17',helper)
  self.assertIn('--config',helper)
  self.assertIn('Debug',helper)
if __name__=='__main__':unittest.main()
