"""Source-preserving generated-game dynamic SMS video adapter tests."""
from __future__ import annotations
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'legacy/RecompDev-v0.4.0.45'))
from nativepilot.generator import generate_project
from runtime_host.bridge import install
from video_sms.bridge import MARKER,transform
from runtime_host.launch import stage
import json

ROM=ROOT/'harness/examples/recomp-pcode/synthetic.sms'
EXPORT=ROOT/'harness/examples/recomp-pcode/function-export.json'
class TestVideoStaging(unittest.TestCase):
 def test_stage_and_cache_preserve_history_and_gamecode(self):
  with tempfile.TemporaryDirectory(prefix='sms-video-stage-') as directory:
   src=Path(directory)/'generated';generate_project(json.loads(EXPORT.read_text()),ROM,src)
   original={p.relative_to(src):p.read_bytes() for p in src.rglob('*') if p.is_file()}
   dest,ident=stage(src,Path(directory)/'cache')
   renderer=(dest/'hardware/adapters/sms.hpp').read_text()
   self.assertIn(MARKER,renderer)
   self.assertIn('rd_sms_mode4_bridge::render(',renderer)
   self.assertNotIn('for(u32 y=0;y<out.height;++y)',renderer)
   self.assertEqual((dest/'translated.cpp').read_bytes(),original[Path('translated.cpp')])
   self.assertEqual(original,{p.relative_to(src):p.read_bytes() for p in src.rglob('*') if p.is_file()})
   self.assertEqual(install(dest)['files_changed'],[])
   cached,ident2=stage(src,Path(directory)/'cache')
   self.assertEqual((cached,ident2),(dest,ident))
 def test_wrong_source_layout_rejected(self):
  with self.assertRaisesRegex(ValueError,'renderer layout'):
   transform('namespace recomp::hw::sms {}')
 def test_generated_project_does_not_contain_game_specific_plugin_logic(self):
  from video_sms.bridge import BRIDGE,HEADER
  self.assertNotIn('Shinobi',BRIDGE.read_text())
  self.assertNotIn('Shinobi',HEADER.read_text())
if __name__=='__main__':unittest.main(verbosity=2)
