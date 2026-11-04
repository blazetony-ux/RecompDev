"""Compile source-authenticated native CPU code and verify optional host sinks.

Only synthetic author-created programs; no claim of commercial ROM parity.
"""
import hashlib
from contextlib import closing
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
import test_continuous_native_v0423 as continuous


class NullBackendTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.dir=Path(self.tmp.name)
 def fixture(self,seed):
  fixture=continuous.ContinuousNativeTests('test_fail_closed_for_wrong_limits_and_missing_rom')
  fixture.setUp();self.addCleanup(fixture.doCleanups)
  rom,project,stats=fixture.synthetic_project(seed)
  exe=fixture.compile(project)
  return rom,project,exe
 def invoke(self,exe,rom,name,extra=(),success=True):
  out=self.dir/name;cmd=[str(exe),str(rom),str(out),'3','300000','-',*extra]
  p=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
  if not success:
   self.assertNotEqual(p.returncode,0,p.stdout+p.stderr)
   return p.stderr
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  doc=json.loads(next(s.partition('=')[2] for s in p.stdout.splitlines() if s.startswith('NATIVE_APP_RESULT=')))
  self.assertEqual(doc['schema'],'recomp-continuous-native-v2')
  self.assertEqual(doc['status'],'FRAME_BUDGET_REACHED')
  self.assertEqual(doc['frames'],3)
  self.assertGreater(doc['audio_samples'],0)
  self.assertGreater(doc['native_steps'],100)
  self.assertFalse(doc['native_qualified'])
  return doc
 def test_generated_native_guest_equal_between_null_and_capture_on_two_programs(self):
  for seed in (3,4):
   with self.subTest(seed=seed):
    rom,project,exe=self.fixture(seed)
    full=self.invoke(exe,rom,f'{seed}-capture')
    null=self.invoke(exe,rom,f'{seed}-null',('--mode','HEADLESS_AUTONOMOUS'))
    again=self.invoke(exe,rom,f'{seed}-null-repeated',('--mode','HEADLESS_AUTONOMOUS'))
    for field in ('native_steps','guest_cycles','frames','audio_samples','guest_state_fingerprint',
                  'guest_vdp_writes','guest_psg_writes'):
     self.assertEqual(full[field],null[field],field)
    self.assertEqual(null,again)
    self.assertEqual(null['video_backend'],'null');self.assertEqual(null['audio_backend'],'null')
    self.assertEqual(null['input_backend'],'neutral')
    self.assertEqual(null['discarded_frames'],3)
    self.assertEqual(null['discarded_audio_samples'],null['audio_samples'])
    self.assertEqual(null['frame_hashes'],[])
    self.assertFalse((self.dir/f'{seed}-null.ppm').exists())
    self.assertFalse((self.dir/f'{seed}-null.wav').exists())
    self.assertTrue((self.dir/f'{seed}-capture.ppm').read_bytes().startswith(b'P6'))
    self.assertTrue((self.dir/f'{seed}-capture.wav').read_bytes().startswith(b'RIFF'))
 def test_mix_and_match_output_and_replayed_input(self):
  rom,project,exe=self.fixture(3)
  replay=self.dir/'press.csv';replay.write_bytes(b'RECOMP_INPUT_CYCLES_V1\n0,0,0\n70000,0,16\n')
  normal=self.invoke(exe,rom,'neutral',('--video','null','--audio','capture','--input','neutral'))
  changed=self.invoke(exe,rom,'replay',('--mode','HEADLESS_AUTONOMOUS',
                 '--input-events',str(replay)))
  capture=self.invoke(exe,rom,'replay-capture',('--video','capture','--audio','capture',
                 '--input','replay','--input-events',str(replay)))
  self.assertNotEqual(normal['guest_state_fingerprint'],changed['guest_state_fingerprint'])
  self.assertEqual(changed['guest_state_fingerprint'],capture['guest_state_fingerprint'])
  self.assertTrue((self.dir/'neutral.wav').exists())
  self.assertFalse((self.dir/'neutral.ppm').exists())
  self.assertEqual(changed['input_backend'],'replay')
  self.assertEqual(changed['audio_samples'],capture['audio_samples'])
 def test_invalid_backend_and_input_modes_fail_closed(self):
  rom,project,exe=self.fixture(3)
  for extras in (('--video','missing'),('--input','replay'),('--input','live'),
                 ('--input','neutral','--input-events','nofile.csv'),
                 ('--mode','HEADLESS_AUTONOMOUS','--video','window'),
                 ('--mode','HEADLESS_AUTONOMOUS','--audio','speaker'),
                 ('--video','window','--mode','HEADLESS_AUTONOMOUS'),
                 ('--audio','speaker','--mode','HEADLESS_AUTONOMOUS'),
                 ('--mode','HEADLESS_AUTONOMOUS','--input','live'),
                 ('--window','--mode','HEADLESS_AUTONOMOUS'),
                 ('--mode','HEADLESS_AUTONOMOUS','--window')):
   with self.subTest(extras=extras):
    self.assertIn('NATIVE_APP_ERROR=',self.invoke(exe,rom,'invalid',extras,False))
 def test_source_attested_launcher_accepts_null_sinks_and_rejects_tamper(self):
  rom,project,exe=self.fixture(3)
  spec=importlib.util.spec_from_file_location('launcher',ROOT/'tools/Run-Continuous-Native.py')
  mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
  source=hashlib.sha256(rom.read_bytes()).hexdigest()
  output=mod.run(project,rom,source,self.dir/'launcher-null',frames=3,steps=300000,mode='HEADLESS_AUTONOMOUS')
  self.assertEqual(output['status'],'FRAME_BUDGET_REACHED')
  self.assertEqual(output['assets'],{})
  self.assertEqual(output['discarded_frames'],3)
  self.assertEqual(output['discarded_audio_samples'],output['audio_samples'])
  self.assertEqual(output['video_backend'],'null')
  self.assertEqual(output['host_mode'],'HEADLESS_AUTONOMOUS')
  capture=mod.run(project,rom,source,self.dir/'launcher-capture',frames=3,steps=300000)
  self.assertEqual(output['guest_state_fingerprint'],capture['guest_state_fingerprint'])
  self.assertEqual(output['guest_cycles'],capture['guest_cycles'])
  self.assertIn('sha256',capture['assets']['ppm'])
  with self.assertRaisesRegex(ValueError,'Autonomous mode cannot require physical'):
   mod.run(project,rom,source,self.dir/'reject',mode='HEADLESS_AUTONOMOUS',video_backend='window')
  rom.write_bytes(rom.read_bytes()[:-1]+b'\x01')
  with self.assertRaisesRegex(ValueError,'source differs'):
   mod.run(project,rom,source,self.dir/'tamper',mode='HEADLESS_AUTONOMOUS')
 def test_integrated_headless_campaign_proves_capture_equivalence(self):
  from nativepilot.generator import sha256
  from discovery.store import connect,store_source
  from nativeprep.engine import prepare
  from platform424.campaign import run
  import sqlite3
  fixture=continuous.ContinuousNativeTests('test_fail_closed_for_wrong_limits_and_missing_rom')
  fixture.setUp();self.addCleanup(fixture.doCleanups)
  rom,project,stats,doc=fixture.synthetic_project(seed=3,return_doc=True)
  db=self.dir/'campaign.sqlite';shutil.copyfile(ROOT/'catalogue.sqlite',db)
  con=connect(db)
  store_source(con,sha256(rom),rom,rom.stat().st_size,
               'SHA256_COMPLETE','mastersystem','Synthetic Headless','author-created')
  con.close()
  prepared=prepare(db,sha256(rom),self.dir/'prepared',[rom.parent],analyze=False)
  doc['target_id']=prepared['target_id']
  export=self.dir/'source-pcode.json';export.write_text(json.dumps(doc))
  with closing(sqlite3.connect(db)) as con:
   con.execute('UPDATE native_preparations_v0403 SET export_path=?,candidate_count=1 WHERE source_id=?',
               (str(export),sha256(rom)))
   con.commit()
  campaign=run(db,sha256(rom),[rom.parent],self.dir/'jobs',steps=100000,frames=2,
               max_recoveries=0,mode='HEADLESS_AUTONOMOUS')
  self.assertEqual(campaign['status'],'EXPERIMENTAL_NATIVE_APPLICATION_EXECUTED',campaign)
  self.assertEqual(campaign['host_backends'],{'video':'null','audio':'null','input':'neutral'})
  self.assertGreater(campaign['guest_vdp_writes'],0)
  self.assertGreater(campaign['guest_psg_writes'],0)
  steps={x['stage']:x for x in campaign['stages']}
  self.assertEqual(steps['null_capture_guest_state_equivalence']['status'],'PASS')
  job=Path(campaign['job_directory'])
  self.assertTrue((job/'host-capture-control'/'native-frame.ppm').is_file())
  self.assertFalse((job/'host'/'native-frame.ppm').exists())
  self.assertFalse((job/'host'/'native-frame.wav').exists())
  # Windows requires every connection to close before the temp directory is deleted.
  if os.name=='nt':
   db.unlink()  # raises WinError 32 immediately if a connection still holds the file
 def test_non_z80_machine_uses_same_null_sink_contract(self):
  cc=shutil.which('g++') or shutil.which('clang++')
  if not cc and (os.name!='nt' or not shutil.which('cmake')):self.skipTest('No C++ compiler')
  source=self.dir/'other.cpp';source.write_text(r'''
#include "hardware/backends.hpp"
#include "hardware/continuous.hpp"
#include "hardware/adapters/alternate.hpp"
#include <cassert>
using namespace recomp::hw;
struct OtherCpu final:NativeCpu {u64 time=0;std::string message;
 bool step()override{time+=500;return true;}u64 cycles()const override{return time;}
 const std::string& blocker()const override{return message;}};
int main(){
 OtherCpu a,b;alternate::Panel p,q;
 Runtime first(2000000,50,16000),second(2000000,50,16000);
 auto displayed=std::make_shared<HeadlessFrames>();auto sounded=std::make_shared<HeadlessAudio>();
 auto null_frames=std::make_shared<NullVideoSink>();auto null_audio=std::make_shared<NullAudioSink>();
 first.bus().attach(std::shared_ptr<Device>(&p,[](Device*){}));
 second.bus().attach(std::shared_ptr<Device>(&q,[](Device*){}));
 first.video(p,displayed);first.audio(p,sounded);first.input(p);
 second.video(q,null_frames);second.audio(q,null_audio);second.input(q);
 NeutralInputSource{}.install(first);NeutralInputSource{}.install(second);
 ContinuousSession normal(a,first),silent(b,second);RunLimits limits;
 limits.max_steps=4000;limits.max_frames=3;
 auto x=normal.run(limits),y=silent.run(limits);
 assert(x.status=="FRAME_BUDGET_REACHED"&&y.status==x.status);
 assert(a.time==b.time&&first.cycles()==second.cycles());
 assert(null_frames->frames()==displayed->fingerprints.size());
 assert(null_audio->samples()==sounded->total_samples);
 assert(p.read({Space::Memory,0x4001})==q.read({Space::Memory,0x4001}));
 assert(video_backend("null")==VideoBackend::Null);
 assert(audio_backend("null")==AudioBackend::Null);
 assert(input_backend("neutral")==InputBackend::Neutral);
}
''')
  if os.name=='nt':
   (self.dir/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.17)\nproject(GenericNull LANGUAGES CXX)\nadd_executable(other other.cpp)\ntarget_compile_features(other PRIVATE cxx_std_17)\ntarget_include_directories(other PRIVATE "'+str(ROOT).replace('\\','/')+'")\n')
   for command in (['cmake','-S',str(self.dir),'-B',str(self.dir/'build')],
                   ['cmake','--build',str(self.dir/'build'),'--config','Release']):
    proc=subprocess.run(command,capture_output=True,text=True,timeout=80)
    self.assertEqual(proc.returncode,0,proc.stderr)
   exe=self.dir/'build'/'Release'/'other.exe'
   if not exe.is_file():exe=self.dir/'build'/'other.exe'
  else:
   exe=self.dir/'other'
   proc=subprocess.run([cc,'-std=c++17','-I',str(ROOT),str(source),'-o',str(exe)],capture_output=True,text=True,timeout=40)
   self.assertEqual(proc.returncode,0,proc.stderr)
  run=subprocess.run([str(exe)],capture_output=True,text=True,timeout=20)
  self.assertEqual(run.returncode,0,run.stderr)

if __name__=='__main__':unittest.main()
