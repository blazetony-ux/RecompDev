"""Source-attested, reusable end-to-end integration, with adversarial cases."""
from contextlib import closing

import hashlib,json,shutil,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from campaign.resume import durable
from campaign.handoff import convert
from campaign.compiled_repair import repair
from tooling.analysis import reconcile

class DurableCampaignTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.dir=Path(self.tmp.name)
  self.source=self.dir/'toy68k.bin';self.source.write_bytes(bytes.fromhex('7001528053804e75'))
 def test_native_campaign_resume_and_source_invalidation(self):
  cxx=shutil.which('g++') or shutil.which('clang++')
  if not cxx:self.skipTest('C++ compiler unavailable')
  work=self.dir/'work'
  first=durable(self.source,work,'m68k',synthetic=True,compiler=cxx)
  self.assertEqual(first['status'],'RECORDED_NEW_ATTEMPT',first)
  proof=json.loads((Path(first['attempt'])/'native-oracle-comparison.json').read_text())
  self.assertEqual(proof['status'],'MATCHED_RESTRICTED_FIXTURE')
  second=durable(self.source,work,'m68k',synthetic=True,compiler=cxx)
  self.assertEqual(second['status'],'REUSED_VERIFIED_ATTEMPT',second)
  self.assertEqual(second['attempt'],first['attempt'])
  self.source.write_bytes(bytes.fromhex('70ff54804e75'))
  third=durable(self.source,work,'m68k',synthetic=True,compiler=cxx)
  self.assertEqual(third['status'],'RECORDED_NEW_ATTEMPT',third)
  self.assertNotEqual(first['attempt'],third['attempt'])
  self.assertEqual(len(list(work.glob('attempt-*/attempt-manifest.json'))),2)
  self.assertFalse(json.loads(Path(third['report']).read_text())['native_qualified'])
 def test_tampered_evidence_blocks_resume(self):
  work=self.dir/'work';r=durable(self.source,work,'m68k',synthetic=True)
  report=Path(r['report']);report.write_text(report.read_text()+'\n')
  with self.assertRaisesRegex(ValueError,'integrity failure'):
   durable(self.source,work,'m68k',synthetic=True)
  self.assertEqual(len(list(work.glob('attempt-*'))),1)
 def test_no_automatic_rerun_of_known_blocker(self):
  self.source.write_bytes(bytes.fromhex('70014e71'))
  work=self.dir/'work';a=durable(self.source,work,'m68k',synthetic=True)
  self.assertEqual(a['original_status'],'BLOCKED')
  b=durable(self.source,work,'m68k',synthetic=True)
  self.assertEqual(b['status'],'REUSED_VERIFIED_ATTEMPT')
  c=durable(self.source,work,'m68k',synthetic=True,retry_blocked=True)
  self.assertEqual(c['status'],'RECORDED_NEW_ATTEMPT')
 def test_recovery_handoff_source_attests_raw_exports(self):
  d=self.dir/'analysis';d.mkdir();raw=self.source.read_bytes();sha=hashlib.sha256(raw).hexdigest()
  gh=d/'ghidra-functions.json';rz=d/'rizin-aflj.json'
  gh.write_text(json.dumps({'schema':'recomp-function-pcode-v1','source_sha256':sha,
   'functions':[{'entry':0,'body_min':0,'body_max':len(raw)-1,
    'instructions':[{'address':0,'length':2,'bytes_sha256':hashlib.sha256(raw[:2]).hexdigest()}]}]}))
  rz.write_text(json.dumps([{'offset':0,'size':len(raw)}]))
  rec=reconcile(self.source,0,'m68k',gh,rz)
  (d/'reconciliation.json').write_text(json.dumps(rec))
  result=convert(self.source,d/'reconciliation.json',d/'queue.json')
  self.assertEqual(result['status'],'SOURCE_ATTESTED_RECOVERY_QUEUE')
  self.assertFalse(result['automatic_codegen'])
  self.assertFalse(result['recovery_tasks'][0]['trusted_as_native_code'])
  self.assertEqual(result['recovery_tasks'][0]['physical_offset'],0)
  rec['candidates'][0]['entry']=2
  (d/'reconciliation.json').write_text(json.dumps(rec))
  with self.assertRaisesRegex(ValueError,'not supported by original'):
   convert(self.source,d/'reconciliation.json',d/'invalid.json')
 def test_ghidra_export_forgery_detected_before_handoff(self):
  d=self.dir/'analysis';d.mkdir();raw=self.source.read_bytes();sha=hashlib.sha256(raw).hexdigest()
  gh=d/'ghidra-functions.json';gh.write_text(json.dumps({'schema':'recomp-function-pcode-v1','source_sha256':sha,
   'functions':[{'entry':0,'body_min':0,'body_max':len(raw)-1,
    'instructions':[{'address':0,'length':2,'bytes_sha256':hashlib.sha256(raw[:2]).hexdigest()}]}]}))
  rec=reconcile(self.source,0,'m68k',ghidra=gh)
  (d/'reconciliation.json').write_text(json.dumps(rec))
  gh.write_text(gh.read_text().replace(hashlib.sha256(raw[:2]).hexdigest(),'f'*64))
  with self.assertRaisesRegex(ValueError,'hash mismatch'):
   convert(self.source,d/'reconciliation.json',d/'queue.json')
 def test_compiled_repair_has_withheld_independent_test(self):
  cxx=shutil.which('g++') or shutil.which('clang++')
  if not cxx:self.skipTest('No compiler')
  training=self.dir/'train.json';holdout=self.dir/'holdout.json'
  def pairs(path,items):
   path.write_text(json.dumps({'schema':'recomp-u32-reference-cases-v1','op':'add-u32','cases':[
     {'a':a,'b':b,'expected':(a+b)&0xffffffff} for a,b in items]}))
  pairs(training,[(0xffffffff,1),(7,15),(42,13)])
  pairs(holdout,[(1000,7),(0x80000000,0x80000000),(1,123456)])
  result=repair(training,holdout,self.dir/'repair',cxx)
  self.assertEqual(result['status'],'ISOLATED_COMPILED_HOLDOUT_PASS',result)
  self.assertEqual(result['selected'],'wrapping-add')
  self.assertTrue(result['dependent_test_retried'])
  self.assertFalse(result['production_patched'])
  self.assertFalse(result['native_qualified'])
  self.assertTrue((self.dir/'repair'/'verified-quarantined-recipe.json').is_file())
 def test_bad_holdout_fails_and_never_commits(self):
  cxx=shutil.which('g++') or shutil.which('clang++')
  if not cxx:self.skipTest('No compiler')
  a=self.dir/'a.json';b=self.dir/'b.json'
  a.write_text(json.dumps({'schema':'recomp-u32-reference-cases-v1','op':'add-u32','cases':[
    {'a':2,'b':3,'expected':5},{'a':4,'b':8,'expected':12}]}))
  b.write_text(json.dumps({'schema':'recomp-u32-reference-cases-v1','op':'add-u32','cases':[
    {'a':20,'b':30,'expected':51},{'a':8,'b':9,'expected':17}]}))
  result=repair(a,b,self.dir/'bad',cxx)
  self.assertEqual(result['status'],'REJECTED_HOLDOUT_DIVERGENCE',result)
  self.assertIsNone(result['selected'])
  self.assertFalse((self.dir/'bad'/'verified-quarantined-recipe.json').exists())
 def test_two_distinct_z80_and_second_isa_shared_campaign_api(self):
  # The unprepared Z80 programs produce an explicit repeatable actionable
  # blocker; they cannot be advertised as converted.
  for i,raw in enumerate((bytes.fromhex('3e423200c0c9'),bytes.fromhex('3e0132ff7fc9'))):
   p=self.dir/f'z80-{i}.bin';p.write_bytes(raw)
   r=durable(p,self.dir/f'run-z80-{i}','z80')
   self.assertEqual(r['original_status'],'FINISHED_WITH_EXPLICIT_GATES')
   report=json.loads(Path(r['report']).read_text())
   self.assertTrue(any(x['status']=='BLOCKED_NEEDS_PREPARED_CATALOGUE' for x in report['stages']))
   self.assertFalse(report['native_qualified'])
  r=durable(self.source,self.dir/'run-68k','m68k',synthetic=True)
  self.assertEqual(r['original_status'],'FINISHED_WITH_EXPLICIT_GATES')

