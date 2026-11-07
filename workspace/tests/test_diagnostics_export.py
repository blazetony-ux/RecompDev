"""Diagnostic export security and source-integrity tests (no ROM upload)."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from workspace.diagnostics_export import archive_job

class DiagnosticsTests(unittest.TestCase):
    def test_redaction_bounded_schema_and_preserved_raw_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);job=root/'jobs'/'job-test-01';job.mkdir(parents=True)
            (job/'sessions'/'cycle-01').mkdir(parents=True)
            (job/'sessions'/'cycle-02').mkdir(parents=True)
            rom='C:\\Users\\owner\\ROMs\\Shinobi.sms';digest='d'*64
            attempts=[]
            for n in (1,2):
                sess=job/'sessions'/f'cycle-{n:02d}'
                attempts.append({'cycle':n,'frames':n*30,'emitted':n*50,'status':'MAX_RECOVERY_ROUNDS_REACHED','output':str(sess)})
                (sess/'orchestration.json').write_text(json.dumps({'schema':'recompdev.native.orchestrator.v1','source_sha256':digest,'rounds':[{'frames':n*30,'recovery_seed':rom}],'password':'super-secret'}))
                (sess/'round-01-observed-stop.json').write_text(json.dumps({'observed_pc':100,'physical_offset':100,'mapper':[0,0,1,2]}))
            (job/'job.json').write_text(json.dumps({'schema':'recompdev.controller.job.v1','id':job.name,'rom':rom,'rom_sha256':digest,'target_frames':1800,'status':'RECOVERY_LIMIT_REACHED','attempts':attempts,'auth_token':'NEVER_EXPORT'}))
            (job/'events.jsonl').write_text(json.dumps({'level':'warning','message':f'Blocker near {rom}'})+'\n')
            (job/'secret.sms').write_bytes(b'PRIVATE-ROM-DATA')
            source=(job/'job.json').read_bytes()
            result=archive_job(job,root/'diagnostics')
            with zipfile.ZipFile(result['path']) as z:
                assert z.testzip() is None
                self.assertNotIn('secret.sms',z.namelist())
                self.assertEqual(len([n for n in z.namelist() if n.endswith('/orchestration.json')]),2)
                self.assertEqual(len([n for n in z.namelist() if 'observed-stop.json' in n]),2)
                manifest=json.loads(z.read('manifest.json'))
                self.assertTrue(manifest['redacted'])
                self.assertFalse(manifest['original_rom_included'])
                self.assertEqual(manifest['source_sha256'],digest)
                for item in manifest['files']:
                    payload=z.read(item['path'])
                    self.assertEqual(len(payload),item['bytes'])
                    self.assertEqual(hashlib.sha256(payload).hexdigest(),item['sha256'])
                combined=b'\n'.join(z.read(n) for n in z.namelist())
                for forbidden in (b'PRIVATE-ROM-DATA',b'NEVER_EXPORT',b'super-secret',b'C:\\Users\\owner',b'Shinobi.sms'):
                    self.assertNotIn(forbidden,combined)
                self.assertIn(b'<local-path-redacted>',combined)
            self.assertEqual((job/'job.json').read_bytes(),source)
            again=archive_job(job,root/'diagnostics')
            self.assertEqual(again['sha256'],result['sha256'])

    def test_symlink_or_missing_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);job=root/'jobs'/'job-test-02';job.mkdir(parents=True)
            (job/'job.json').write_text(json.dumps({'schema':'recompdev.controller.job.v1','id':job.name,'attempts':[{'output':'C:\\foo','frames':3}]}))
            with self.assertRaises(ValueError):archive_job(job,root/'diagnostics')
            self.assertFalse(list((root/'diagnostics').glob('*.zip')))

if __name__=='__main__':unittest.main()
