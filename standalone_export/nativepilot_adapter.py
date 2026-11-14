"""Nativepilot v1 adapter for already source-verified generated native C++.

This is an explicit transition adapter for the maintained native app project
shape. The generic exporter does not know Z80, SMS, ROM banking or ports.
Future machine providers implement a different source adapter, not a new
controller/exporter branch.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re

ADAPTER = 'recompdev.nativepilot-embedded-v1'
# Exactly the known, source-vendored nativepilot compilation set. CMake from
# the untrusted project is deliberately NOT executed by this exporter.
SOURCES = ('interactive.cpp', 'runtime.cpp', 'translated.cpp')
_REQUIRED = ('generation.json', 'live_sms.hpp', 'runtime.hpp', 'counters.hpp', 'z80_cycles.hpp',
             'hardware/backends.hpp', 'hardware/continuous.hpp',
             'hardware/runtime.hpp', 'hardware/adapters/sms.hpp')
_ROM_RE = re.compile(r'  std::ifstream f\(argv\[1\],std::ios::binary\|std::ios::ate\);\s*'
    r'if\(!f\|\|f.tellg\(\)<0\|\|f.tellg\(\)>64\*1024\*1024\)throw std::runtime_error\("OWNER_ROM_MISSING_OR_TOO_LARGE"\);\s*'
    r'f.seekg\(0\);std::vector<std::uint8_t> rom\(std::istreambuf_iterator<char>\{f\},\{\}\);')


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate(project: Path, source_data: bytes) -> dict:
    for name in (*SOURCES, *_REQUIRED):
        if not (project / name).is_file():
            raise ValueError('EXPORT_PROJECT_MISSING_REQUIRED_SOURCE: ' + name)
    try:
        generation = json.loads((project/'generation.json').read_text(encoding='utf8'))
    except (OSError, ValueError) as exc:
        raise ValueError('EXPORT_GENERATION_MANIFEST_INVALID') from exc
    digest = _sha(source_data)
    if generation.get('original_source_sha256') != digest:
        raise ValueError('EXPORT_SOURCE_SHA256_MISMATCH')
    if generation.get('translated_cpp_sha256') is not None and generation['translated_cpp_sha256'] != _sha((project/'translated.cpp').read_bytes()):
        raise ValueError('EXPORT_GENERATED_INSTRUCTION_SOURCE_HASH_MISMATCH')
    if generation.get('translated_instructions', 0) <= 0:
        raise ValueError('EXPORT_NO_SOURCE_VERIFIED_NATIVE_INSTRUCTIONS')
    # The project has a source attestation; unresolved execution coverage remains
    # explicitly unqualified, regardless of the instruction count.
    orig = (project/'interactive.cpp').read_text(encoding='utf8')
    if len(_ROM_RE.findall(orig)) != 1 or orig.count('int main(int argc,char**argv)') != 1:
        raise ValueError('EXPORT_NATIVEPILOT_ADAPTER_ABI_MISMATCH')
    if 'bool execute_native_instruction' not in (project/'translated.cpp').read_text(encoding='utf8'):
        raise ValueError('EXPORT_GENERATED_NATIVE_INSTRUCTION_ENTRYPOINT_MISSING')
    return {
        'adapter': ADAPTER, 'source_sha256': digest,
        'source_size': len(source_data),
        'translated_cpp_sha256': _sha((project/'translated.cpp').read_bytes()),
        'generation_sha256': _sha((project/'generation.json').read_bytes()),
        'translated_instructions': generation['translated_instructions'],
        'unsupported_instructions': generation.get('unsupported_instructions', 'UNKNOWN'),
        'source_coverage': 'UNQUALIFIED',
        'hardware_parity': 'NOT_TESTED',
    }


def stage(project: Path, destination: Path, source_data: bytes) -> None:
    """Clone known code, embed authorised data and generate trusted build recipe."""
    import shutil
    for name in (*SOURCES, *_REQUIRED):
        dest = destination/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(project/name, dest)
    # Copy vendored headers only; never use caller-controlled CMake scripts or
    # blindly copy source subtrees containing symlinks or arbitrary CMake files.
    for file in project.glob('*.hpp'):
        shutil.copyfile(file, destination/file.name)
    for sub in ('hardware',):
        for file in (project/sub).rglob('*'):
            if file.is_symlink():
                raise ValueError('EXPORT_SOURCE_SYMLINK_FORBIDDEN')
            if file.is_file() and file.suffix in ('.hpp', '.h'):
                rel = file.relative_to(project)
                dest = destination/rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(file, dest)
    orig = (destination/'interactive.cpp').read_text(encoding='utf8')
    transformed = _ROM_RE.sub('  std::vector<std::uint8_t> rom(rd_standalone_embedded_source, '
                               'rd_standalone_embedded_source+sizeof(rd_standalone_embedded_source));', orig)
    transformed = transformed.replace('int main(int argc,char**argv)',
                                      'static int rd_generated_native_main(int argc,char**argv)', 1)
    transformed = '#include "rd_standalone_source.hpp"\n' + transformed + '''
// Generic source-adapter argument bridge. No path to any ROM is required.
int main(int argc, char** argv) {
 std::vector<char*> arguments;
 arguments.reserve(static_cast<std::size_t>(argc)+12u);
 arguments.push_back(argv[0]);
 arguments.push_back(const_cast<char*>("embedded-authorised-data"));
 if(argc==1) {
#if defined(_WIN32)
   const char* defaults[]={"game", "36000", "20000000", "-", "--video", "window", "--audio", "speaker", "--input", "live"};
#else
   const char* defaults[]={"game", "60", "500000", "-", "--video", "capture", "--audio", "capture", "--input", "neutral"};
#endif
   for(auto p:defaults) arguments.push_back(const_cast<char*>(p));
 } else {
   for(int i=1;i<argc;++i) arguments.push_back(argv[i]);
 }
 return rd_generated_native_main(static_cast<int>(arguments.size()), arguments.data());
}
'''
    (destination/'interactive.cpp').write_text(transformed, encoding='utf8')
    # A byte array avoids temporary or runtime ROM paths. The generated source
    # is never linked from a user-local location during execution.
    hex_bytes = [f'0x{value:02x}' for value in source_data]
    chunks = [', '.join(hex_bytes[i:i+16]) for i in range(0,len(hex_bytes),16)]
    (destination/'rd_standalone_source.hpp').write_text(
        '#ifndef RD_STANDALONE_SOURCE_HPP\n#define RD_STANDALONE_SOURCE_HPP\n'
        '#include <cstdint>\nstatic const std::uint8_t rd_standalone_embedded_source[] = {\n' +
        ',\n'.join(chunks) + '\n};\n#endif\n', encoding='utf8')
    (destination/'CMakeLists.txt').write_text('''cmake_minimum_required(VERSION 3.17)
project(RecompDevStandalone LANGUAGES CXX)
add_executable(RecompDevStandalone interactive.cpp runtime.cpp translated.cpp)
target_compile_features(RecompDevStandalone PRIVATE cxx_std_17)
if(WIN32)
  target_link_libraries(RecompDevStandalone PRIVATE user32 gdi32 winmm)
  if(MSVC)
    target_compile_options(RecompDevStandalone PRIVATE /W3 /EHsc /bigobj)
    set_property(TARGET RecompDevStandalone PROPERTY MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
    target_link_options(RecompDevStandalone PRIVATE /STACK:8388608)
  endif()
else()
  target_compile_options(RecompDevStandalone PRIVATE -Wall -Wextra)
endif()
''', encoding='utf8')
