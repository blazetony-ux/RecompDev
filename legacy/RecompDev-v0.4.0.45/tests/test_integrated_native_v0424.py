"""Authentic workflow integration on original author-created test ROMs only."""
import hashlib
import os
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from platform424.evidence import inspect_native_job,inspect_session,history
from tooling.release_contract import version
from platform424.campaign import run
from nativecore.eventstream import manifest_for_native

class IntegratedReleaseTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.work=Path(self.t.name)
 def test_source_linked_verified_old_legacy_job_and_tamper(self):
  install=self.work/'RecompDev-v0.4.0.23';job=install/'evidence'/'native-pilot-v0423'/'jobs'/'0123456789abcdef';job.mkdir(parents=True)
  sha='a'*64;stream=job/'event-streams'/'attempt-00-budget-50';stream.mkdir(parents=True)
  chunk=stream/'hardware-events-000000.jsonl';chunk.write_text(json.dumps({'step':3,'pc':2,'kind':'PSG_WRITE','address':127,'value':159})+'\n')
  trace={'event_stream_chunks':1,'event_stream_events':1,'events_total':1,'event_stream_bytes':chunk.stat().st_size,'event_stream_complete':True,
         'events':[{'step':3,'pc':2,'kind':'PSG_WRITE','address':127,'value':159}], 'event_stream_directory':'event-streams/attempt-00-budget-50'}
  trace['event_stream_manifest']=manifest_for_native(stream,trace)
  (job/'pilot-report.json').write_text(json.dumps({'source_id':sha,'status':'NATIVE_STEP_BUDGET_REACHED','translated_instructions':4,
    'native_steps':50,'trace':trace,'generation':{'translated_instructions':4},'reference_parity':'NOT_TESTED'}))
  first=history(sha,[install]);self.assertEqual(len(first['pilots']),1)
  self.assertEqual(first['pilots'][0]['event_integrity'],'SHA256_VERIFIED_FULL_STREAM')
  self.assertFalse(first['native_qualified'])
  chunk.write_text(chunk.read_text().replace('159','160'))
  second=history(sha,[install]);self.assertEqual(second['pilots'],[])
  self.assertIn('hash mismatch',second['rejected_evidence'][0]['reason'])
  self.assertEqual(history('b'*64,[install])['pilots'],[])
 def test_session_assets_verified_no_parity_claims(self):
  folder=self.work/'session';folder.mkdir()
  ppm=folder/'native-frame.ppm';ppm.write_bytes(b'P6\n1 1\n255\n\x00\x00\x00')
  sha='f'*64
  (folder/'continuous-session.json').write_text(json.dumps({'schema':'recomp-continuous-owner-session-v1','source_sha256':sha,
    'status':'FRAME_BUDGET_REACHED','native_steps':100,'frames':1,'audio_samples':0,
    'assets':{'ppm':{'size':ppm.stat().st_size,'sha256':hashlib.sha256(ppm.read_bytes()).hexdigest()}}}))
  self.assertEqual(inspect_session(folder,sha)['asset_integrity'],'SHA256_VERIFIED')
  ppm.write_bytes(ppm.read_bytes()+b'bad')
  with self.assertRaisesRegex(ValueError,'mismatch'):inspect_session(folder,sha)
 @unittest.skipUnless(shutil.which('cmake') and (os.name=='nt' or shutil.which('g++') or shutil.which('clang++')),'C++ compiler and CMake needed')
 def test_real_pilot_and_continuous_launch_on_source_attested_z80_fixture(self):
  from test_native_execution_v0404 import NativeExecutionTests
  f=NativeExecutionTests('test_wrong_rom_and_outside_root_blocked');f.setUp()
  try:
   r=run(f.db,f.sha,[f.roms],self.work/'jobs',steps=50,frames=2,max_recoveries=0)
   self.assertEqual(r['source_sha256'],f.sha)
   self.assertEqual(r['status'],'NATIVE_APPLICATION_BLOCKED',r)
   self.assertEqual([x['stage'] for x in r['stages']],['source_authentication','compile_and_trace','verified_native_observations','deterministic_native_replay','continuous_native_host'])
   self.assertEqual(r['stages'][2]['event_integrity'],'SHA256_VERIFIED_FULL_STREAM')
   self.assertEqual(r['stages'][4]['status'],'BANKED_CODE_NOT_TRANSLATED')
   self.assertFalse(r['native_qualified'])
   self.assertTrue((Path(r['job_directory'])/'campaign-result.json').is_file())
   # A different source with the same path must be rejected before compilation.
   b=f.rom.read_bytes();f.rom.write_bytes(b[:-1]+b'X')
   with self.assertRaisesRegex(ValueError,'no longer matches'):
    run(f.db,f.sha,[f.roms],self.work/'changed',steps=50)
  finally:f.doCleanups()
 @unittest.skipUnless(shutil.which('cmake') and (os.name=='nt' or shutil.which('g++') or shutil.which('clang++')),'C++ compiler and CMake needed')
 def test_successful_full_compiled_z80_native_video_audio_host(self):
  from test_continuous_native_v0423 import ContinuousNativeTests
  from discovery.store import connect,store_source
  from nativeprep.engine import prepare
  from nativepilot.generator import sha256
  fixture=ContinuousNativeTests('test_fail_closed_for_wrong_limits_and_missing_rom');fixture.setUp()
  try:
   rom,project,stats,doc=fixture.synthetic_project(seed=3,return_doc=True)
   db=self.work/'catalogue.sqlite';shutil.copyfile(ROOT/'catalogue.sqlite',db)
   con=connect(db);store_source(con,sha256(rom),rom,rom.stat().st_size,'SHA256_COMPLETE','mastersystem','Synthetic Controls','author-created');con.close()
   prepared=prepare(db,sha256(rom),self.work/'prepared',[rom.parent],analyze=False)
   doc['target_id']=prepared['target_id']
   export=self.work/'source-pcode.json';export.write_text(json.dumps(doc))
   con=sqlite3.connect(db);con.execute('UPDATE native_preparations_v0403 SET export_path=?,candidate_count=1 WHERE source_id=?',(str(export),sha256(rom)))
   con.commit();con.close()
   result=run(db,sha256(rom),[rom.parent],self.work/'success',steps=100000,frames=2,max_recoveries=0)
   self.assertEqual(result['status'],'EXPERIMENTAL_NATIVE_APPLICATION_EXECUTED',result)
   self.assertGreaterEqual(result['frames'],2)
   self.assertEqual(result['stages'][-2]['status'],'PASS')
   self.assertTrue(result['host_assets']['ppm']['sha256'])
   self.assertTrue(result['host_assets']['wav']['sha256'])
   self.assertEqual(result['independent_parity'],'NOT_ESTABLISHED')
   self.assertFalse(result['native_qualified'])
  finally:fixture.doCleanups()
 def test_workbench_unified_source_api_reports_registered_target(self):
  import socket,time
  from urllib.request import urlopen
  from test_native_execution_v0404 import NativeExecutionTests
  f=NativeExecutionTests('test_wrong_rom_and_outside_root_blocked');f.setUp()
  with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  proc=subprocess.Popen([sys.executable,str(ROOT/'recomp.py'),'--db',str(f.db),'serve','--port',str(port),'--rom-root',str(f.roms)],
      cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  try:
   for _ in range(80):
    try:
     with urlopen(f'http://127.0.0.1:{port}/api/unified-evidence',timeout=2) as stream:doc=json.load(stream)
     break
    except OSError:time.sleep(.05)
   else:self.fail('Workbench failed to provide unified evidence API')
   self.assertTrue(doc['ok']);self.assertEqual(doc['data']['release'],version(ROOT))
   self.assertIn(f.sha,[x['source_id'] for x in doc['data']['targets']])
   with urlopen(f'http://127.0.0.1:{port}/tooling',timeout=2) as stream:html=stream.read().decode()
   self.assertIn('Source-linked native evidence',html)
   self.assertIn('v'+version(ROOT),html)
  finally:
   proc.terminate()
   try:proc.wait(timeout=4)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
   f.doCleanups()
 def test_wrong_platform_does_not_fallback(self):
  db=self.work/'cat.sqlite';con=sqlite3.connect(db)
  con.execute('CREATE TABLE discovery_sources (source_id TEXT,path TEXT,system TEXT,bytes INTEGER)')
  rom=self.work/'program';rom.write_bytes(b'\x00\x01\x02');sha=hashlib.sha256(rom.read_bytes()).hexdigest()
  con.execute('INSERT INTO discovery_sources VALUES(?,?,?,?)',(sha,str(rom),'megadrive',3));con.commit();con.close()
  with self.assertRaisesRegex(ValueError,'CONTINUOUS_MACHINE_ADAPTER_NOT_AVAILABLE'):
   run(db,sha,[self.work],self.work/'unused',steps=100)
if __name__=='__main__':unittest.main()
