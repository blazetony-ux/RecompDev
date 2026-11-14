"""Conservative 68000 static decoder for control transfers and simple words.

Variable-length instructions not covered here are recorded UNRESOLVED, not
mistaken for one-word instructions. This is NOT a full 68000 decoder.
"""
from offline_analysis.model import Instruction, Unresolved,AbstractFacts
ANALYSIS_ABI=2

def decode(fetch,pc):
    if pc&1:raise Unresolved('M68000_UNALIGNED_PC')
    w=int.from_bytes(fetch(pc,2),'big')
    if w==0x4e71:return Instruction(2,mnemonic='NOP')
    if w==0x4e75:return Instruction(2,'return',mnemonic='RTS',effects={'stack_bytes':4})
    if w in (0x4e73,0x4e77):raise Unresolved('M68000_EXCEPTION_RETURN_CONTEXT_UNQUALIFIED')
    if w==0x4e72:return Instruction(4,'stop',mnemonic='STOP')
    if w in (0x4ef9,0x4eb9):
        target=int.from_bytes(fetch(pc+2,4),'big')
        return Instruction(6,'call' if w==0x4eb9 else 'jump',target,
                           effects={'stack_bytes':-4} if w==0x4eb9 else {},mnemonic='JSR/JMP_ABSL')
    if w in (0x4ef8,0x4eb8):
        value=int.from_bytes(fetch(pc+2,2),'big')
        if value&0x8000:value-=0x10000
        return Instruction(4,'call' if w==0x4eb8 else 'jump',value&0xffffffff,
                           effects={'stack_bytes':-4} if w==0x4eb8 else {},mnemonic='JSR/JMP_ABSW')
    if w in (0x4efa,0x4eba):
        disp=int.from_bytes(fetch(pc+2,2),'big')
        if disp&0x8000:disp-=0x10000
        return Instruction(4,'call' if w==0x4eba else 'jump',(pc+2+disp)&0xffffffff,
                           effects={'stack_bytes':-4} if w==0x4eba else {},mnemonic='JSR/JMP_PC')
    if (w&0xf000)==0x6000:
        cond=(w>>8)&15;lo=w&255
        if lo==0:
            disp=int.from_bytes(fetch(pc+2,2),'big');disp=disp-0x10000 if disp&0x8000 else disp;length=4
        elif lo==0xff:
            # 0xFF is -1 on the 68000 (long displacement is 68020+).
            disp=-1;length=2
        else:
            disp=lo-256 if lo&0x80 else lo;length=2
        target=(pc+2+disp)&0xffffffff
        if cond==0:return Instruction(length,'jump',target,mnemonic='BRA')
        if cond==1:return Instruction(length,'call',target,effects={'stack_bytes':-4},mnemonic='BSR')
        return Instruction(length,'branch',target,True,mnemonic='Bcc')
    if w&0xf100==0x7000:
        imm=w&255;imm=imm-256 if imm&128 else imm
        return Instruction(2,mnemonic='MOVEQ',effects={'reg_set':('D'+str((w>>9)&7),imm&0xffffffff)})
    if w&0xf1ff==0x41fa: # LEA d16(PC),An: base PC is extension word
        dest='A'+str((w>>9)&7)
        displacement=int.from_bytes(fetch(pc+2,2),'big',signed=True)
        return Instruction(4,mnemonic='LEA_PC_DISP',
                           effects={'reg_set':(dest,(pc+2+displacement)&0xffffffff)})
    if w&0xf1f8==0x41d0: # LEA (An),Am: no memory read
        dest='A'+str((w>>9)&7)
        return Instruction(2,mnemonic='LEA_An',effects={'reg_copy':(dest,'A'+str(w&7))})
    if w&0xf1ff in (0x207c,0x307c): # MOVEA.L/W #immediate,An
        dest='A'+str((w>>9)&7)
        if w&0xf1ff==0x207c:
            value=int.from_bytes(fetch(pc+2,4),'big');length=6
        else:
            value=int.from_bytes(fetch(pc+2,2),'big',signed=True)&0xffffffff;length=4
        return Instruction(length,mnemonic='MOVEA_IMMEDIATE',effects={'reg_set':(dest,value)})
    if w&0xf1f8 in (0x5080,0x5180,0x5088,0x5188):
        # ADDQ/SUBQ.L to Dn or An, never a guessed memory E/A mode.
        delta=(w>>9)&7
        if delta==0:delta=8
        if w&0x0100:delta=-delta
        reg=('A' if w&8 else 'D')+str(w&7)
        return Instruction(2,mnemonic='ADDQ/SUBQ_LONG',effects={'reg_adjust':(reg,delta)})
    if w&0xfff8==0x4280: # CLR.L Dn
        return Instruction(2,mnemonic='CLR_LONG',effects={'reg_set':('D'+str(w&7),0)})
    if w&0xfff8==0x4a80: # TST.L Dn only affects condition flags
        return Instruction(2,mnemonic='TST_LONG')
    if w&0xf1ff==0x41f9: # LEA absolute long, An
        dest='A'+str((w>>9)&7)
        value=int.from_bytes(fetch(pc+2,4),'big')
        return Instruction(6,mnemonic='LEA_ABSL',effects={'reg_set':(dest,value)})
    if (w&0xfff8) in (0x4e90,0x4ed0):
        return Instruction(2,'call' if w&0xfff8==0x4e90 else 'indirect',
                           effects={'indirect_reg':'A'+str(w&7),
                                    **({'stack_bytes':-4} if w&0xfff8==0x4e90 else {})},mnemonic='JSR/JMP_An')
    if w in (0x4e70,0x4e76):return Instruction(2,'stop',mnemonic='RESET/TRAPV')
    if 0x4e40<=w<=0x4e4f:return Instruction(2,'indirect',mnemonic='TRAP_VECTOR')
    # Never guess the instruction length of an unknown 68000 instruction.
    raise Unresolved('M68000_INSTRUCTION_LENGTH_UNVERIFIED')


