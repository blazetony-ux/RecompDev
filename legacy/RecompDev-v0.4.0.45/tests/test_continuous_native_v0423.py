"""Source-authenticated continuous native execution, not commercial-ROM parity."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nativepilot.generator import generate_project


def locate_native_app(build_directory, *, windows=None):
  """Select the actual CMake product, never an MSVC project/metadata file.

  Windows treats many ordinary files as accessible with os.X_OK, so
  rglob('RecompDevNativeApp*') is not a safe executable discovery strategy.
  """
  build=Path(build_directory)
  if windows is None:windows=os.name=='nt'
  if windows:
   candidates=(build/'Release'/'RecompDevNativeApp.exe',
               build/'RecompDevNativeApp.exe')
  else:
   candidates=(build/'RecompDevNativeApp',)
  return next((path for path in candidates if path.is_file()),None)


class ContinuousNativeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.dir=Path(self.tmp.name)
 def synthetic_project(self,seed=3,return_doc=False):
  # Two independent authored programs use the same translator and native host.
  # The Z80 program polls active-low controller port DC and changes SMS CRAM 0,
  # produces PSG writes, and runs until a bounded frame limit.
  raw=bytearray(65536);program=bytearray(b'\xc3\x03\x00')
  ins=[]
  def var(space,size,offset):return {'space':space,'size':size,'offset':offset}
  def add(bs,mnemonic,pcode):
   pc=len(program);program.extend(bs)
   ins.append({'address':pc,'length':len(bs),'fallthrough':pc+len(bs),
     'mnemonic':mnemonic,'bytes_sha256':hashlib.sha256(bs).hexdigest(),'pcode':pcode})
  def ld(v):add(bytes([0x3e,v]),'LD',[{'op':'COPY','inputs':[var('const',1,v)],'output':var('register',1,1)}])
  def out(port):add(bytes([0xd3,port]),'OUT',[{'op':'STORE','memory_space':'io','inputs':[var('const',1,0),var('const',2,port),var('register',1,1)]}])
  ld(0x80);out(0x7f);ld(0x01);out(0x7f);ld(0x90);out(0x7f)
  loop=len(program)
  ld(0);out(0xbf);ld(0xc0);out(0xbf)
  add(bytes([0xdb,0xdc]),'IN',[{'op':'LOAD','memory_space':'io','inputs':[var('const',1,0),var('const',2,0xdc)],'output':var('register',1,1)}])
  out(0xbe)
  if seed==4:
   ld(0x70);out(0x7f)  # a second independently-authored control flow
  add(bytes([0xc3,loop&255,loop>>8]),'JP',[{'op':'BRANCH','inputs':[var('ram',1,loop)]}])
  raw[:len(program)]=program;raw[0x7ff0:0x7ff8]=b'TMR SEGA'
  rom=self.dir/f'fixture-{seed}.sms';rom.write_bytes(raw)
  sha=hashlib.sha256(raw).hexdigest()
  doc={'schema':'recomp-function-pcode-v1','source_sha256':sha,'target_id':f'fixture-{seed}',
   'language':'z80:LE:16:default','functions':[{'entry':3,'name':'AUTHOR_REPLAY', 'instructions':ins}]}
  project=self.dir/f'build-{seed}';stats=generate_project(doc,rom,project)
  return (rom,project,stats,doc) if return_doc else (rom,project,stats)
 def compile(self,p):
  if not shutil.which('cmake') or not (os.name=='nt' or shutil.which('g++') or shutil.which('clang++')):self.skipTest('CMake and C++ required')
  for command in (['cmake','-S',str(p),'-B',str(p/'build')],['cmake','--build',str(p/'build'),'--config','Release','-j','2']):
   proc=subprocess.run(command,text=True,capture_output=True,timeout=100)
   self.assertEqual(proc.returncode,0,proc.stderr[-4500:]+proc.stdout[-500:])
  exe=locate_native_app(p/'build')
  self.assertIsNotNone(exe, f'Expected compiled RecompDevNativeApp binary under {p / "build"}; CMake metadata is not executable')
  return exe
 def execute(self,exe,rom,label,replay='-'):
  prefix=str(self.dir/label)
  proc=subprocess.run([str(exe),str(rom),prefix,'3','300000',str(replay)],capture_output=True,text=True,timeout=45)
  self.assertEqual(proc.returncode,0,proc.stderr[-1500:])
  result=json.loads(next(x.split('=',1)[1] for x in proc.stdout.splitlines() if x.startswith('NATIVE_APP_RESULT=')))
  self.assertEqual(result['status'],'FRAME_BUDGET_REACHED',result)
  self.assertEqual(result['frames'],3);self.assertEqual(len(result['frame_hashes']),3)
  self.assertGreater(result['native_steps'],10)
  self.assertGreater(result['audio_samples'],0)
  self.assertFalse(result['native_qualified'])
  self.assertEqual(result['hardware_parity'],'NOT_TESTED')
  self.assertTrue((self.dir/(label+'.ppm')).read_bytes().startswith(b'P6\n256 192\n255\n'))
  self.assertTrue((self.dir/(label+'.wav')).read_bytes().startswith(b'RIFF'))
  return result
 def test_windows_cmake_project_metadata_is_not_an_executable(self):
  build=self.dir/'generated-build'
  build.mkdir()
  (build/'RecompDevNativeApp.vcxproj').write_text('<Project/>')
  (build/'RecompDevNativeApp.vcxproj.filters').write_text('<Project/>')
  (build/'RecompDevNativeApp.pdb').write_bytes(b'debug symbols')
  self.assertIsNone(locate_native_app(build,windows=True))
  product=build/'Release'/'RecompDevNativeApp.exe'
  product.parent.mkdir()
  product.write_bytes(b'test executable placeholder')
  self.assertEqual(locate_native_app(build,windows=True),product)
  linux=build/'RecompDevNativeApp'
  linux.write_bytes(b'test executable placeholder')
  self.assertEqual(locate_native_app(build,windows=False),linux)

 def test_both_z80_programs_execute_animated_native_host_headlessly(self):
  for seed in (3,4):
   rom,project,stats=self.synthetic_project(seed)
   self.assertGreater(stats['translated_instructions'],5)
   exe=self.compile(project)
   one=self.execute(exe,rom,f'{seed}-one')
   two=self.execute(exe,rom,f'{seed}-two')
   self.assertEqual(one,two)
   self.assertEqual((self.dir/f'{seed}-one.ppm').read_bytes(),(self.dir/f'{seed}-two.ppm').read_bytes())
   self.assertEqual((self.dir/f'{seed}-one.wav').read_bytes(),(self.dir/f'{seed}-two.wav').read_bytes())
   input_csv=self.dir/f'press-{seed}.csv'
   input_csv.write_bytes(b'RECOMP_INPUT_CYCLES_V1\r\n0,0,0\r\n70000,0,16\r\n')
   changed=self.execute(exe,rom,f'{seed}-pressed',input_csv)
   self.assertNotEqual(one['frame_hashes'],changed['frame_hashes'])
 def test_fail_closed_for_wrong_limits_and_missing_rom(self):
  rom,project,_=self.synthetic_project(3);exe=self.compile(project)
  for args in ((str(rom),str(self.dir/'bad'),'99999','20'),(str(self.dir/'notfound.rom'),str(self.dir/'bad'),'1','20')):
   proc=subprocess.run([str(exe),*args],capture_output=True,text=True,timeout=10)
   self.assertNotEqual(proc.returncode,0)
 def test_source_attested_launcher_and_replay_rejection(self):
  import importlib.util
  from nativepilot.generator import sha256
  rom,project,_=self.synthetic_project(3);exe=self.compile(project)
  spec=importlib.util.spec_from_file_location('native_app_launcher',ROOT/'tools/Run-Continuous-Native.py')
  mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
  manifest=mod.run(project,rom,sha256(rom),self.dir/'launcher',frames=2,steps=300000)
  self.assertEqual(manifest['status'],'FRAME_BUDGET_REACHED')
  self.assertEqual(manifest['source_sha256'],sha256(rom))
  self.assertTrue(manifest['assets']['wav']['sha256'])
  self.assertTrue((self.dir/'launcher'/'continuous-session.json').is_file())
  with self.assertRaisesRegex(ValueError,'source differs'):
   mod.run(project,rom,'0'*64,self.dir/'reject')
  raw=rom.read_bytes();rom.write_bytes(raw[:-1]+b'\x01')
  with self.assertRaisesRegex(ValueError,'source differs'):
   mod.run(project,rom,hashlib.sha256(raw).hexdigest(),self.dir/'reject2')
 def test_generic_continuous_runner_not_tied_to_z80(self):
  source=self.dir/'generic.cpp';source.write_text(r'''
#include "hardware/continuous.hpp"
#include "hardware/adapters/alternate.hpp"
#include <cassert>
using namespace recomp::hw;
class OtherCpu final:public NativeCpu {
 u64 t_=0;std::string no_;
 public:bool step()override{t_+=1000;return true;}
 u64 cycles()const override{return t_;}
 const std::string& blocker()const override{return no_;}
};
int main(){OtherCpu cpu;auto panel=std::make_shared<alternate::Panel>();
 Runtime runtime(2000000,50,16000);auto frames=std::make_shared<HeadlessFrames>();auto audio=std::make_shared<HeadlessAudio>();
 runtime.bus().attach(panel);runtime.video(*panel,frames);runtime.audio(*panel,audio);runtime.input(*panel);
 ContinuousSession s(cpu,runtime);RunLimits l;l.max_steps=5000;l.max_frames=3;
 auto result=s.run(l);assert(result.status=="FRAME_BUDGET_REACHED");
 assert(frames->fingerprints.size()==3);assert(audio->total_samples==960);}
''')
  cc=shutil.which('g++') or shutil.which('clang++')
  if not cc:self.skipTest('C++ unavailable')
  exe=self.dir/'other'
  compiled=subprocess.run([cc,'-std=c++17','-I',str(ROOT),str(source),'-o',str(exe)],capture_output=True,text=True,timeout=30)
  self.assertEqual(compiled.returncode,0,compiled.stderr)
  ran=subprocess.run([str(exe)],capture_output=True,text=True,timeout=15)
  self.assertEqual(ran.returncode,0,ran.stderr)
if __name__=='__main__':unittest.main()
