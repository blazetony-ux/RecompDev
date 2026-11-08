"""v21 source-agnostic native monitor launch, terminal clocks and bounded evidence."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from execution_monitor.job_preview import frame_accounting,candidate_capture,diagnostic_zip
from execution_monitor import job_preview

class NativeV21(unittest.TestCase):
 def test_native_viewer_only_and_versioned_schema(self):
  source=(ROOT/'execution_monitor/job_preview.py').read_text()
  self.assertIn('RecompDevMonitor', (ROOT/'harness/CMakeLists.txt').read_text())
  self.assertIn('NATIVE_WIN32_LAUNCHED_UNVERIFIED',source)
  self.assertNotIn("'-m','execution_monitor.viewer'",source)
  self.assertNotIn('import tkinter', (ROOT/'execution_monitor/native/monitor_model.hpp').read_text())
  self.assertIn('ws2_32',(ROOT/'harness/CMakeLists.txt').read_text().lower())
 def test_distinguishes_terminal_guest_from_sampled(self):
  a=frame_accounting({'frames':1800,'guest_frames':1799},{'frame':1797})
  self.assertEqual(a['host_output_frames'],1800)
  self.assertEqual(a['guest_vdp_frames_at_native_exit'],1799)
  self.assertEqual(a['last_sampled_guest_frame'],1797)
  self.assertEqual(a['delta_host_minus_guest_vdp'],1)
  self.assertFalse(a['gameplay_parity_qualified'])
 def test_candidate_video_only_and_manifest(self):
  src='a'*64
  capture=candidate_capture({'frames':3,'frame_hashes':[0,0x10,(1<<64)-1]},src)
  self.assertEqual(capture['video_fingerprints'],['0000000000000000','0000000000000010','ffffffffffffffff'])
  self.assertNotIn('audio_sha256',capture)
  self.assertNotIn('input_sha256',capture)
  self.assertFalse(capture['gameplay_parity_qualified'])
  self.assertIsNone(candidate_capture({'frames':2,'frame_hashes':[0]},src))
  with tempfile.TemporaryDirectory() as tmp:
   t=Path(tmp);out=t/'run';out.mkdir()
   zip_path=diagnostic_zip(out,t/'zip',{'schema':'recompdev.preview.session.v1'},[],capture=capture)
   with zipfile.ZipFile(zip_path) as z:
    self.assertIn('candidate-capture.json',z.namelist())
    self.assertTrue(json.loads(z.read('candidate-capture.json'))['video_fingerprints'])
 def test_bounded_cycle_limits_aligned(self):
  controller=(ROOT/'controller/native_job.cpp').read_text()
  exporter=(ROOT/'workspace/diagnostics_export.py').read_text()
  self.assertIn('number("MAX_CYCLES",val,1,128)',controller)
  self.assertIn('j.attempts.size()>128',controller)
  self.assertIn('MAX_SESSIONS = 128',exporter)
  self.assertIn('MAX_FILES = 1300',exporter)
  self.assertTrue(job_preview.CYCLE.fullmatch('cycle-128'))
  self.assertFalse(job_preview.CYCLE.fullmatch('cycle-129'))
 def test_recovery_preflight_matches_large_cycle(self):
  from analysis_integration.preview_frontier import CYCLE
  self.assertTrue(CYCLE.fullmatch('cycle-128'))
  self.assertFalse(CYCLE.fullmatch('cycle-129'))

if __name__=='__main__':unittest.main()
