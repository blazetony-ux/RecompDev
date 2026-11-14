#!/usr/bin/env python3
"""Compiled-controller v36 contract across three independent ISA providers."""
from __future__ import annotations
import hashlib,json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

class Dispatch(unittest.TestCase):
    def test_three_isa_abstract_dispatch_and_unqualified_evidence(self):
        self.assertGreaterEqual(len(sys.argv),2,'Compiled controller path required')
        exe=Path(sys.argv[1])
        self.assertTrue(exe.is_file(),str(exe))
        with tempfile.TemporaryDirectory(prefix='rd-v36-controller-') as tmp:
            root=Path(tmp)
            sms=bytearray(b'\xff'*(0x4000*4));sms[0x7ff0:0x7ff8]=b'TMR SEGA'
            sms[0:3]=bytes.fromhex('c3 00 01')
            sms[0x38]=sms[0x66]=0xc9
            sms[0x100:0x104]=bytes.fromhex('21 20 01 e9')
            sms[0x120:0x122]=bytes.fromhex('18 fe')
            md=bytearray(0x1000);md[:4]=(0xfff000).to_bytes(4,'big')
            md[4:8]=(0x200).to_bytes(4,'big');md[0x100:0x104]=b'SEGA'
            md[0x200:0x208]=bytes.fromhex('41 f9 00 00 02 20 4e d0')
            md[0x220:0x224]=bytes.fromhex('60 fe 4e 71')
            psx=bytearray(0x900);psx[:8]=b'PS-X EXE'
            for off,value in ((0x10,0x80010000),(0x18,0x80010000),(0x1c,0x100)):
                psx[off:off+4]=value.to_bytes(4,'little')
            for off,value in ((0x800,0x3c088001),(0x804,0x35080020),(0x808,0x01000008),
                              (0x80c,0),(0x820,0x08004008),(0x824,0)):
                psx[off:off+4]=value.to_bytes(4,'little')
            for ix,(data,profile,target) in enumerate(((sms,'sega-master-system',0x120),
                              (md,'sega-mega-drive',0x220),(psx,'sony-psx-exe',0x80010020))):
                src=root/f'fixture{ix}.bin';src.write_bytes(data)
                out=root/f'output{ix}'
                run=subprocess.run([str(exe),'analyze','--rom',str(src),'--out',str(out),'--budget','2000'],
                                   capture_output=True,text=True,timeout=90)
                self.assertEqual(run.returncode,0,run.stdout+run.stderr)
                report=json.loads((out/'analysis.json').read_text())
                self.assertEqual(report['profile'],profile)
                self.assertEqual(report['source_sha256'],hashlib.sha256(data).hexdigest())
                self.assertEqual(report['release'],'workspace/'+json.loads((ROOT/'workspace'/'components.json').read_text())['workspace_release'])
                self.assertEqual(report['abstract_execution']['provider_abstract_state_abi'],2)
                self.assertGreaterEqual(report['abstract_execution']['resolved_indirect_sites'],1)
                self.assertFalse(report['launches_game'])
                self.assertFalse(report['native_compilation_performed'])
                self.assertFalse(report['whole_game_code_coverage_qualified'])
                instructions=json.loads((out/'instructions.json').read_text())
                self.assertIn(target,[i['pc'] for i in instructions])
            unknown=root/'unrecognised.bin';unknown.write_bytes(b'unsupported-input')
            run=subprocess.run([str(exe),'analyze','--rom',str(unknown),
                                '--out',str(root/'unknown'),'--budget','300'],
                               capture_output=True,text=True,timeout=30)
            self.assertEqual(run.returncode,2,run.stdout+run.stderr)
            report=json.loads((root/'unknown'/'analysis.json').read_text())
            self.assertEqual(report['status'],'UNSUPPORTED_FORMAT')

if __name__=='__main__':
    unittest.main(argv=[sys.argv[0]],verbosity=2)
