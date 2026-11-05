"""Hardware-neutral controller subscriber and native staging regression tests."""
from __future__ import annotations
import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'legacy/RecompDev-v0.4.0.45'))
from controller.diagnostics import ControllerDiagnostics, SCHEMA, normalize
from execution_monitor.stream import NativeEventReader
from execution_monitor.bridge import live_transform, MARKER
from nativepilot.generator import generate_project
from runtime_host.launch import stage

class BrokerTests(unittest.TestCase):
    def test_only_controller_subscribers_get_events(self):
        with ControllerDiagnostics() as controller:
            controller.publish({'type':'instruction','cpu':'synthetic','pc':4, 'steps':1})
            with socket.create_connection(('127.0.0.1',controller.port),timeout=3) as subscriber:
                request={'schema':SCHEMA,'role':'subscribe','token':controller.token}
                subscriber.sendall((json.dumps(request)+'\n').encode())
                stream=subscriber.makefile('rb')
                self.assertEqual(json.loads(stream.readline())['type'],'connected')
                data=json.loads(stream.readline())
                self.assertEqual(data['pc'],4)
                controller.publish({'type':'input','buttons':17})
                self.assertEqual(json.loads(stream.readline())['buttons'],17)
                stream.close()
            with socket.create_connection(('127.0.0.1',controller.port),timeout=2) as denied:
                denied.sendall((json.dumps({'schema':SCHEMA,'role':'subscribe','token':'wrong'})+'\n').encode())
                self.assertEqual(denied.recv(32),b'')

    def test_queue_bound_validation_and_slow_subscriber(self):
        with ControllerDiagnostics(history_limit=8) as controller:
            for i in range(2000):
                controller.publish({'type':'instruction','pc':i,'cpu':'synthetic'})
            self.assertEqual(len(controller._history),8)
            with self.assertRaisesRegex(ValueError,'Unsupported'):
                normalize({'type':'invalid'})
            with self.assertRaisesRegex(ValueError,'too large'):
                normalize({'type':'notice','message':'x'*6000})

    def test_file_adapter_handles_partial_lines_once(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/'telemetry.jsonl'
            output=[]
            reader=NativeEventReader(file,output.append)
            self.assertEqual(reader.poll(),0)
            file.write_bytes(b'{"type":"instruction","pc":42}\n{"type":"input"')
            self.assertEqual(reader.poll(),1)
            self.assertEqual(output[0]['pc'],42)
            self.assertEqual(reader.poll(),0)
            with file.open('ab') as f:f.write(b',"buttons":2}\nnot-json\n')
            self.assertEqual(reader.poll(),1)
            self.assertEqual(output[1]['buttons'],2)
            self.assertEqual(reader.rejected,1)

    def test_source_only_staging_and_unmodified_translated_cpp(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'source';out=Path(d)/'cache'
            rom=ROOT/'harness/examples/recomp-pcode/synthetic.sms'
            doc=json.loads((ROOT/'harness/examples/recomp-pcode/function-export.json').read_text())
            generate_project(doc,rom,p)
            translated=(p/'translated.cpp').read_bytes()
            staged,identity=stage(p,out)
            self.assertEqual((staged/'translated.cpp').read_bytes(),translated)
            self.assertEqual((p/'translated.cpp').read_bytes(),translated)
            self.assertIn(MARKER,(staged/'live_sms.hpp').read_text())
            self.assertNotIn(MARKER,(p/'live_sms.hpp').read_text())
            self.assertIn('rd_sms_memory_adapter::sample(state_.tstates,state_.frames,state_);',(staged/'live_sms.hpp').read_text())
            self.assertIn('rd_movement_trace::frame(state_.tstates,state_.frames,state_.vram,state_.vdp_regs);',(staged/'live_sms.hpp').read_text())
            self.assertEqual(stage(p,out)[1],identity)

    def test_transform_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'Unexpected'):
            live_transform('int main() { return 0; }')

if __name__=='__main__':unittest.main()
