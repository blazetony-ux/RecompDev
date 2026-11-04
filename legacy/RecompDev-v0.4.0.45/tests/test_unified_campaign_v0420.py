"""Consolidated synthetic acceptance tests; no commercial ROM required."""
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
from campaign.engine import run
from campaign.repair import trial
from nativecore.alignment import make_anchor, compare_anchors
from nativecore.hardware_gate import compare as compare_hw
from nativecore.m68k_fixture import decode

class ConsolidatedMilestones(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name)
  self.source=self.root/'author-m68k.bin'
  self.source.write_bytes(bytes.fromhex('7001528053804e75'))
 def test_second_isa_and_unified_campaign_not_just_metadata(self):
  gxx=shutil.which('g++') or shutil.which('clang++')
  if not gxx:self.skipTest('No C++ compiler')
  out=run(self.source,self.root/'campaign','m68k',synthetic=True,compiler=gxx)
  self.assertEqual(out['status'],'FINISHED_WITH_EXPLICIT_GATES',out)
  result=json.loads((self.root/'campaign'/'native-oracle-comparison.json').read_text())
  self.assertEqual(result['status'],'MATCHED_RESTRICTED_FIXTURE')
  self.assertFalse(result['general_native_parity'])
  self.assertEqual(result['native']['registers'][0],1)
  self.assertEqual(out['release_milestones']['second_isa'],'RESTRICTED_FIXTURE_PASS')
  self.assertFalse(out['native_qualified']);self.assertEqual(out['gameplay'],'NOT_ESTABLISHED')
  self.assertTrue(out['source_unchanged'])
  with self.assertRaisesRegex(ValueError,'existing campaign'):run(self.source,self.root/'campaign','m68k',synthetic=True)
 def test_existing_z80_native_pilot_is_connected_to_campaign(self):
  if not shutil.which('cmake') or not shutil.which('g++'):self.skipTest('Requires CMake and C++')
  # Existing author-created Z80 ROM test harness creates source-attested
  # function p-code in a temporary SQLite catalogue, not a commercial ROM.
  from test_native_execution_v0404 import NativeExecutionTests
  fixture=NativeExecutionTests('test_wrong_rom_and_outside_root_blocked')
  fixture.setUp()
  try:
   out=run(fixture.rom,self.root/'z80-e2e','z80',db=fixture.db,rom_roots=[fixture.roms],steps=50)
   translated=next(x for x in out['stages'] if x['stage']=='NATIVE_TRANSLATION_AND_EXECUTION')
   self.assertEqual(translated['status'],'NATIVE_TRACE_STOPPED',out)
   self.assertGreaterEqual(translated['details']['native_steps'],6)
   self.assertGreater(translated['details']['translated_instructions'],0)
   self.assertFalse(out['native_qualified'])
   self.assertTrue(out['source_unchanged'])
  finally:fixture.doCleanups()
 def test_two_distinct_binary_runs_same_pipeline(self):
  for i,data in enumerate((bytes.fromhex('7001528053804e75'),bytes.fromhex('70ff54804e75'))):
   src=self.root/f'fixture{i}.bin';src.write_bytes(data)
   result=run(src,self.root/f'run{i}','m68k',synthetic=True)
   self.assertEqual(result['status'],'FINISHED_WITH_EXPLICIT_GATES')
   self.assertEqual(result['source_sha256'],hashlib.sha256(data).hexdigest())
  self.assertNotEqual(json.loads((self.root/'run0'/'campaign-report.json').read_text())['source_sha256'],
                      json.loads((self.root/'run1'/'campaign-report.json').read_text())['source_sha256'])
 def test_z80_must_not_pretend_to_be_compiled_without_catalogue(self):
  src=self.root/'z80.bin';src.write_bytes(bytes.fromhex('3e423200c0c9'))
  r=run(src,self.root/'z80job','z80')
  self.assertTrue(any(x['status']=='BLOCKED_NEEDS_PREPARED_CATALOGUE' for x in r['stages']))
  self.assertFalse(r['native_qualified'])
 def test_unaligned_reference_never_promoted(self):
  regs={f'd{i}':0 for i in range(8)}
  ref=make_anchor(self.source,'m68k','raw',0,0,regs)
  nat=make_anchor(self.source,'m68k','raw',2,2,regs)
  alignment=compare_anchors(ref,nat,self.source)
  self.assertEqual(alignment['status'],'UNALIGNED_EXECUTION_IDENTITY')
  self.assertFalse(alignment['hardware_aligned'])
  hw=compare_hw({'source_sha256':ref['source_sha256']},{'source_sha256':ref['source_sha256']},alignment)
  self.assertEqual(hw['status'],'BLOCKED_UNALIGNED_HARDWARE_STATE')
 def test_same_code_location_different_state_is_a_failure(self):
  regs={f'd{i}':0 for i in range(8)}
  ref=make_anchor(self.source,'m68k','raw',0,0,regs)
  regs['d0']=1
  nat=make_anchor(self.source,'m68k','raw',0,0,regs)
  a=compare_anchors(ref,nat,self.source)
  self.assertEqual(a['status'],'DIVERGED_AT_COMMON_CODE_IDENTITY')
  self.assertEqual(a['different_registers']['d0']['native'],1)
 def test_forged_bytes_and_changed_source_rejected(self):
  reg={f'd{i}':0 for i in range(8)}
  a=make_anchor(self.source,'m68k','raw',0,0,reg)
  b=dict(a,instruction_hex='ffff')
  with self.assertRaisesRegex(ValueError,'byte mismatch'):compare_anchors(a,b,self.source)
  self.source.write_bytes(b'\x00\x00'+self.source.read_bytes()[2:])
  with self.assertRaisesRegex(ValueError,'source hash'):compare_anchors(a,a,self.source)
 def test_explicit_anchor_bundle_blocks_hardware_with_no_device_alignment(self):
  regs={f'd{i}':0 for i in range(8)}
  a=make_anchor(self.source,'m68k','raw',0,0,regs)
  bundle=self.root/'anchors.json';bundle.write_text(json.dumps({'schema':'recomp-explicit-anchor-pair-v1','reference':a,'native':a}))
  out=run(self.source,self.root/'aligned','m68k',synthetic=True,reference_anchors=bundle)
  self.assertEqual(out['release_milestones']['reference_alignment'],'MATCHED_CODE_IDENTITY_WITH_SELECTED_REGISTERS')
  self.assertNotEqual(out['reference_parity'],'PASS')
 def test_unsupported_opcode_fails_closed(self):
  with self.assertRaisesRegex(ValueError,'Unsupported'):decode(bytes.fromhex('4e714e75'))
 def test_semantic_recipe_search_and_holdout(self):
  discovery=self.root/'train.json';holdout=self.root/'holdout.json'
  def fixture(f,pairs):
   f.write_text(json.dumps({'schema':'recomp-u32-reference-cases-v1','op':'add-u32','cases':[
     {'a':a,'b':b,'expected':(a+b)&0xffffffff} for a,b in pairs]}))
  fixture(discovery,[(0xffffffff,1),(2,2),(5,7),(0,7)])
  fixture(holdout,[(0xf0000000,0x40000000),(31,17),(0x80000000,0x80000000)])
  output=self.root/'recipe.json'
  result=trial(discovery,holdout,output)
  self.assertEqual(result['status'],'SYNTHETIC_RECIPE_VALIDATED')
  self.assertEqual(result['selected_recipe'],'wrapping-add')
  self.assertFalse(result['runtime_semantics_modified'])
  with self.assertRaisesRegex(ValueError,'overwrite'):trial(discovery,holdout,output)
 def test_bad_holdout_never_committed_as_verified(self):
  train=self.root/'train.json';hold=self.root/'hold.json'
  train.write_text(json.dumps({'schema':'recomp-u32-reference-cases-v1','op':'add-u32','cases':[
    {'a':2,'b':3,'expected':5},{'a':5,'b':7,'expected':12}]}))
  hold.write_text(json.dumps({'schema':'recomp-u32-reference-cases-v1','op':'add-u32','cases':[
    {'a':2,'b':3,'expected':999},{'a':9,'b':10,'expected':19}]}))
  result=trial(train,hold,self.root/'reject.json')
  self.assertEqual(result['status'],'BLOCKED_NO_VERIFIED_IMPROVEMENT')
  self.assertIsNone(result['selected_recipe'])
 def test_host_contract_smoke(self):
  cc=shutil.which('c++') or shutil.which('g++')
  if not cc:self.skipTest('C++ compiler unavailable')
  exe=self.root/'host'
  p=subprocess.run([cc,'-std=c++17',str(ROOT/'host'/'StandaloneHost.cpp'),'-o',str(exe)],capture_output=True,text=True,timeout=30)
  self.assertEqual(p.returncode,0,p.stderr)
  if sys.platform!='win32':
   p=subprocess.run([str(exe)],capture_output=True,text=True,timeout=5)
   self.assertEqual(p.returncode,0);self.assertIn('NO_GAMEPLAY_PARITY',p.stdout)

if __name__=='__main__':unittest.main()
