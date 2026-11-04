"""Compiled device output and strictly-scoped independent frame comparison."""
import hashlib,json,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
from nativecore.output_qualification_v0437 import verify_outputs,reference_ppm,reference_wav
from nativecore.reference_parity_v0437 import compare_frame_observations
ROOT=Path(__file__).resolve().parents[1]

class Parity437(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.tmp=Path(self.temp.name)
 def test_compiled_native_video_audio_exact_bytes(self):
  if not shutil.which('cmake') or not (os.name=='nt' or shutil.which('g++') or shutil.which('clang++')):
   self.fail('Real compiled output gate requires a C++ compiler and CMake')
  p=subprocess.run([sys.executable,str(ROOT/'tools/Validate-Native-Outputs-v0437.py'),
                    '--output',str(self.tmp/'qualification.json')],cwd=ROOT,capture_output=True,text=True,timeout=180)
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  doc=json.loads((self.tmp/'qualification.json').read_text())
  self.assertEqual(doc['status'],'PASS')
  self.assertEqual(doc['video']['distinct_rgb_colors'],2)
  self.assertEqual(doc['audio']['nonzero_samples'],4410)
 def test_corrupted_video_or_audio_is_detected(self):
  ppm=self.tmp/'frame.ppm';wav=self.tmp/'tone.wav'
  ppm.write_bytes(reference_ppm());wav.write_bytes(reference_wav())
  self.assertEqual(verify_outputs(ppm,wav)['status'],'PASS')
  altered=bytearray(ppm.read_bytes());altered[-1]^=1;ppm.write_bytes(altered)
  self.assertEqual(verify_outputs(ppm,wav)['video']['status'],'FAIL')
  ppm.write_bytes(reference_ppm())
  altered=bytearray(wav.read_bytes());altered[50]^=1;wav.write_bytes(altered)
  self.assertEqual(verify_outputs(ppm,wav)['audio']['status'],'FAIL')
 def fixture(self,mismatch=False):
  rom=self.tmp/'program.sms';rom.write_bytes(bytes([0xc3,0,0])*100)
  sha=hashlib.sha256(rom.read_bytes()).hexdigest()
  ref=self.tmp/'mame';ref.mkdir(exist_ok=True)
  lines=[json.dumps({'type':'frame','ordinal':i+1,'pc':100+i,'sp':0xd000})+'\n' for i in range(3)]
  raw=''.join(lines).encode();(ref/'mame-frames.jsonl').write_bytes(raw)
  manifest={'schema':'recomp-external-frame-observations-v1','source_sha256':sha,
            'independent_source':'MAME owner-installed sms','raw_sha256':hashlib.sha256(raw).hexdigest(),
            'script_sha256':'b'*64,'executable_sha256':'a'*64,'requested_frames':3,
            'observations':[json.loads(x) for x in lines]}
  (ref/'frame-observations.json').write_text(json.dumps(manifest))
  native=self.tmp/'continuous-session.json'
  frames=[{'frame':i+1,'pc':100+i+(10 if mismatch and i==1 else 0),'sp':0xd000,
           'guest_cycles':50000*(i+1),'steps':10*(i+1)} for i in range(3)]
  native.write_text(json.dumps({'schema':'recomp-continuous-native-v2','source_sha256':sha,
                                'executable_sha256':'c'*64,'frame_hardware':frames}))
  return rom,ref,native
 def test_frame_agreement_is_not_cpu_parity(self):
  rom,ref,native=self.fixture()
  result=compare_frame_observations(ref,native,rom)
  self.assertEqual(result['status'],'FRAME_SAMPLES_AGREE_UNALIGNED')
  self.assertEqual(result['cpu_parity'],'NOT_ESTABLISHED')
  self.assertEqual(result['frame_phase_alignment'],'NOT_ESTABLISHED')
 def test_authentic_native_schema_supported(self):
  rom,ref,native=self.fixture()
  doc=json.loads(native.read_text());doc['schema']='recomp-continuous-owner-session-v1'
  native.write_text(json.dumps(doc))
  self.assertEqual(compare_frame_observations(ref,native,rom)['cpu_parity'],'NOT_ESTABLISHED')
 def test_first_observed_difference_does_not_claim_causality(self):
  rom,ref,native=self.fixture(True)
  result=compare_frame_observations(ref,native,rom)
  self.assertEqual(result['status'],'FRAME_SAMPLES_DIFFER_UNALIGNED')
  self.assertEqual(result['first_unaligned_frame_difference']['frame_ordinal'],2)
  self.assertEqual(result['cpu_parity'],'NOT_ESTABLISHED')
 def test_wrong_rom_or_tampered_reference_rejected(self):
  rom,ref,native=self.fixture()
  rom.write_bytes(rom.read_bytes()+b'x')
  with self.assertRaisesRegex(ValueError,'do not match'):
   compare_frame_observations(ref,native,rom)
  rom.write_bytes(rom.read_bytes()[:-1])
  (ref/'mame-frames.jsonl').write_bytes(b'invalid')
  with self.assertRaisesRegex(ValueError,'digest mismatch'):
   compare_frame_observations(ref,native,rom)

if __name__=='__main__':unittest.main()
