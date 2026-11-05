"""Regressions for input replay, identity pinning, and immutable guest code."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'legacy/RecompDev-v0.4.0.45')]
from input_recovery.replay import HEADER,create_replay,validate_replay
from input_recovery.run import reproduce,select_project,matching_native_report
from runtime_host.bridge import install
from runtime_host.launch import stage
from nativepilot.generator import generate_project

ROM=ROOT/'harness/examples/recomp-pcode/synthetic.sms'
EXPORT=ROOT/'harness/examples/recomp-pcode/function-export.json'
HASH=hashlib.sha256(ROM.read_bytes()).hexdigest()

class InputRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='rd-input-recovery-')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def fixture_zip(self,*,exact=None,wrong_rom=False):
        path=self.root/'input-evidence.zip'
        report={'source_rom_sha256':'0'*64 if wrong_rom else HASH,
                'guest_status':'UNTRANSLATED_INITIAL_CODE','frames_observed':201,
                'original_project':str(self.root/'native-project')}
        items={
            'evidence/runtime-host-report.json':json.dumps(report).encode(),
            'evidence/native-stdout.log':b'NATIVE_APP_RESULT={"pc":31720,"physical_offset":31720,"guest_cycles":11994305}\n',
            'evidence/input-events.jsonl':b'{"elapsed_ms":2152,"buttons":16}\n{"elapsed_ms":2247,"buttons":0}\n',
        }
        if exact is not None:items['evidence/guest-input-cycles.csv']=exact.encode()
        with zipfile.ZipFile(path,'w') as z:
            for name,data in items.items():z.writestr(name,data)
            z.writestr('bundle-manifest.json',json.dumps({'files':[
                {'path':name,'sha256':hashlib.sha256(data).hexdigest()}
                for name,data in items.items()]}))
        return path

    def test_legacy_events_annotated_estimated_and_preserved(self):
        source=self.fixture_zip()
        dest=self.root/'replay.csv'
        result=create_replay(source,HASH,dest,guest_hz=3579545)
        self.assertEqual(result['method'],'HOST_MILLISECONDS_ESTIMATED')
        self.assertFalse(result['exact_replay_guarantee'])
        self.assertEqual(result['prior_pc'],0x7be8)
        self.assertEqual(result['prior_frames'],201)
        self.assertEqual(validate_replay(dest)['active_events'],1)
        self.assertIn('7703',dest.read_text())
        with self.assertRaises(FileExistsError):create_replay(source,HASH,dest,guest_hz=3579545)

    def test_exact_guest_cycles_prefer_wall_time_and_need_no_hz(self):
        exact=HEADER+'\n0,0,0\n7712304,0,16\n8014304,0,0\n'
        source=self.fixture_zip(exact=exact)
        result=create_replay(source,HASH,self.root/'out.csv')
        self.assertEqual(result['method'],'GUEST_CYCLES_EXACT')
        self.assertEqual((self.root/'out.csv').read_text(),exact)
        self.assertTrue(result['exact_replay_guarantee'])

    def test_wrong_rom_fails_closed(self):
        source=self.fixture_zip(wrong_rom=True)
        with self.assertRaisesRegex(ValueError,'ROM_IDENTITY_MISMATCH'):
            create_replay(source,HASH,self.root/'out.csv',guest_hz=3579545)

    def test_manifests_reject_tampered_input_evidence(self):
        src=self.fixture_zip()
        tampered=self.root/'tampered.zip'
        with zipfile.ZipFile(src) as inp,zipfile.ZipFile(tampered,'w') as out:
            for name in inp.namelist():
                data=inp.read(name)
                if name=='evidence/input-events.jsonl':data=data.replace(b'"buttons":16',b'"buttons":32')
                out.writestr(name,data)
        with self.assertRaisesRegex(ValueError,'Evidence manifest checksum mismatch'):
            create_replay(tampered,HASH,self.root/'tampered-replay.csv',guest_hz=3579545)

    def test_invalid_input_and_mismatched_replay_stop_rejected(self):
        p=self.root/'invalid.csv';p.write_text(HEADER+'\n2,0,16\n1,0,0\n')
        with self.assertRaisesRegex(ValueError,'INPUT_REPLAY_OUT_OF_RANGE'):validate_replay(p)
        prior={'prior_status':'UNTRANSLATED_INITIAL_CODE','prior_pc':0x7be8,'prior_frames':201,'method':'HOST_MILLISECONDS_ESTIMATED'}
        good={'guest_status':'UNTRANSLATED_INITIAL_CODE','guest_stop_pc':0x7be8,'frames_observed':201}
        bad={**good,'guest_stop_pc':0x56c7,'frames_observed':198}
        self.assertEqual(reproduce(prior,good)['status'],'STOP_REPRODUCED')
        self.assertEqual(reproduce(prior,bad)['status'],'REPLAY_DIVERGED')

    def test_postflight_must_be_new_and_for_exact_generated_project(self):
        import time
        version='v0.4.9'
        report_path=self.root/version/'runtime-host'/'run-1'/'runtime-host-report.json'
        report_path.parent.mkdir(parents=True)
        project=self.root/'project'
        report_path.write_text(json.dumps({'input_replay_sha256':'abc','source_rom_sha256':HASH,
                                          'original_project':str(project),'frames_observed':220}))
        path,doc=matching_native_report(self.root,version,'abc',HASH,project,since=time.time())
        self.assertEqual(path,report_path)
        with self.assertRaisesRegex(ValueError,'No matching new native execution'):
            matching_native_report(self.root,version,'different',HASH,project,since=time.time())
        with self.assertRaisesRegex(ValueError,'No matching new native execution'):
            matching_native_report(self.root,version,'abc',HASH,project,since=time.time()+3600)

    def test_staged_interactive_capture_does_not_touch_guest_translation(self):
        project=self.root/'source'
        generate_project(json.loads(EXPORT.read_text()),ROM,project)
        before={p.relative_to(project).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                for p in project.rglob('*') if p.is_file()}
        cached,_=stage(project,self.root/'cache')
        self.assertEqual(before['translated.cpp'],hashlib.sha256((cached/'translated.cpp').read_bytes()).hexdigest())
        self.assertIn('RECOMPDEV_GUEST_INPUT_TAP_V1',(cached/'interactive.cpp').read_text())
        self.assertIn('RECOMP_INPUT_CYCLES_V1',(cached/'hardware/rd_guest_input_tap.hpp').read_text())
        stage(project,self.root/'cache')
        after={p.relative_to(project).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
               for p in project.rglob('*') if p.is_file()}
        self.assertEqual(before,after)
        (cached/'interactive.cpp').write_text((cached/'interactive.cpp').read_text()+'\n// corruption\n')
        with self.assertRaisesRegex(ValueError,'Cached native input frontend has been changed'):
            stage(project,self.root/'cache')

    def test_workspace_uses_independent_input_recovery_component(self):
        registry=json.loads((ROOT/'workspace/components.json').read_text())
        self.assertEqual(registry['components']['input_recovery']['version'],'0.1.0')
        self.assertEqual(registry['components']['rd_runtime_host']['version'],'0.1.0')
        self.assertEqual(registry['components']['controller']['version'],'0.4.4')

if __name__=='__main__':unittest.main(verbosity=2)
