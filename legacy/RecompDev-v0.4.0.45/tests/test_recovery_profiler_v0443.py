import importlib.util,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('recovery_profiler_v0443',ROOT/'tools/Recovery-Profiler-v0443.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Profiler443(unittest.TestCase):
 def test_sum_measured_fields_only(self):
  x=m.summarize({'source_sha256':'a'*64,'maximum_frames_observed':342,
    'coverage_cache':{'loaded_instruction_offsets':2547},'attempts':[
    {'index':0,'frames':342,'translated_instructions':8380,'new_instruction_addresses':0,
      'status':'UNTRANSLATED_INITIAL_CODE','timings_seconds':{'build':12.5,'reset_replays':8.25}}]})
  self.assertEqual(x['timings_total_seconds']['build'],12.5)
  self.assertEqual(x['cache']['loaded_instruction_offsets'],2547)
  self.assertEqual(x['reference_parity'],'NOT_TESTED')
 def test_bad_timing_rejected(self):
  with self.assertRaises(ValueError):m.summarize({'attempts':[{'timings_seconds':{'build':-1}}]})
if __name__=='__main__':unittest.main()
