#!/usr/bin/env python3
"""Compiled hardware-neutral controller dispatch to new source-attested state probes."""
from __future__ import annotations
import hashlib,json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

class CompiledDispatch(unittest.TestCase):
    def test_generic_controller_uses_pluggable_state_lifters(self):
        exe=Path(sys.argv[1]);self.assertTrue(exe.exists())
        release='workspace/'+json.loads((ROOT/'workspace/components.json').read_text())['workspace_release']
        with tempfile.TemporaryDirectory(prefix='rd-v38-compiled-') as folder:
            home=Path(folder)
            z=bytearray(b'\xff'*(4*0x4000));z[:3]=bytes.fromhex('c3 00 01')
            z[0x38]=z[0x66]=0xc9;z[0x7ff0:0x7ff8]=b'TMR SEGA'
            z[0x100:0x105]=bytes.fromhex('3e 05 3c 18 fd')
            m=bytearray(0x1000);m[:4]=(0xfff000).to_bytes(4,'big')
            m[4:8]=(0x200).to_bytes(4,'big');m[0x100:0x104]=b'SEGA'
            m[0x200:0x206]=bytes.fromhex('70 05 52 80 60 fc')
            for tag,data,reg,profile in (('sms',z,'A','sega-master-system'),
                                         ('md',m,'D0','sega-mega-drive')):
                src=home/(tag+'.bin');src.write_bytes(data)
                report=home/(tag+'-analysis');native=home/(tag+'-native')
                a=subprocess.run([str(exe),'analyze','--rom',str(src),'--out',str(report)],
                                 capture_output=True,text=True,timeout=60)
                self.assertEqual(a.returncode,0,a.stdout+a.stderr)
                receipt=json.loads((report/'analysis.json').read_text())
                self.assertEqual(receipt['release'],release)
                self.assertEqual(receipt['profile'],profile)
                self.assertEqual(receipt['source_sha256'],hashlib.sha256(data).hexdigest())
                self.assertFalse(receipt['launches_game'])
                b=subprocess.run([str(exe),'analyze-native','--rom',str(src),
                                  '--analysis',str(report),'--out',str(native),
                                  '--rights-confirmed'],capture_output=True,text=True,timeout=60)
                self.assertEqual(b.returncode,0,b.stdout+b.stderr)
                proof=json.loads((native/'native-probe.json').read_text())
                self.assertIn(reg,proof['tracked_registers'])
                self.assertGreaterEqual(proof['state_operations_lifted'],2)
                self.assertFalse(proof['full_cpu_semantics'])
                self.assertFalse(proof['native_execution_parity'])
                self.assertFalse(proof['external_game_data_embedded'])
                self.assertTrue((native/'native_probe.cpp').is_file())
                self.assertTrue((native/'CMakeLists.txt').is_file())

if __name__=='__main__':unittest.main(argv=[sys.argv[0]],verbosity=2)
