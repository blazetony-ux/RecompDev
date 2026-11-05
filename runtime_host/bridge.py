"""Stage generic presentation adapter in a *copy* of generated native source.

Never mutate the preserved generator, any historical evidence folder or the ROM.
Install is idempotent; the semantic translated.cpp is byte-identical to input.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
from runtime_host.guest_input_tap import instrument
from video_sms.bridge import install as install_sms_video

ROOT=Path(__file__).resolve().parents[1]
BRIDGE=ROOT/'runtime_host'/'bridge'
HEADER=ROOT/'runtime_host'/'include'/'rd_runtime_host.h'

def install(project:Path)->dict:
    project=Path(project).resolve(strict=True)
    if not (project/'generation.json').is_file() or not (project/'translated.cpp').is_file() or not (project/'CMakeLists.txt').is_file():
        raise ValueError('Not a complete authenticated native project')
    before=hashlib.sha256((project/'translated.cpp').read_bytes()).hexdigest()
    touched=[]
    for item in ('rd_host_loader.hpp','win32_window.hpp','win32_audio.hpp','rd_guest_input_tap.hpp'):
        dest=project/'hardware'/item
        data=(BRIDGE/item).read_bytes()
        if not dest.exists() or dest.read_bytes()!=data:
            dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);touched.append('hardware/'+item)
    dest=project/'hardware'/'rd_runtime_host.h'
    if not dest.exists() or dest.read_bytes()!=HEADER.read_bytes():
        dest.write_bytes(HEADER.read_bytes());touched.append('hardware/rd_runtime_host.h')
    cmake=project/'CMakeLists.txt'
    raw=cmake.read_text(encoding='utf8')
    line='target_link_libraries(RecompDevNativeApp PRIVATE ${CMAKE_DL_LIBS})\n'
    if line not in raw:cmake.write_text(raw.rstrip()+'\n\n# Generic runtime host: dynamic presentation adapter only.\n'+line,encoding='utf8');touched.append('CMakeLists.txt')
    touched.extend(install_sms_video(project))
    tap=instrument(project)
    if tap['status']=='INSTRUMENTED':touched.append('interactive.cpp')
    after=hashlib.sha256((project/'translated.cpp').read_bytes()).hexdigest()
    if before!=after:raise RuntimeError('Generated native game-code source unexpectedly changed')
    return {'status':'BRIDGE_INSTALLED','files_changed':touched,'generated_game_code_sha256':after,
            'cpu_or_machine_specific_host_code':False}
