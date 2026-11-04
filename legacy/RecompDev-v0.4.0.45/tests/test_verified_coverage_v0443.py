"""Persistent code coverage must remain byte-attested across independently executed runs."""
import hashlib
import json
import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from nativecore.continuous_recovery_v0436 import run
from nativecore.verified_coverage_v0443 import VerifiedCoverageCache,coverage_path
from test_continuous_recovery_v0435 import fixture

class VerifiedCoverage443(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name)
  self.rom,self.export,self.overlay=fixture(self.root)
  self.source=hashlib.sha256(self.rom.read_bytes()).hexdigest()
  self.cache=self.root/'Shared-Data'/'verified-coverage-v0443.sqlite'
 def store(self):
  return VerifiedCoverageCache(self.cache,self.source,'synthetic')
 def builder(self,project):
  build=project/'build';build.mkdir(exist_ok=True)
  app=build/'RecompDevNativeApp';app.write_bytes(b'compiled-host-test-stub')
  pilot=build/'RecompDevNativePilot';pilot.write_bytes(b'compiled-pilot-test-stub')
  return pilot,'successful test build'
 def session(self,project,rom,source,out,frames,steps,input_file):
  available=set(json.loads((project/'emitted-offsets.json').read_text())['physical_offsets'])
  complete=6 in available
  return {'source_sha256':source,'reference_parity':'NOT_TESTED','gameplay':'NOT_ESTABLISHED',
    'status':'FRAME_BUDGET_REACHED' if complete else 'UNTRANSLATED_INITIAL_CODE',
    'pc':6,'physical_offset':6,'mapper':[0,0,1,2],
    'native_steps':150 if complete else 3,'frames':frames if complete else 0,
    'guest_state_fingerprint':11,'frame_hashes':[],'trace_tail':[]}
 def recover(self,rom,source,target,pc,mapper,out):
  self.assertEqual((source,target,pc),(self.source,'synthetic',6))
  (out/'bank-functions.json').write_text(json.dumps(self.overlay))
  return self.overlay,{'status':'SOURCE_BYTES_VERIFIED','exact_instructions':1}
 def test_warm_cache_skips_recovery_and_preserves_input_hash(self):
  input_file=self.root/'controller.csv';input_file.write_text('frame,button\n',encoding='utf-8')
  report=run(self.rom,self.export,self.root/'first',frames=5,max_recoveries=2,
    coverage_cache=self.cache,recover=self.recover,build=self.builder,session=self.session,input_events=input_file)
  self.assertEqual(report['attempt_count'],2,report)
  self.assertEqual(report['status'],'CONTINUOUS_SESSION_COMPLETE')
  self.assertEqual(report['coverage_cache']['new_documents_saved'],1)
  def forbidden_recovery(*args):raise AssertionError('Warm cache must not rediscover code')
  fresh=run(self.rom,self.export,self.root/'second',frames=5,max_recoveries=0,
    coverage_cache=self.cache,recover=forbidden_recovery,build=self.builder,session=self.session,input_events=input_file)
  self.assertEqual(fresh['attempt_count'],1,fresh)
  self.assertEqual(fresh['maximum_frames_observed'],5)
  self.assertEqual(fresh['coverage_cache']['loaded_instruction_offsets'],1)
  self.assertEqual(fresh['input_sha256'],report['input_sha256'])
 def test_wrong_rom_never_imports_previous_game(self):
  self.assertTrue(self.store().put(self.overlay,self.rom,6))
  raw=bytearray(self.rom.read_bytes());raw[7]^=0xff
  changed=self.root/'changed.sms';changed.write_bytes(raw)
  other=VerifiedCoverageCache(self.cache,hashlib.sha256(raw).hexdigest(),'other-target')
  self.assertEqual(other.load(changed)[2],0)
  with self.assertRaisesRegex(ValueError,'ROM differs'):
   self.store().load(changed)
 def test_tamper_in_cached_export_fails_closed(self):
  self.store().put(self.overlay,self.rom,6)
  with closing(sqlite3.connect(self.cache)) as con, con:
   con.execute("UPDATE verified_overlays SET document_json='{}'")
  with self.assertRaisesRegex(ValueError,'digest mismatch'):
   self.store().load(self.rom)
 def test_source_byte_hash_tamper_fails_even_if_cache_digest_rewritten(self):
  self.store().put(self.overlay,self.rom,6)
  bad=json.loads(json.dumps(self.overlay))
  bad['functions'][0]['instructions'][0]['bytes_sha256']='0'*64
  raw=json.dumps(bad,sort_keys=True,separators=(',',':'),ensure_ascii=True)
  with closing(sqlite3.connect(self.cache)) as con, con:
   con.execute('UPDATE verified_overlays SET document_json=?,content_sha256=?',(raw,hashlib.sha256(raw.encode()).hexdigest()))
  with self.assertRaisesRegex(ValueError,'bytes mismatch'):
   self.store().load(self.rom)
 def test_historical_exports_can_be_imported_without_modification(self):
  history=self.root/'old-v0442'/'evidence'/'recovery'/'attempt-01'
  history.mkdir(parents=True)
  source=history/'bank-functions.json';source.write_text(json.dumps(self.overlay))
  original=hashlib.sha256(source.read_bytes()).hexdigest()
  result=self.store().import_history(self.rom,[history.parent.parent])
  self.assertEqual(result['matching_exports_imported'],1)
  self.assertEqual(len(self.store().load(self.rom)[0]),1)
  self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),original)
 def test_no_cat_migration_or_rom_content_in_exported_report(self):
  self.assertEqual(coverage_path(self.root),self.root.parent/'RecompDev-Data'/'verified-coverage-v0443.sqlite')
  self.assertFalse((self.root/'catalogue.sqlite').exists())

if __name__=='__main__':unittest.main()
