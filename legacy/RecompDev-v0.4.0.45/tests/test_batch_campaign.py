"""No commercial ROM fixtures; function status never inferred from C++ compilation."""
import hashlib
import os
import subprocess
from unittest.mock import patch
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from native_batch import create_campaign,index_sources,init,attempt_go,probe_go_sources
from workbench import data
from graph_store import connect

ROOT=Path(__file__).resolve().parents[1]
class BatchTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.db=Path(self.temp.name)/'c.sqlite';shutil.copyfile(ROOT/'catalogue.sqlite',self.db)

 def test_real_snapshot_all_targets_assessed(self):
  result=create_campaign(self.db)
  self.assertEqual(result['totals']['targets'],3)
  self.assertEqual(result['totals']['function_candidates'],309)
  self.assertEqual(result['totals']['stages']['SOURCE_UNAVAILABLE'],309)
  c=connect(self.db,readonly=True)
  try:
   ui=data(c,'conversion',{})
   self.assertEqual(len(ui['targets']),3)
   self.assertEqual(len(ui['jobs']),309)
   self.assertTrue(all(j['stage']=='SOURCE_UNAVAILABLE' for j in ui['jobs']))
   self.assertEqual(c.execute('SELECT count(*) FROM capabilities').fetchone()[0],0)
  finally:c.close()

 def test_source_match_is_sha_bound_not_filename(self):
  sample=b'synthetic-test-input-no-game-rom';sha=hashlib.sha256(sample).hexdigest()
  source=Path(self.temp.name)/'test.bin';source.write_bytes(sample)
  c=connect(self.db)
  with c:
   c.execute('INSERT INTO targets VALUES (?,?,?,?,?)',('synthetic', 'm68k',sha,'raw','test'))
   c.execute('INSERT INTO graph_runs VALUES (?,?,?,?,?,?,?,?,?,?)',('run-x','synthetic',sha,'test','a'*64,0,0,1024,3,'partial_static_discovery'))
   c.execute('INSERT INTO graph_functions VALUES (?,?,?,?,?,?)',('run-x',0,'test','static_candidate',3,'boundary_not_verified'))
  c.close()
  r=create_campaign(self.db,sources=[source]);t=next(t for t in r['targets'] if t['target_id']=='synthetic')
  self.assertEqual(t['input_status'],'SHA256_VERIFIED')
  self.assertEqual(r['totals']['stages']['NEEDS_VERIFIED_BOUNDARY'],1)
  source.write_bytes(sample+b'x')
  r2=create_campaign(self.db,sources=[source]);t=next(t for t in r2['targets'] if t['target_id']=='synthetic')
  self.assertEqual(t['input_status'],'SOURCE_UNAVAILABLE')

 def test_missing_source_fails_before_writes(self):
  c=sqlite3.connect(self.db)
  before=c.execute('SELECT count(*) FROM batch_campaigns').fetchone()[0];c.close()
  with self.assertRaises(ValueError):create_campaign(self.db,sources=['/path/does/not/exist.bin'])
  c=sqlite3.connect(self.db)
  self.assertEqual(c.execute('SELECT count(*) FROM batch_campaigns').fetchone()[0],before)
  c.close()

 def test_test_sources_are_not_parity_evidence(self):
  source=Path(self.temp.name)/'go';t=source/'tools/chqdev';t.mkdir(parents=True)
  r=probe_go_sources(source)
  self.assertTrue(all(x['status']=='MISSING' for x in r))
  (t/'recomp_m68k_abs_long_test.go').write_text('package main')
  (t/'recomp_ir.go').write_text('package main');(t/'recomp_ir_codegen.go').write_text('package main')
  r=probe_go_sources(source)
  self.assertEqual(r[0]['status'],'TEST_SOURCE_PRESENT_NOT_EXECUTION_PARITY')

 def test_native_manifest_authenticated_and_bounded(self):
  # Production looks for a platform-specific Go binary; the test must not
  # execute a POSIX shell script (or require a real Go toolchain) on Windows.
  t=Path(self.temp.name);source=t/'synthetic.md';source.write_bytes(b'fake')
  sha=hashlib.sha256(b'fake').hexdigest()
  root=t/'root'
  exe=root/'tools/chqdev/bin'/('chqdev-windows-amd64.exe' if os.name=='nt' else 'chqdev-linux-amd64')
  exe.parent.mkdir(parents=True)
  exe.write_bytes(b'synthetic-placeholder-not-an-executable')
  campaign=t/'external-campaign';campaign.mkdir()
  obj={'schema':'recomp-native-campaign-v1','sourceSHA256':sha,
       'compileStatus':'COMPILED_NOT_PARITY_VERIFIED','generatedUnits':2,
       'generatedInstructions':5,'blockers':[]}
  manifest=campaign/'manifest.json';manifest.write_text(json.dumps(obj))
  fake_result=subprocess.CompletedProcess(args=[str(exe)],returncode=0,
             stdout='Output: '+str(campaign)+'\n',stderr='')
  with patch('native_batch.subprocess.run',return_value=fake_result) as invoked:
   result=attempt_go(root,source,sha,2)
   self.assertEqual(invoked.call_count,1)
   command=invoked.call_args.args[0]
   self.assertEqual(command,[str(exe),'--root',str(root.resolve()),'recomp','convert',str(source)])
   self.assertEqual(invoked.call_args.kwargs['timeout'],2)
  self.assertEqual(result['units'],2)
  self.assertEqual(result['status'],'COMPILED_NOT_PARITY_VERIFIED')
  self.assertIn('NOT_WHOLE_FUNCTION',result['note'])
  obj['sourceSHA256']='0'*64;manifest.write_text(json.dumps(obj))
  with patch('native_batch.subprocess.run',return_value=fake_result):
   result=attempt_go(root,source,sha,2)
  self.assertEqual(result['status'],'BACKEND_IDENTITY_MISMATCH')
  source.write_bytes(b'changed')
  with patch('native_batch.subprocess.run') as invoked:
   with self.assertRaisesRegex(ValueError,'source changed'):
    attempt_go(root,source,sha,2)
   invoked.assert_not_called()

 def test_native_backend_missing_fails_closed_on_current_platform(self):
  from native_batch import go_executable
  root=Path(self.temp.name)/'missing-backend'
  with self.assertRaisesRegex(ValueError,'native CLI executable absent'):
   go_executable(root)
  exe=root/'tools/chqdev/bin'/('chqdev-windows-amd64.exe' if os.name=='nt' else 'chqdev-linux-amd64')
  exe.parent.mkdir(parents=True)
  exe.write_bytes(b'placeholder-is-not-executed')
  resolved,selected=go_executable(root)
  self.assertEqual(resolved,root.resolve())
  self.assertEqual(selected,exe)
  self.assertTrue(str(selected).endswith('.exe') if os.name=='nt' else not str(selected).endswith('.exe'))

 def test_native_backend_timeout_and_process_errors_are_bounded(self):
  t=Path(self.temp.name);root=t/'root';rom=t/'synthetic.md';rom.write_bytes(b'fixture')
  expected=hashlib.sha256(rom.read_bytes()).hexdigest()
  exe=root/'tools/chqdev/bin'/('chqdev-windows-amd64.exe' if os.name=='nt' else 'chqdev-linux-amd64')
  exe.parent.mkdir(parents=True);exe.write_bytes(b'placeholder')
  with patch('native_batch.subprocess.run',side_effect=subprocess.TimeoutExpired(str(exe),2)):
   self.assertEqual(attempt_go(root,rom,expected,2)['status'],'BACKEND_TIMEOUT')
  failed=subprocess.CompletedProcess(args=[str(exe)],returncode=1,stdout='',stderr='synthetic failure')
  with patch('native_batch.subprocess.run',return_value=failed):
   self.assertEqual(attempt_go(root,rom,expected,2)['status'],'BACKEND_FAILED')
  malformed=subprocess.CompletedProcess(args=[str(exe)],returncode=0,stdout='unparseable',stderr='')
  with patch('native_batch.subprocess.run',return_value=malformed):
   self.assertEqual(attempt_go(root,rom,expected,2)['status'],'BACKEND_RESULT_UNPARSEABLE')

if __name__=='__main__':unittest.main()
