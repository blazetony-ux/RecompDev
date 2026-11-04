"""Regress original owner failure: a non-SHA source must not crash either Workbench API."""
import json
import socket
import subprocess
import time
from urllib.request import urlopen
from contextlib import closing
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from discovery import store
from graph_store import connect as graph_connect,register_target_if_absent
from workbench import data,_native_history_sources,_read_history_for_sources

ROOT=Path(__file__).resolve().parents[1]
SHA='a'*64
INVALID='legacy-import-source-0001'

class UnifiedSourceIdentity(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.folder=Path(self.tmp.name)
  self.db=self.folder/'catalogue.sqlite'
  shutil.copyfile(ROOT/'catalogue.sqlite',self.db)
  with closing(store.connect(self.db)) as con:
   store.store_source(con,INVALID,'C:/Legacy/archive.bin',123,'LEGACY_UNKNOWN','unknown','Legacy unrelated','synthetic')
  self.con=graph_connect(self.db);self.addCleanup(self.con.close)
  register_target_if_absent(self.con,'mastersystem-aaaaaaaaaaaa','z80',SHA,'mastersystem','synthetic')
  self.install=self.folder/'RecompDev-v0.4.0.29'
  self.job=self.install/'evidence'/'integrated-native-v0429'/'jobs'/'0123456789abcdef'
  (self.job/'pilot').mkdir(parents=True)
  (self.job/'host').mkdir()
  (self.job/'campaign-result.json').write_text(json.dumps({'schema':'recomp-end-to-end-campaign-v0424','source_sha256':SHA,'status':'EXPERIMENTAL_NATIVE_APPLICATION_EXECUTED'}))
  (self.job/'pilot'/'pilot-report.json').write_text(json.dumps({'source_id':SHA,'status':'NATIVE_STEP_BUDGET_REACHED','translated_instructions':5075,'native_steps':500000,'dependency_graph':{'unresolved_edges':12},'trace':{'event_stream_manifest':{'status':'INCOMPLETE'}}}))
  (self.job/'host'/'continuous-session.json').write_text(json.dumps({'schema':'recomp-continuous-owner-session-v1','source_sha256':SHA,'status':'FRAME_BUDGET_REACHED','host_mode':'HEADLESS_AUTONOMOUS','frames':120,'audio_samples':88200,'discarded_frames':120,'discarded_audio_samples':88200,'guest_state_fingerprint':5,'native_steps':764503,'video_backend':'null','audio_backend':'null','assets':{}}))

 def test_known_graph_target_without_discovery_source_is_visible(self):
  candidates,warnings=_native_history_sources(self.con)
  matches=[c for c in candidates if c['source_id']==SHA]
  self.assertEqual(len(matches),1)
  self.assertEqual(matches[0]['target_id'],'mastersystem-aaaaaaaaaaaa')
  self.assertEqual([i['source_id'] for i in warnings if i['reason']=='DISCOVERY_SOURCE_ID_NOT_FULL_SHA256'],[INVALID])
  records,errors=_read_history_for_sources(matches,[self.install],check_events=False)
  self.assertFalse(errors)
  self.assertEqual(len(records),1)
  self.assertEqual(records[0][1]['integrated_campaigns'][0]['native_steps'],764503)

 def test_overview_honours_authenticated_job_and_does_not_touch_graph_counts(self):
  with patch('workbench._installation_roots',return_value=[self.install]):
   overview=data(self.con,'overview',{})
  found=[x for x in overview['native_history'] if x['source_id']==SHA]
  self.assertEqual(len(found),1)
  self.assertEqual(found[0]['integrated_campaigns'][0]['translated_instructions'],5075)
  self.assertEqual(found[0]['integrated_campaigns'][0]['frames'],120)
  self.assertTrue(any(x['source_id']==INVALID for x in overview['native_history_issues']))
  static=next(x for x in overview['targets'] if x['target_id']=='mastersystem-aaaaaaaaaaaa')
  self.assertEqual(static['instruction_count'],0)
  self.assertEqual(static['functions'],0)

 def test_tampered_host_is_rejected_but_other_targets_still_load(self):
  file=self.job/'host'/'continuous-session.json'
  session=json.loads(file.read_text());session['source_sha256']='b'*64
  file.write_text(json.dumps(session))
  with patch('workbench._installation_roots',return_value=[self.install]):
   overview=data(self.con,'overview',{})
  self.assertFalse([x for x in overview['native_history'] if x['source_id']==SHA])
  candidates,_=_native_history_sources(self.con)
  records,errors=_read_history_for_sources(candidates,[self.install],check_events=False)
  self.assertFalse(errors)
  bad=next((h for s,h in records if s['source_id']==SHA),None)
  self.assertIsNotNone(bad)
  self.assertTrue(bad['rejected_evidence'])

 def test_real_http_api_does_not_abruptly_close_on_legacy_id(self):
  with socket.socket() as sock:
   sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  process=subprocess.Popen([sys.executable,str(ROOT/'recomp.py'),'--db',str(self.db),
      'serve','--port',str(port)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  try:
   url='http://127.0.0.1:'+str(port)
   for _ in range(70):
    try:
     with urlopen(url+'/',timeout=1) as response:
      if response.status==200:break
    except OSError:
     if process.poll() is not None:self.fail('Workbench exited unexpectedly')
     time.sleep(0.05)
   else:self.fail('Workbench did not start')
   for api in ('/api/overview','/api/unified-evidence'):
    with urlopen(url+api,timeout=15) as response:
     self.assertEqual(response.status,200)
     self.assertIn('application/json',response.headers['Content-Type'])
     document=json.load(response)
     self.assertTrue(document['ok'])
     if api.endswith('unified-evidence'):
      self.assertTrue(any(x['source_id']==INVALID for x in document['data']['identity_issues']))
      self.assertTrue(any(x['source_id']==SHA for x in document['data']['targets']))
  finally:
   if process.poll() is None:process.terminate()
   try:process.wait(timeout=6)
   except subprocess.TimeoutExpired:
    process.kill();process.wait(timeout=6)

 def test_invalid_id_is_not_rehashed_or_attached_to_another_game(self):
  sources,issues=_native_history_sources(self.con)
  self.assertNotIn(INVALID,{x['source_id'] for x in sources})
  self.assertTrue(issues)
  self.assertEqual(len(set(x['source_id'] for x in sources)),len(sources))

if __name__=='__main__':unittest.main()
