"""New compiled-controller preview: immutable job, traced guest and upload-safe ZIP."""
import hashlib
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from execution_monitor.job_preview import select_source,copy_and_instrument,collect_input_stop,diagnostic_zip,preview,digest
from execution_monitor.bridge import MARKER


def fixture(root):
    rom=root/'test.sms';rom.write_bytes(b'\x00'*16384)
    sha=digest(rom)
    jid='job-20261107T000000Z-deadbeef-99-0'
    jobdir=root/'jobs'/jid;project=jobdir/'sessions'/'cycle-01'/'round-01'
    project.mkdir(parents=True)
    job={'schema':'recompdev.controller.job.v1','id':jid,'rom':str(rom),'rom_sha256':sha,'status':'RECOVERY_LIMIT_REACHED'}
    (jobdir/'job.json').write_text(json.dumps(job))
    (project.parent/'orchestration.json').write_text(json.dumps({'schema':'recompdev.native.orchestrator.v1','source_sha256':sha,'rounds':[{'status':'MAX_RECOVERY_ROUNDS_REACHED'}]}))
    for x in ('CMakeLists.txt','interactive.cpp','live_sms.hpp','main.cpp','z80_cycles.hpp'):
        (project/x).write_bytes((ROOT/'runtime_sms/templates'/x).read_bytes())
    (project/'rd_sha256.hpp').write_bytes((ROOT/'harness/include/rd_sha256.hpp').read_bytes())
    (project/'native_part_0.cpp').write_text('#include "runtime.hpp"\nint rd_native_part_0(rd::State&,unsigned){return 0;}\n')
    (project/'translated.cpp').write_text('''#include "runtime.hpp"
        bool execute_native_instruction(rd::State& s){
          if(s.pc==0){s.pc=1;return true;}
          s.stopped="UNTRANSLATED_PHYSICAL_ROM_OFFSET";return false;
        }
    ''')
    (project/'translation-manifest.json').write_text(json.dumps({'schema':'recompdev.native.pcode.generated.v1',
      'source_sha256':sha,'backend':'dll_sms_native_runtime','full_CPU_state_port':True,'emitted':1,
      'accepted_instructions':[{'physical':0,'pc':0,'length':1}]}))
    return rom,jobdir,project

