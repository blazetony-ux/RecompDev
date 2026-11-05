"""Source-attested native CPU diagnostics adapter, staged only in generated game.

This file is the first hardware-side provider of controller's generic event ABI.
The monitor has no dependency on this or any other provider.
"""
from pathlib import Path

HEADER=Path(__file__).resolve().parent/'bridge'/'rd_execution_events.hpp'
MARKER='RECOMPDEV_CONTROLLER_EXECUTION_PROVIDER_V1'

def live_transform(source: str) -> str:
    if MARKER in source:
        return source
    include='#include "runtime.hpp"'
    # The generated native project uses an exact, preserved live_sms.hpp.
    # This is the only producer bridge; never modify translated.cpp.
    if include not in source:
        include='#include "hardware/continuous.hpp"'
    transition='  history_[written_%history_.size()]=t;++written_;'
    rendering='  return recomp::hw::sms::render_mode4(state_.vram,state_.cram,state_.vdp_regs,state_.tstates,state_.frames);'
    input_anchor='  state_.apply_host_input(in.buttons);'
    for label, anchor in [('include',include),('transition',transition),('render',rendering),('input',input_anchor)]:
        if source.count(anchor)!=1:
            raise ValueError('Unexpected native machine source '+label+' anchor; no instrumentation applied')
    source=source.replace(include,include+'\n#include "hardware/rd_execution_events.hpp" // '+MARKER,1)
    source=source.replace(transition,
        '  rd_execution_events::transition("z80",t.step,t.cycles,state_.frames,t.before,t.after,t.sp_before,t.physical,\n'
        '    t.physical<state_.rom.size()?state_.rom[t.physical]:0,t.opcode_class,kind);\n'+transition,1)
    source=source.replace(rendering,
        '  rd_execution_events::frame(state_.frames,state_.tstates,state_.steps);\n'+rendering,1)
    source=source.replace(input_anchor,
        '  rd_execution_events::input(state_.tstates,in.buttons);\n'+input_anchor,1)
    return source


def install(project: Path) -> list[str]:
    project=Path(project)
    if not (project/'translated.cpp').is_file() or not (project/'generation.json').is_file():
        raise ValueError('Not an authenticated generated game project')
    target=project/'hardware/rd_execution_events.hpp'
    target.parent.mkdir(exist_ok=True,parents=True)
    changes=[]
    if not target.exists() or target.read_bytes()!=HEADER.read_bytes():
        target.write_bytes(HEADER.read_bytes())
        changes.append('hardware/rd_execution_events.hpp')
    native=project/'live_sms.hpp'
    raw=native.read_text(encoding='utf8')
    result=live_transform(raw)
    if raw!=result:
        native.write_text(result,encoding='utf8')
        changes.append('live_sms.hpp')
    return changes
