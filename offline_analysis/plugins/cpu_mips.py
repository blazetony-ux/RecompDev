"""MIPS R3000A static length/flow decoder (not a semantic CPU emulator)."""
from offline_analysis.model import Instruction, Unresolved
ANALYSIS_ABI=1

def decode(fetch,pc):
    if pc&3: raise Unresolved('MIPS_UNALIGNED_PC')
    w=int.from_bytes(fetch(pc,4),'little')
    op=w>>26;rs=(w>>21)&31;rt=(w>>16)&31;fn=w&63
    nextpc=(pc+4)&0xffffffff
    if op in (2,3):
        target=(nextpc&0xf0000000)|((w&0x03ffffff)<<2)
        return Instruction(4,'call' if op==3 else 'jump',target,delay_slots=1,mnemonic='JAL' if op==3 else 'J')
    if op==0:
        if fn in (8,9):return Instruction(4,'indirect',delay_slots=1,mnemonic='JR/JALR')
        if fn in (12,13):return Instruction(4,'stop',mnemonic='SYSCALL/BREAK')
        if fn in (0,2,3,4,6,7,16,17,18,19,32,33,34,35,36,37,38,39,42,43):return Instruction(4,mnemonic='SPECIAL')
        raise Unresolved('UNSUPPORTED_MIPS_SPECIAL_FUNCTION')
    if op in (1,4,5,6,7):
        if op==1 and rt not in (0,1,16,17):raise Unresolved('UNSUPPORTED_REGIMM_VARIANT')
        imm=w&65535
        if imm&0x8000:imm-=65536
        target=(pc+4+(imm<<2))&0xffffffff
        return Instruction(4,'branch',target,conditional=True,delay_slots=1,mnemonic='MIPS_BRANCH')
    if op==16 and rs==16 and fn==16:return Instruction(4,'indirect',mnemonic='RFE_PRIVILEGED_STATE')
    if op in (8,9,10,11,12,13,14,15,32,33,34,35,36,37,38,39,40,41,42,43,46):
        return Instruction(4,mnemonic='MIPS_32BIT_WORD')
    raise Unresolved('UNSUPPORTED_MIPS_OPCODE')
