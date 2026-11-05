"""Machine-specific observation adapter for generated SMS native projects.

Only disposably *staged* C++ is instrumented. Neither generated translated.cpp,
nor the preserved production Z80 translator / machine implementation is edited.
The diagnostic recorder itself is host- and CPU-neutral.
"""
from pathlib import Path

HEADER = Path(__file__).resolve().parent / 'bridge' / 'rd_movement_trace.hpp'
MARKER = 'RD_MOVEMENT_TRACE_SMS_V1'


def live_sms_transform(source: str) -> str:
    if MARKER in source:
        return source
    anchor = '  state_.apply_host_input(in.buttons);'
    render = '  return recomp::hw::sms::render_mode4(state_.vram,state_.cram,state_.vdp_regs,state_.tstates,state_.frames);'
    include = '#include "hardware/adapters/sms.hpp"'
    if source.count(anchor) != 1 or source.count(render) != 1 or source.count(include) != 1:
        raise ValueError('Unexpected native SMS guest input/render source: instrumentation refused')
    return (source.replace(include, include + '\n#include "hardware/rd_movement_trace.hpp" // ' + MARKER, 1)
                  .replace(anchor, anchor + '\n  rd_movement_trace::controller(state_.tstates,in.buttons,state_.controller_a,state_.controller_b);', 1)
                  .replace(render,
                           '  rd_movement_trace::frame(state_.tstates,state_.frames,state_.vram,state_.vdp_regs);\n' + render, 1))


def runtime_transform(source: str) -> str:
    if MARKER in source:
        return source
    include = '#include "runtime.hpp"'
    dc = 'if(p==0xdc){record_event("INPUT_READ",p,controller_a);return controller_a;}'
    dd = 'record_event("INPUT_READ",p,value);return value;'
    if source.count(include) != 1 or source.count(dc) != 1 or source.count(dd) != 1:
        raise ValueError('Unexpected native SMS I/O read source: instrumentation refused')
    return (source.replace(include,include+'\n#include "hardware/rd_movement_trace.hpp" // '+MARKER,1)
                  .replace(dc,'if(p==0xdc){record_event("INPUT_READ",p,controller_a);'
                              'rd_movement_trace::port(tstates,pc,p,controller_a);return controller_a;}',1)
                  .replace(dd,'record_event("INPUT_READ",p,value);'
                              'rd_movement_trace::port(tstates,pc,p,value);return value;',1))


def install(project: Path) -> list[str]:
    project=Path(project)
    if not (project/'translated.cpp').is_file() or not (project/'generation.json').is_file():
        raise ValueError('Only complete generated native projects may be instrumented')
    changes=[]
    target=project/'hardware/rd_movement_trace.hpp'
    data=HEADER.read_bytes()
    if not target.exists() or target.read_bytes()!=data:
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(data)
        changes.append('hardware/rd_movement_trace.hpp')
    for rel,func in [('live_sms.hpp',live_sms_transform),('runtime.cpp',runtime_transform)]:
        path=project/rel
        if not path.is_file():raise ValueError('Generated project missing '+rel)
        original=path.read_text(encoding='utf8')
        updated=func(original)
        if original!=updated:path.write_text(updated,encoding='utf8');changes.append(rel)
    return changes
