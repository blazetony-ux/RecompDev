"""v0.4.9.22 native monitor, capture-watch and filter pipeline contracts."""
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
from execution_monitor.job_preview import watch_number,watch_range,safe_excerpt

class V22Watch(unittest.TestCase):
 def test_exact_watches_and_validation(self):
  self.assertEqual(watch_number('0x0BDB'),0x0BDB)
  self.assertEqual(watch_number('65535'),65535)
  self.assertEqual(watch_range('0x0BD8:0x0BE4'),(0x0BD8,0x0BE4))
  for value in ('-1','0x100000000','0xG1','65536x','', '2.4'):
   with self.assertRaises(ValueError):watch_number(value)
  for value in ('55:54','1:2:3','bad'):
   with self.assertRaises(ValueError):watch_range(value)
 def test_protocol_retains_watch_hit_and_source(self):
  event={'type':'instruction','cpu':'generic','pc':17,'physical_offset':12,'watch_hit':True,'opcode_class':'BRANCH','junk':'ignore'}
  row=safe_excerpt(event)
  self.assertTrue(row['watch_hit'])
  self.assertNotIn('junk',row)
  bridge=(ROOT/'execution_monitor/bridge/rd_execution_events.hpp').read_text()
  self.assertIn('const bool watch_hit=hit(pc)',bridge)
  self.assertIn('&& !watch_hit)return;',bridge)
  self.assertIn('MONITOR_WATCH_PC_RANGE',bridge)
  self.assertNotIn('shinobi',bridge.lower())
 def test_compiled_controller_routes_capture_watch(self):
  controller=(ROOT/'controller/native_job.cpp').read_text()
  for marker in ('--monitor-pc','--monitor-pc-range','--monitor-matched-only','MONITOR_WATCH_LIMIT'):
   self.assertIn(marker,controller)
  preview=(ROOT/'execution_monitor/job_preview.py').read_text()
  self.assertIn('RECOMPDEV_MONITOR_WATCH_PC',preview)
  self.assertIn('RECOMPDEV_MONITOR_WATCH_PC_RANGE',preview)
  self.assertIn('monitor_watch_hits',preview)
 def test_win32_nonblocking_ui_structure(self):
  source=(ROOT/'execution_monitor/native/viewer_win32.cpp').read_text()
  self.assertIn('SetTimer(hwnd,kRefreshTimer,100',source)
  self.assertIn('ui.queue.take(768)',source)
  self.assertIn('EM_REPLACESEL',source)
  self.assertIn('kSearch',source)
  self.assertIn('kMatch',source)
  self.assertIn('kFollow',source)
  self.assertIn('kPrev',source)
  self.assertIn('kNext',source)
  self.assertNotIn('PostMessageW',source)
  self.assertNotIn('std::string(value.begin(),value.end())',source)

if __name__=='__main__':unittest.main()
