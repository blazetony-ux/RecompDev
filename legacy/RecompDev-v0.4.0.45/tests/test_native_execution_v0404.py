"""Real compiler + local HTTP native execution regression without any copyrighted ROM."""
import hashlib
import json
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from discovery.store import connect,store_source
from nativeprep.engine import prepare
from nativepilot.engine import pilot
from nativepilot.generator import sha256,generate_project

class NativeExecutionTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
  self.root=Path(self.t.name);self.roms=self.root/'roms';self.roms.mkdir()
  self.rom=self.roms/'TinySMS.sms'
  self.raw=bytearray(65536)
  self.raw[:3]=b'\xc3\x03\x00'
  self.raw[3:5]=b'\x3e\x42'
  self.raw[5:8]=b'\x32\x00\xc0'
  self.raw[8:10]=b'\x3e\x03'
  self.raw[10:13]=b'\x32\xff\xff'
  self.raw[13:16]=b'\xc3\x00\x80'
  self.raw[0x7ff0:0x7ff8]=b'TMR SEGA'
  self.rom.write_bytes(self.raw)
  self.sha=sha256(self.rom)
  self.db=self.root/'catalogue.sqlite';shutil.copyfile(ROOT/'catalogue.sqlite',self.db)
  con=connect(self.db);store_source(con,self.sha,self.rom,len(self.raw),'SHA256_COMPLETE','mastersystem','Tiny SMS','test header');con.close()
  prepared=prepare(self.db,self.sha,self.root/'prepared',allowed_roots=[self.roms],analyze=False)
  self.target=prepared['target_id']
  def v(space,size,offset):return {'space':space,'size':size,'offset':offset}
  def copy(dst,src):return {'op':'COPY','inputs':[src],'output':dst}
  def ins(pc,length,fall,mnem,pcode):
   return {'address':pc,'length':length,'fallthrough':fall,'mnemonic':mnem,
    'bytes_sha256':hashlib.sha256(self.raw[pc:pc+length]).hexdigest(),'pcode':pcode}
  functions=[{'entry':3,'name':'TEST_Z80_BOOT','instructions':[
   ins(3,2,5,'LD',[copy(v('register',1,1),v('const',1,0x42))]),
   ins(5,3,8,'LD',[copy(v('ram',1,0xc000),v('register',1,1))]),
   ins(8,2,10,'LD',[copy(v('register',1,1),v('const',1,3))]),
   ins(10,3,13,'LD',[copy(v('ram',1,0xffff),v('register',1,1))]),
   ins(13,3,None,'JP',[{'op':'BRANCH','inputs':[v('ram',1,0x8000)]}])]}]
  self.doc={'schema':'recomp-function-pcode-v1','source_sha256':self.sha,
    'target_id':self.target,'language':'z80:LE:16:default','functions':functions}
  self.export=self.root/'functions.json';self.export.write_text(json.dumps(self.doc))
  con=sqlite3.connect(self.db);con.execute('UPDATE native_preparations_v0403 SET export_path=?,candidate_count=1 WHERE source_id=?',(str(self.export),self.sha));con.commit();con.close()

 @unittest.skipUnless(shutil.which('cmake') and shutil.which('g++'),'CMake and C++ compiler required')
 def test_compiled_native_boot_and_bank_stop(self):
  before=sha256(self.rom)
  output=pilot(self.db,self.sha,self.root/'output',[self.roms],50,max_recoveries=0)
  self.assertEqual(output['status'],'NATIVE_TRACE_STOPPED',output)
  self.assertEqual(output['trace']['native_steps'],6)
  self.assertEqual(output['trace']['bank_switches'],1)
  self.assertEqual(output['trace']['events_total'],1)
  self.assertEqual(output['trace']['events'][0]['kind'],'MAPPER_WRITE')
  self.assertEqual(output['trace']['events'][0]['address'],0xffff)
  self.assertFalse(output['trace']['events_truncated'])
  self.assertEqual(output['trace']['ram_writes'],2)
  self.assertEqual(output['trace']['status'],'BANKED_CODE_NOT_TRANSLATED')
  self.assertEqual(before,sha256(self.rom),'Source ROM was modified')
  con=sqlite3.connect(self.db)
  self.assertEqual(con.execute('SELECT COUNT(*) FROM native_pilots_v0404').fetchone()[0],1)
  con.close()

 def test_wrong_rom_and_outside_root_blocked(self):
  r=pilot(self.db,self.sha,self.root/'outside',[self.root/'elsewhere'],100,False)
  self.assertEqual(r['status'],'PILOT_BLOCKED')
  self.assertIn('outside',r['blocker'])
  data=self.rom.read_bytes();self.rom.write_bytes(data[:-1]+b'\x7f')
  r=pilot(self.db,self.sha,self.root/'changed',[self.roms],100,False)
  self.assertEqual(r['status'],'PILOT_BLOCKED')
  self.assertIn('SHA-256',r['blocker'])

 def test_forged_instruction_hash_rejected(self):
  self.doc['functions'][0]['instructions'][0]['bytes_sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'mismatch'):
   generate_project(self.doc,self.rom,self.root/'invalid')

 def test_diagnostic_ppm_to_png(self):
  from nativepilot.preview import convert_ppm
  ppm=self.root/'frame.ppm';png=self.root/'frame.png'
  ppm.write_bytes(b'P6\n256 192\n255\n'+bytes([0,85,170])*256*192)
  convert_ppm(ppm,png)
  self.assertTrue(png.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'))
  with self.assertRaisesRegex(ValueError,'Unexpected'):
   ppm.write_bytes(b'invalid');convert_ppm(ppm,png)

 def test_intra_pcode_branch_not_misclassified_as_game_jump(self):
  from nativepilot.generator import emit_instruction
  ins={'mnemonic':'DAA','pcode':[{'op':'CBRANCH','inputs':[
    {'space':'const','offset':7,'size':4},{'space':'register','offset':0,'size':1}]}]}
  self.assertEqual(emit_instruction(ins),['s.decimal_adjust_accumulator();'])
  ins['mnemonic']='JR'
  with self.assertRaisesRegex(ValueError,'Intra-instruction'):
   emit_instruction(ins)

 def test_workbench_route_and_local_action_security(self):
  with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  base=f'http://127.0.0.1:{port}'
  proc=subprocess.Popen([sys.executable,str(ROOT/'recomp.py'),'--db',str(self.db),'serve','--port',str(port),'--rom-root',str(self.roms)],
                        cwd=str(ROOT),stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
  self.addCleanup(lambda:proc.kill() if proc.poll() is None else None)
  try:
   for _ in range(120):
    try:
     with urlopen(base+'/api/native-pilot-control',timeout=1) as f:token=json.load(f)['data']['token']
     break
    except OSError:time.sleep(.04)
   else:self.fail('Workbench failed to start')
   with urlopen(base+'/execution') as f:self.assertIn('id="pilot-run"',f.read().decode())
   with urlopen(base+'/static/execution.js') as f:self.assertIn('native-pilot-run',f.read().decode())
   body=json.dumps({'source_id':self.sha,'max_steps':10,'max_recoveries':0}).encode()
   req=Request(base+'/api/native-pilot-run',data=body,headers={'Origin':base,'Content-Type':'application/json','X-RecompDev-Token':'wrong'},method='POST')
   with self.assertRaises(HTTPError) as error:urlopen(req,timeout=1)
   self.assertEqual(error.exception.code,403)
   req=Request(base+'/api/native-pilot-run',data=json.dumps({'source_id':self.sha,'max_steps':-1}).encode(),
               headers={'Origin':base,'Content-Type':'application/json','X-RecompDev-Token':token},method='POST')
   with self.assertRaises(HTTPError) as error:urlopen(req,timeout=1)
   self.assertEqual(error.exception.code,400)
   # Parent test verifies the server actually starts the bounded build worker.
   body=json.dumps({'source_id':self.sha,'max_steps':10,'max_recoveries':0}).encode()
   req=Request(base+'/api/native-pilot-run',data=body,
      headers={'Origin':base,'Content-Type':'application/json','X-RecompDev-Token':token},method='POST')
   with urlopen(req,timeout=3) as f:job=json.load(f)['data']
   self.assertIn(job['state'],('RUNNING','COMPLETE'))
   for _ in range(200):
    with urlopen(base+'/api/native-pilot-job',timeout=2) as f:job=json.load(f)['data']
    if job['state'] not in ('RUNNING','STOP_REQUESTED'):break
    time.sleep(.075)
   self.assertEqual(job['state'],'COMPLETE',job)
   self.assertTrue(job['report_written'])
   with urlopen(base+'/api/native-pilots') as f:
    evidence=json.load(f)['data']['jobs']
   self.assertEqual(len(evidence),1)
   self.assertEqual(evidence[0]['translated_instructions'],6)  # Deliberately no autonomous bank recovery in this baseline test
  finally:
   proc.terminate()
   try:proc.wait(timeout=4)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
   proc.stderr.close()
