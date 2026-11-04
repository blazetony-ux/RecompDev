"""Regression gates: automatic, safe, non-destructive upload bundles."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from modular.evidence_bundle import create_evidence_bundle

COMPILED_EXE = Path(sys.argv[1]).resolve() if len(sys.argv)>1 else None

class TestEvidenceBundle(unittest.TestCase):
    def test_artifacts_manifest_and_exclusions(self):
        with tempfile.TemporaryDirectory(prefix='RecompDev bundle spaces ') as temp:
            root=Path(temp)/'run has spaces'
            (root/'recovery/native-project/build').mkdir(parents=True)
            (root/'recovery/sessions/attempt-01').mkdir(parents=True)
            (root/'controller-report.json').write_text('{"status":"RECOVERY_BLOCKED"}')
            (root/'recovery/native-project/build/translated.obj').write_bytes(b'x'*200)
            (root/'a-game.sms').write_bytes(b'ROM')
            (root/'other.bin').write_bytes(b'ROM?')
            (root/'recovery/sessions/attempt-01/native-frame.ppm').write_bytes(b'P6\n1 1\n255\n\xff\x00\x00')
            (root/'recovery/sessions/attempt-01/native-frame.wav').write_bytes(b'WAVE')
            (root/'working-catalogue.sqlite').write_bytes(b'sqlite fixture bytes')
            (root/'recovery/diagnostic.log').write_text('a diagnostic')
            result=create_evidence_bundle(root,source_sha256='a'*64,status='RECOVERY_LIMITED_OR_BLOCKED')
            self.assertEqual(result['status'],'READY')
            self.assertTrue(result['source_image_included'] is False)
            archive=Path(result['path'])
            self.assertEqual(archive.parent, root.parent)
            with zipfile.ZipFile(archive) as z:
                names=z.namelist()
                self.assertIn('evidence/controller-report.json',names)
                self.assertIn('evidence/working-catalogue.sqlite',names)
                self.assertIn('evidence/recovery/sessions/attempt-01/native-frame.ppm',names)
                self.assertIn('evidence/recovery/sessions/attempt-01/native-frame.wav',names)
                self.assertNotIn('evidence/a-game.sms',names)
                self.assertNotIn('evidence/other.bin',names)
                self.assertFalse(any('native-project' in x for x in names))
                manifest=json.loads(z.read('bundle-manifest.json'))
                self.assertEqual(manifest['workflow_status'],'RECOVERY_LIMITED_OR_BLOCKED')
                self.assertEqual(manifest['source_sha256'],'a'*64)
                for row in manifest['files']:
                    self.assertEqual(hashlib.sha256(z.read(row['path'])).hexdigest(),row['sha256'])
            self.assertTrue((root/'recovery/native-project/build/translated.obj').is_file())
            with self.assertRaises(FileExistsError):create_evidence_bundle(root)

    def test_blocked_workflow_still_packages(self):
        with tempfile.TemporaryDirectory(prefix='RecompDev blocked run ') as temp:
            p=Path(temp)/'stage'
            p.mkdir()
            (p/'controller-report.json').write_text('{"status":"RECOVERY_LIMITED_OR_BLOCKED"}')
            result=create_evidence_bundle(p,status='RECOVERY_LIMITED_OR_BLOCKED')
            self.assertEqual(result['status'],'READY')

    def test_compiled_cli_generates_bundle(self):
        if COMPILED_EXE is None:return
        exe=COMPILED_EXE.resolve(strict=True)
        with tempfile.TemporaryDirectory(prefix='RecompDev compiled upload ') as temp:
            tmp=Path(temp)
            out=tmp/'evidence with spaces'
            rom=tmp/'toy.sms'
            shutil.copyfile(ROOT/'harness/examples/recomp-pcode/synthetic.sms',rom)
            db=ROOT/'legacy/RecompDev-v0.4.0.45/catalogue.sqlite'
            proc=subprocess.run([str(exe),'--rom',str(rom),'--stage','discover',
                 '--catalogue',str(db),'--out',str(out),'--budget','5','--timeout','120'],
                 text=True,capture_output=True,timeout=120)
            self.assertEqual(proc.returncode,0,(proc.stderr[-1000:],proc.stdout[-1000:]))
            doc=json.loads(proc.stdout)
            self.assertEqual(doc['evidence_bundle']['status'],'READY')
            self.assertIn('RECOMPDEV_EVIDENCE_ZIP=',proc.stderr)
            with zipfile.ZipFile(doc['evidence_bundle']['path']) as z:
                self.assertIn('evidence/controller-report.json',z.namelist())
                self.assertNotIn('evidence/toy.sms',z.namelist())
            self.assertTrue(rom.is_file())

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(TestEvidenceBundle)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
