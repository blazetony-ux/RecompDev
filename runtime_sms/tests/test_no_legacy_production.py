"""Production dependency regression; frozen originals may be used by test oracles."""
from pathlib import Path
import sys
root=Path(sys.argv[1]).resolve()
paths=[
    'harness/CMakeLists.txt',
    'translation_pcode/src/translator.cpp',
    'controller/native_translate.cpp',
    'runtime_sms/templates/CMakeLists.txt',
    'runtime_sms/templates/main.cpp',
    'runtime_sms/templates/interactive.cpp',
    'runtime_sms/templates/live_sms.hpp',
    'runtime_sms/src/runtime.cpp',
]
for name in paths:
    content=(root/name).read_text(encoding='utf-8')
    # The CMake file also compiles independent differential tests using legacy
    # headers; this is a test-only include and should remain as the oracle.
    if name=='harness/CMakeLists.txt':
        content='\n'.join(x for x in content.splitlines()
             if not ('rd_video_sms_mode4_smoke' in x and 'legacy/' in x))
    assert 'legacy/' not in content, f'active source dependency reintroduced: {name}'
    assert 'baselines/' not in content, f'frozen PoC dependency reintroduced: {name}'
    assert 'RecompDev-v0.4.0.45' not in content, f'old runtime referenced: {name}'
for name in ['runtime_sms/include/runtime.hpp', 'runtime_sms/include/hardware/core.hpp',
             'runtime_sms/include/hardware/adapters/sms.hpp',
             'runtime_sms/templates/z80_cycles.hpp']:
    assert (root/name).is_file(),name
cmake=(root/'runtime_sms/templates/CMakeLists.txt').read_text()
assert 'add_library(rd_sms_native_runtime SHARED' in cmake
assert 'add_library(rd_video_sms_mode4 SHARED' in cmake
assert 'add_library(rd_runtime_host SHARED' in cmake
assert 'target_link_libraries(RecompDevNativeApp PRIVATE rd_sms_native_runtime rd_video_sms_mode4 rd_runtime_host)' in cmake
assert 'runtime.cpp' not in cmake.split('add_executable(RecompDevNativePilot')[1]
assert 'rd_host_present' in (root/'runtime_sms/templates/interactive.cpp').read_text()
assert 'rd_sms_mode4_render' in (root/'runtime_sms/templates/live_sms.hpp').read_text()
assert 'rd_sms_mode4_render' in (root/'runtime_sms/src/runtime.cpp').read_text()
print('PASS independent native SMS runtime / video / host; historical compare path remains test-only')

# An exported C++ class must not expose static constexpr data members: MSVC C2487.
# These timing / bounded event counters have compile-time-only semantics.
runtime_hpp=(root/'runtime_sms/include/runtime.hpp').read_text(encoding='utf-8')
state_part=runtime_hpp.split('struct RD_SMS_NATIVE_API State',1)[1]
import re
assert not re.search(r'^\s*static\s+constexpr\s', state_part, re.M), 'MSVC C2487: exported State declares a static constexpr member'
assert 'enum : unsigned { TSTATES_PER_SCANLINE=228, NTSC_SCANLINES=262, VBLANK_START_SCANLINE=192 }' in state_part
assert 'enum : std::uint64_t { EVENT_STREAM_LIMIT=500000, EVENT_STREAM_BYTE_LIMIT=64ull*1024ull*1024ull, EVENTS_PER_CHUNK=1024 }' in state_part
