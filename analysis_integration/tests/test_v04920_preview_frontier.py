"""Controller archive handoff: bound CPU state, ROM, source, session and provenance."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from analysis_integration.preview_frontier import verify_and_stage_preview,PreviewFrontierError
from analysis_integration.recovery_history import import_previous
from execution_monitor.job_preview import diagnostic_zip,preview_recovery_seed,frame_accounting

def sha(x):return hashlib.sha256(x).hexdigest()

class Handoff(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
  r=Path(self.t.name);self.root=r
  self.rom=r/'actual.sms';self.rom.write_bytes(b'\x00'*0x10000)
  self.jid='job-20261107T100000Z-deadbeef-55-0';self.session=r/'jobs'/self.jid/'sessions'/'cycle-04'
  self.project=self.session/'round-01';self.project.mkdir(parents=True)
  (self.project/'translated.cpp').write_text('int source_attested_native(){return 0;}\n')
  (self.session/'orchestration.json').write_text(json.dumps({'schema':'recompdev.native.orchestrator.v1','source_sha256':sha(self.rom.read_bytes()),'rounds':[{'round':1,'status':'MAX_RECOVERY_ROUNDS_REACHED'}]}))
  self.native={'status':'UNTRANSLATED_INITIAL_CODE','pc':44463,'physical_offset':44463,
               'sp':0xdffa,'mapper':[0,0,1,2],'native_steps':6336791,
               'rom_bytes':len(self.rom.read_bytes()),'frames':936}
  # mapper slot2 bank2%4=2: 0xADAF-> 0xADAF
  self.stop={'type':'stop','pc':44463,'physical_offset':44463,'status':'untranslated_code','frame':934}
  self.seed=preview_recovery_seed(self.native,self.rom,sha(self.rom.read_bytes()),0,self.stop)
  assert self.seed is not None
  self.summary={'schema':'recompdev.preview.session.v1','job_id':self.jid,
    'status':'GUEST_BLOCKED_UNTRANSLATED','process_exit_code':0,
    'recovery_state_modified':False,'recovery_seed_available':True,
    'source_sha256':sha(self.rom.read_bytes()),'cycle':'cycle-04','round':'round-01',
    'translated_cpp_sha256':sha((self.project/'translated.cpp').read_bytes()),
    'native_stop':{'status':self.native['status'],'pc':self.native['pc'],
       'physical_offset':self.native['physical_offset'],'published_stop':self.stop}}
  self.output=r/'preview-evidence';self.output.mkdir()
  self.archive=diagnostic_zip(self.output,r/'diagnostics',self.summary,[self.stop],self.seed)

 def verify(self,arc=None):return verify_and_stage_preview(arc or self.archive,self.session,self.rom,self.jid,self.root/'next'/'preview-stop.json')
 def rewrite(self, mutate):
  with zipfile.ZipFile(self.archive) as z: data={n:z.read(n) for n in z.namelist()}
  mutate(data)
  if 'recovery-seed.json' in data:
   man=json.loads(data['manifest.json'])
   man['files']['recovery-seed.json']={'bytes':len(data['recovery-seed.json']),'sha256':sha(data['recovery-seed.json'])}
   data['manifest.json']=json.dumps(man).encode()
  dest=self.root/'modified.zip'
  with zipfile.ZipFile(dest,'w') as z:
   for key,val in data.items():z.writestr(key,val)
  return dest

 def test_valid_seed_is_rom_source_and_session_attested(self):
  p=self.verify();self.assertEqual(json.loads(p.read_text())['pc'],0xadaf)
  self.assertEqual(frame_accounting(self.native,self.stop)['delta_host_minus_guest'],2)
  self.assertFalse(frame_accounting(self.native,self.stop)['same_clock_domain'])
  original=(self.session/'orchestration.json').read_bytes()
  base=self.root/'base.json'
  base.write_text(json.dumps({'schema':'recomp-function-pcode-v1','analyzer':'ghidra-raw-pcode','source_sha256':sha(self.rom.read_bytes()),
    'language':'z80:LE:16:default','target_id':'synthetic',
    'functions':[{'entry':0,'body_min':0,'body_max':0,'instructions':[{'address':0,'length':1,'bytes_sha256':sha(b'\x00')}]}]}))
  seeds,banks,audit=import_previous(self.session,self.root/'imported',self.rom,base,p)
  self.assertEqual((len(seeds),len(banks),audit['preview_stops']),(1,0,1))
  self.assertEqual(original,(self.session/'orchestration.json').read_bytes())
  # Next cycle inherits the preview seed without needing the original ZIP.
  next_session=self.root/'next-session';next_session.mkdir()
  (next_session/'orchestration.json').write_text((self.session/'orchestration.json').read_text())
  import shutil
  shutil.copytree(self.root/'imported',next_session/'imported-history')
  seeds2,banks2,audit2=import_previous(next_session,self.root/'inherited2',self.rom,base)
  self.assertEqual((len(seeds2),audit2['inherited_stops']),(1,1))

 def test_rejects_wrong_rom(self):
  self.rom.write_bytes(b'\x01'*0x10000)
  with self.assertRaisesRegex(PreviewFrontierError,'ATTESTATION_MISMATCH'):self.verify()
 def test_rejects_bad_mapper_even_with_rewritten_manifest_hash(self):
  def change(data):
   d=json.loads(data['recovery-seed.json']);d['mapper'][3]=3
   data['recovery-seed.json']=json.dumps(d).encode()
  with self.assertRaisesRegex(PreviewFrontierError,'PHYSICAL_MISMATCH'):
   self.verify(self.rewrite(change))
 def test_rejects_original_source_modification(self):
  (self.project/'translated.cpp').write_text('changed')
  with self.assertRaisesRegex(PreviewFrontierError,'TRANSLATION_SOURCE_MISMATCH'):self.verify()
 def test_rejects_other_job_and_cycle(self):
  with self.assertRaisesRegex(PreviewFrontierError,'JOB_PATH_MISMATCH'):
   verify_and_stage_preview(self.archive,self.session,self.rom,'job-other',self.root/'bad')
  def change(data):
   d=json.loads(data['preview.json']);d['cycle']='cycle-03'
   data['preview.json']=json.dumps(d).encode()
  # The source/session consistency gate must reject an archived preview from the wrong cycle.
  with zipfile.ZipFile(self.archive) as z:data={name:z.read(name) for name in z.namelist()}
  change(data);man=json.loads(data['manifest.json']);man['files']['preview.json']={'bytes':len(data['preview.json']),'sha256':sha(data['preview.json'])};data['manifest.json']=json.dumps(man).encode()
  alt=self.root/'wrong-cycle.zip'
  with zipfile.ZipFile(alt,'w') as z:
   for n,v in data.items():z.writestr(n,v)
  with self.assertRaisesRegex(PreviewFrontierError,'SESSION_ATTESTATION_MISMATCH'):self.verify(alt)
 def test_rejects_missing_seed_in_previous_version_diagnostics(self):
  def change(data):
   del data['recovery-seed.json']
  with self.assertRaisesRegex(PreviewFrontierError,'PREVIEW_SEED_MISSING'):
   self.verify(self.rewrite(change))
 def test_rejects_archive_hash_mutation(self):
  def change(data):
   data['recovery-seed.json']=data['recovery-seed.json']+b' '
  # rewrite() adjusts manifest so make a separate invalid version by damaging manifest bytes.
  with zipfile.ZipFile(self.archive) as z:data={name:z.read(name) for name in z.namelist()}
  data['recovery-seed.json']+=b' '
  wrong=self.root/'wrong.zip'
  with zipfile.ZipFile(wrong,'w') as z:
   for n,v in data.items():z.writestr(n,v)
  with self.assertRaisesRegex(PreviewFrontierError,'MANIFEST_HASH_MISMATCH'):self.verify(wrong)
 def test_rejects_non_gap_and_mismatched_native_pc(self):
  other=dict(self.native,status='FRAME_BUDGET_REACHED')
  self.assertIsNone(preview_recovery_seed(other,self.rom,sha(self.rom.read_bytes()),0,self.stop))
  self.assertIsNone(preview_recovery_seed(self.native,self.rom,sha(self.rom.read_bytes()),0,dict(self.stop,pc=1)))
 def test_rejects_bad_or_unobserved_native_mapper(self):
  self.assertIsNone(preview_recovery_seed(dict(self.native,mapper=[0,0,1,3]),self.rom,sha(self.rom.read_bytes()),0,self.stop))
  self.assertIsNone(preview_recovery_seed(self.native,self.rom,sha(self.rom.read_bytes()),2,self.stop))

if __name__=='__main__':unittest.main()
