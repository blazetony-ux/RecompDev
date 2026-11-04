"""Bounded, ISA-specific source-supported recovery of local constant transfers.

Not an emulator, global constant propagation, or proof of a function boundary.
No guesses for unknown register states, switch tables or unproven CFG joins.
"""
import hashlib
from collections import defaultdict


def _signed16(value):
    return value - 0x10000 if value & 0x8000 else value


def _mips_linear_constants(pc, rs, bytes_at, fallthrough_only, max_window=8):
    """Prove a register constant through a unique straight-line predecessor window.

    Conservative transfer rules only; unknown register writes, load or control
    transfers break the proof. These are static *candidates*, not runtime facts.
    """
    chain=[]; cursor=pc
    for _ in range(max_window):
        prev=cursor-4
        if not fallthrough_only(cursor,prev):break
        raw=bytes_at(prev)
        if raw is None or len(raw)!=4:break
        w=int.from_bytes(raw,'little'); op=w>>26; fn=w&63
        # Stop rather than guess across loads, stores, coprocessor operations,
        # branches or unsupported ALU instructions (including code mutation).
        if (op==0 and fn not in (0,2,3,32,33,35,36,37,38,39)) or (op!=0 and op not in (8,9,10,11,12,13,14,15)):
            break
        chain.insert(0,(prev,w))
        cursor=prev
    constants={0:0}; writers={}
    support={0:[]}
    for address,w in chain:
        op=w>>26; a=(w>>21)&31; b=(w>>16)&31; d=(w>>11)&31; imm=w&65535; fn=w&63
        target=None; val=None; parents=[]
        if op==15:target=b;val=imm<<16
        elif op in (9,13) and a in constants:
            target=b;val=((constants[a]+_signed16(imm)) if op==9 else (constants[a]|imm))&0xffffffff
            parents=support.get(a,[])
        elif op==0 and fn in (32,33,35,36,37,38) and a in constants and b in constants:
            target=d
            if fn in (32,33):val=(constants[a]+constants[b])&0xffffffff
            elif fn==35:val=(constants[a]-constants[b])&0xffffffff
            elif fn==36:val=constants[a]&constants[b]
            elif fn==37:val=constants[a]|constants[b]
            else:val=constants[a]^constants[b]
            parents=list(dict.fromkeys([*support.get(a,[]),*support.get(b,[])]))
        elif op==0 and fn in (0,2,3) and a==0 and b in constants:
            target=d; sh=(w>>6)&31
            if fn==0:val=(constants[b]<<sh)&0xffffffff
            elif fn==2:val=constants[b]>>sh
            else:
                sv=constants[b] if constants[b]<0x80000000 else constants[b]-0x100000000
                val=(sv>>sh)&0xffffffff
            parents=support.get(b,[])
        # Known instructions with destination register overwrite prior constants.
        # Loads and most ALU operations are represented as unknown writes.
        if target is None:
            if op in (8,10,11,12,14):target=b
            elif op==0 and fn in (39,):target=d
        if target is not None and target!=0:
            constants.pop(target,None);support.pop(target,None)
            if val is not None:
                constants[target]=val;support[target]=list(dict.fromkeys([*parents,address]))
    if rs in constants and support.get(rs):
        selected=support[rs]
        if len(selected)<=10:return constants[rs],selected
    return None,None


