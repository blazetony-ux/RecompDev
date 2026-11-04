import tempfile,unittest
from pathlib import Path
from platform_profiles import PROFILES,assess,inspect_source
class PlatformProfiles434(unittest.TestCase):
 def test_all_z80_not_all_sms(self):
  for key,p in PROFILES.items():
   self.assertEqual(p.cpu,'z80')
   self.assertNotEqual(assess(key,'extension-hint-only')['native_status'],'EXPERIMENTAL_SMS_NATIVE_PILOT')
  for key in PROFILES.keys()-{'mastersystem'}:
   self.assertEqual(assess(key,'owner-asserted')['native_status'],'BLOCKED_NO_MATCHING_NATIVE_HARDWARE')
 def test_sega8_structural_header_and_console_distinction(self):
  with tempfile.TemporaryDirectory() as d:
   for suffix,expected in (('.sms','mastersystem'),('.gg','gamegear')):
    f=Path(d)/('synthetic'+suffix);raw=bytearray(0x8000);raw[0x7ff0:0x7ff8]=b'TMR SEGA';f.write_bytes(raw)
    r=inspect_source(f);self.assertEqual(r['system'],expected)
    self.assertEqual(r['classification'],'structural-header')
    self.assertEqual(r['native_status'], 'EXPERIMENTAL_SMS_NATIVE_PILOT' if suffix=='.sms' else 'BLOCKED_NO_MATCHING_NATIVE_HARDWARE')
 def test_unknown_and_unverified_extension_fail_closed(self):
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'unknown.sms';f.write_bytes(b'no sega header')
   r=inspect_source(f);self.assertEqual(r['native_status'],'BLOCKED_UNVERIFIED_PLATFORM_IDENTITY')
   f=Path(d)/'sample.z80';f.write_bytes(b'not a valid snapshot')
   self.assertEqual(inspect_source(f)['native_status'],'BLOCKED_NO_MATCHING_NATIVE_HARDWARE')
 def test_explicit_owner_assertion_is_not_hardware_proof(self):
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'sample.bin';f.write_bytes(b'abc')
   r=inspect_source(f,'msx1');self.assertEqual(r['system'],'msx1')
   self.assertEqual(r['independent_hardware_parity'],'NOT_ESTABLISHED')
   self.assertEqual(r['native_status'],'BLOCKED_NO_MATCHING_NATIVE_HARDWARE')
if __name__=='__main__':unittest.main()
