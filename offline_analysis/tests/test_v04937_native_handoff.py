#!/usr/bin/env python3
"""Real compiler proof, two independently authored CPU bytecode fixtures.

This is NOT game parity, CPU completeness, full ROM recovery or a hardware
runtime; failure on unsupported/attestation changes is expected and required.
"""
import hashlib,json,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from offline_analysis.engine import interrogate,AnalysisFailure
from offline_analysis.native_probe import prepare

class NativeProbe(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='rd-v37-native-')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
    def fixture(self,kind='z80'):
        if kind=='z80':
            a=bytearray(b'\xff'*(0x4000*4));a[:3]=bytes.fromhex('c3 00 01')
            a[0x7ff0:0x7ff8]=b'TMR SEGA';a[0x38]=a[0x66]=0xc9
            a[0x100:0x103]=bytes.fromhex('00 18 fd')
        elif kind=='m68k':
            a=bytearray(0x1000);a[:4]=(0xfff000).to_bytes(4,'big')
            a[4:8]=(0x200).to_bytes(4,'big');a[0x100:0x104]=b'SEGA'
            a[0x200:0x204]=bytes.fromhex('4e 71 60 fc')
        else:raise ValueError(kind)
        source=self.root/(kind+'.bin');source.write_bytes(a)
        out=self.root/('analysis-'+kind)
        receipt=interrogate(source,out,budget=2000)
        return source,out,receipt
    def compiled(self,tree):
        if shutil.which('cmake') is None:self.skipTest('CMake is required')
        build=tree/'build'
        run=subprocess.run(['cmake','-S',str(tree),'-B',str(build)],capture_output=True,text=True,timeout=90)
        self.assertEqual(run.returncode,0,run.stderr)
        run=subprocess.run(['cmake','--build',str(build),'--config','Release'],capture_output=True,text=True,timeout=90)
        self.assertEqual(run.returncode,0,run.stderr)
        exe=(build/'Release'/'RecompDevOfflineNativeProbe.exe') if sys.platform=='win32' else build/'RecompDevOfflineNativeProbe'
        self.assertTrue(exe.is_file(),str(build))
        run=subprocess.run([str(exe),'25'],capture_output=True,text=True,timeout=30)
        self.assertEqual(run.returncode,0,run.stderr+run.stdout)
        line=next((line for line in run.stdout.splitlines() if line.startswith('RECOMPDEV_OFFLINE_NATIVE_PROBE=')),None)
        self.assertIsNotNone(line,run.stdout)
        result=json.loads(line.split('=',1)[1])
        self.assertEqual(result['native_steps'],25)
        self.assertEqual(result['status'],'STEP_BUDGET_REACHED')
    def test_z80_native_compilation_execution_without_source_image(self):
        src,analysis,r=self.fixture('z80')
        tree=self.root/'native-z80'
        receipt=prepare(src,analysis,tree,rights_confirmed=True)
        self.assertEqual(receipt['lifted_instructions'],3)
        self.assertFalse(receipt['full_cpu_semantics'])
        self.assertFalse(receipt['gameplay_qualified'])
        self.assertFalse(receipt['external_game_data_embedded'])
        src.unlink()  # execution must not need original binary
        self.compiled(tree)
    def test_m68000_native_compilation_execution_without_source_image(self):
        src,analysis,r=self.fixture('m68k')
        tree=self.root/'native-m68k'
        receipt=prepare(src,analysis,tree,rights_confirmed=True)
        self.assertEqual(receipt['cpu'],'m68000')
        src.unlink()
        self.compiled(tree)
    def test_rights_and_source_hash_required(self):
        src,analysis,r=self.fixture('z80')
        with self.assertRaisesRegex(AnalysisFailure,'RIGHTS_CONFIRMATION'):
            prepare(src,analysis,self.root/'no-rights')
        src.write_bytes(src.read_bytes()+b'wrong')
        with self.assertRaisesRegex(AnalysisFailure,'ATTESTATION_FAILED'):
            prepare(src,analysis,self.root/'tamper',rights_confirmed=True)
        self.assertFalse((self.root/'tamper').exists())
    def test_speculative_only_source_will_not_lift(self):
        src,analysis,r=self.fixture('z80')
        ins=analysis/'instructions.json'
        rows=json.loads(ins.read_text())
        for row in rows:row['classification']='SPECULATIVE_CALL_CONTINUATION_NOT_REACHABILITY_PROOF'
        raw=(json.dumps(rows,sort_keys=True,indent=2,ensure_ascii=False)+'\n').encode()
        ins.write_bytes(raw)
        report=json.loads((analysis/'analysis.json').read_text())
        report['artifacts']['instructions.json']['bytes']=len(raw)
        report['artifacts']['instructions.json']['sha256']=hashlib.sha256(raw).hexdigest()
        (analysis/'analysis.json').write_text(json.dumps(report))
        with self.assertRaisesRegex(AnalysisFailure,'NO_SUPPORTED_NON_SPECULATIVE'):
            prepare(src,analysis,self.root/'spec-only',rights_confirmed=True)
    def test_source_candidate_bytes_cannot_be_tampered(self):
        src,analysis,r=self.fixture('z80')
        rows=json.loads((analysis/'instructions.json').read_text())
        rows[0]['bytes_sha256']='0'*64
        raw=(json.dumps(rows,sort_keys=True,indent=2)+'\n').encode()
        (analysis/'instructions.json').write_bytes(raw)
        report=json.loads((analysis/'analysis.json').read_text())
        report['artifacts']['instructions.json']['sha256']=hashlib.sha256(raw).hexdigest()
        report['artifacts']['instructions.json']['bytes']=len(raw)
        (analysis/'analysis.json').write_text(json.dumps(report))
        with self.assertRaisesRegex(AnalysisFailure,'INSTRUCTION_HASH_MISMATCH'):
            prepare(src,analysis,self.root/'tampered',rights_confirmed=True)

if __name__=='__main__':unittest.main(verbosity=2)
