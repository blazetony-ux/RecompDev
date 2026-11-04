"""No real ROM required: authentic-shaped native history, tampering and version discovery."""
import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from platform424.evidence import history

SHA='a'*64

class CurrentHistory(unittest.TestCase):
 def test_newest_release_discovered_without_version_list(self):
  with tempfile.TemporaryDirectory() as temp:
   install=Path(temp)/'RecompDev-v0.4.0.29'
   j=install/'evidence'/'integrated-native-v0429'/'jobs'/'1234567890abcdef'
   (j/'host').mkdir(parents=True);(j/'pilot').mkdir()
   (j/'campaign-result.json').write_text(json.dumps({'schema':'recomp-end-to-end-campaign-v0424','source_sha256':SHA,'status':'EXPERIMENTAL_NATIVE_APPLICATION_EXECUTED'}))
   (j/'pilot'/'pilot-report.json').write_text(json.dumps({'source_id':SHA,'status':'NATIVE_STEP_BUDGET_REACHED','translated_instructions':5075,'native_steps':500000,'dependency_graph':{'unresolved_edges':12},'trace':{'event_stream_manifest':{'status':'INCOMPLETE'}}}))
   (j/'host'/'continuous-session.json').write_text(json.dumps({'schema':'recomp-continuous-owner-session-v1','source_sha256':SHA,'status':'FRAME_BUDGET_REACHED','host_mode':'HEADLESS_AUTONOMOUS','frames':120,'audio_samples':88200,'discarded_frames':120,'discarded_audio_samples':88200,'guest_state_fingerprint':5,'native_steps':764503,'video_backend':'null','audio_backend':'null','assets':{}}))
   result=history(SHA,[install])
   self.assertEqual(len(result['integrated_campaigns']),1)
   record=result['integrated_campaigns'][0]
   self.assertEqual(record['translated_instructions'],5075)
   self.assertEqual(record['native_steps'],764503)
   self.assertEqual(record['frames'],120)
   self.assertEqual(record['unresolved_dependency_edges'],12)
   self.assertFalse(record['native_qualified'])
   self.assertEqual(result['pilots'],[])
   changed=json.loads((j/'host'/'continuous-session.json').read_text());changed['frames']=119
   (j/'host'/'continuous-session.json').write_text(json.dumps(changed))
   altered=history(SHA,[install]);self.assertFalse(altered['integrated_campaigns'])
   self.assertTrue(altered['rejected_evidence'])
   changed['frames']=120;changed['source_sha256']='b'*64
   (j/'host'/'continuous-session.json').write_text(json.dumps(changed))
   altered=history(SHA,[install]);self.assertFalse(altered['integrated_campaigns'])
   self.assertTrue(altered['rejected_evidence'])

if __name__=='__main__':unittest.main()
