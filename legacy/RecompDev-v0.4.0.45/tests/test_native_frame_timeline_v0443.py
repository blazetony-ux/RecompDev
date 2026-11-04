"""Offline visual inspection never invents or silently transforms original frames."""
import hashlib,tempfile,unittest
from pathlib import Path
import importlib.util
R=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('frame_tool',R/'tools'/'View-Frame-Timeline-v0443.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class Timeline443(unittest.TestCase):
 def test_png_and_html_from_real_sampled_ppm(self):
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d)
   original=b'P6\n2 1\n255\n'+bytes((255,0,0,0,0,255))
   image=folder/'native-frame-snapshot-000300.ppm';image.write_bytes(original)
   html,meta=mod.generate(folder)
   self.assertEqual(meta['images'][0]['source_sha256'],hashlib.sha256(original).hexdigest())
   self.assertEqual(meta['images'][0]['frame'],300)
   self.assertTrue((folder/'native-frame-snapshot-000300.png').read_bytes().startswith(b'\x89PNG\r\n\x1a\n'))
   self.assertIn('NOT_TESTED',mod.json.dumps(meta))
   self.assertIn('Frame Timeline',html.read_text())
 def test_reject_malformed_or_unbounded_frames(self):
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d)
   (folder/'native-frame-snapshot-000030.ppm').write_bytes(b'P6\n1000 1000\n255\n')
   with self.assertRaises(ValueError):mod.generate(folder)
if __name__=='__main__':unittest.main()
