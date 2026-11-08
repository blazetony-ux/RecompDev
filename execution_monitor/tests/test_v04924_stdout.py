"""Actual streamed terminal record validation independent of event sampling."""
import json
import tempfile
import unittest
from pathlib import Path
from execution_monitor.native_result import extract_terminal_result,NativeResultError,DIAGNOSTIC_LOG_BUDGET,HARD_LOG_BUDGET

GOOD={'schema':'recomp-continuous-native-v2','status':'FRAME_BUDGET_REACHED',
      'frames':2400,'guest_frames':2396,'native_steps':15645817,'pc':7037,'physical_offset':7037}

class TerminalRecord(unittest.TestCase):
    def check(self,data,code=0):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/'native-stdout.log';file.write_bytes(data)
            return extract_terminal_result(file,process_returncode=code)
    def record(self):return b'NATIVE_APP_RESULT='+json.dumps(GOOD).encode()+b'\n'
    def test_oversized_diagnostics_still_contains_valid_terminal_result(self):
        data=(b'DIAGNOSTIC_EVENT=large-but-separate\n'*19000)+self.record()
        self.assertGreater(len(data),DIAGNOSTIC_LOG_BUDGET)
        result,meta=self.check(data)
        self.assertEqual(result['frames'],2400)
        self.assertTrue(meta['native_stdout_over_diagnostic_budget'])
        self.assertEqual(meta['native_stdout_bytes'],len(data))
    def test_strict_negative_cases(self):
        cases=(b'stuff\n',self.record()*2,
               b'NATIVE_APP_RESULT={\"schema\":\"x\",\"schema\":\"x\"}\n',
               b'NATIVE_APP_RESULT=broken\n',
               b'NATIVE_APP_RESULT='+json.dumps({**GOOD,'frames':-1}).encode()+b'\n',
               b'NATIVE_APP_RESULT='+json.dumps({**GOOD,'frames':True}).encode()+b'\n',
               b'junk-prefix-'+self.record(),
               b'NATIVE_APP_RESULT='+b' '*(2*1024*1024)+b'\n')
        for entry in cases:
            with self.subTest(entry=entry[:50]),self.assertRaises(NativeResultError):self.check(entry)
    def test_hard_limit_and_nonzero_exit(self):
        with self.assertRaisesRegex(NativeResultError,'PROCESS_NOT_SUCCESSFUL'):
            self.check(self.record(),code=2)
        with self.assertRaisesRegex(NativeResultError,'HARD_LIMIT'):
            self.check(b'x'*(HARD_LOG_BUDGET+1))
    def test_does_not_edit_log(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'stdout';raw=b'notice\n'+self.record();p.write_bytes(raw)
            extract_terminal_result(p,process_returncode=0)
            self.assertEqual(p.read_bytes(),raw)

if __name__=='__main__':unittest.main()
