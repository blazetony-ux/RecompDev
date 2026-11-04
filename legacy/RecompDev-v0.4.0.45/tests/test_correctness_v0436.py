"""Correctness and recovery regressions (synthetic ROMs only)."""
import hashlib,json,os,shutil,subprocess,tempfile,unittest
from pathlib import Path
from nativecore.continuous_recovery_v0436 import run
from nativecore.session_triage_v0436 import analyze_session,analyze_campaign
from tests.test_continuous_recovery_v0435 import fixture

class Correctness436(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);self.rom,self.export,self.overlay=fixture(self.root)
 def build_mock(self,project):
  exe=project/'fake-executable';exe.write_text('synthetic-only')
  return exe,'fake compile'
 def stop(self,pc=3,code='UNTRANSLATED_INITIAL_CODE'):
  return lambda project,rom,source,out,frames,steps,input_file: {
   'source_sha256':source,'status':code,'pc':pc,'physical_offset':pc,
   'mapper':[0,0,1,2],'native_steps':3,'frames':0,
   'reference_parity':'NOT_TESTED','gameplay':'NOT_ESTABLISHED'}
 def test_source_attested_but_not_emitted_diagnosis(self):
  doc=json.loads(self.export.read_text())
  doc['functions'][0]['instructions'][0]['pcode']=[{'op':'CALLOTHER','inputs':[]}]
  self.export.write_text(json.dumps(doc))
  def recover(*args):
   overlay=json.loads(self.export.read_text());overlay['bank_context']={'slot':0,'bank':0,'base':0,'physical_start':0}
   return overlay,{}
  result=run(self.rom,self.export,self.root/'blocked',recover=recover,build=self.build_mock,
             session=self.stop(),max_recoveries=1)
  self.assertEqual(result['status'],'RECOVERY_BLOCKED',result)
  self.assertEqual(result['blocker'],'SOURCE_ATTESTED_BUT_NOT_EMITTED')
  self.assertFalse(result['attempts'][0]['emission_diagnosis']['emitted'])
 def test_emitted_dispatch_mismatch_not_called_missing_recovery(self):
  def recover(*args):
   doc=json.loads(self.export.read_text());doc['bank_context']={'slot':0,'bank':0,'base':0,'physical_start':0}
   return doc,{}
  result=run(self.rom,self.export,self.root/'existing',recover=recover,build=self.build_mock,
             session=self.stop(),max_recoveries=1)
  self.assertEqual(result['blocker'],'ALREADY_EMITTED_DISPATCH_OR_MAPPER_MISMATCH',result)
  self.assertTrue(result['attempts'][0]['emission_diagnosis']['emitted'])
 def test_compiler_timeout_returns_json(self):
  def timeout(project):raise subprocess.TimeoutExpired('cmake --build',45)
  result=run(self.rom,self.export,self.root/'timeout',build=timeout,compile_timeout=60)
  self.assertEqual(result['status'],'BUILD_TIMEOUT')
  self.assertEqual(result['attempt_count'],0)
  self.assertTrue((self.root/'timeout'/'continuous-recovery-report.json').is_file())
 def test_ram_predecessor_is_observation_not_cause(self):
  doc={'source_sha256':'a'*64,'reference_parity':'NOT_TESTED','status':'RAM_EXECUTION_NOT_TRANSLATED',
       'pc':0xfec0,'native_steps':5,'trace_tail':[
           {'pc_before':0x38,'pc_after':0xfec0,'opcode_class':'RETURN','sp_before':0xfff0,'sp_after':0xfff2},
           {'pc_before':0xfec0,'pc_after':0xfec0,'kind':'ram_execution_blocked'}]}
  triage=analyze_session(doc)
  self.assertEqual(triage['entry_provenance']['pc_before'],0x38)
  self.assertEqual(triage['root_cause'],'NOT_ESTABLISHED')
  self.assertIn('RAM_PC_PREDECESSOR_OBSERVED_NOT_PROVEN_CORRECT',triage['findings'])
 def test_real_compiled_tail_source_attested(self):
  if not shutil.which('cmake') or not (os.name=='nt' or shutil.which('g++') or shutil.which('clang++')):
   self.fail('C++ compile acceptance requires CMake and a C++ compiler')
  def recovery(rom,sha,target,pc,mapper,out):return self.overlay,{'status':'VERIFIED'}
  result=run(self.rom,self.export,self.root/'compile',frames=2,steps=16000,max_recoveries=1,recover=recovery,capture_hardware=True)
  self.assertEqual(result['attempt_count'],2,result)
  session=json.loads((self.root/'compile'/result['attempts'][1]['session_path']).read_text())
  tail=session['trace_tail'];self.assertTrue(1<=len(tail)<=256)
  self.assertTrue(all(0<=t['pc_before']<=65535 and 0<=t['pc_after']<=65535 for t in tail))
  self.assertTrue(all('sp_before' in t and 'mapper_before' in t and 'opcode_class' in t for t in tail))
  self.assertEqual(session['reference_parity'],'NOT_TESTED')
  self.assertEqual(len(session['frame_hardware']),2,session['status'])
  self.assertEqual(len(session['frame_hashes']),2)
  self.assertIn('vdp_writes',session['frame_hardware'][-1])
  self.assertEqual(session['video_backend'],'capture')
 def test_campaign_shared_symptoms_not_causes(self):
  campaigns={'schema':'test','games':[{'slug':'a','game':'A','status':'STOP'}, {'slug':'b','game':'B','status':'STOP'}]}
  for slug in ('a','b'):
   p=self.root/slug/'recovery'/'sessions'/'attempt-00';p.mkdir(parents=True)
   (p/'continuous-session.json').write_text(json.dumps({'source_sha256':'f'*64,
     'reference_parity':'NOT_TESTED','status':'RAM_EXECUTION_NOT_TRANSLATED','pc':0xc000,
     'trace_tail':[],'cram_nonzero_bytes':0,'video_backend':'null'}))
  triage=analyze_campaign(campaigns,self.root)
  self.assertEqual(len(triage['shared_observations']['RAM_EXECUTION_NOT_PROVEN_OR_TRANSLATED']),2)
  self.assertEqual(triage['causal_attribution'],'NOT_ESTABLISHED')
if __name__=='__main__':unittest.main()