class ReferenceInvestigationTests(unittest.TestCase):
 def test_external_comparison_without_alignment_recommends_boot_provenance(self):
  from campaign.reference_triage import triage
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);source=root/'rom.bin';source.write_bytes(bytes.fromhex('3e423200c0c9'))
   sha=hashlib.sha256(source.read_bytes()).hexdigest()
   doc={'schema':'recomp-mame-sms-bus-comparison-v1','status':'SELECTED_IO_DIVERGED',
        'source_sha256':sha,'reference_writes':2860,'native_writes':470,
        'matching_prefix_writes':0,'first_divergence':{'bus_index':0,'native':{'kind':'PSG_WRITE'}},
        'pc_aligned':False,'step_aligned':False,'frame_aligned':False}
   evidence=root/'comparison.json';evidence.write_text(json.dumps(doc))
   result=triage(source,evidence,root/'investigation.json')
   self.assertEqual(result['status'],'BLOCKED_UNALIGNED_EXECUTIONS')
   self.assertEqual(result['next_action'],'ACQUIRE_AUTHENTICATED_BOOT_MAPPING_AND_COMMON_CPU_STATE')
   self.assertFalse(result['automatic_repair'])
   # Import it into the durable campaign; the resulting action is persisted.
   campaign=durable(source,root/'campaign','z80',bus_comparison=evidence)
   self.assertEqual(campaign['status'],'RECORDED_NEW_ATTEMPT')
   self.assertTrue((Path(campaign['attempt'])/'reference-investigation.json').exists())
   doc['source_sha256']='f'*64;evidence.write_text(json.dumps(doc))
   with self.assertRaisesRegex(ValueError,'identity mismatch'):
    triage(source,evidence,root/'forged.json')

