"""Stage a replaceable Master System VDP DLL call into a generated project copy.

This changes only hardware/adapters/sms.hpp in an external staging directory;
no immutable legacy source, generated Z80 code, ROM or original evidence is edited.
"""
from __future__ import annotations
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HEADER=ROOT/'video_sms'/'include'/'rd_sms_mode4.h'
BRIDGE=ROOT/'video_sms'/'bridge'/'rd_sms_mode4_bridge.hpp'
START='inline Frame render_mode4('
END='\nclass Vdp final'
MARKER='// RD_SMS_MODE4_DYNAMIC_VIDEO_PLUGIN_V1'


def transform(source:str)->str:
    if MARKER in source:
        return source
    if source.count(START)!=1 or source.count(END)!=1 or source.count('namespace recomp::hw::sms {')!=1:
        raise ValueError('Unexpected generated Master System renderer layout; refusing silent patch')
    a=source.index(START)
    b=source.index(END,a)
    replacement='''// RD_SMS_MODE4_DYNAMIC_VIDEO_PLUGIN_V1
inline Frame render_mode4(const std::array<u8,16384>& vram,
 const std::array<u8,32>& cram,const std::array<u8,16>& regs,u64 cycle=0,u64 ordinal=0){
 Frame out;out.width=256;out.height=192;out.source_cycle=cycle;out.ordinal=ordinal;
 out.pixels.resize(std::size_t(out.width)*out.height);
 rd_sms_mode4_bridge::render(vram.data(),cram.data(),regs.data(),out.pixels.data(),ordinal);
 return out;
}
'''
    source=source[:a]+replacement+source[b:]
    return source.replace('namespace recomp::hw::sms {',
        '#include "../rd_sms_mode4_bridge.hpp"\nnamespace recomp::hw::sms {',1)


def install(project:Path)->list[str]:
    project=Path(project)
    dest=project/'hardware'/'adapters'/'sms.hpp'
    if not dest.is_file():
        raise ValueError('Generated native project has no SMS hardware adapter')
    changes=[]
    for data,rel in ((HEADER,'hardware/rd_sms_mode4.h'),(BRIDGE,'hardware/rd_sms_mode4_bridge.hpp')):
        location=project/rel
        if not location.is_file() or location.read_bytes()!=data.read_bytes():
            location.parent.mkdir(parents=True,exist_ok=True)
            location.write_bytes(data.read_bytes());changes.append(rel)
    original=dest.read_text(encoding='utf8')
    updated=transform(original)
    if updated!=original:
        dest.write_text(updated,encoding='utf8');changes.append('hardware/adapters/sms.hpp')
    return changes
