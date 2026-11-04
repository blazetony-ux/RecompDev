"""Replaceable ISA control-flow descriptors. No instruction execution or hardware."""
from dataclasses import dataclass
from .isa import m68k_flow, signed

@dataclass
class Flow:
    kind: str
    edges: list
    barrier: str | None = None
    delay_slot: bool = False


def classify(image,ins):
    if image.isa=='m68k':
        kind, edges, reason=m68k_flow(image,ins)
        if kind in ('indirect_call','indirect_jump'):
            edges=[(None,kind)]
        return Flow(kind,edges,reason,False)
    if image.isa!='mips':
        raise ValueError('ISA flow adapter unavailable')
    if len(ins.bytes)!=4:
        return Flow('invalid',[],'MIPS instruction not four bytes')
    w=int.from_bytes(ins.bytes,'little');op=w>>26;func=w&63; rs=(w>>21)&31;rt=(w>>16)&31
    pc=ins.address;after=pc+8
    branch_target=pc+4+(signed(w&0xffff,16)<<2)
    jump_target=((pc+4)&0xf0000000)|((w&0x03ffffff)<<2)
    if op==3: return Flow('call',[(jump_target,'direct_call'),(after,'return_site')],delay_slot=True)
    if op==2: return Flow('jump',[(jump_target,'direct_jump')],delay_slot=True)
    if op in (4,5,6,7):return Flow('conditional',[(branch_target,'taken'),(after,'fallthrough')],delay_slot=True)
    if op==1:
        if rt in (0,1):return Flow('conditional',[(branch_target,'taken'),(after,'fallthrough')],delay_slot=True)
        return Flow('unresolved_branch',[],f'ISA-variant/REGIMM encoding 0x{rt:x} not qualified',True)
    if op==0 and func==8:
        if rs==31:return Flow('return',[],delay_slot=True)
        return Flow('indirect_jump',[(None,'indirect_jump')], 'register jump target unknown',True)
    if op==0 and func==9:
        return Flow('indirect_call',[(None,'indirect_call'),(after,'return_site')], 'register call target unknown',True)
    if op==0 and func in (12,13):return Flow('exception',[],'system call/break; no dynamic execution')
    return Flow('sequential',[(pc+4,'fallthrough')])
