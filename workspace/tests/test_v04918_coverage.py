"""Verified compact coverage-delta and frontier diagnostics tests."""
from __future__ import annotations
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from workspace.diagnostics_export import archive_job

class CoverageTests(unittest.TestCase):
    def test_real_manifest_delta_and_previous_stop_are_address_only(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);job=root/'jobs'/'job-coverage-01';job.mkdir(parents=True)
            sha='f'*64;attempts=[]
            for i in (1,2):
                sess=job/'sessions'/f'cycle-{i:02d}';(sess/'round-01').mkdir(parents=True)
                attempts.append({'cycle':i,'output':str(sess),'frames':896,'emitted':i+1})
                report={'schema':'recompdev.native.orchestrator.v1','source_sha256':sha,
                        'analysis':{'cache_reuse':'SOURCE_TOOL_PROVIDER_ATTESTED' if i==2 else 'NEW_ANALYSIS'},
                        'rounds':[{'round':1,'status':'UNTRANSLATED_BANKED_CODE','frames':896,
                                   'pc':0x8001,'physical_offset':0x18001,'mapper':[0,0,1,6]}]}
                (sess/'orchestration.json').write_text(json.dumps(report))
                instructions=[{'physical':0x18000,'pc':0x8000,'length':1}]
                if i==2:instructions.append({'physical':0x18001,'pc':0x8001,'length':1})
                (sess/'round-01/translation-manifest.json').write_text(json.dumps({
                    'schema':'recompdev.native.pcode.generated.v1','source_sha256':sha,
                    'accepted_instructions':instructions,'emitted':len(instructions)}))
            (job/'job.json').write_text(json.dumps({'schema':'recompdev.controller.job.v1',
                'id':job.name,'status':'RECOVERY_LIMIT_REACHED','rom_sha256':sha,'target_frames':1800,
                'attempts':attempts}))
            result=archive_job(job,root/'v0.4.9.18'/'diagnostics')
            with ZipFile(result['path']) as z:
                doc=json.loads(z.read('coverage-diff.json'))
                self.assertEqual([s['new_count'] for s in doc['sessions']],[1,1])
                self.assertEqual(doc['sessions'][1]['new_addresses'],[{'physical':0x18001,'pc':0x8001,'length':1}])
                self.assertTrue(doc['sessions'][1]['frontiers'][0]['in_translation_manifest'])
                self.assertEqual(doc['sessions'][1]['analysis_reuse'],'SOURCE_TOOL_PROVIDER_ATTESTED')
                self.assertNotIn('translation-manifest.json',z.namelist())
                for entry in json.loads(z.read('manifest.json'))['files']:
                    self.assertEqual(hashlib.sha256(z.read(entry['path'])).hexdigest(),entry['sha256'])

    def test_refuses_mismatched_translation_source(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);job=root/'jobs'/'job-coverage-02';sess=job/'sessions'/'cycle-01'
            (sess/'round-01').mkdir(parents=True)
            (job/'job.json').write_text(json.dumps({'schema':'recompdev.controller.job.v1','id':job.name,
                'status':'BLOCKED','rom_sha256':'a'*64,'attempts':[{'output':str(sess)}]}))
            (sess/'orchestration.json').write_text(json.dumps({'schema':'recompdev.native.orchestrator.v1',
                'source_sha256':'a'*64,'rounds':[]}))
            (sess/'round-01/translation-manifest.json').write_text(json.dumps({'schema':'recompdev.native.pcode.generated.v1',
                'source_sha256':'b'*64,'emitted':0,'accepted_instructions':[]}))
            with self.assertRaisesRegex(ValueError,'source/schema mismatch'):
                archive_job(job,root/'diagnostics')
            self.assertFalse(list((root/'diagnostics').glob('*.zip')))

if __name__=='__main__':unittest.main()
