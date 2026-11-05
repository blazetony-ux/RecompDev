"""Check build relocation against deep native projects, no historical source edits."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'legacy/RecompDev-v0.4.0.45')]
from production_translation.native_build import build_native_project,NativeBuildError
from nativepilot.generator import generate_project

ROM=ROOT/'harness/examples/recomp-pcode/synthetic.sms'
EXPORT=ROOT/'harness/examples/recomp-pcode/function-export.json'

class TestNativeBuild(unittest.TestCase):
    def test_external_compiler_dir_and_preserved_game_code(self):
        with tempfile.TemporaryDirectory(prefix='rd-native-short-path-') as t:
            root=Path(t)
            # Deliberately exceeds the normal 260-character CMake scratch path.
            project=root/('long-input-recovery-'+'x'*32)/('production-recovery-'+'y'*24)/'recovery'/'round-00'/'native-project'
            generate_project(json.loads(EXPORT.read_text()),ROM,project)
            original=hashlib.sha256((project/'translated.cpp').read_bytes()).hexdigest()
            exe,log=build_native_project(project,timeout=180,build_root=root/'short')
            self.assertTrue(exe.is_file())
            self.assertTrue((project/'build'/('Release' if sys.platform=='win32' else '')/('RecompDevNativeApp'+('.exe' if sys.platform=='win32' else ''))).is_file())
            self.assertFalse((project/'build/CMakeCache.txt').exists())
            self.assertFalse((project/'build/CMakeFiles').exists())
            self.assertTrue((project/'compiler-evidence/configure.log').exists())
            self.assertTrue((project/'compiler-evidence/build.log').exists())
            state=json.loads((project/'compiler-evidence/external-native-build.json').read_text())
            self.assertEqual(state['status'],'BUILT')
            self.assertTrue(Path(state['external_build_dir']).is_dir())
            self.assertEqual(original,hashlib.sha256((project/'translated.cpp').read_bytes()).hexdigest())

    def test_bad_project_configuration_records_failure_and_cannot_publish(self):
        with tempfile.TemporaryDirectory(prefix='rd-native-failure-') as t:
            root=Path(t);project=root/'project';project.mkdir()
            (project/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.16)\nerror_forever()\n')
            with self.assertRaisesRegex(NativeBuildError,'CMake configure failed'):
                build_native_project(project,timeout=60,build_root=root/'build')
            state=json.loads((project/'compiler-evidence/external-native-build.json').read_text())
            self.assertEqual(state['status'],'BUILD_FAILED')
            self.assertIn('full log:',state['error'])
            self.assertFalse((project/'build').exists())
            self.assertTrue((project/'compiler-evidence/configure.log').is_file())

    def test_explicit_history_root_enables_verified_import_only(self):
        import production_translation.run_recovery as runner
        import nativecore.continuous_recovery_v0436 as original
        from production_translation.provider import select_provider
        observed=[]
        old_build=original._build
        old_gen=original.generate_project
        with tempfile.TemporaryDirectory(prefix='rd-recovery-history-') as t:
            out=Path(t)/'out'
            argv=['python','--no-history-import','--history-root',str(Path(t)/'history'),
                  '--output-dir',str(out)]
            def fake_run(path,run_name):
                observed.extend(sys.argv[1:])
                self.assertIsNot(original._build,old_build)
                raise SystemExit(2)
            with patch.object(sys,'argv',argv), patch('runpy.run_path',side_effect=fake_run):
                with self.assertRaises(SystemExit):runner.main()
            self.assertNotIn('--no-history-import',observed)
            self.assertIn('--history-root',observed)
            self.assertIs(original._build,old_build)
            self.assertIs(original.generate_project,old_gen)
            evidence=json.loads((out/'production-translation.json').read_text())
            self.assertTrue(evidence['history_import_enabled'])
            self.assertEqual(evidence['native_build_layout'],'EXTERNAL_SHORT_DIRECTORY')
        observed.clear()
        with tempfile.TemporaryDirectory() as t:
            with patch.object(sys,'argv',['python','--no-history-import','--output-dir',t]),patch('runpy.run_path',side_effect=fake_run):
                with self.assertRaises(SystemExit):runner.main()
            self.assertIn('--no-history-import',observed)

if __name__=='__main__':unittest.main(verbosity=2)
