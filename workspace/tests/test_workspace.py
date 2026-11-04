"""v0.4.4 isolated component versioning, rollout and evidence-root regressions."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from workspace import manager
from modular.cli import fresh_evidence
EXE=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else None


class TestProtectedWorkspace(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(prefix='RecompDev v044 isolated workspace ')
        self.addCleanup(self.t.cleanup)
        self.dir=Path(self.t.name)
        self.source=self.dir/'RecompDev'
        self.source.mkdir()
        (self.source/'workspace').mkdir()
        doc=json.loads((ROOT/'workspace/components.json').read_text())
        (self.source/'workspace/components.json').write_text(json.dumps(doc))
        self.env=patch.dict(os.environ, {'RECOMPDEV_PROJECTS_ROOT':str(self.dir)})
        self.env.start();self.addCleanup(self.env.stop)

    def fake_dll(self, component, bytestring):
        p=manager.binary_path(component,self.source)
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(bytestring)
        return p

    def test_out_of_tree_paths_and_evidence(self):
        r=manager.roots(self.source)
        for key in ('build','runtime','archive','data','evidence','cache'):
            self.assertNotIn(self.source,r[key].parents)
            self.assertNotEqual(r[key],self.source)
        self.assertNotIn(ROOT.resolve(),fresh_evidence().resolve().parents)

    def test_independent_component_version_increment(self):
        before=manager.manifest(self.source)['components']
        result=manager.bump('rd_cpu_z80','patch',self.source)
        after=manager.manifest(self.source)['components']
        v=before['rd_cpu_z80']['version'].split('.')
        self.assertEqual(result['version'],'.'.join(v[:2]+[str(int(v[2])+1)]))
        self.assertTrue(all(after[k]==v for k,v in before.items() if k!='rd_cpu_z80'))

    def test_immutable_version_and_rollback(self):
        original_version=manager.manifest(self.source)['components']['rd_cpu_z80']['version']
        self.fake_dll('rd_cpu_z80',b'first valid test DLL')
        first=manager.install_candidate('rd_cpu_z80',self.source,validated=True)
        self.assertEqual(first['version'],original_version)
        self.fake_dll('rd_cpu_z80',b'different DLL same version')
        with self.assertRaisesRegex(ValueError,'IMMUTABLE_VERSION_CONFLICT'):
            manager.install_candidate('rd_cpu_z80',self.source,validated=True)
        self.assertEqual(manager.read_state(self.source)['active']['rd_cpu_z80']['sha256'],first['sha256'])
        manager.bump('rd_cpu_z80','patch',self.source)
        nextone=manager.install_candidate('rd_cpu_z80',self.source,validated=True)
        self.assertNotEqual(nextone['version'],original_version)
        rolled=manager.rollback('rd_cpu_z80',self.source)
        self.assertEqual(rolled['version'],original_version)
        self.assertEqual(manager.read_state(self.source)['active']['rd_cpu_z80']['sha256'],first['sha256'])
        self.assertEqual(manager.binary_path('rd_cpu_z80',self.source).read_bytes(),b'different DLL same version')

    def test_invalid_release_does_not_touch_live_runtime(self):
        self.fake_dll('rd_cpu_z80',b'previous')
        manager.install_candidate('rd_cpu_z80',self.source,validated=True)
        lock=manager.state_file(self.source)
        previous=lock.read_bytes()
        with self.assertRaisesRegex(ValueError,'No previously'):
            manager.rollback('rd_audio_wav',self.source)
        self.assertEqual(lock.read_bytes(),previous)

    def test_deployed_compiled_controller_can_read_external_source_pointer(self):
        if EXE is None or not EXE.exists():return
        runtime=manager.roots(ROOT)['runtime']
        runtime.mkdir(parents=True,exist_ok=True)
        deployed=runtime/EXE.name
        # Do not overwrite an already-installed controller during a test.
        with tempfile.TemporaryDirectory(prefix='controller runtime isolated ') as tmp:
            isolated=Path(tmp)/EXE.name
            shutil.copy2(EXE,isolated)
            (isolated.parent/'source-root.txt').write_text(str(ROOT.resolve())+'\n')
            p=subprocess.run([str(isolated),'--plugins'],capture_output=True,text=True,timeout=45)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn('legacy.recovery',p.stdout)

    def test_source_protection_and_manifest(self):
        self.assertEqual(manager.manifest(ROOT)['components']['legacy.recovery']['scope'],'production-workflow')
        self.assertEqual(manager.manifest(ROOT)['components']['rd_cpu_z80']['scope'],'harness')
        self.assertFalse((ROOT/'build-win').exists())
        self.assertFalse((ROOT/'evidence').exists())


if __name__=='__main__':
    # Remove binary argument before unittest parses flags/positional entries.
    sys.argv=[sys.argv[0]]
    unittest.main(verbosity=2)
