"""Host-stack regression: generated projects preserve portable PE stack policy."""
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class WindowsNativeStackTests(unittest.TestCase):
    def test_windows_both_native_targets_have_stack_reserve(self):
        cmake=(ROOT/'nativepilot/CMakeLists.txt').read_text()
        self.assertIn('if(WIN32)',cmake)
        self.assertIn('if(MSVC)',cmake)
        self.assertIn('8388608',cmake)
        for target in ('RecompDevNativeApp','RecompDevNativePilot'):
            self.assertIn(f'target_link_options({target} PRIVATE /STACK:8388608)',cmake)
            self.assertIn(f'target_link_options({target} PRIVATE "LINKER:--stack,8388608")',cmake)
        self.assertNotIn('set(CMAKE_EXE_LINKER_FLAGS',cmake)

    def test_generator_delivers_same_cmake_to_new_projects(self):
        source=(ROOT/'nativepilot/generator.py').read_text()
        self.assertIn("'CMakeLists.txt'",source)
        self.assertIn('copy_if_changed(src,out/name)',source)
        # The generator copies the same CMake file for each new project,
        # avoiding a game-specific linker adjustment.
        with tempfile.TemporaryDirectory() as tmp:
            project=Path(tmp)/'generated-project'
            project.mkdir()
            (project/'CMakeLists.txt').write_bytes((ROOT/'nativepilot/CMakeLists.txt').read_bytes())
            self.assertEqual((project/'CMakeLists.txt').read_bytes(),
                             (ROOT/'nativepilot/CMakeLists.txt').read_bytes())

if __name__=='__main__': unittest.main()
