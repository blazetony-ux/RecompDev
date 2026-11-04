"""Fixture: copy existing attested translated code, rebuild new host, compare Start."""
import json
import tempfile
import unittest
from pathlib import Path
import test_continuous_native_v0423 as previous
import test_native_interaction_v0441 as input_tests

runner=input_tests.interaction
class HostRefreshTests(unittest.TestCase):
 def test_rebuilt_attested_host_and_explicit_missing_nmi_vector(self):
  f=previous.ContinuousNativeTests('test_windows_cmake_project_metadata_is_not_an_executable')
  f.setUp()
  try:
   rom,original,stats=f.synthetic_project()
   sha=runner.digest(rom)
   project=f.dir/'v0441-copy'
   att=runner.prepare(original,project,sha)
   self.assertEqual(att['guest_translation_sha256'],runner.digest(original/'translated.cpp'))
   app,_=runner.build(project)
   neutral=runner.run_native(app,rom,f.dir/'neutral-v0441',3,300000,'neutral')
   self.assertEqual(neutral['status'],'FRAME_BUDGET_REACHED',neutral)
   self.assertEqual(neutral['nmi_events'],0)
   timeline=f.dir/'start-v0441.csv'
   runner.start_timeline(timeline,1,1,3)
   pressed=runner.run_native(app,rom,f.dir/'start-v0441',3,300000,'start',timeline)
   # Source-attested fixture deliberately has no instruction at NMI vector.
   # Guest engine must fail CLOSED, not skip the missing vector or emulate it.
   self.assertEqual(pressed['nmi_events'],1)
   self.assertEqual(pressed['status'],'UNTRANSLATED_INITIAL_CODE')
  finally:
   f.doCleanups()
if __name__=='__main__':unittest.main()
