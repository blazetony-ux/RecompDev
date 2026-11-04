"""Owner-independent exact-address and padding screening acceptance tests."""
import hashlib,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from nativecore.instruction_evidence import inspect_entry
from nativecore.parity import compare,SCHEMA
from nativepilot.generator import sha256,verify_export
from nativepilot.recovery import recover_bank


@unittest.skipUnless(os.name!='nt','Stub Ghidra launcher requires POSIX shebang')
class TestExactAddressWithoutFunction(unittest.TestCase):
 def create_rom(self,path,code=b'\x3e\x01',fill=False):
  rom=bytearray(65536);rom[0x38:0x38+len(code)]=code
  rom[0x7ff0:0x7ff8]=b'TMR SEGA';path.write_bytes(rom)

 def test_missing_function_but_exact_instruction_recovers(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);rom=root/'second-game.sms';self.create_rom(rom)
   digest=sha256(rom);fake=root/'fake-ghidra';fake.write_text('''#!/usr/bin/env python3
import hashlib,json,pathlib,sys
args=sys.argv[1:]
source=pathlib.Path(args[args.index('-import')+1]).read_bytes()
out=args[args.index('-postScript')+2];exact=args[args.index('-postScript',args.index('-postScript')+1)+2]
identity=args[args.index('-postScript')+3:args.index('-postScript')+5]
target,digest=identity
pathlib.Path(out).write_text(json.dumps({'language':'z80:LE:16:default','source_sha256':digest,'target_id':target,'functions':[]}))
ins={'address':0x38,'length':2,'fallthrough':0x3a,'mnemonic':'LD','bytes_sha256':hashlib.sha256(source[0x38:0x3a]).hexdigest(),
     'pcode':[{'op':'COPY','output':{'space':'register','offset':1,'size':1},'inputs':[{'space':'const','offset':1,'size':1}]}]}
pathlib.Path(exact).write_text(json.dumps({'schema':'recomp-exact-instruction-v1','language':'z80:LE:16:default','entry':0x38,'status':'EXACT_INSTRUCTION_RECOVERED','instructions':[ins]}))
''');fake.chmod(0o755)
   doc,evidence=recover_bank(rom,digest,'sms-z80',0x38,[0,0,1,2],root/'result',str(fake))
   self.assertEqual(evidence['exact_instructions'],1)
   verified,_,_=verify_export(doc,rom)
   self.assertIn(0x38,verified)
   self.assertEqual(json.loads((root/'result/entry-diagnostics.json').read_text())['classification'],'UNCLASSIFIED_BYTES')

 def test_hash_invalid_exact_instruction_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);rom=root/'another.sms';self.create_rom(rom);digest=sha256(rom)
   fake=root/'ghidra';fake.write_text('''#!/usr/bin/env python3
import json,pathlib,sys
args=sys.argv[1:];idx=args.index('-postScript');out=args[idx+2];target=args[idx+3];digest=args[idx+4]
exact=args[args.index('-postScript',idx+1)+2]
pathlib.Path(out).write_text(json.dumps({'language':'z80:LE:16:default','source_sha256':digest,'target_id':target,'functions':[]}))
pathlib.Path(exact).write_text(json.dumps({'schema':'recomp-exact-instruction-v1','language':'z80:LE:16:default','entry':56,'instructions':[{'address':56,'length':2,'bytes_sha256':'0'*64,'mnemonic':'LD','pcode':[]}]}))
''');fake.chmod(0o755)
   with self.assertRaisesRegex(ValueError,'bytes mismatch'):
    recover_bank(rom,digest,'sms-z80',0x38,[0,0,1,2],root/'result',str(fake))

 def test_repetitive_ff_vector_is_not_auto_translated(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);rom=root/'padded.sms';self.create_rom(rom,b'\xff'*32)
   info=inspect_entry(rom,0x38)
   self.assertEqual(info['classification'],'REPETITIVE_FF_SUSPECTED_PADDING')
   self.assertFalse(info['translation_allowed'])
   with self.assertRaisesRegex(RuntimeError,'RECOVERY_UNSAFE_PADDING_SUSPECTED'):
    recover_bank(rom,sha256(rom),'sms-z80',0x38,[0,0,1,2],root/'result')
   self.assertTrue((root/'result/entry-diagnostics.json').is_file())

class TestIndependentReferenceParity(unittest.TestCase):
 def test_sampled_cpu_comparison_and_first_divergence(self):
  digest='a'*64
  reference={'schema':SCHEMA,'source_sha256':digest,'independent_source':'external-executable-test-fixture',
             'checkpoints':[{'step':3,'pc':0x38,'af':0x23,'mapper':[0,0,1,2]}]}
  native={'source_id':digest,'trace':{'checkpoints':[{'step':3,'pc':0x38,'af':0x23,'mapper':[0,0,1,2]}]}}
  self.assertEqual(compare(reference,native)['status'],'MATCHED_SAMPLED_CHECKPOINTS')
  native['trace']['checkpoints'][0]['af']=0x24
  r=compare(reference,native)
  self.assertEqual(r['status'],'DIVERGED')
  self.assertEqual(r['mismatches'][0]['field'],'af')
  native['trace']['checkpoints']=[]
  self.assertEqual(compare(reference,native)['status'],'INCOMPLETE_REFERENCE_COVERAGE')
  with self.assertRaisesRegex(ValueError,'hashes'):
   compare(reference,{'source_id':'b'*64,'trace':{'checkpoints':[]}})
