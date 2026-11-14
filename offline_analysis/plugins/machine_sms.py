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

def _destinations(effect,registers):
    """Return definitely-written 16-bit addresses, or None if not provable.

    Bounded by Z80's 16-bit BC and pointer wrap. This provider alone owns
    mapper register addresses; CPU decoders only declare memory effects.
    """
    address=effect.get('mem_addr')
    if address is None and 'mem_addr_from' in effect:
        address=registers.get(effect['mem_addr_from'])
    if address is None:return None
    address=(address+effect.get('mem_displacement',0))&0xffff
    count=effect.get('mem_count',effect.get('mem_width',1))
    if effect.get('copy_count_from'):
        count=registers.get(effect['copy_count_from'])
        if count==0:count=65536
    if not isinstance(count,int) or count<1 or count>65536:return None
    direction=effect.get('mem_direction',1)
    # Only four bytes can affect the SMS mapper. Constant-time alias test
    # even for the BC=0 / 65536-copy wraparound case.
    impacted=[target for target in range(0xfffc,0x10000)
              if (((target-address)*direction)&0xffff) < count]
    return impacted,count

def transition(image,ins,state,registers:AbstractFacts):
    effect=ins.effects;banks=list(state.banks);reasons=[]
    if effect.get('unknown_memory_write') or 'mem_addr' in effect:
        destinations=_destinations(effect,registers)
        if destinations is None:
            banks=[None,None,None]
            reasons.append('UNKNOWN_MEMORY_WRITE_MAY_TOUCH_MAPPER')
        else:
            impacted,width=destinations
            for dest in impacted:
                if dest==0xfffc:
                    banks=[None,None,None]
                    reasons.append('MAPPER_CONTROL_WRITE_INVALIDATES_ROM_WINDOW')
                elif 0xfffd<=dest<=0xffff:
                    index=dest-0xfffd
                    # Multi-byte stores, block copies and computed stores
                    # cannot infer their payload from an unrelated register.
                    source=effect.get('mem_value_from')
                    known=registers.get(source) if source else effect.get('mem_value')
                    if width>1 or effect.get('block_copy'):known=None
                    if known is None:
                        banks[index]=None
                        reasons.append('BANK_REGISTER_VALUE_UNRESOLVED')
                    else:
                        banks[index]=known%max(1,image.data_length//0x4000)
    if effect.get('stack_push'):
        sp=registers.get('SP')
        # Stack writes use SP-1 and SP-2, even when the updated CPU facts
        # reflect the decremented SP. A known safe stack never affects mapper.
        if sp is None or any(((sp-d)&0xffff)>=0xfffc for d in (1,2)):
            banks=[None,None,None]
            reasons.append('STACK_WRITE_MAY_CHANGE_MAPPER')
    return State(tuple(banks)),tuple(sorted(set(reasons)))

def inventory(image,data):
    return [{'id':f'bank-{i:03}', 'start':i*0x4000,'bytes':0x4000,
             'role':'unclassified-rom-bank'} for i in range(image.data_length//0x4000)]

def probes(image):
    for bank in range(image.data_length//0x4000):
        if bank in (0,1,2):continue
        yield f'bank-{bank:03}-slot1',0x4000,State((0,bank,2))
        yield f'bank-{bank:03}-slot2',0x8000,State((0,1,bank))
