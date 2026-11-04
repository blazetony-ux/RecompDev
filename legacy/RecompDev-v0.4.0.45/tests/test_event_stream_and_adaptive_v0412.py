"""Synthetic and cross-producer contract tests; no commercial game parity claim."""
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from nativecore.eventstream import iter_verified,manifest_for_native
from nativecore.parity import compare
from nativepilot.engine import budget_plan,observable_progress
ROOT=Path(__file__).resolve().parents[1]
SHA='a'*64

def importer():
    p=ROOT/'tools'/'Import-Independent-Trace.py'
    spec=importlib.util.spec_from_file_location('recomp_reference_importer_v0412',p)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

class StreamTests(unittest.TestCase):
    def test_budget_plan_bounded_and_progress_observable(self):
        self.assertEqual(budget_plan(500000,True),[50000,100000,200000,400000,500000])
        self.assertEqual(budget_plan(500000,False),[500000])
        self.assertEqual(budget_plan(100,True),[100])
        self.assertFalse(observable_progress({'checkpoints':[{'pc':20,'tstates':5},{'pc':20,'tstates':999}]}))
        self.assertTrue(observable_progress({'checkpoints':[{'pc':20,'bc':10},{'pc':20,'bc':9}]}))
        self.assertTrue(observable_progress({'checkpoints':[{'pc':20,'vram_writes':0},{'pc':20,'vram_writes':2}]}))
        self.assertFalse(observable_progress({'checkpoints':[{'pc':0},{'pc':20},{'pc':20}]}))
        with self.assertRaises(ValueError):budget_plan(3,'yes')

    def test_large_stream_full_reference_match_and_first_divergence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);native=root/'native';external=root/'reference';native.mkdir();external.mkdir()
            refraw=root/'external.jsonl'
            events=[{'step':i+1,'pc':5,'kind':'VRAM_WRITE','address':i%16384,'value':i%256} for i in range(7100)]
            # Both engines are synthetic fixtures. Never infer external independence.
            refraw.write_text(''.join(json.dumps({'type':'event',**x})+'\n' for x in events))
            reference=importer().import_stream_trace(refraw,external/'reference.json',SHA,'Independent synthetic fixture',prefix_only=False)
            chunks=[];nbytes=0
            for start in range(0,len(events),1024):
                part=events[start:start+1024];filename=f'hardware-events-{len(chunks):06d}.jsonl'
                b=''.join(json.dumps(x,separators=(',',':'))+'\n' for x in part).encode()
                (native/filename).write_bytes(b);nbytes+=len(b)
                chunks.append({'name':filename,'events':len(part),'size_bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
            trace={'events':events[:4096],'events_total':len(events),'events_truncated':True,
                   'event_stream_chunks':len(chunks),'event_stream_events':len(events),'event_stream_bytes':nbytes,
                   'event_stream_complete':True,'checkpoints':[]}
            trace['event_stream_manifest']=manifest_for_native(native,trace)
            candidate={'source_id':SHA,'trace':trace}
            result=compare(reference,candidate,event_root=native,reference_root=external)
            self.assertEqual(result['status'],'MATCHED_EVENT_TRACE')
            self.assertEqual(result['reference_events'],7100)
            self.assertEqual(result['candidate_events_total'],7100)
            # Reference hashes must fail closed on tampering.
            with (external/'hardware-events-000003.jsonl').open('ab') as f:f.write(b' ') 
            with self.assertRaisesRegex(ValueError,'hash mismatch'):
                compare(reference,candidate,event_root=native,reference_root=external)
            # Restore and mutate an event while preserving the valid manifest.
            ref2=external/'new_reference';ref2.mkdir()
            records=[{**x} for x in events];records[5050]['value']=55
            diff=root/'external-difference.jsonl'
            diff.write_text(''.join(json.dumps({'type':'event',**x})+'\n' for x in records))
            changed=importer().import_stream_trace(diff,ref2/'reference.json',SHA,'Independent synthetic fixture',prefix_only=False)
            diffreport=compare(changed,candidate,event_root=native,reference_root=ref2)
            self.assertEqual(diffreport['status'],'DIVERGED')
            self.assertEqual(diffreport['mismatches'][0]['event_index'],5050)

    @unittest.skipUnless(shutil.which('g++'), 'g++ unavailable')
    def test_compiled_native_event_recorder_writes_complete_chunks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/'demo.cpp';out=root/'demo'
            source.write_text('''#include "runtime.hpp"
#include <iostream>
int main(int argc,char**argv){rd::State s;s.enable_event_stream(argv[1]);
 for(unsigned i=0;i<7061;++i){s.steps=i;s.pc=14;s.record_event("VDP_CONTROL_WRITE",191,i%256);}
 s.finish_event_stream();std::cout<<s.events_total<<" "<<s.event_stream_chunks<<" "<<s.event_stream_complete<<" "<<s.event_stream_bytes<<"\\n";}
''')
            cmd=['g++','-std=c++17','-O0','-I',str(ROOT/'systems/mastersystem'),str(source),str(ROOT/'systems/mastersystem/runtime.cpp'),'-o',str(out)]
            build=subprocess.run(cmd,capture_output=True,text=True,timeout=45)
            self.assertEqual(build.returncode,0,build.stderr[-3000:])
            run=subprocess.run([str(out),str(root/'hardware-events')],capture_output=True,text=True,timeout=20)
            self.assertEqual(run.returncode,0,run.stderr)
            total,chunks,complete,nbytes=map(int,run.stdout.split())
            self.assertEqual((total,chunks,complete),(7061,7,1))
            meta={'events_total':total,'event_stream_events':total,'event_stream_chunks':chunks,
                  'event_stream_complete':True,'event_stream_bytes':nbytes}
            manifest=manifest_for_native(root,meta)
            self.assertEqual(sum(1 for _ in iter_verified(root,manifest)),7061)
            (root/'hardware-events-000001.jsonl').write_text('malicious\n')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):
                list(iter_verified(root,manifest))

if __name__=='__main__':unittest.main()

class ExternalAdapterTests(unittest.TestCase):
    def test_owner_approved_external_capture_and_hash_controls(self):
        import sys
        import importlib.util
        spec=importlib.util.spec_from_file_location('recomp_oracle_runner',ROOT/'tools'/'Run-External-Oracle.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            rom=root/'sample.rom';rom.write_bytes(b'author-created fixture ROM')
            digest=hashlib.sha256(rom.read_bytes()).hexdigest()
            program=root/'emulator_fixture.py'
            program.write_text('''import json,sys
rom,output,steps=sys.argv[1:]
assert int(steps)>0
with open(output,'w') as f:
 f.write(json.dumps(dict(type='event',step=2,pc=3,kind='VDP_CONTROL_WRITE',address=191,value=128))+'\\n')
''')
            adapter=root/'adapter.json'
            adapter.write_text(json.dumps({'schema':module.SCHEMA,'producer':'Second synthetic engine fixture',
                'executable':sys.executable,'arguments':[str(program),'{rom}','{output}','{steps}']}))
            out=root/'independent'
            result=module.capture(adapter,Path(sys.executable).resolve().parent,rom,digest,out,10,20)
            self.assertEqual(result['status'],'CAPTURE_IMPORTED_NOT_PARITY_VERIFIED')
            self.assertEqual(result['events'],1)
            self.assertTrue((out/'reference.json').is_file())
            with self.assertRaisesRegex(ValueError,'already exists'):
                module.capture(adapter,Path(sys.executable).resolve().parent,rom,digest,out,10,20)
            with self.assertRaisesRegex(ValueError,'SHA-256 mismatch'):
                module.capture(adapter,Path(sys.executable).resolve().parent,rom,'0'*64,root/'other',10,20)
