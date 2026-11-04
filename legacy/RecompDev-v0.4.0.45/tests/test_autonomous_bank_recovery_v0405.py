"""Bank-qualified native executable and bounded recover/rebuild/retry tests.

Only synthetic Master System source bytes are used; never includes game ROM data.
"""
import hashlib
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from nativepilot.recovery import bank_context
from nativepilot.generator import generate_project,verify_export,sha256
from nativepilot.engine import pilot
import test_native_execution_v0404 as native_fixture

class BankRecoveryTests(unittest.TestCase):
 def setUp(self):
  native_fixture.NativeExecutionTests.setUp(self)
  # Alter after source setup, then synchronise the authenticated fixture hash.
  # This patch mimics code stored in physical bank 3, but executing at CPU 0x8000.
  raw=bytearray(self.rom.read_bytes())
  raw[0xc000:0xc005]=b'\x3e\x77\x32\x01\xc0'
  self.rom.write_bytes(raw)
  self.sha2=sha256(self.rom)
  con=sqlite3.connect(self.db)
  con.execute('UPDATE discovery_sources SET source_id=? WHERE source_id=?',(self.sha2,self.sha))
  con.execute('UPDATE native_preparations_v0403 SET source_id=?,source_sha256=? WHERE source_id=?',
              (self.sha2,self.sha2,self.sha))
  con.execute('UPDATE targets SET source_sha256=? WHERE target_id=?',(self.sha2,self.target))
  con.commit();con.close()
  self.sha=self.sha2
  self.doc['source_sha256']=self.sha
  self.export.write_text(json.dumps(self.doc))

 def fake_bank_doc(self,bank=3):
  def v(space,offset,size=1):return {'space':space,'offset':offset,'size':size}
  def code(pc,n,fall,mnem,op):
   off=bank*0x4000+pc-0x8000
   raw=self.rom.read_bytes()
   return {'address':pc,'length':n,'fallthrough':fall,'mnemonic':mnem,
           'bytes_sha256':hashlib.sha256(raw[off:off+n]).hexdigest(),'pcode':op}
  return {'language':'z80:LE:16:default','target_id':self.target,'source_sha256':self.sha,
          'bank_context':{'slot':2,'bank':bank,'base':0x8000,'physical_start':bank*0x4000},
          'functions':[{'entry':0x8000,'name':'BANK3_FROM_OWNER_ROM','instructions':[
           code(0x8000,2,0x8002,'LD',[{'op':'COPY','output':v('register',1),'inputs':[v('const',0x77)]}]),
           code(0x8002,3,0x8005,'LD',[{'op':'COPY','output':v('ram',0xc001),'inputs':[v('register',1)]}])]}]}

 def test_physical_mapping(self):
  x=bank_context(262144,0x8a68,[0,0,1,6])
  self.assertEqual(x['entry_physical'],0x18a68)
  self.assertEqual(x['bank'],6)
  self.assertEqual(x['slot'],2)
  self.assertEqual(bank_context(262144,0x0110,[0,4,5,6])['entry_physical'],0x110)
  for bad in (-1,0xc000):
   with self.assertRaises(ValueError):bank_context(262144,bad,[0,0,1,6])
  with self.assertRaises(ValueError):bank_context(262144,0x8000,[0,1,2])

 def test_bank_context_invalid_or_forged_rejected(self):
  doc=self.fake_bank_doc()
  verified,_,_=verify_export(doc,self.rom)
  self.assertEqual(sorted(verified),[0xc000,0xc002])
  doc['bank_context']['physical_start']=0x8000
  with self.assertRaisesRegex(ValueError,'mapping'):verify_export(doc,self.rom)
  doc=self.fake_bank_doc();doc['functions'][0]['instructions'][0]['bytes_sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'mismatch'):verify_export(doc,self.rom)

 def test_bank_disambiguation_and_native_code_generation(self):
  project=self.root/'gen'
  result=generate_project(self.doc,self.rom,project,[self.fake_bank_doc()])
  self.assertEqual(result['recovered_bank_overlays'][0]['bank'],3)
  code=(project/'translated.cpp').read_text()
  self.assertIn('switch(physical)',code)
  self.assertIn('case 0xc000u:',code)

 @unittest.skipUnless(shutil.which('cmake') and shutil.which('g++'),'CMake and native C++ compiler required')
 def test_autonomous_recompile_replay_executes_physical_bank(self):
  prior_sha=sha256(self.rom)
  hits=[]
  def recover(path,source_sha,target,pc,mapper,output):
   hits.append((pc,mapper[3]))
   self.assertEqual(bank_context(path.stat().st_size,pc,mapper)['entry_physical'],0xc000)
   output.mkdir(parents=True,exist_ok=True)
   doc=self.fake_bank_doc()
   (output/'bank-functions.json').write_text(json.dumps(doc))
   return doc,{'status':'SOURCE_BYTES_VERIFIED','bank':3,'slot':2,'instructions':2}
  result=pilot(self.db,self.sha,self.root/'recovery-run',[self.roms],max_steps=20,
               max_recoveries=1,recovery_function=recover)
  self.assertEqual(hits,[(0x8000,3)],result)
  self.assertEqual(result['status'],'NATIVE_TRACE_STOPPED',result)
  self.assertEqual([x['native_steps'] for x in result['recovery_attempts']],[6,8],result)
  self.assertEqual(result['trace']['pc'],0x8005)
  self.assertEqual(result['trace']['physical_offset'],0xc005)
  self.assertEqual(result['trace']['ram_writes'],3)
  self.assertEqual(result['recovery_attempts'][0]['recovery'],'BANK_SOURCE_VERIFIED')
  self.assertEqual(result['bank_overlays'][0]['bank'],3)
  self.assertEqual(prior_sha,sha256(self.rom))
  self.assertTrue((self.root/'recovery-run'/'execution-attempt-00.log').is_file())
  self.assertTrue((self.root/'recovery-run'/'execution-attempt-01.log').is_file())

 def test_max_recoveries_zero_remains_a_strict_native_stop(self):
  result=pilot(self.db,self.sha,self.root/'off',[self.roms],max_steps=12,
               max_recoveries=0,compile_native=False)
  self.assertEqual(result['status'],'CPP_GENERATED_NOT_COMPILED')
  self.assertEqual(result['max_recoveries'],0)

class GhidraRecoveryInvocationTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
  self.root=Path(self.t.name);self.rom=self.root/'TestSMS.sms'
  raw=bytearray(256*1024)
  raw[0x18a68:0x18a6a]=b'\x3e\xab'
  raw[0x7ff0:0x7ff8]=b'TMR SEGA'
  self.rom.write_bytes(raw)
  self.sha=sha256(self.rom)

 @unittest.skipUnless(__import__('os').name!='nt','Synthetic Ghidra launcher uses POSIX shebang')
 def test_seeded_bank_6_window_is_physically_attested(self):
  from nativepilot.recovery import recover_bank
  tool=self.root/'fake-ghidra'
  tool.write_text('''#!/usr/bin/env python3
import hashlib,json,sys,pathlib
args=sys.argv[1:]
base=int(args[args.index('-loader-baseAddr')+1],0)
assert base==0x8000
src=pathlib.Path(args[args.index('-import')+1]).read_bytes()
seed=int(args[args.index('-preScript')+2],0)
assert seed==0x8a68
assert src[seed-base:seed-base+2]==b'\\x3e\\xab'
post=args.index('-postScript')
path,target,sha=args[post+2:post+5]
ins={'address':seed,'length':2,'fallthrough':seed+2,'mnemonic':'LD',
 'bytes_sha256':hashlib.sha256(src[seed-base:seed-base+2]).hexdigest(),
 'pcode':[{'op':'COPY','output':{'space':'register','offset':1,'size':1},
 'inputs':[{'space':'const','offset':171,'size':1}]}]}
doc={'language':'z80:LE:16:default','target_id':target,'source_sha256':sha,
 'functions':[{'entry':seed,'name':'FAKE_GHIDRA_BANK6','instructions':[ins]}]}
pathlib.Path(path).write_text(json.dumps(doc))
''')
  tool.chmod(0o755)
  out=self.root/'bank6'
  doc,meta=recover_bank(self.rom,self.sha,'mastersystem-test',0x8a68,[0,0,1,6],out,str(tool))
  self.assertEqual(meta['physical_offset'],0x18a68)
  self.assertEqual(meta['status'],'SOURCE_BYTES_VERIFIED')
  self.assertEqual(doc['bank_context']['bank'],6)
  generated=generate_project({'language':'z80:LE:16:default','target_id':'mastersystem-test',
       'source_sha256':self.sha,'functions':[]},self.rom,self.root/'output',[doc])
  self.assertEqual(generated['translated_instructions'],1)
  self.assertIn('case 0x18a68u:',(self.root/'output'/'translated.cpp').read_text())
  self.assertEqual(sha256(self.rom),self.sha)

 def test_recovery_rejects_modified_original_rom(self):
  from nativepilot.recovery import recover_bank
  with self.assertRaisesRegex(ValueError,'SHA-256'):
   recover_bank(self.rom,'0'*64,'wrong-target',0x8a68,[0,0,1,6],self.root/'output')
