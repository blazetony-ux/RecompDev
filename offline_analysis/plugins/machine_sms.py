"""SMS banked source mapper. All bank policies live here, never in the engine.

Source candidate exploration does not imply any bank is definitely executable.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
from offline_analysis.model import Unresolved
ANALYSIS_ABI=1

@dataclass(frozen=True)
class State:
    banks: tuple[int|None,int|None,int|None] = (0,1,2)
    a: int|None = None
    sp: int|None = None
    hl: int|None = None
    de: int|None = None

def initial(image): return State()
def key(state): return f'{state.banks}/{state.a}/{state.sp}/{state.hl}/{state.de}'
def resolve(image,pc,state):
    if pc<0 or pc>=0xc000: raise Unresolved('ADDRESS_OUTSIDE_CARTRIDGE_WINDOWS')
    if pc<0x400: return pc
    bank=state.banks[pc//0x4000]
    if bank is None: raise Unresolved('ROM_BANK_CONTEXT_UNRESOLVED')
    offset=bank*0x4000+(pc&0x3fff)
    if offset>=image.data_length:raise Unresolved('ROM_BANK_OUTSIDE_SOURCE')
    return offset

def transition(image,ins,state):
    effect=ins.effects
    banks=list(state.banks);a=state.a;sp=state.sp;hl=state.hl;de=state.de
    reasons=[]
    if 'set_a' in effect:a=effect['set_a']
    elif effect.get('clear_a'): a=None
    if 'set_sp' in effect:sp=effect['set_sp']
    elif effect.get('clear_sp'):sp=None
    if 'set_hl' in effect:hl=effect['set_hl']
    elif 'adjust_hl' in effect and hl is not None:hl=(hl+effect['adjust_hl'])&65535
    elif effect.get('clear_hl'):hl=None
    if 'set_de' in effect:de=effect['set_de']
    elif 'adjust_de' in effect and de is not None:de=(de+effect['adjust_de'])&65535
    elif effect.get('clear_de'):de=None
    if effect.get('stack_push'):
        if sp is None or (sp-2)&0xffff in (0xfffc,0xfffd,0xfffe,0xffff):
            banks=[None,None,None]
            reasons.append('STACK_WRITE_MAY_CHANGE_MAPPER')
        else:sp=(sp-2)&0xffff
    if effect.get('stack_pop') and sp is not None:sp=(sp+2)&0xffff
    addr=effect.get('mem_addr')
    if addr is not None:
        width=effect.get('mem_width',1)
        for dest in ((addr+i)&0xffff for i in range(width)):
            if not 0xfffd<=dest<=0xffff:continue
            index=dest-0xfffd
            value=a if effect.get('mem_from_a') and width==1 else effect.get('mem_value')
            if value is None:
                banks[index]=None
                reasons.append('BANK_REGISTER_VALUE_UNRESOLVED')
            else:
                banks[index]=value % max(1,image.data_length//0x4000)
    if effect.get('unknown_memory_write'):
        origin=effect.get('mem_addr_from')
        known={'HL':hl,'DE':de,'SP':sp}.get(origin)
        # Even a known address in RAM is safe only if it cannot be a mapper
        # register. Repeated writes have an unknown length, so invalidate.
        if known is None or known>=0xfffc or effect.get('repeat_write'):
            banks=[None,None,None]
            reasons.append('UNKNOWN_MEMORY_WRITE_MAY_TOUCH_MAPPER')
    return State(tuple(banks),a,sp,hl,de),tuple(reasons)

def inventory(image,data):
    return [{'id':f'bank-{i:03}', 'start':i*0x4000,'bytes':0x4000,
             'role':'unclassified-rom-bank'} for i in range(image.data_length//0x4000)]

def probes(image):
    """Non-authoritative candidate seeds for never-executed banks.

    No guessed bank entry is treated as confirmed executable code.
    """
    for bank in range(image.data_length//0x4000):
        if bank in (0,1,2):continue
        yield f'bank-{bank:03}-slot1', 0x4000, State((0,bank,2))
        yield f'bank-{bank:03}-slot2', 0x8000, State((0,1,bank))
