#!/usr/bin/env python3
"""Compiled-controller neutral native handoff, one owner route for CPU plugins."""
import hashlib,json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

class ControllerHandoff(unittest.TestCase):
    def test_controller_routes_attested_handoff_without_gameplay(self):
        exe=Path(sys.argv[1]);self.assertTrue(exe.is_file())
        with tempfile.TemporaryDirectory(prefix='rd-v37-compiled-') as temp:
            root=Path(temp)
            data=bytearray(b'\xff'*(4*0x4000))
            data[0x7ff0:0x7ff8]=b'TMR SEGA';data[0:3]=bytes.fromhex('c3 00 01')
            data[0x38]=data[0x66]=0xc9
            data[0x100:0x103]=bytes.fromhex('00 18 fd')
            rom=root/'fixture.bin';rom.write_bytes(data)
            analysis=root/'analysis';native=root/'native'
            a=subprocess.run([str(exe),'analyze','--rom',str(rom),'--out',str(analysis)],
                             capture_output=True,text=True,timeout=60)
            self.assertEqual(a.returncode,0,a.stdout+a.stderr)
            receipt=json.loads((analysis/'analysis.json').read_text())
            self.assertEqual(receipt['source_sha256'],hashlib.sha256(data).hexdigest())
            self.assertFalse(receipt['launches_game'])
            self.assertTrue(receipt['release'].endswith('0.4.9.37'))
            b=subprocess.run([str(exe),'analyze-native','--rom',str(rom),'--analysis',str(analysis),
                              '--out',str(native),'--rights-confirmed'],
                             capture_output=True,text=True,timeout=60)
            self.assertEqual(b.returncode,0,b.stdout+b.stderr)
            self.assertIn('RECOMPDEV_OFFLINE_NATIVE_HANDOFF=',b.stdout)
            nr=json.loads((native/'native-probe.json').read_text())
            self.assertEqual(nr['schema'],'recompdev.offline.native-probe.v1')
            self.assertFalse(nr['native_execution_parity'])
            self.assertGreaterEqual(nr['lifted_instructions'],3)
            self.assertTrue((native/'native_probe.cpp').is_file())
            self.assertTrue((native/'CMakeLists.txt').is_file())
            denied=subprocess.run([str(exe),'analyze-native','--rom',str(rom),'--analysis',str(analysis),
                                   '--out',str(root/'not-approved')],capture_output=True,text=True,timeout=60)
            self.assertEqual(denied.returncode,2,denied.stdout+denied.stderr)
            self.assertIn('RIGHTS_CONFIRMATION_REQUIRED',denied.stderr)
if __name__=='__main__':unittest.main(argv=[sys.argv[0]],verbosity=2)
