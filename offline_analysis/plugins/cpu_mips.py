"""MIPS R3000A static length/flow decoder (not a semantic CPU emulator)."""
from offline_analysis.model import Instruction, Unresolved,AbstractFacts
ANALYSIS_ABI=2

def decode(fetch,pc):
    if pc&3: raise Unresolved('MIPS_UNALIGNED_PC')
    w=int.from_bytes(fetch(pc,4),'little')
    op=w>>26;rs=(w>>21)&31;rt=(w>>16)&31;fn=w&63
    nextpc=(pc+4)&0xffffffff
    if op in (2,3):
        target=(nextpc&0xf0000000)|((w&0x03ffffff)<<2)
        return Instruction(4,'call' if op==3 else 'jump',target,delay_slots=1,
                           effects={'link_reg':('R31',(pc+8)&0xffffffff)} if op==3 else {},
                           mnemonic='JAL' if op==3 else 'J')
    if op==0:
        if fn in (8,9):
            rd=(w>>11)&31
            eff={'indirect_reg':'R'+str(rs)}
            if fn==9:eff['link_reg']=('R'+str(rd),(pc+8)&0xffffffff)
            return Instruction(4,'return' if fn==8 and rs==31 else
                               'call' if fn==9 else 'indirect',delay_slots=1,
                               effects=eff,mnemonic='JR/JALR')
        if fn in (12,13):return Instruction(4,'stop',mnemonic='SYSCALL/BREAK')
        if fn in (0,2,3,4,6,7,16,17,18,19,32,33,34,35,36,37,38,39,42,43):
            # Only constant-fold operations with fully verified operand interpretation.
            if fn in (0,2,3) and rs==0:
                return Instruction(4,mnemonic='SHIFT',effects={'constant_op':('shift',rs,rt,(w>>11)&31,(w>>6)&31,fn)})
            if fn in (33,35,36,37,38,39,42,43):
                return Instruction(4,mnemonic='MIPS_REGISTER_ALU',
                                   effects={'constant_op':('alu',rs,rt,(w>>11)&31,0,fn)})
            if fn in (4,6,7):
                return Instruction(4,mnemonic='MIPS_VARIABLE_SHIFT',
                                   effects={'constant_op':('variable_shift',rs,rt,(w>>11)&31,0,fn)})
            return Instruction(4,mnemonic='SPECIAL',effects={'clear_reg':('R'+str((w>>11)&31),)})
        raise Unresolved('UNSUPPORTED_MIPS_SPECIAL_FUNCTION')
    if op in (1,4,5,6,7):
        if op==1 and rt not in (0,1,16,17):raise Unresolved('UNSUPPORTED_REGIMM_VARIANT')
        imm=w&65535
        if imm&0x8000:imm-=65536
        target=(pc+4+(imm<<2))&0xffffffff
        return Instruction(4,'branch',target,conditional=True,delay_slots=1,
                           effects={'link_reg':('R31',(pc+8)&0xffffffff)} if op==1 and rt in (16,17) else {},mnemonic='MIPS_BRANCH')
    if op==16 and rs==16 and fn==16:return Instruction(4,'indirect',mnemonic='RFE_PRIVILEGED_STATE')
    if op==15 and rs!=0:
        raise Unresolved('UNSUPPORTED_MIPS_RESERVED_LUI_ENCODING')
    if op in (8,9,10,11,12,13,14,15,32,33,34,35,36,37,38,39,40,41,42,43,46):
        eff={'clear_reg':('R'+str(rt),)}
        if op in (8,9,10,11,12,13,14,15):eff={'immediate_op':(op,rs,rt,w&65535)}
        return Instruction(4,effects=eff,mnemonic='MIPS_32BIT_WORD')
    raise Unresolved('UNSUPPORTED_MIPS_OPCODE')


def initial(image):return AbstractFacts((('R0',0),))
def key(state):return state.pairs
def advance(ins,state:AbstractFacts):
    e=ins.effects;new={};clear=set(e.get('clear_reg',()))
    if 'link_reg' in e:
        r,v=e['link_reg'];new[r]=v
    if 'immediate_op' in e:
        op,rs,rt,imm=e['immediate_op'];r='R'+str(rt)
        src=state.get('R'+str(rs))
        value=None
        if op==15:value=(imm<<16)&0xffffffff
        elif src is not None:
            signed=imm-65536 if imm&32768 else imm
            if op in (8,9):
                total=(src if src<0x80000000 else src-0x100000000)+signed
                # Signed ADDI overflows trap; silently wrapping and following
                # the next instruction would invent an execution path.
                if op==8 and not -0x80000000<=total<=0x7fffffff:
                    raise Unresolved('MIPS_ADDI_OVERFLOW_EXCEPTION_UNQUALIFIED')
                value=total&0xffffffff
            elif op==10:value=int((src if src<0x80000000 else src-0x100000000)<signed)
            elif op==11:value=int(src<(signed&0xffffffff))
            elif op==12:value=src&imm
            elif op==13:value=src|imm
            elif op==14:value=src^imm
        elif op==8:
            raise Unresolved('MIPS_ADDI_POSSIBLE_OVERFLOW_UNQUALIFIED')
        clear.add(r)
        if value is not None:new[r]=value
    if 'constant_op' in e:
        op,rs,rt,rd,shift,fn=e['constant_op'];r='R'+str(rd)
        l=state.get('R'+str(rs));v=state.get('R'+str(rt))
        clear.add(r)
        if op=='shift' and v is not None:
            new[r]=((v<<shift) if fn==0 else (v>>shift) if fn==2 else
                    ((v if v<0x80000000 else v-0x100000000)>>shift))&0xffffffff
        elif op=='variable_shift' and l is not None and v is not None:
            sh=l&31
            new[r]=((v<<sh) if fn==4 else (v>>sh) if fn==6 else
                    ((v if v<0x80000000 else v-0x100000000)>>sh))&0xffffffff
        elif op=='alu' and l is not None and v is not None:
            signed_l=l if l<0x80000000 else l-0x100000000
            signed_r=v if v<0x80000000 else v-0x100000000
            new[r]={33:lambda:(l+v)&0xffffffff,
                    35:lambda:(l-v)&0xffffffff,36:lambda:l&v,
                    37:lambda:l|v,38:lambda:l^v,
                    39:lambda:(~(l|v))&0xffffffff,
                    42:lambda:int(signed_l<signed_r),
                    43:lambda:int(l<v)}[fn]()
    clear.discard('R0');new.pop('R0',None)
    return state.change(set_values=new,clear=tuple(clear))

def indirect(ins,state:AbstractFacts):
    reg=ins.effects.get('indirect_reg')
    return state.get(reg) if reg else None
