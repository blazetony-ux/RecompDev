"""Conservative 68000 static decoder for control transfers and simple words.

Variable-length instructions not covered here are recorded UNRESOLVED, not
mistaken for one-word instructions. This is NOT a full 68000 decoder.
"""
from offline_analysis.model import Instruction, Unresolved
ANALYSIS_ABI=1

def decode(fetch,pc):
    if pc&1:raise Unresolved('M68000_UNALIGNED_PC')
    w=int.from_bytes(fetch(pc,2),'big')
    if w==0x4e71:return Instruction(2,mnemonic='NOP')
    if w in (0x4e75,0x4e73,0x4e77):return Instruction(2,'return',mnemonic='RTS/RTE/RTR')
    if w==0x4e72:return Instruction(4,'stop',mnemonic='STOP')
    if w in (0x4ef9,0x4eb9):
        target=int.from_bytes(fetch(pc+2,4),'big')
        return Instruction(6,'call' if w==0x4eb9 else 'jump',target,mnemonic='JSR/JMP_ABSL')
    if w in (0x4ef8,0x4eb8):
        value=int.from_bytes(fetch(pc+2,2),'big')
        if value&0x8000:value-=0x10000
        return Instruction(4,'call' if w==0x4eb8 else 'jump',value&0xffffffff,mnemonic='JSR/JMP_ABSW')
    if w in (0x4efa,0x4eba):
        disp=int.from_bytes(fetch(pc+2,2),'big')
        if disp&0x8000:disp-=0x10000
        return Instruction(4,'call' if w==0x4eba else 'jump',(pc+2+disp)&0xffffffff,mnemonic='JSR/JMP_PC')
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
        if cond==1:return Instruction(length,'call',target,mnemonic='BSR')
        return Instruction(length,'branch',target,True,mnemonic='Bcc')
    if w&0xf100==0x7000:return Instruction(2,mnemonic='MOVEQ')
    if w in (0x4e70,0x4e76):return Instruction(2,'stop',mnemonic='RESET/TRAPV')
    if 0x4e40<=w<=0x4e4f:return Instruction(2,'indirect',mnemonic='TRAP_VECTOR')
    # Never guess the instruction length of an unknown 68000 instruction.
    raise Unresolved('M68000_INSTRUCTION_LENGTH_UNVERIFIED')
