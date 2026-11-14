#!/usr/bin/env python3
"""Cross-platform compiled RecompDev.exe dispatch for three genuine ISA fixtures."""
from pathlib import Path
import json,subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from offline_analysis.tests.test_v04935_offline import Fixture

class CompiledDispatch(unittest.TestCase):
    def test_controller_recognises_three_isa_images_using_same_command(self):
        exe=Path(sys.argv[1]).resolve(strict=True)
        with tempfile.TemporaryDirectory(prefix='rd-v35-cli-') as folder:
            home=Path(folder)
            mock=Fixture();mock.setUp();self.addCleanup(mock.doCleanups)
            try:
                for i,(name,data,profile) in enumerate((
                    ('synthetic.sms',mock.sms(),'sega-master-system'),
                    ('synthetic.md',mock.md(),'sega-mega-drive'),
                    ('synthetic.exe',mock.psx(),'sony-psx-exe'))):
                    src=home/name;src.write_bytes(data)
                    out=home/(f'out{i}')
                    run=subprocess.run([str(exe),'analyze','--rom',str(src),'--out',str(out),'--budget','2000'],
                                       capture_output=True,text=True,timeout=60)
                    self.assertEqual(run.returncode,0,run.stdout+run.stderr)
                    report=json.loads((out/'analysis.json').read_text(encoding='utf8'))
                    self.assertEqual(report['profile'],profile)
                    self.assertFalse(report['launches_game'])
                    self.assertFalse(report['standalone_export_ready'])
                    self.assertGreater(report['decoded_candidates'],0)
                # A nonrecognised source must still yield a typed, verifiable report.
                bad=home/'unrecognised.rom';bad.write_bytes(b'not an executable format')
                bad_out=home/'unknown_report'
                run=subprocess.run([str(exe),'analyze','--rom',str(bad),'--out',str(bad_out)],
                                   capture_output=True,text=True,timeout=60)
                self.assertEqual(run.returncode,2,run.stdout+run.stderr)
                self.assertEqual(json.loads((bad_out/'analysis.json').read_text())['status'],'UNSUPPORTED_FORMAT')
                # Native discovery receipts must derive their release from the
                # compiled authoritative registry, not a stale v0.4.9.11 string.
                src=home/'fixture.sms';src.write_bytes(mock.sms())
                native_out=home/'native_receipt'
                cmd=[str(exe),'--stage','discover','--rom',str(src),
                     '--plugin-dir',str(exe.parent),'--out',str(native_out),'--budget','300']
                native=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
                self.assertEqual(native.returncode,0,native.stdout+native.stderr)
                native_report=json.loads((native_out/'native-discovery.json').read_text())
                reg=json.loads((ROOT/'workspace'/'components.json').read_text())['workspace_release']
                self.assertEqual(native_report['workspace_release'],'workspace/'+reg)
                self.assertEqual(native_report['controller_version'],reg[1:])
            finally:pass

if __name__=='__main__':
    unittest.main(argv=[sys.argv[0]],verbosity=2)
