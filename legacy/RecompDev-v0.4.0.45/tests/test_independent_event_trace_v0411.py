"""Synthetic cross-game evidence contracts; not a commercial ROM parity claim."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from nativecore.parity import EVENT_SCHEMA,compare

SHA='7'*64

def ref(events=None,**kwargs):
    x={'schema':EVENT_SCHEMA,'source_sha256':SHA,'independent_source':'Other independently operated Z80 engine v1',
       'prefix_only':True,'alignment':'ordinal','events':events or [
        {'step':12,'pc':25,'kind':'VDP_CONTROL_WRITE','address':191,'value':128},
        {'step':13,'pc':28,'kind':'VRAM_WRITE','address':4,'value':20}]}
    x.update(kwargs)
    return x

def candidate(events=None,**kwargs):
    x={'source_id':SHA,'trace':{'events':events or [
        {'step':22,'pc':25,'kind':'VDP_CONTROL_WRITE','address':191,'value':128},
        {'step':23,'pc':28,'kind':'VRAM_WRITE','address':4,'value':20}],
        'events_total':2,'events_truncated':False,'checkpoints':[],
        'hardware_sha256':{'vram':'a'*64}}}
    x['trace'].update(kwargs)
    return x

class EventComparisonTests(unittest.TestCase):
    def test_ordinal_accepts_step_drift_only_and_reports_it(self):
        got=compare(ref(),candidate())
        self.assertEqual(got['status'],'MATCHED_EVENT_PREFIX')
        self.assertEqual(got['step_drift'][0]['native_step'],22)
        self.assertEqual(compare(ref(alignment='step'),candidate())['status'],'DIVERGED')
    def test_real_event_divergence_first_field_and_order(self):
        bad=candidate();bad['trace']['events'][1]['value']=21
        result=compare(ref(),bad)
        self.assertEqual(result['status'],'DIVERGED')
        self.assertEqual(result['mismatches'][0]['event_index'],1)
        self.assertEqual(result['mismatches'][0]['field'],'value')
        bad['trace']['events'].reverse()
        self.assertEqual(compare(ref(),bad)['status'],'DIVERGED')
    def test_truncation_missing_events_and_complete_trace(self):
        partial=candidate(events=[candidate()['trace']['events'][0]],events_total=100,events_truncated=True)
        self.assertEqual(compare(ref(),partial)['status'],'INCOMPLETE_EVENT_COVERAGE')
        self.assertEqual(compare(ref(prefix_only=False),candidate())['status'],'MATCHED_EVENT_TRACE')
        more=candidate(events_total=3,events_truncated=True)
        self.assertEqual(compare(ref(prefix_only=False),more)['status'],'INCOMPLETE_EVENT_COVERAGE')
    def test_rom_identity_and_external_provenance_mandatory(self):
        with self.assertRaisesRegex(ValueError,'hashes do not match'):
            compare(ref(),{'source_id':'0'*64,'trace':candidate()['trace']})
        with self.assertRaisesRegex(ValueError,'provenance'):
            compare(ref(independent_source=''),candidate())
        with self.assertRaisesRegex(ValueError,'prefix_only'):
            compare(ref(prefix_only='True'),candidate())
        with self.assertRaisesRegex(ValueError,'count inconsistent'):
            compare(ref(),candidate(events_total=1))
        with self.assertRaisesRegex(ValueError,'truncation evidence'):
            compare(ref(),candidate(events_truncated=True))
    def test_hardware_digest_and_cpu_sample_comparison(self):
        source=ref(final_hardware_sha256={'vram':'a'*64},checkpoints=[{'step':200,'pc':100,'af':20}])
        observed=candidate(checkpoints=[{'step':200,'pc':100,'af':20}])
        self.assertEqual(compare(source,observed)['status'],'MATCHED_EVENT_PREFIX')
        observed['trace']['hardware_sha256']['vram']='b'*64
        self.assertEqual(compare(source,observed)['status'],'DIVERGED')
        observed['trace']['hardware_sha256']['vram']='a'*64
        observed['trace']['checkpoints'][0]['af']=21
        self.assertEqual(compare(source,observed)['status'],'DIVERGED')
        observed['trace']['checkpoints']=[]
        self.assertEqual(compare(source,observed)['status'],'INCOMPLETE_EVENT_COVERAGE')
    def test_import_external_jsonl_with_raw_provenance_and_rejection(self):
        module=Path(__file__).resolve().parents[1]/'tools'/'Import-Independent-Trace.py'
        spec=importlib.util.spec_from_file_location('reference_importer',module)
        tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'reference.jsonl'
            line={'type':'event','step':12,'pc':25,'kind':'VDP_CONTROL_WRITE','address':191,'value':128}
            path.write_text(json.dumps(line)+'\n')
            imported=tool.import_trace(path,SHA,'Z80 reference engine v2')
            self.assertEqual(imported['events'][0]['kind'],'VDP_CONTROL_WRITE')
            self.assertEqual(imported['external_raw_trace_sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
            path.write_text(json.dumps(line)+'\n'+json.dumps({**line,'step':4})+'\n')
            with self.assertRaisesRegex(ValueError,'Non-monotonic'):
                tool.import_trace(path,SHA,'Z80 reference engine v2')

if __name__=='__main__':unittest.main()
