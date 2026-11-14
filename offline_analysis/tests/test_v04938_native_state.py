#!/usr/bin/env python3
"""Compile and execute limited, source-attested register operations on two ISAs.

Proof is not a CPU emulator, game exporter, interrupt machine, or parity gate.
"""
from __future__ import annotations
import hashlib,json,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from offline_analysis.engine import interrogate,AnalysisFailure
from offline_analysis.native_probe import prepare

class NativeStateProbe(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory(prefix='rd-v38-native-')
        self.addCleanup(folder.cleanup)
        self.root=Path(folder.name)
    def source(self,kind):
        if kind=='z80':
            code=bytearray(b'\xff'*(4*0x4000))
            code[:3]=bytes.fromhex('c3 00 01')
            code[0x38]=code[0x66]=0xc9
            code[0x7ff0:0x7ff8]=b'TMR SEGA'
            code[0x100:0x105]=bytes.fromhex('3e 05 3c 18 fd')
        elif kind=='m68k':
            code=bytearray(0x1000)
            code[:4]=(0xfff000).to_bytes(4,'big')
            code[4:8]=(0x200).to_bytes(4,'big')
            code[0x100:0x104]=b'SEGA'
            code[0x200:0x206]=bytes.fromhex('70 05 52 80 60 fc')
        else:raise ValueError(kind)
        source=self.root/(kind+'.bin');source.write_bytes(code)
        analysis=self.root/('report-'+kind)
        result=interrogate(source,analysis,budget=4000)
        self.assertIn(result['status'],('ANALYSED_PARTIAL','ANALYSED_STATIC_CANDIDATES'))
        return source,analysis
    def build(self,tree):
        if not shutil.which('cmake'):
            self.skipTest('Native compiler unavailable')
        build=tree/'build'
        cmd=['cmake','-S',str(tree),'-B',str(build)]
        result=subprocess.run(cmd,capture_output=True,text=True,timeout=90)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        result=subprocess.run(['cmake','--build',str(build),'--config','Release'],capture_output=True,text=True,timeout=90)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        exe=build/('Release/RecompDevOfflineNativeProbe.exe' if sys.platform=='win32' else 'RecompDevOfflineNativeProbe')
        self.assertTrue(exe.exists())
        result=subprocess.run([str(exe),'25'],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        line=next(x for x in result.stdout.splitlines() if x.startswith('RECOMPDEV_OFFLINE_NATIVE_PROBE='))
        value=json.loads(line.split('=',1)[1])
        self.assertEqual(value['native_steps'],25)
        self.assertEqual(value['status'],'STEP_BUDGET_REACHED')
        return value
    def test_z80_attested_native_register_arithmetic(self):
        src,analysis=self.source('z80')
        tree=self.root/'native-z80'
        manifest=prepare(src,analysis,tree,rights_confirmed=True)
        self.assertEqual(manifest['tracked_registers'],['A'])
        self.assertGreaterEqual(manifest['state_operations_lifted'],2)
        self.assertFalse(manifest['full_cpu_semantics'])
        self.assertFalse(manifest['external_game_data_embedded'])
        src.unlink()
        result=self.build(tree)
        self.assertEqual(result['registers']['A'],17)
    def test_m68k_attested_native_register_arithmetic(self):
        src,analysis=self.source('m68k')
        tree=self.root/'native-m68k'
        manifest=prepare(src,analysis,tree,rights_confirmed=True)
        self.assertEqual(manifest['tracked_registers'],['D0'])
        self.assertGreaterEqual(manifest['state_operations_lifted'],2)
        src.unlink()
        result=self.build(tree)
        self.assertEqual(result['registers']['D0'],17)
    def test_lifter_must_not_accept_unqualified_opcode(self):
        from offline_analysis.plugins import cpu_z80,cpu_m68k
        self.assertIsNone(cpu_z80.lift_probe(b'\xed\x56',0))
        self.assertIsNone(cpu_m68k.lift_probe(b'\x4e\x75',0))
        self.assertIsNone(cpu_z80.lift_probe(b'\xdb\xbf',0))
    def test_binary_source_tamper_blocks_native_handoff(self):
        src,analysis=self.source('m68k')
        data=bytearray(src.read_bytes());data[0x201]^=1;src.write_bytes(data)
        with self.assertRaisesRegex(AnalysisFailure,'ATTESTATION_FAILED'):
            prepare(src,analysis,self.root/'must-not-exist',rights_confirmed=True)
        self.assertFalse((self.root/'must-not-exist').exists())

if __name__=='__main__':unittest.main(verbosity=2)