def recover(image, decode, decoded, edges, barriers):
    """Return candidate mapping {pc: evidence}, using only decoded input bytes.

    An edge is added only when its target is mapped, decodable, properly aligned,
    and its transfer source has a locally explicit constant value. For register
    patterns every input edge to the relevant instruction must be the observed
    fallthrough predecessor. Never infer a register value across a branch join.
    """
    incoming=defaultdict(set)
    for edge in edges:
        if edge['target'] is not None and edge['kind']!='delay_slot':
            incoming[edge['target']].add((edge['source'],edge['kind']))
    reachable={r['address'] for r in decoded}
    problems={b['address'] for b in barriers}

    def bytes_at(pc):
        if pc not in reachable: return None
        ins=decode(pc)
        return ins.bytes if ins is not None else None

    def fallthrough_only(pc, prev):
        return incoming.get(pc)=={(prev,'fallthrough')}

    recovered={}
    for pc in sorted(problems & reachable):
        raw=bytes_at(pc)
        if not raw:continue
        target=None; pattern=None; support=[]
        if image.isa=='m68k' and len(raw)>=2:
            word=int.from_bytes(raw[:2],'big')
            if (word & 0xffc0) not in (0x4e80,0x4ec0):continue
            mode=(word>>3)&7;reg=word&7
            if mode==7 and reg==2 and len(raw)==4:
                # JMP/JSR d16(PC) uses the extension word's address as PC.
                target=(pc+2+_signed16(int.from_bytes(raw[2:4],'big')))&0xffffffff
                pattern='m68k_pc_relative_d16';support=[pc]
            elif mode==2:
                # Only a contiguous, uniquely reached immediate register setup.
                for length in (6,4):
                    p=pc-length
                    if not fallthrough_only(pc,p):continue
                    before=bytes_at(p)
                    if before is None or len(before)!=length:continue
                    op=int.from_bytes(before[:2],'big')
                    if length==6 and op==0x207c+(reg<<9):
                        target=int.from_bytes(before[2:6],'big')
                        pattern='m68k_movea_immediate';support=[p,pc];break
                    if length==6 and op==0x41f9+(reg<<9):
                        target=int.from_bytes(before[2:6],'big')
                        pattern='m68k_lea_absolute_long';support=[p,pc];break
                    if length==4 and op==0x41f8+(reg<<9):
                        target=_signed16(int.from_bytes(before[2:4],'big'))&0xffffffff
                        pattern='m68k_lea_absolute_word';support=[p,pc];break
                    if length==4 and op==0x41fa+(reg<<9):
                        target=(p+2+_signed16(int.from_bytes(before[2:4],'big')))&0xffffffff
                        pattern='m68k_lea_pc_relative';support=[p,pc];break
        elif image.isa=='mips' and len(raw)==4:
            w=int.from_bytes(raw,'little')
            if (w>>26)!=0 or (w&63) not in (8,9):continue
            rs=(w>>21)&31
            if rs==0:
                target=0;pattern='mips_zero_register';support=[pc]
            elif rs!=31:
                p=pc-4
                if fallthrough_only(pc,p):
                    before=bytes_at(p)
                    if before is not None and len(before)==4:
                        a=int.from_bytes(before,'little');op=a>>26
                        rt=(a>>16)&31;source=(a>>21)&31;imm=a&0xffff
                        if rt==rs and op==15 and source==0:
                            target=(imm<<16)&0xffffffff
                            pattern='mips_lui';support=[p,pc]
                        elif rt==rs and source==0 and op in (9,13):
                            target=(_signed16(imm) if op==9 else imm)&0xffffffff
                            pattern='mips_constant_from_zero';support=[p,pc]
                        elif rt==rs and source==rs and op in (9,13):
                            p0=p-4
                            if fallthrough_only(p,p0):
                                pre=bytes_at(p0)
                                if pre is not None and len(pre)==4:
                                    b=int.from_bytes(pre,'little')
                                    if b>>26==15 and (b>>16)&31==rs and (b>>21)&31==0:
                                        hi=(b&0xffff)<<16
                                        target=(hi+_signed16(imm) if op==9 else hi|imm)&0xffffffff
                                        pattern='mips_lui_addiu' if op==9 else 'mips_lui_ori'
                                        support=[p0,p,pc]
            if target is None and rs not in (0,31):
                target,selected=_mips_linear_constants(pc,rs,bytes_at,fallthrough_only)
                if target is not None:
                    support=[*selected,pc];pattern='mips_linear_constant_propagation'
        if target is None or not image.valid(target):continue
        target_ins=decode(target)
        if target_ins is None:continue
        source_ins=decode(pc)
        if source_ins is None:continue
        proof=[{'address':a,'sha256':hashlib.sha256(bytes_at(a)).hexdigest()} for a in support]
        recovered[pc]={'target':target,'kind':'direct_call' if (image.isa=='m68k' and (int.from_bytes(raw[:2],'big')&0xffc0)==0x4e80) or (image.isa=='mips' and (int.from_bytes(raw,'little')&63)==9) else 'direct_jump',
                       'pattern':pattern,'support':proof,'target_instruction_sha256':hashlib.sha256(target_ins.bytes).hexdigest(),
                       'confidence':'source_local_constant_candidate_not_executed'}
    return recovered
