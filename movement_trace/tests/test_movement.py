"""No ROM, translator mutation, or game-specific state assumptions."""
import csv
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from movement_trace.bridge import install,live_sms_transform,runtime_transform,MARKER
from movement_trace.analyze import analyze,write_report,HEADERS

LEGACY=ROOT/'legacy/RecompDev-v0.4.0.45'

class MovementTraceTests(unittest.TestCase):
    def test_staged_only_transformation_and_idempotence(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            (d/'translated.cpp').write_bytes(b'original CPU code\n')
            (d/'generation.json').write_text('{}')
            for src,dst in [('nativepilot/live_sms.hpp','live_sms.hpp'),
                            ('systems/mastersystem/runtime.cpp','runtime.cpp')]:
                shutil.copy2(LEGACY/src,d/dst)
            before={k:hashlib.sha256((d/k).read_bytes()).hexdigest() for k in ['live_sms.hpp','runtime.cpp','translated.cpp']}
            modified=install(d)
            self.assertIn('runtime.cpp',modified)
            self.assertIn('live_sms.hpp',modified)
            self.assertIn('hardware/rd_movement_trace.hpp',modified)
            self.assertIn('hardware/rd_state_observer.hpp',modified)
            self.assertIn('hardware/rd_sms_memory_adapter.hpp',modified)
            self.assertIn('rd_sms_memory_adapter::sample', (d/'live_sms.hpp').read_text())
            self.assertIn('state.ram.data()', (d/'hardware/rd_sms_memory_adapter.hpp').read_text())
            self.assertNotIn('state_.ram', (d/'hardware/rd_state_observer.hpp').read_text())
            self.assertEqual(before['translated.cpp'],hashlib.sha256((d/'translated.cpp').read_bytes()).hexdigest())
            self.assertEqual([],install(d))
            self.assertEqual(MARKER in (LEGACY/'nativepilot/live_sms.hpp').read_text(),False)
            self.assertEqual(MARKER in (LEGACY/'systems/mastersystem/runtime.cpp').read_text(),False)

    def test_fail_closed_on_unfamiliar_machine_anchors(self):
        with self.assertRaisesRegex(ValueError,'instrumentation refused'):
            live_sms_transform('other source')
        with self.assertRaisesRegex(ValueError,'instrumentation refused'):
            runtime_transform('other source')

    def test_correlates_input_port_scroll_and_raw_sat(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            def table(name,rows):
                with (d/name).open('w',newline='') as f:
                    wr=csv.writer(f);wr.writerow(HEADERS[name]);wr.writerows(rows)
            table('movement-controller.csv',[(0,0,255,255),(100,8,247,255), (300,4,251,255)])
            table('movement-port-reads.csv',[(101,1234,220,247),(103,1235,221,255),(302,1200,220,251)])
            table('movement-frames.csv',[(0,0,0,0,0,0,0,16128,0),
                (1,1,150,1,0,0,0,16128,1),(2,2,350,3,0,0,0,16128,1)])
            table('movement-sprites.csv',[(1,150,0,88,90,23,88,91), (2,350,0,86,90,23,86,91)])
            result=write_report(d)
            self.assertEqual('CONSISTENT_OBSERVED_MAPPING',result['trace_validity'])
            self.assertEqual(2,result['guest_controller_reads_dc'])
            self.assertEqual(2,result['scroll_register_change_frames'])
            self.assertEqual('INCONCLUSIVE_PLAYER_IDENTITY_AND_WORLD_COORDINATES_UNKNOWN',result['movement_assessment'])
            self.assertEqual(2,len(result['direction_segments']))
            self.assertTrue((d/'movement-diagnostics.json').is_file())

    def test_diagnostic_detects_controller_mapping_error(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            for name,rows in [('movement-controller.csv',[(0,8,251,255)]),
                              ('movement-port-reads.csv',[(0,200,220,251)]),
                              ('movement-frames.csv',[]),('movement-sprites.csv',[])]:
                with (d/name).open('w',newline='') as f:
                    wr=csv.writer(f);wr.writerow(HEADERS[name]);wr.writerows(rows)
            r=analyze(d)
            self.assertEqual('MAPPING_MISMATCH',r['trace_validity'])
            self.assertTrue(r['host_to_guest_controller_mismatches'])

    def test_diagnostic_fails_closed_on_missing_or_bad_trace(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'Missing movement trace'):analyze(Path(d))

if __name__=='__main__':unittest.main()
