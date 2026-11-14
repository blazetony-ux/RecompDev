"""Real compiled offline-standalone game acceptance and exporter negative gates."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'legacy/RecompDev-v0.4.0.45')]
from nativepilot.generator import generate_project # test fixture only; not production exporter
from standalone_export.exporter import build, verify, sha256
from workspace.release_identity import evidence_version, release


def loop_fixture(home: Path):
    rom=bytes([0xc3,0,0])+bytes(65536-3)
    data=home/'authored-loop.sms'
    data.write_bytes(rom)
    doc=json.loads((ROOT/'harness/examples/recomp-pcode/function-export.json').read_text())
    doc['source_sha256']=hashlib.sha256(rom).hexdigest()
    doc['target_id']='recompdev-authored-jp-loop'
    doc['analyzer']='authored-unit-test-not-ghidra'
    doc['functions']=[{'entry':0,'name':'AUTHOR_LICENSED_LOOP', 'instructions':[
        {'address':0,'length':3,'fallthrough':0,'mnemonic':'JP',
         'bytes_sha256':hashlib.sha256(rom[:3]).hexdigest(),
         'pcode':[{'op':'BRANCH','inputs':[{'space':'ram','offset':0,'size':1}]}]}
    ]}]
    project=home/'project'
    generate_project(doc,data,project)
    return data,project


class ExportContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.holder=tempfile.TemporaryDirectory(prefix='recompdev-v34-contract-')
        cls.home=Path(cls.holder.name)
        cls.data,cls.project=loop_fixture(cls.home)
        cls.translated_sha=sha256(cls.project/'translated.cpp')
        cls.bundle=cls.home/'bundle'
        cls.result=build(project=cls.project,data=cls.data,output=cls.bundle,rights_confirmed=True)

    @classmethod
    def tearDownClass(cls):
        cls.holder.cleanup()

    def test_01_source_and_native_code_bound(self):
        self.assertEqual(self.result['source_data_sha256'],sha256(self.data))
        self.assertEqual(self.result['translated_cpp_sha256'],self.translated_sha)
        self.assertEqual(sha256(self.project/'translated.cpp'),self.translated_sha)
        self.assertEqual(self.result['source_data_storage'],'embedded_in_native_executable')
        self.assertEqual(self.result['adapter'],'recompdev.nativepilot-embedded-v1')
        self.assertFalse(self.result['controller_required_on_target'])
        self.assertFalse(self.result['compiler_required_on_target'])
        self.assertEqual(self.result['coverage_qualification'],'NOT_ESTABLISHED')
        self.assertEqual(self.result['hardware_parity'],'NOT_TESTED')

    def test_02_isolated_execution_and_frames_without_source(self):
        self.assertEqual(self.result['isolated_native_launch']['status'],'PASS')
        fresh=self.home/'moved-standalone'
        shutil.copytree(self.bundle,fresh)
        shutil.rmtree(self.project)
        self.project=None
        self.data.unlink()
        exe=fresh/self.result['native_executable']
        empty=self.home/'no-developer-files'; empty.mkdir()
        args=[str(exe),str(empty/'frames'),'3','250000','-',
              '--video','capture','--audio','capture','--input','neutral']
        p=subprocess.run(args,cwd=empty,capture_output=True,text=True,timeout=50)
        self.assertEqual(p.returncode,0,p.stderr[-1000:])
        found=[line for line in p.stdout.splitlines() if line.startswith('NATIVE_APP_RESULT=')]
        self.assertEqual(len(found),1)
        record=json.loads(found[0].split('=',1)[1]); self.assertGreaterEqual(record['frames'],3)
        self.assertGreater(record['native_steps'],10000)
        self.assertEqual(record['status'],'FRAME_BUDGET_REACHED')
        self.assertTrue((empty/'frames.ppm').is_file())
        self.assertEqual(verify(fresh,sha256(fresh/'export-manifest.json'))['status'],'VERIFIED')
        with self.assertRaisesRegex(ValueError,'MANIFEST_PIN_MISMATCH'):
            verify(fresh,'f'*64)

    def test_03_verify_tamper_rejected(self):
        target=self.home/'tampered'
        shutil.copytree(self.bundle,target)
        exe=target/self.result['native_executable']
        with exe.open('ab') as out:out.write(b'TAMPER')
        with self.assertRaisesRegex(ValueError,'HASH_MISMATCH'):
            verify(target)

    def test_04_overwrite_rejected(self):
        with self.assertRaisesRegex(ValueError,'EXPORT_DESTINATION_EXISTS'):
            build(project=self.home, data=self.bundle/'README.txt',output=self.bundle,rights_confirmed=True)

    def test_05_manifest_missing_and_injection_rejected(self):
        tampered=self.home/'unknown-file';shutil.copytree(self.bundle,tampered)
        (tampered/'extraneous.dll').write_bytes(b'unknown dependency')
        with self.assertRaisesRegex(ValueError,'EXPORT_BUNDLE_FILES_INVALID'):
            verify(tampered)

    def test_06_release_identifier_from_registry(self):
        self.assertEqual(release(ROOT),'workspace/v0.4.9.34')
        self.assertEqual(evidence_version(ROOT),'v0.4.9.34')


class NegativeBeforeBuild(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='rd-v34-negative-')
        self.home=Path(self.temp.name)
        self.data,self.project=loop_fixture(self.home)
    def tearDown(self):self.temp.cleanup()

    def test_rights_must_be_explicit(self):
        with self.assertRaisesRegex(ValueError,'RIGHTS_CONFIRMATION_REQUIRED'):
            build(project=self.project,data=self.data,output=self.home/'out',rights_confirmed=False)
    def test_mismatched_source_rejected_before_compiler(self):
        self.data.write_bytes(self.data.read_bytes()+b'x')
        with self.assertRaisesRegex(ValueError,'SOURCE_SHA256_MISMATCH'):
            build(project=self.project,data=self.data,output=self.home/'out',rights_confirmed=True)
    def test_source_symlink_rejected(self):
        original=self.project/'runtime.cpp'
        backup=original.read_bytes()
        original.unlink()
        try:
            original.symlink_to(self.project/'translated.cpp')
        except OSError as exc:
            # Unprivileged Windows accounts cannot always create file symlinks
            # (WinError 1314). Exercise the real export admission check with
            # a simulated symlink rather than failing before reaching it.
            if getattr(exc,'winerror',None)!=1314:
                raise
            original.write_bytes(backup)
            with mock.patch.object(Path,'is_symlink',autospec=True,
                                   side_effect=lambda path:path==original) as probe:
                with self.assertRaisesRegex(ValueError,'PROJECT_SYMLINK_FORBIDDEN'):
                    build(project=self.project,data=self.data,output=self.home/'out',rights_confirmed=True)
                self.assertTrue(any(c.args[0]==original for c in probe.call_args_list))
        else:
            with self.assertRaisesRegex(ValueError,'PROJECT_SYMLINK_FORBIDDEN'):
                build(project=self.project,data=self.data,output=self.home/'out',rights_confirmed=True)
    def test_wrong_generated_entrypoint_rejected(self):
        file=self.project/'translated.cpp';file.write_text('// removed verified entrypoint\n')
        with self.assertRaisesRegex(ValueError,'INSTRUCTION_ENTRYPOINT_MISSING'):
            build(project=self.project,data=self.data,output=self.home/'out',rights_confirmed=True)


if __name__=='__main__':unittest.main(verbosity=2)
