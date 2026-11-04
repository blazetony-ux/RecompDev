"""v0.4.0.22 author-created hardware and native-Z80 device acceptance tests."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

class HardwareRuntimeTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.work=Path(self.t.name)
 def _compile(self,sources,out,extra=()):
  cxx=shutil.which('g++') or shutil.which('clang++')
  if not cxx:self.skipTest('C++17 compiler not installed')
  res=subprocess.run([cxx,'-std=c++17','-O2','-I',str(ROOT),*map(str,sources),'-o',str(out),*extra],
                      capture_output=True,text=True,timeout=90)
  self.assertEqual(res.returncode,0,res.stderr[-2500:]);return out
 def test_two_platforms_deterministic_io_clock_video_audio_input_and_wav(self):
  exe=self._compile([ROOT/'hardware/tests/device_contract.cpp'],self.work/'contracts')
  wav=self.work/'synthetic.wav'
  run=subprocess.run([str(exe),str(wav)],capture_output=True,text=True,timeout=30)
  self.assertEqual(run.returncode,0,run.stderr+' '+run.stdout)
  self.assertIn('TWO_PLATFORMS',run.stdout)
  data=wav.read_bytes();self.assertEqual(data[:4],b'RIFF')
  self.assertEqual(data[8:12],b'WAVE');self.assertEqual(len(data),54)
 def test_universal_host_runs_headless_two_device_demo(self):
  import os
  if os.name=='nt':self.skipTest('Win32 universal host requires interactive window')
  exe=self._compile([ROOT/'host/UniversalHost.cpp'],self.work/'host')
  run=subprocess.run([str(exe)],capture_output=True,text=True,timeout=20)
  self.assertEqual(run.returncode,0,run.stdout+' '+run.stderr)
  self.assertIn('UNIVERSAL_HOST_TWO_DEVICE_SYNTHETIC_PASS',run.stdout)
 def test_actual_z80_native_state_drives_common_video_and_audio_exports(self):
  cpp=self.work/'guest.cpp'
  cpp.write_text(r'''
#include "systems/mastersystem/runtime.hpp"
#include <cassert>
int main(int argc,char** argv){
 rd::State s;s.out(0x7f,0x80);s.out(0x7f,0x01);s.out(0x7f,0x90);
 s.advance_cycles(200000);s.vdp_regs[2]=0x0e;s.vdp_addr=0;s.vdp_code=1;
 s.out(0xbe,0x80);s.cram[1]=3;
 s.write_ppm(argv[1]);assert(s.write_wav(argv[2]));
 return 0;
}''')
  exe=self._compile([cpp,ROOT/'systems/mastersystem/runtime.cpp'],self.work/'native')
  ppm=self.work/'frame.ppm';wav=self.work/'native.wav'
  run=subprocess.run([str(exe),str(ppm),str(wav)],capture_output=True,text=True,timeout=25)
  self.assertEqual(run.returncode,0,run.stderr)
  frame=ppm.read_bytes();self.assertTrue(frame.startswith(b'P6\n256 192\n255\n'))
  self.assertEqual(frame[len(b'P6\n256 192\n255\n'):][:3],bytes([255,0,0]))
  a=wav.read_bytes();self.assertEqual(a[:4],b'RIFF');self.assertGreater(len(a),100)
  self.assertEqual(hashlib.sha256(a).hexdigest(),hashlib.sha256(wav.read_bytes()).hexdigest())
 def test_compiled_authored_z80_io_program_emits_video_and_audio_evidence(self):
  if not shutil.which('cmake') or not shutil.which('g++'):
   self.skipTest('Native compiler/CMake required')
  import sqlite3
  from test_native_execution_v0404 import NativeExecutionTests
  from discovery.store import connect,store_source
  from nativeprep.engine import prepare
  from nativepilot.engine import pilot
  fixture=NativeExecutionTests('test_wrong_rom_and_outside_root_blocked');fixture.setUp()
  try:
   raw=bytearray(65536)
   program=bytes.fromhex('3e80d37f3e01d37f3e90d37f3e00d3bf3e40d3bf3effd3bedbdc3200c076')
   raw[:len(program)]=program;raw[0x7ff0:0x7ff8]=b'TMR SEGA'
   fixture.rom.write_bytes(raw);sha=hashlib.sha256(raw).hexdigest()
   con=connect(fixture.db)
   store_source(con,sha,fixture.rom,len(raw),'SHA256_COMPLETE','mastersystem','IO test','author-created')
   con.close()
   target=prepare(fixture.db,sha,self.work/'prepared',[fixture.roms],analyze=False)['target_id']
   def v(space,n,offset):return {'space':space,'size':n,'offset':offset}
   instructions=[]
   pc=0
   while pc<len(program):
    op=raw[pc];length=1 if op==0x76 else 2
    if op==0x3e:
     pcode=[{'op':'COPY','inputs':[v('const',1,raw[pc+1])],'output':v('register',1,1)}];mnem='LD'
    elif op==0xd3:
     pcode=[{'op':'STORE','memory_space':'io','inputs':[v('const',1,0),v('const',2,raw[pc+1]),v('register',1,1)]}];mnem='OUT'
    elif op==0xdb:
     pcode=[{'op':'LOAD','memory_space':'io','inputs':[v('const',1,0),v('const',2,raw[pc+1])],'output':v('register',1,1)}];mnem='IN'
    elif op==0x32:
     pcode=[{'op':'COPY','inputs':[v('register',1,1)],'output':v('ram',1,0xc000)}];mnem='LD'
     length=3
    elif op==0x76:
     pcode=[{'op':'CALLOTHER','inputs':[v('const',1,9)]}];mnem='HALT'
    else:raise AssertionError('fixture')
    instructions.append({'address':pc,'length':length,'fallthrough':pc+length,
                         'mnemonic':mnem,'bytes_sha256':hashlib.sha256(raw[pc:pc+length]).hexdigest(),
                         'pcode':pcode})
    pc+=length
   doc={'schema':'recomp-function-pcode-v1','source_sha256':sha,'target_id':target,
        'language':'z80:LE:16:default','functions':[{'entry':0,'name':'AUTHOR_Z80_IO','instructions':instructions}]}
   source=self.work/'io-pcode.json';source.write_text(json.dumps(doc))
   con=sqlite3.connect(fixture.db)
   con.execute('UPDATE native_preparations_v0403 SET export_path=?,candidate_count=1 WHERE source_id=?',(str(source),sha))
   con.commit();con.close()
   replay=self.work/'inputs.csv';replay.write_bytes(b'RECOMP_INPUT_CYCLES_V1\r\n0,0,16\r\n')
   output=pilot(fixture.db,sha,self.work/'io-pilot',[fixture.roms],120,max_recoveries=0,
                watch_addresses=(0xc000,),input_events=replay)
   self.assertGreaterEqual(output['trace']['vram_writes'],1)
   self.assertEqual(output['trace']['watched_memory'][0]['value'],0xef)
   self.assertEqual(output['input_replay']['sha256'],hashlib.sha256(replay.read_bytes()).hexdigest())
   self.assertEqual(output['trace']['io_reads'],1)
   self.assertGreaterEqual(output['trace']['psg_writes'],3)
   self.assertIn(output['trace']['audio_capture']['status'],('CANDIDATE_PSG_PCM_APPROXIMATE_NOT_REFERENCE_VERIFIED',))
   stream=self.work/'io-pilot'/output['trace']['audio_capture']['path']
   self.assertTrue(stream.read_bytes().startswith(b'RIFF'))
   self.assertTrue((self.work/'io-pilot'/'diagnostic-background.ppm').is_file())
   self.assertFalse(output.get('native_qualified',False))
  finally:fixture.doCleanups()
 def test_generated_z80_native_build_contains_portable_device_adapter(self):
  # Use existing genuine C++ generator + source attestation fixture, but no
  # commercial ROM, and check that generated projects are self-contained.
  from test_native_execution_v0404 import NativeExecutionTests
  fixture=NativeExecutionTests('test_wrong_rom_and_outside_root_blocked');fixture.setUp()
  try:
   from nativepilot.generator import generate_project
   project=self.work/'generated'
   result=generate_project(fixture.doc,fixture.rom,project)
   self.assertGreater(result['translated_instructions'],0)
   for file in ('hardware/core.hpp','hardware/wav.hpp','hardware/adapters/sms.hpp'):
    self.assertTrue((project/file).is_file())
   if shutil.which('cmake') and (shutil.which('g++') or shutil.which('clang++')):
    subprocess.run(['cmake','-S',str(project),'-B',str(project/'build')],check=True,capture_output=True,timeout=30)
    subprocess.run(['cmake','--build',str(project/'build')],check=True,capture_output=True,timeout=90)
  finally:fixture.doCleanups()
