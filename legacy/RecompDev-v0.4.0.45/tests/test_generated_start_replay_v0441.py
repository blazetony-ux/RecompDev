"""End-to-end authored Z80 ROM fixture exercises source-attested Start NMI."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import test_continuous_native_v0423 as continuous_native
from nativepilot.generator import generate_project

class GeneratedInputTests(unittest.TestCase):
 def test_compiled_source_attested_nmi_vector(self):
  fixture=continuous_native.ContinuousNativeTests('test_windows_cmake_project_metadata_is_not_an_executable')
  fixture.setUp()
  try:
   rom,project,_,doc=fixture.synthetic_project(return_doc=True)
   raw=bytearray(rom.read_bytes())
   raw[0x66:0x69]=b'\xc3\x03\x00'  # authored NMI handler -> existing instruction loop
   rom.write_bytes(raw)
   new_sha=hashlib.sha256(raw).hexdigest()
   doc['source_sha256']=new_sha
   instruction={'address':0x66,'length':3,'fallthrough':0x69,
      'mnemonic':'JP','bytes_sha256':hashlib.sha256(raw[0x66:0x69]).hexdigest(),
      'pcode':[{'op':'BRANCH','inputs':[{'space':'ram','offset':3,'size':1}]}]}
   doc['functions'].append({'entry':0x66,'name':'AUTHORED_NMI_VECTOR','instructions':[instruction]})
   stats=generate_project(doc,rom,project)
   self.assertGreater(stats['translated_instructions'],10)
   exe=fixture.compile(project)
   neutral=fixture.execute(exe,rom,'nmi-neutral')
   self.assertEqual(neutral['nmi_events'],0)
   path=fixture.dir/'nmi-start.csv'
   path.write_text('RECOMP_INPUT_CYCLES_V1\n0,0,0\n60000,0,128\n69000,0,0\n',encoding='ascii')
   pressed=fixture.execute(exe,rom,'nmi-pressed',path)
   self.assertEqual(pressed['nmi_events'],1)
   self.assertNotEqual(pressed['guest_state_fingerprint'],neutral['guest_state_fingerprint'])
   self.assertEqual(pressed['input_backend'],'replay')
  finally:
   fixture.doCleanups()
if __name__=='__main__':unittest.main()