class CrossTargetNativeTests(unittest.TestCase):
 @unittest.skipUnless(shutil.which('cmake') and shutil.which('g++'),'CMake and compiler required')
 def test_two_distinct_z80_sources_compile_without_shared_core_edits(self):
  # Two independently SHA-attested synthetic Master System ROMs prepared in
  # the same SQLite catalogue, using the real guest P-code / C++ backend.
  from test_native_execution_v0404 import NativeExecutionTests
  from discovery.store import connect,store_source
  from nativeprep.engine import prepare
  from nativepilot.generator import sha256
  import sqlite3
  fx=NativeExecutionTests('test_wrong_rom_and_outside_root_blocked');fx.setUp()
  try:
   with tempfile.TemporaryDirectory() as d:
    base=Path(d)
    a=durable(fx.rom,base/'job-a','z80',db=fx.db,rom_roots=[fx.roms],steps=50)
    self.assertEqual(a['original_status'],'FINISHED_WITH_EXPLICIT_GATES')
    cached=durable(fx.rom,base/'job-a','z80',db=fx.db,rom_roots=[fx.roms],steps=50)
    self.assertEqual(cached['status'],'REUSED_VERIFIED_ATTEMPT',cached)
    one=json.loads(Path(a['report']).read_text())
    self.assertGreater(next(s for s in one['stages'] if s['stage']=='NATIVE_TRANSLATION_AND_EXECUTION')['details']['native_steps'],0)
    alternate=fx.roms/'TinySMS2.sms';modified=bytearray(fx.raw);modified[4]=0x43
    alternate.write_bytes(modified);hash2=sha256(alternate)
    con=connect(fx.db);store_source(con,hash2,alternate,len(modified),'SHA256_COMPLETE','mastersystem','Other synthetic ROM','test');con.close()
    target=prepare(fx.db,hash2,base/'prepared2',allowed_roots=[fx.roms],analyze=False)
    doc=json.loads(json.dumps(fx.doc));doc['source_sha256']=hash2;doc['target_id']=target['target_id']
    # Source-byte hash and verified P-code immediates reflect the second,
    # genuinely distinct source instead of spoofing the first.
    ins=doc['functions'][0]['instructions'][0]
    ins['bytes_sha256']=hashlib.sha256(modified[3:5]).hexdigest()
    ins['pcode'][0]['inputs'][0]['offset']=0x43
    second_export=base/'functions2.json';second_export.write_text(json.dumps(doc))
    with closing(sqlite3.connect(fx.db)) as con, con:
     con.execute('UPDATE native_preparations_v0403 SET export_path=?,candidate_count=1 WHERE source_id=?',
                 (str(second_export),hash2))
    b=durable(alternate,base/'job-b','z80',db=fx.db,rom_roots=[fx.roms],steps=50)
    self.assertEqual(b['original_status'],'FINISHED_WITH_EXPLICIT_GATES')
    two=json.loads(Path(b['report']).read_text())
    self.assertGreater(next(s for s in two['stages'] if s['stage']=='NATIVE_TRANSLATION_AND_EXECUTION')['details']['native_steps'],0)
    self.assertNotEqual(one['source_sha256'],two['source_sha256'])
    self.assertFalse(one['native_qualified'] or two['native_qualified'])
  finally:fx.doCleanups()

class NativeHostBridgeTests(unittest.TestCase):
 def test_generated_style_guest_contract_links_and_accepts_input(self):
  import subprocess
  cc=shutil.which('g++') or shutil.which('clang++')
  if not cc:self.skipTest('C++ compiler not installed')
  with tempfile.TemporaryDirectory() as td:
   exe=Path(td)/'synthetic-guest'
   proc=subprocess.run([cc,'-std=c++17','-DRECOMPDEV_GUEST_BRIDGE',
      str(ROOT/'host/StandaloneHost.cpp'),str(ROOT/'host/SyntheticGuest.cpp'),'-o',str(exe)],
      capture_output=True,text=True,timeout=30)
   self.assertEqual(proc.returncode,0,proc.stderr)
   if sys.platform!='win32':
    out=subprocess.run([str(exe)],capture_output=True,text=True,timeout=5)
    self.assertEqual(out.returncode,0,out.stderr)
    self.assertIn('GUEST_BRIDGE_SYNTHETIC_PASS',out.stdout)
    self.assertIn('NO_GAMEPLAY_PARITY',out.stdout)

if __name__=='__main__':unittest.main()
