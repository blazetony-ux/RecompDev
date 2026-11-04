"""Cross-ISA end-to-end owned binaries; verifies one-workflow codegen + triage."""
import hashlib, json, struct, tempfile, unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from multisa.campaign import run
from unittest.mock import patch
from test_cross_isa_recovery_v0430 import Engine

class UniversalCampaign(unittest.TestCase):
 def setUp(self):
  # Mock only optional external decoder API. Authenticated native CPU operations,
  # compilation, and execution still run as actual C++ executables.
  cm=patch('scan_graph.make_capstone',side_effect=lambda isa,endian:Engine(isa))
  cm.start();self.addCleanup(cm.stop)

 def test_unseen_m68k_source_compiled_in_generic_campaign(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);blob=bytes.fromhex('7002 5280 4e75');(p/'new-system-code.bin').write_bytes(blob)
   result=run(p/'new-system-code.bin',p/'job',fmt='raw',isa='m68k',endian='big',base=0,entry=0,
              max_instructions=90,compile=True,run_steps=20,expected_sha256=hashlib.sha256(blob).hexdigest())
   self.assertEqual(result['native_subset']['translated_instructions'],3)
   self.assertEqual(result['compiler']['status'],'COMPILED_SUBSET')
   self.assertEqual(result['execution']['registers'][0],3)
   self.assertEqual(result['execution']['stop'],'RETURNED_TO_HOST')
   self.assertEqual(result['native_qualified'],False)
   self.assertEqual(result['game_specific_fixes'],0)
   self.assertTrue((p/'job'/'discovery'/'barrier-triage.json').exists())

 def test_unseen_mips_source_compiled_in_generic_campaign(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);blob=struct.pack('<5I',0x24080007,0x25090005,0x03e00008,0,0)
   (p/'m.bin').write_bytes(blob)
   result=run(p/'m.bin',p/'job',fmt='raw',isa='mips',endian='little',base=0x4000,entry=0x4000,
              max_instructions=90,compile=True,run_steps=20)
   self.assertEqual(result['compiler']['status'],'COMPILED_SUBSET')
   self.assertEqual(result['execution']['registers'][9],12)
   self.assertEqual(result['execution']['stop'],'UNMAPPED_TRANSLATED_PC')

 def test_no_silent_reuse_or_wrong_source(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'src').write_bytes(b'\x70\x03\x4e\x75')
   with self.assertRaisesRegex(ValueError,'SHA-256'):
    run(p/'src',p/'blocked',fmt='raw',isa='m68k',endian='big',base=0,entry=0,expected_sha256='0'*64)
   run(p/'src',p/'job',fmt='raw',isa='m68k',endian='big',base=0,entry=0,max_instructions=80)
   with self.assertRaisesRegex(ValueError,'already exists'):
    run(p/'src',p/'job',fmt='raw',isa='m68k',endian='big',base=0,entry=0,max_instructions=80)

if __name__=='__main__':unittest.main()
