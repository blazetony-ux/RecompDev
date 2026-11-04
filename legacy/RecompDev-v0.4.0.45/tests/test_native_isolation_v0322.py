"""Parent survival tests use artificial subprocess exits, not CPU parity."""
import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from recovery.native_workers import run_isolated
from recovery.pipeline import check_pypcode
from recovery.autopilot import autopilot

class WorkerSurvival(unittest.TestCase):
    def test_fast_fail_exit_classified(self):
        from types import SimpleNamespace
        with patch('recovery.native_workers.subprocess.run',return_value=SimpleNamespace(
                 returncode=-1073740791,stdout='',stderr='')):
            x=run_isolated('pypcode',{})
        self.assertEqual(x['status'],'NATIVE_WORKER_CRASH_OR_ERROR')
        self.assertEqual(x['exit_hex'],'0xC0000409')
    def test_nonzero_child_exit_does_not_kill_parent(self):
        x=run_isolated('pypcode',{},argv=[sys.executable,'-c','import os;os._exit(23)'])
        self.assertEqual(x['status'],'NATIVE_WORKER_CRASH_OR_ERROR')
        self.assertEqual(x['exit_hex'],'0x00000017')
    def test_valid_child_output(self):
        x=run_isolated('pypcode',{},argv=[sys.executable,'-c',
                          'import json,sys;json.loads(sys.stdin.read());print(json.dumps({"status":"TEST_PASS"}))'])
        self.assertEqual(x['status'],'TEST_PASS')
    def test_invalid_output_not_misreported_as_success(self):
        x=run_isolated('unicorn',{},argv=[sys.executable,'-c','print("not json")'])
        self.assertEqual(x['status'],'NATIVE_WORKER_INVALID_OUTPUT')
    def test_pypcode_crash_is_advisory_not_parity(self):
        class Img:
            data=bytes.fromhex('7005')
            def offset(self,x):return 0
        f={'instructions':[{'address':0x200,'length':2}]}
        with patch('recovery.native_workers.run_isolated',return_value={
            'status':'NATIVE_WORKER_CRASH_OR_ERROR','exit_hex':'0xC0000409'}):
            self.assertEqual(check_pypcode(f,Img(),'68000:BE:32:default',True),
                             'PYPCODE_WORKER_FAILED_0xC0000409')
    def test_no_targets_has_checkpoint_and_report(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);db=p/'db.sqlite';con=sqlite3.connect(db)
            con.executescript('CREATE TABLE targets(target_id TEXT PRIMARY KEY,system_tag TEXT,isa TEXT,source_sha256 TEXT);')
            con.execute('INSERT INTO targets VALUES(?,?,?,?)',('fixture','megadrive','m68k','1'*64))
            con.commit();con.close()
            summary=autopilot(db,[],[],None,p/'output',limit=1,compare_samples=True,pypcode_check=True)
            self.assertEqual(summary['successes'],[])
            checkpoint=json.loads((p/'output'/'last-stage.json').read_text())
            self.assertEqual(checkpoint['stage'],'complete')
            self.assertTrue((p/'output'/'autopilot-report.json').is_file())
            self.assertEqual(summary['issues'][0]['status'],'AUTHENTICATED_SOURCE_NOT_FOUND')
if __name__=='__main__':unittest.main()
