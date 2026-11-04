"""Required compiled native subset acceptance on a real C++17 compiler, both ISAs.
No game-specific code. Rejects missing compilation rather than silently skipping.
"""
import hashlib,json,struct,subprocess,tempfile,unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from multisa.native import generate,compile_project

class NativeMultiISATests(unittest.TestCase):
    def run_native(self,blob,isa,base,steps=40):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);p=d/'holdout.bin';p.write_bytes(blob)
            report=generate(p,d/'native',fmt='raw',isa=isa,endian='little' if isa=='mips' else 'big',base=base,entry=base,
                            expected_sha256=hashlib.sha256(blob).hexdigest(),require_supported=True)
            self.assertEqual(report['unsupported_boundaries'],[])
            self.assertTrue(report['translated_instructions'])
            exe=compile_project(d/'native')
            a=subprocess.run([str(exe),str(steps)],capture_output=True,text=True,timeout=35)
            self.assertEqual(a.returncode,0,a.stdout+a.stderr)
            b=subprocess.run([str(exe),str(steps)],capture_output=True,text=True,timeout=35)
            self.assertEqual(b.returncode,0,b.stderr)
            self.assertEqual(a.stdout,b.stdout)
            result=json.loads(a.stdout)
            self.assertEqual(result['isa'],isa)
            return result

    def test_m68k_compiled_register_math(self):
        b=bytes.fromhex('7003 5280 4e75')
        r=self.run_native(b,'m68k',0)
        self.assertEqual(r['steps'],3)
        self.assertEqual(r['registers'][0],4)
        self.assertEqual(r['stop'],'RETURNED_TO_HOST')

    def test_m68k_compiled_conditional_branch_and_call(self):
        # MOVEQ #0,D0; BEQ +4; MOVEQ #5,D0 (skipped); MOVEQ #9,D1; RTS
        b=bytes.fromhex('7000 6702 7005 7209 4e75')
        r=self.run_native(b,'m68k',0)
        self.assertEqual(r['registers'][0],0)
        self.assertEqual(r['registers'][1],9)
        self.assertEqual(r['steps'],4)

    def test_mips_compiled_branch_delay_slot(self):
        b=struct.pack('<9I',0x3c080001,0x35080020,0x24090003,0x01095021,
                      0x11290002,0x25290001,0x25080063,0x03e00008,0)
        r=self.run_native(b,'mips',0x10000)
        self.assertEqual(r['registers'][8],0x10020)
        self.assertEqual(r['registers'][9],4)
        self.assertEqual(r['registers'][10],0x10023)
        self.assertEqual(r['steps'],9)
        self.assertEqual(r['stop'],'UNMAPPED_TRANSLATED_PC')

    def test_mips_compiled_unseen_holdout_arithmetic(self):
        # Distinct unseen program using negative immediate, OR/AND and shift.
        b=struct.pack('<7I',0x2408ffff,0x310900ff,0x00095080,0x01285026,0x03e00008,0,0)
        r=self.run_native(b,'mips',0x2000)
        self.assertEqual(r['registers'][8],0xffffffff)
        self.assertEqual(r['registers'][9],255)
        self.assertEqual(r['registers'][10],0xffffffff^255)

    def test_unsupported_isa_encoding_does_not_compile_strict(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'src').write_bytes(bytes.fromhex('4e71 4afc'))
            with self.assertRaisesRegex(ValueError,'unsupported'):
                generate(p/'src',p/'generated',fmt='raw',isa='m68k',endian='big',base=0,entry=0,require_supported=True)
            r=generate(p/'src',p/'bounded',fmt='raw',isa='m68k',endian='big',base=0,entry=0)
            self.assertEqual(len(r['unsupported_boundaries']),1)
            exe=compile_project(p/'bounded')
            result=subprocess.run([str(exe),'20'],capture_output=True,text=True)
            self.assertEqual(result.returncode,3)
            self.assertEqual(json.loads(result.stdout)['stop'],'UNSUPPORTED_TRANSLATION')

    def test_source_and_generated_cpp_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);src=p/'rom';src.write_bytes(bytes.fromhex('7003 4e75'))
            with self.assertRaisesRegex(ValueError,'SHA-256'):
                generate(src,p/'wrong',fmt='raw',isa='m68k',endian='big',base=0,entry=0,expected_sha256='0'*64)
            generate(src,p/'out',fmt='raw',isa='m68k',endian='big',base=0,entry=0)
            with (p/'out'/'translated.cpp').open('a') as fp:fp.write('// altered\n')
            with self.assertRaisesRegex(ValueError,'changed after'):
                compile_project(p/'out')

if __name__=='__main__':unittest.main()
