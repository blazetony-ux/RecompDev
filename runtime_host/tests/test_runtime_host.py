"""Generic host staging, source provenance and preservation tests."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'legacy/RecompDev-v0.4.0.45')]
from nativepilot.generator import generate_project
from runtime_host.bridge import install
from runtime_host.launch import verify_project,stage,find_project
from workspace import manager

ROM=ROOT/'harness/examples/recomp-pcode/synthetic.sms'
EXPORT=ROOT/'harness/examples/recomp-pcode/function-export.json'

class TestHost(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='generic-runtime-host-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.project=self.root/'original'/'native-project'
        generate_project(json.loads(EXPORT.read_text()),ROM,self.project)

    def test_bridge_preserves_generated_code_and_historical_source(self):
        original={str(p.relative_to(self.project)):p.read_bytes() for p in self.project.rglob('*') if p.is_file()}
        cache,identity=stage(self.project,self.root/'external-cache')
        self.assertEqual((cache/'translated.cpp').read_bytes(),original['translated.cpp'])
        self.assertEqual(install(cache)['files_changed'],[])
        # Windows and Linux legacy generators may vendor different optional
        # presentation headers. The staged bridge must be installed either way.
        replacement=(cache/'hardware/win32_window.hpp').read_bytes()
        self.assertEqual(replacement,(ROOT/'runtime_host/bridge/win32_window.hpp').read_bytes())
        if 'hardware/win32_window.hpp' in original:
            self.assertNotEqual(replacement,original['hardware/win32_window.hpp'])
        self.assertNotIn(b'Shinobi',(cache/'hardware/win32_window.hpp').read_bytes())
        self.assertNotIn(b'Sega',(cache/'hardware/rd_runtime_host.h').read_bytes())
        self.assertEqual({str(p.relative_to(self.project)):p.read_bytes() for p in self.project.rglob('*') if p.is_file()},original)
        cache2,identity2=stage(self.project,self.root/'external-cache')
        self.assertEqual((cache,identity),(cache2,identity2))

    def test_bridge_can_supply_missing_optional_windows_headers(self):
        # Some historical generated native projects lack the Windows presenter
        # headers. Staging must supply them without touching the source project.
        for name in ('win32_window.hpp','win32_audio.hpp'):
            original_header=self.project/'hardware'/name
            if original_header.exists():original_header.unlink()
        original={str(p.relative_to(self.project)):p.read_bytes() for p in self.project.rglob('*') if p.is_file()}
        cache,_=stage(self.project,self.root/'external-cache-missing-headers')
        for name in ('win32_window.hpp','win32_audio.hpp'):
            self.assertEqual((cache/'hardware'/name).read_bytes(),(ROOT/'runtime_host/bridge'/name).read_bytes())
        self.assertEqual((cache/'translated.cpp').read_bytes(),original['translated.cpp'])
        self.assertEqual({str(p.relative_to(self.project)):p.read_bytes() for p in self.project.rglob('*') if p.is_file()},original)
        self.assertEqual(install(cache)['files_changed'],[])

    def test_rom_hash_rejects_other_source(self):
        self.assertEqual(verify_project(self.project,ROM),json.loads((self.project/'generation.json').read_text())['original_source_sha256'])
        other=self.root/'other.sms';other.write_bytes(b'other');
        with self.assertRaisesRegex(ValueError,'different source SHA-256'):
            verify_project(self.project,other)

    def test_newest_generated_project_discovery(self):
        fake=self.root/'evidence/v0.4.8/job/recovery/round-00/native-project'
        fake.parent.mkdir(parents=True)
        shutil.copytree(self.project,fake)
        self.assertEqual(find_project(self.root/'evidence'),fake)
        with self.assertRaises(FileNotFoundError):find_project(self.root/'empty-evidence')

    def test_component_is_separately_versioned(self):
        m=manager.manifest(ROOT)['components']
        self.assertEqual(m['rd_runtime_host']['version'],'0.1.0')
        self.assertEqual(m['rd_runtime_host']['scope'],'production-presentation')
        self.assertEqual(m['controller']['version'],'0.4.4')
        self.assertEqual(m['rd_cpu_z80']['version'],'0.2.0')
        self.assertFalse((ROOT/'build-win').exists())

if __name__=='__main__':unittest.main()
