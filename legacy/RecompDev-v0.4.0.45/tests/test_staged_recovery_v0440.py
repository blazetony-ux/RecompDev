"""Staged recovery does not fabricate progress or omit budget evidence."""
import tempfile,unittest
from pathlib import Path
from nativecore.continuous_recovery_v0436 import run
from nativecore.recovery import RecoveryPlanner
from nativepilot.generator import copy_if_changed,write_if_changed
from test_continuous_recovery_v0435 import fixture

class StagedRecoveryV0440(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);self.rom,self.export,_=fixture(self.root)
 def builder(self,project):
  build=project/'build';build.mkdir(exist_ok=True)
  app=build/'RecompDevNativeApp';app.write_bytes(b'app-synthetic')
  pilot=build/'RecompDevNativePilot';pilot.write_bytes(b'pilot-synthetic')
  return pilot,'synthetic built project fixture'
 def observe(self,stops=None):
  stages=[]
  def session(project,rom,sha,out,frames,steps,input_events):
   stages.append((frames,steps))
   status='FRAME_BUDGET_REACHED' if stops is None or frames<stops else 'BANKED_CODE_NOT_TRANSLATED'
   return {'source_sha256':sha,'reference_parity':'NOT_TESTED','gameplay':'NOT_ESTABLISHED',
           'status':status,'pc':0x4006,'physical_offset':0x4006,'mapper':[0,0,1,2],
           'native_steps':frames*100,'frames':frames if status=='FRAME_BUDGET_REACHED' else frames-1,
           'guest_state_fingerprint':123,'frame_hashes':[],'trace_tail':[]}
  return stages,session
 def test_auto_extend_proven_frame_budget_only(self):
  calls,session=self.observe()
  report=run(self.rom,self.export,self.root/'complete',frames=600,steps=2_000_000,
             max_recoveries=0,build=self.builder,session=session)
  self.assertEqual(calls,[(120,2_000_000),(300,5_000_000),(600,10_000_000)])
  self.assertEqual(report['status'],'CONTINUOUS_SESSION_COMPLETE')
  self.assertEqual(report['maximum_frames_observed'],600)
  self.assertEqual(len(report['attempts'][0]['frame_checkpoints']),3)
  self.assertEqual(report['attempt_count'],1)
 def test_later_missing_rom_does_not_count_as_full_session(self):
  calls,session=self.observe(stops=300)
  report=run(self.rom,self.export,self.root/'blocked',frames=1800,steps=2_000_000,
             max_recoveries=0,build=self.builder,session=session)
  self.assertEqual([x[0] for x in calls],[120,300])
  self.assertEqual(report['status'],'RECOVERY_BLOCKED')
  self.assertEqual(report['blocker'],'RECOVERY_BUDGET_EXHAUSTED')
  self.assertLess(report['maximum_frames_observed'],300)
  self.assertEqual(len(report['attempts'][0]['frame_checkpoints']),2)
 def test_short_session_unchanged(self):
  calls,session=self.observe()
  report=run(self.rom,self.export,self.root/'short',frames=2,steps=700,
             max_recoveries=0,build=self.builder,session=session)
  self.assertEqual(calls,[(2,700)])
  self.assertEqual(report['frame_checkpoints'],[2])
 def test_progress_planner_is_bounded(self):
  self.assertEqual(RecoveryPlanner(24).budget,24)
  with self.assertRaises(ValueError):RecoveryPlanner(25)
 def test_generator_keeps_unchanged_file_timestamp(self):
  p=self.root/'sample.cpp'
  self.assertTrue(write_if_changed(p,'content'))
  before=p.stat().st_mtime_ns
  self.assertFalse(write_if_changed(p,'content'))
  self.assertEqual(before,p.stat().st_mtime_ns)
  self.assertTrue(write_if_changed(p,'changed'))
  q=self.root/'copied.cpp'
  self.assertTrue(copy_if_changed(p,q))
  self.assertFalse(copy_if_changed(p,q))

if __name__=='__main__':unittest.main()
