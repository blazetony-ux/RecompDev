"""First selected-event divergence must not be misreported as CPU parity failure."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from nativecore.sms_startup_v0433 import inspect
from nativecore.eventstream import _read_chunk
from nativecore.bus_oracle import import_bus
SHA='1'*64
class StartupTests(unittest.TestCase):
 def test_distinct_first_io_event_is_unaligned_not_cpu_failure(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);reference=root/'mame';reference.mkdir();pilot=root/'pilot';pilot.mkdir()
   bus=reference/'mame-bus.jsonl';bus.write_text(json.dumps(dict(type='bus',ordinal=1,kind='PSG_WRITE',address=127,value=0x9f,pc=400))+'\n')
   manifest=import_bus(bus,SHA,'Independent synthetic fixture')
   (reference/'selected-bus-reference.json').write_text(json.dumps(manifest))
   pdir=pilot/'event-streams'/'attempt-00-budget-1000';pdir.mkdir(parents=True)
   chunk=pdir/'hardware-events-000000.jsonl'
   chunk.write_text(json.dumps(dict(step=1,pc=12,kind='PSG_WRITE',address=127,value=0x80))+'\n')
   arr,digest,size=_read_chunk(chunk)
   event_manifest={'schema':'recomp-event-stream-manifest-v1','status':'COMPLETE','count':1,'bytes':size,
                   'chunks':[{'name':chunk.name,'events':1,'sha256':digest,'size_bytes':size}]}
   report=pilot/'pilot-report.json';report.write_text(json.dumps({'source_id':SHA,'trace':{'event_stream_directory':'event-streams/attempt-00-budget-1000','event_stream_manifest':event_manifest,'events_total':1}}))
   got=inspect(reference,report)
   self.assertEqual(got['status'],'FIRST_IO_DIFFERENCE_WITH_UNALIGNED_START')
   self.assertEqual(got['matching_selected_io_prefix'],0)
   self.assertFalse(got['same_initial_machine_state_proven'])
   self.assertFalse(got['native_qualified'])
   self.assertEqual(got['first_selected_io_difference']['bus_index'],0)
   bus.write_text(bus.read_text().replace('159','128'))
   with self.assertRaisesRegex(ValueError,'SHA-256 mismatch'):inspect(reference,report)
   report.write_text(report.read_text().replace(SHA,'2'*64))
   with self.assertRaisesRegex(ValueError,'sources do not agree'):inspect(reference,report)
if __name__=='__main__':unittest.main()