class PreviewContract(unittest.TestCase):
    def test_source_attestation_and_immutable_copy(self):
        with tempfile.TemporaryDirectory() as t:
            _,jobdir,project=fixture(Path(t))
            job,rom,session,actual,manifest=select_source(jobdir)
            self.assertEqual(actual,project)
            original={p.name:digest(p) for p in project.iterdir() if p.is_file()}
            out=Path(t)/'staged'
            info=copy_and_instrument(project,out)
            self.assertIn(MARKER,(out/'live_sms.hpp').read_text())
            self.assertEqual(info['translated_cpp_sha256'],digest(project/'translated.cpp'))
            self.assertEqual(original,{p.name:digest(p) for p in project.iterdir() if p.is_file()})
            (project/'interactive.cpp').write_text('tamper')
            with self.assertRaisesRegex(ValueError,'NOT_ATTESTED'): select_source(jobdir)

    def test_input_stop_is_correlated_not_declared_causal(self):
        observed=[{'type':'instruction','pc':10,'guest_cycles':100},
          {'type':'input','buttons':1,'guest_cycles':101},
          {'type':'stop','status':'untranslated_code','pc':14,'physical_offset':14,'guest_cycles':105}]
        out,n=collect_input_stop(observed,{'status':'UNTRANSLATED_INITIAL_CODE','frames':6,
           'native_steps':23,'pc':14,'physical_offset':14,'guest_cycles':105})
        self.assertEqual(n,3)
        self.assertEqual(out['preceding_input']['buttons'],1)
        self.assertEqual(out['guest_cycles_since_input'],4)
        self.assertIn('NOT_CAUSAL',out['interpretation'])

    def test_diagnostic_zip_excludes_rom_paths_and_binaries(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);out=root/'preview';out.mkdir()
            p=diagnostic_zip(out,root/'diagnostics',{'schema':'recompdev.preview.session.v1','status':'PREVIEW_CAPTURE_COMPLETE'},
                             [{'type':'input','buttons':1},{'type':'stop','pc':100,'status':'untranslated_code'}])
            with zipfile.ZipFile(p) as z:
                self.assertEqual(sorted(z.namelist()),['manifest.json','monitor-events.jsonl','preview.json'])
                manifest=json.loads(z.read('manifest.json'))
                for name,entry in manifest['files'].items():
                    self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(),entry['sha256'])
                self.assertFalse(manifest['rom_included'])

    def test_reuses_existing_compiled_translation_archive(self):
        with tempfile.TemporaryDirectory(prefix='rd-v19-reuse-') as t:
            root=Path(t);_,jobdir,project=fixture(root)
            with (project/'CMakeLists.txt').open('a') as f:
                f.write('\nadd_library(rd_generated_translation STATIC translated.cpp native_part_0.cpp)\n'
                        'target_include_directories(rd_generated_translation PRIVATE "${RECOMPDEV_SOURCE_ROOT}/runtime_sms/include")\n')
            # Real native archive from this exact fixture, built separately.
            p=subprocess.run(['cmake','-S',str(project),'-B',str(project/'build'),
                '-DRECOMPDEV_SOURCE_ROOT='+str(ROOT),'-DCMAKE_BUILD_TYPE=Release'],
                capture_output=True,text=True,timeout=120)
            self.assertEqual(p.returncode,0,p.stdout[-2000:]+p.stderr[-2000:])
            p=subprocess.run(['cmake','--build',str(project/'build'),'--target','rd_generated_translation',
                '--config','Release','--parallel','2'],capture_output=True,text=True,timeout=180)
            self.assertEqual(p.returncode,0,p.stdout[-2000:]+p.stderr[-2000:])
            opts=type('Options',(),dict(job_dir=str(jobdir),source_root=str(ROOT),out_dir=str(root/'preview'),
                diagnostics_dir=str(root/'diagnostics'),cycle=0,frames=2,steps=1200,sample_every=1,
                video='capture',input='neutral',timeout=180,no_viewer=True,hold_window=False))()
            self.assertEqual(preview(opts),0)
            artifact=next((root/'diagnostics').glob('*.zip'))
            with zipfile.ZipFile(artifact) as z:
                summary=json.loads(z.read('preview.json'))
                self.assertFalse(summary['translation_binary_rebuilt'])
                self.assertEqual(summary['binary_provenance'],'REUSED_SOURCE_MATCHED_OWNER_NATIVE_ARCHIVE_NOT_INDEPENDENTLY_RECOMPILED')
                self.assertEqual(summary['native_stop']['pc'],1)
            self.assertEqual(json.loads((jobdir/'job.json').read_text())['status'],'RECOVERY_LIMIT_REACHED')

    def test_native_capture_and_event_zip(self):
        if os.environ.get('RECOMPDEV_SKIP_NATIVE_PREVIEW')=='1':self.skipTest('set explicit skip')
        with tempfile.TemporaryDirectory(prefix='rd-v19-preview-') as t:
            root=Path(t);_,jobdir,project=fixture(root)
            opts=type('Options',(),dict(job_dir=str(jobdir),source_root=str(ROOT),out_dir=str(root/'preview'),
                diagnostics_dir=str(root/'diagnostics'),cycle=0,frames=2,steps=1200,sample_every=1,
                video='capture',input='neutral',timeout=180,no_viewer=True,hold_window=False))()
            self.assertEqual(preview(opts),0)
            artifacts=list((root/'diagnostics').glob('*.zip'))
            self.assertEqual(len(artifacts),1)
            with zipfile.ZipFile(artifacts[0]) as z:
                summary=json.loads(z.read('preview.json'))
                self.assertEqual(summary['status'],'PREVIEW_CAPTURE_COMPLETE')
                self.assertTrue(summary['observed_events']>0)
                self.assertEqual(summary['native_stop']['status'],'UNTRANSLATED_INITIAL_CODE')
                self.assertEqual(summary['native_stop']['pc'],1)
                self.assertFalse(summary['recovery_state_modified'])
            self.assertNotIn(MARKER,(project/'live_sms.hpp').read_text())
            self.assertEqual(json.loads((jobdir/'job.json').read_text())['status'],'RECOVERY_LIMIT_REACHED')

if __name__=='__main__':unittest.main()