def initial(image):
    sp=image.details.get('initial_sp')
    return AbstractFacts((('A7',sp&0xffffffff),)) if type(sp)==int else AbstractFacts()
def key(state):return state.pairs
def advance(ins,state):
    effect=ins.effects
    changes={}
    reg=effect.get('reg_set')
    if reg:changes[reg[0]]=reg[1]
    clear=[]
    if 'reg_copy' in effect:
        dst,src=effect['reg_copy']
        value=state.get(src);clear.append(dst)
        if value is not None:changes[dst]=value
    if 'reg_adjust' in effect:
        dst,delta=effect['reg_adjust']
        value=state.get(dst);clear.append(dst)
        if value is not None:changes[dst]=(value+delta)&0xffffffff
    if 'stack_bytes' in effect:
        old=state.get('A7');clear.append('A7')
        if old is not None:changes['A7']=(old+effect['stack_bytes'])&0xffffffff
    return state.change(set_values=changes,clear=tuple(clear))
def indirect(ins,state):
    reg=ins.effects.get('indirect_reg')
    return state.get(reg) if reg else None

def lift_probe(raw:bytes,pc:int):
    """Proof-only NOP/BRA/STOP 68000 control flow, not machine semantics."""
    if raw==b'\x4e\x71':return {'kind':'next'}
    if len(raw)==2:
        word=int.from_bytes(raw,'big')
        if word&0xf100==0x7000:
            imm=word&255
            if imm&128:imm-=256
            return {'kind':'reg','register':'D'+str((word>>9)&7),
                    'width':32,'op':'set','value':imm&0xffffffff}
        if word&0xf1f8 in (0x5080,0x5180):
            value=(word>>9)&7
            if value==0:value=8
            if word&0x0100:value=-value
            return {'kind':'reg','register':'D'+str(word&7),
                    'width':32,'op':'add','value':value}
        if word&0xfff8==0x4280:
            return {'kind':'reg','register':'D'+str(word&7),
                    'width':32,'op':'set','value':0}
    if len(raw)==4 and raw[:2]==b'\x4e\x72':return {'kind':'stop'}
    if raw and raw[0]==0x60:
        if len(raw)==2 and raw[1]!=0:
            disp=raw[1]-256 if raw[1]&0x80 else raw[1]
        elif len(raw)==4 and raw[1]==0:
            disp=int.from_bytes(raw[2:],'big',signed=True)
        else:return None
        return {'kind':'jump','target':(pc+2+disp)&0xffffffff}
    return None
