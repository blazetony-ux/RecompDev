"""Actually compile and execute source-attested Z80 to test framebuffer snapshots."""
import hashlib,importlib.util,json,unittest
from pathlib import Path
import test_continuous_native_v0423 as continuous_native_fixture
R=Path(__file__).resolve().parents[1]
def module(path):
 spec=importlib.util.spec_from_file_location('recomp_'+Path(path).stem.replace('-','_'),path)
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
native=module(R/'tools/Run-Continuous-Native.py')
viewer=module(R/'tools/View-Frame-Timeline-v0443.py')
class GeneratedSnapshots443(unittest.TestCase):
 def test_compiled_native_guest_produces_real_sampled_frames(self):
  fixture=continuous_native_fixture.ContinuousNativeTests('test_windows_cmake_project_metadata_is_not_an_executable')
  fixture.setUp()
  try:
   rom,project,_=fixture.synthetic_project(3)
   fixture.compile(project)
   output=fixture.dir/'sampled'
   result=native.run(project,rom,hashlib.sha256(rom.read_bytes()).hexdigest(),output,
      frames=3,steps=300000,snapshot_every=1)
   self.assertEqual(result['status'],'FRAME_BUDGET_REACHED',result)
   self.assertEqual(result['snapshots_written'],3)
   self.assertEqual(result['snapshot_every'],1)
   self.assertEqual(len(result['frame_hashes']),3)
   snapshots=list(output.glob('native-frame-snapshot-*.ppm'))
   self.assertEqual(len(snapshots),3)
   page,metadata=viewer.generate(output)
   self.assertEqual(len(metadata['images']),3)
   self.assertTrue(page.is_file())
   self.assertGreater(result['audio_nonzero_samples'],0)
  finally:
   fixture.doCleanups()
if __name__=='__main__':unittest.main()
