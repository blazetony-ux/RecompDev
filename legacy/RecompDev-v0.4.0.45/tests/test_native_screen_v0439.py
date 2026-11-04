"""Generic framebuffer launch selection must be source matched and fail closed."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/'tools'/'View-Native-Output-v0439.py'
spec=importlib.util.spec_from_file_location('native_screen_0439',MODULE)
screen=importlib.util.module_from_spec(spec)
spec.loader.exec_module(screen)

class NativeScreenTests(unittest.TestCase):
 def make(self,p):
  rom=p/'shinobi.sms';rom.write_bytes(b'ROM_FIXTURE_STUB')
  sha=screen.digest(rom)
  project=p/'RecompDev-v0.4.0.38'/'evidence'/'sms-seven-v0438-20261102-000000'/'shinobi'/'recovery'/'native-project'
  project.mkdir(parents=True)
  (project/'generation.json').write_text(json.dumps({'original_source_sha256':sha}))
  (project/'translated.cpp').write_text('// test fixture')
  exe=project/'build'/'RecompDevNativeApp.exe';exe.parent.mkdir()
  exe.write_bytes(b'MOCK_BINARY_NOT_EXECUTED')
  pilot=project/'build'/'RecompDevNativePilot.exe';pilot.write_bytes(b'ATTESTED_PILOT')
  report=project.parent/'continuous-recovery-report.json'
  report.write_text(json.dumps({'source_sha256':sha,'attempts':[{'executable_sha256':screen.digest(pilot),'native_app_sha256':screen.digest(exe)}]}))
  return project,exe,rom,sha
 def test_source_verified_compiled_project_selected(self):
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp);project,exe,rom,sha=self.make(base)
   _,found,actual,_=screen.find_candidate([base/'RecompDev-v0.4.0.38'],'shinobi',sha)
   self.assertEqual((found,actual),(project,exe))
 def test_reject_mismatched_source(self):
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp);_,_,_,sha=self.make(base)
   with self.assertRaisesRegex(ValueError,'No verified compiled'):screen.find_candidate([base/'RecompDev-v0.4.0.38'],'shinobi','0'*64)
 def test_reject_binary_changed_since_attestation(self):
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp);_,exe,_,sha=self.make(base);exe.write_bytes(b'ALTERED')
   with self.assertRaisesRegex(ValueError,'No verified compiled'):screen.find_candidate([base/'RecompDev-v0.4.0.38'],'shinobi',sha)
 def test_reject_missing_report(self):
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp);project,_,_,sha=self.make(base);(project.parent/'continuous-recovery-report.json').unlink()
   with self.assertRaisesRegex(ValueError,'No verified compiled'):screen.find_candidate([base/'RecompDev-v0.4.0.38'],'shinobi',sha)
 def test_shift_pcode_is_emittable(self):
  from nativepilot.generator import emit_instruction
  ins={'mnemonic':'SRA','address':100,'fallthrough':102,'pcode':[{'op':'INT_SRIGHT',
       'inputs':[{'space':'register','offset':0,'size':1},{'space':'const','offset':1,'size':1}],
       'output':{'space':'register','offset':0,'size':1}}]}
  lines=emit_instruction(ins)
  self.assertIn('rd::Op::INT_SRIGHT','\n'.join(lines))

if __name__=='__main__':unittest.main()
