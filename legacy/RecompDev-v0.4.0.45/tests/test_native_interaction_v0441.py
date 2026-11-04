"""No-ROM tests for source-attested native input test harness."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('interaction',ROOT/'tools'/'Test-Native-Interaction-v0441.py')
interaction=importlib.util.module_from_spec(spec);spec.loader.exec_module(interaction)
class InteractionHarnessTests(unittest.TestCase):
 def test_guest_cycle_mapping_and_bounded_pause_edges(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'input.csv'
   out=interaction.start_timeline(p,300,4,600)
   self.assertEqual(out['start_cycle'],300*3579545//60)
   self.assertEqual(out['release_cycle'],304*3579545//60)
   self.assertEqual(p.read_text().splitlines(),['RECOMP_INPUT_CYCLES_V1','0,0,0',f"{out['start_cycle']},0,128",f"{out['release_cycle']},0,0"])
   self.assertEqual(out['input_sha256'],interaction.digest(p))
 def test_invalid_pulse_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   for at,duration,limit in ((0,1,600),(300,0,600),(300,122,600),(599,1,600),(300,4,303)):
    with self.assertRaises(ValueError):interaction.start_timeline(Path(td)/'no.csv',at,duration,limit)
 def test_fingerprints_are_not_automatically_gameplay_claims(self):
  self.assertEqual(interaction.first_frame_difference({'frame_hashes':[1,2,3]},{'frame_hashes':[1,2,4]}),3)
  self.assertIsNone(interaction.first_frame_difference({'frame_hashes':[1,2]},{'frame_hashes':[1,2,3]}))
 def test_only_source_attested_guest_code_is_reused(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);old=root/'old';new=root/'new';old.mkdir()
   (old/'translated.cpp').write_bytes(b'ORIGINAL_SOURCE_ATTESTED_CODE')
   (old/'generation.json').write_text(json.dumps({'original_source_sha256':'a'*64,'translated_instructions':2}))
   out=interaction.prepare(old,new,'a'*64)
   self.assertEqual(out['guest_translation_sha256'],interaction.digest(old/'translated.cpp'))
   self.assertEqual((new/'translated.cpp').read_bytes(),(old/'translated.cpp').read_bytes())
   self.assertIn('service_pending_console_nmi',(new/'runtime.cpp').read_text())
 def test_wrong_rom_hash_fails_before_copying(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);old=root/'old';old.mkdir();(old/'generation.json').write_text(json.dumps({'original_source_sha256':'a'*64,'translated_instructions':2}))
   (old/'translated.cpp').write_bytes(b'no')
   with self.assertRaisesRegex(ValueError,'does not match'):interaction.prepare(old,root/'new','b'*64)
if __name__=='__main__':unittest.main()
