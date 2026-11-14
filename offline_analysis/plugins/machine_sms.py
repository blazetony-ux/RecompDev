"""Replaceable Sega mapper provider: no ISA decoder or game-specific addresses.

Only this machine plugin knows 0xFFFD..0xFFFF and the cartridge slots. Register
facts are passed from the separate CPU provider, never owned by the mapper.
"""
from __future__ import annotations
from dataclasses import dataclass
from offline_analysis.model import Unresolved,AbstractFacts,ANALYSIS_ABI

@dataclass(frozen=True)
class State:
    banks:tuple[int|None,int|None,int|None]=(0,1,2)

def initial(image):return State()
def key(state):return state.banks

def resolve(image,pc,state):
    if pc<0 or pc>=0xc000:raise Unresolved('ADDRESS_OUTSIDE_CARTRIDGE_WINDOWS')
    if pc<0x400:return pc
    bank=state.banks[pc//0x4000]
    if bank is None:raise Unresolved('ROM_BANK_CONTEXT_UNRESOLVED')
    offset=bank*0x4000+(pc&0x3fff)
    if offset>=image.data_length:raise Unresolved('ROM_BANK_OUTSIDE_SOURCE')
    return offset

def transition(image,ins,state,registers:AbstractFacts):
    effect=ins.effects;banks=list(state.banks);reasons=[]
    addr=effect.get('mem_addr')
    if addr is None and 'mem_addr_from' in effect:
        addr=registers.get(effect['mem_addr_from'])
    if effect.get('unknown_memory_write') or 'mem_addr' in effect:
        # A write whose address is unknown could touch a mapper register.
        if addr is None or effect.get('repeat_write'):
            banks=[None,None,None]
            reasons.append('UNKNOWN_MEMORY_WRITE_MAY_TOUCH_MAPPER')
        else:
            width=effect.get('mem_width',1)
            for i in range(width):
                dest=(addr+i)&0xffff
                # 0xFFFC is cartridge-RAM enable/control; code mapping can
                # change even though it is not a simple ROM bank selector.
                if dest==0xfffc:
                    banks=[None,None,None]
                    reasons.append('MAPPER_CONTROL_WRITE_INVALIDATES_ROM_WINDOW')
                    continue
                if not 0xfffd<=dest<=0xffff:continue
                index=dest-0xfffd
                source=effect.get('mem_value_from')
                value=registers.get(source) if source is not None else effect.get('mem_value')
                if value is None:
                    banks[index]=None;reasons.append('BANK_REGISTER_VALUE_UNRESOLVED')
                else:
                    banks[index]=value%max(1,image.data_length//0x4000)
    if effect.get('stack_push'):
        sp=registers.get('SP')
        if sp is None or any(((sp-d)&0xffff) in range(0xfffc,0x10000) for d in (1,2)):
            banks=[None,None,None]
            reasons.append('STACK_WRITE_MAY_CHANGE_MAPPER')
    return State(tuple(banks)),tuple(reasons)

def inventory(image,data):
    return [{'id':f'bank-{i:03}', 'start':i*0x4000,'bytes':0x4000,
             'role':'unclassified-rom-bank'} for i in range(image.data_length//0x4000)]

def probes(image):
    for bank in range(image.data_length//0x4000):
        if bank in (0,1,2):continue
        yield f'bank-{bank:03}-slot1',0x4000,State((0,bank,2))
        yield f'bank-{bank:03}-slot2',0x8000,State((0,1,bank))
