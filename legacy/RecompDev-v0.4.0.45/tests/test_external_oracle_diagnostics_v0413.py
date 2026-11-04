"""v0.4.0.13: independent-evidence handling, no native-to-reference synthesis."""
import hashlib
from nativecore.bus_oracle import import_bus, compare_bus
import json
import tempfile
import unittest
from pathlib import Path
from nativecore.divergence import diagnose
from nativecore.frame_oracle import validate_frames
from nativecore.eventstream import _read_chunk

HASH='a'*64

def stream(root, events):
    root.mkdir(exist_ok=True)
    chunks=[]
    for i in range(0,len(events),1024):
        name=f'hardware-events-{i//1024:06d}.jsonl'
        file=root/name
        file.write_text(''.join(json.dumps(e)+'\n' for e in events[i:i+1024]))
        read,digest,size=_read_chunk(file)
        chunks.append({'name':name,'events':len(read),'sha256':digest,'size_bytes':size})
    return {'schema':'recomp-event-stream-manifest-v1','status':'COMPLETE','count':len(events),
            'bytes':sum(c['size_bytes'] for c in chunks),'chunks':chunks}

class DiagnosisTests(unittest.TestCase):
    def test_first_difference_after_old_inline_cap_and_classification(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);native=base/'native';external=base/'external'
            entries=[dict(step=i,pc=100,kind='PSG_WRITE',address=127,value=i%256) for i in range(4205)]
            native_manifest=stream(native,entries)
            other=[dict(x) for x in entries]
            other[4104]['value']=9
            external_manifest=stream(external,other)
            ref={'schema':'recomp-independent-stream-reference-v1','source_sha256':HASH,
                 'independent_source':'External fixture engine', 'alignment':'ordinal',
                 'prefix_only':False,'event_stream_manifest':external_manifest,'checkpoints':[]}
            candidate={'source_id':HASH,'trace':{'event_stream_manifest':native_manifest,'events_total':len(entries),'checkpoints':[]}}
            result=diagnose(ref,candidate,native,external)
            self.assertEqual(result['status'],'DIVERGED')
            self.assertEqual(result['classification'],'AUDIO_IO_SEMANTICS')
            self.assertEqual(result['first_event_divergence']['event_index'],4104)
            self.assertEqual(len(result['first_event_divergence']['preceding_events']),4)
            self.assertFalse(result['automatic_patch_applied'])
            (external/'hardware-events-000004.jsonl').write_text('tampered\n')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):
                diagnose(ref,candidate,native,external)

    def test_prefix_extra_native_events_are_not_divergence(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            events=[dict(step=i,pc=1,kind='VDP_CONTROL_WRITE',address=191,value=123) for i in range(5)]
            native=base/'native';external=base/'external'
            ref={'schema':'recomp-independent-stream-reference-v1','source_sha256':HASH,
                 'independent_source':'External fixture','alignment':'ordinal','prefix_only':True,
                 'event_stream_manifest':stream(external,events[:3]),'checkpoints':[]}
            candidate={'source_id':HASH,'trace':{'event_stream_manifest':stream(native,events),
                       'events_total':5,'checkpoints':[]}}
            result=diagnose(ref,candidate,native,external)
            self.assertEqual(result['status'],'MATCHED_EVENT_PREFIX')
            self.assertIsNone(result['first_event_divergence'])

    def test_wrong_rom_rejected(self):
        with self.assertRaisesRegex(ValueError,'hashes do not match'):
            diagnose({'schema':'recomp-independent-event-trace-v1','source_sha256':HASH,
                      'independent_source':'MAME'}, {'source_id':'f'*64,'trace':{}},None,None)

class FrameCaptureTests(unittest.TestCase):
    def test_valid_unaligned_frames_are_not_parity(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'frames.jsonl'
            file.write_text('\n'.join(json.dumps({'type':'frame','ordinal':i,'pc':i*17,'af':i}) for i in range(1,4))+'\n')
            report=validate_frames(file,HASH,'Fake independent test engine',3)
            self.assertEqual(report['captured_frames'],3)
            self.assertEqual(report['parity'],'NOT_TESTED')
            self.assertEqual(report['raw_sha256'],hashlib.sha256(file.read_bytes()).hexdigest())
            with self.assertRaisesRegex(ValueError,'incomplete'):
                validate_frames(file,HASH,'Producer',4)
            file.write_text(file.read_text().replace('"ordinal": 2','"ordinal": 8'))
            with self.assertRaisesRegex(ValueError,'contiguous'):
                validate_frames(file,HASH,'Producer',3)
    def test_missing_pc_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'frames.jsonl';file.write_text('{"type":"frame","ordinal":1}\n')
            with self.assertRaisesRegex(ValueError,'PC'):
                validate_frames(file,HASH,'MAME',1)

if __name__=='__main__':unittest.main()

class ExternalMameHarnessTests(unittest.TestCase):
    def test_launcher_synthetic_process_contract_without_real_emulator(self):
        import sys, importlib.util
        if sys.platform == 'win32':self.skipTest('POSIX executable fixture only')
        root=Path(__file__).resolve().parents[1]
        spec=importlib.util.spec_from_file_location('mame_harness',root/'tools'/'Capture-MAME-SMS.py')
        runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);rom=tmp/'synthetic.sms';rom.write_bytes(b'author-created external fixture')
            sha=hashlib.sha256(rom.read_bytes()).hexdigest()
            mame=tmp/'mame-synthetic-fixture'
            program = ('#!/usr/bin/env python3\nimport os,json\n'
                       "with open(os.environ['RECOMPDEV_MAME_FRAME_OUTPUT'],'w') as f:\n"
                       " for i in range(1,int(os.environ['RECOMPDEV_MAME_FRAME_LIMIT'])+1):\n"
                       "  f.write(json.dumps({'type':'frame','ordinal':i,'pc':i})+'\\n')\n"
                       "with open(os.environ['RECOMPDEV_MAME_BUS_OUTPUT'],'w') as f:\n"
                       " f.write(json.dumps({'type':'bus','ordinal':1,'kind':'PSG_WRITE','address':127,'value':4,'pc':2})+'\\n')\n")
            mame.write_text(program)
            mame.chmod(0o755)
            report=runner.capture(mame,tmp,rom,sha,tmp/'capture',frames=3,timeout=20)
            self.assertEqual(report['parity'],'NOT_TESTED')
            self.assertEqual(report['captured_frames'],3)
            self.assertTrue((tmp/'capture'/'frame-observations.json').is_file())
            self.assertEqual(report['selected_io_writes'],1)
            self.assertTrue((tmp/'capture'/'selected-bus-reference.json').is_file())
            self.assertTrue((tmp/'capture'/'mame-frame-capture.lua').is_file())
            with self.assertRaisesRegex(ValueError,'immutable'):
                runner.capture(mame,tmp,rom,sha,tmp/'capture',frames=3)
            with self.assertRaisesRegex(ValueError,'SHA-256 mismatch'):
                runner.capture(mame,tmp,rom,'f'*64,tmp/'capture2',frames=3)

class BusComparisonTests(unittest.TestCase):
    def test_selected_bus_prefix_and_first_divergence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);native=root/'native'
            events=[{'step':i,'pc':55,'kind':('PSG_WRITE' if i%2==0 else 'VRAM_WRITE'),
                     'address':(127 if i%2==0 else i),'value':i%256} for i in range(8)]
            manifest=stream(native,events)
            candidate={'source_id':HASH,'trace':{'event_stream_manifest':manifest,'events_total':8}}
            reference_file=root/'bus.jsonl'
            ref_events=[{'type':'bus','ordinal':i+1,'pc':123,'kind':'PSG_WRITE','address':127,'value':v}
                        for i,v in enumerate((0,2,4))]
            reference_file.write_text(''.join(json.dumps(x)+'\n' for x in ref_events))
            ref=import_bus(reference_file,HASH,'Independent synthetic fixture')
            matched=compare_bus(ref,reference_file,candidate,native)
            self.assertEqual(matched['status'],'MATCHED_SELECTED_IO_PREFIX')
            self.assertFalse(matched['pc_aligned'])
            ref_events[2]['value']=99
            reference_file.write_text(''.join(json.dumps(x)+'\n' for x in ref_events))
            ref=import_bus(reference_file,HASH,'Independent synthetic fixture')
            diverged=compare_bus(ref,reference_file,candidate,native)
            self.assertEqual(diverged['status'],'SELECTED_IO_DIVERGED')
            self.assertEqual(diverged['first_divergence']['bus_index'],2)
            reference_file.write_text('tampered')
            with self.assertRaisesRegex(ValueError,'SHA-256 mismatch'):
                compare_bus(ref,reference_file,candidate,native)
