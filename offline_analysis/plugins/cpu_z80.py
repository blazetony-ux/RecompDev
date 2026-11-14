"""Conservative, instruction-length-attested Z80 static decoder.

It follows immediate/relative transfers and recognises selected register and
memory writes for the machine mapping plugin; it is not a semantics-certified
Z80 recompiler. Unusual/ambiguous prefixed forms remain explicit gaps.
"""
from offline_analysis.model import Instruction,Unresolved
ANALYSIS_ABI=1

_IMM8={0x06,0x0e,0x16,0x1e,0x26,0x2e,0x36,0x3e,0x10,0x18,0x20,0x28,0x30,0x38,
       0xc6,0xce,0xd6,0xde,0xe6,0xee,0xf6,0xfe,0xd3,0xdb}
_IMM16={0x01,0x11,0x21,0x31,0x22,0x2a,0x32,0x3a,0xc3,0xcd,
        0xc2,0xca,0xd2,0xda,0xe2,0xea,0xf2,0xfa,
        0xc4,0xcc,0xd4,0xdc,0xe4,0xec,0xf4,0xfc}
_ED16={0x43,0x4b,0x53,0x5b,0x63,0x6b,0x73,0x7b}

def decode(fetch,pc):
    start=pc;prefix=None;raw=fetch(pc,1);opcode=raw[0]
    # Up to two repeated index prefixes: register names change but the base
    # instruction length remains verifiable. Arbitrary prefix streams do not.
    for _ in range(2):
        if opcode not in (0xdd,0xfd):break
        prefix=opcode;pc+=1;opcode=fetch(pc,1)[0]
    if opcode in (0xdd,0xfd):raise Unresolved('REPEATED_Z80_INDEX_PREFIX_LIMIT')
    op_pc=pc;leading=pc-start
    if opcode==0xcb:
        if prefix is None:
            fetch(op_pc+1,1);return Instruction(leading+2,mnemonic='CB_BIT_ROTATE')
        fetch(op_pc+1,2);return Instruction(leading+3,mnemonic='INDEXED_CB')
    if opcode==0xed:
        if prefix is not None:raise Unresolved('Z80_INDEX_PREFIX_WITH_ED_UNQUALIFIED')
        e=fetch(op_pc+1,1)[0]
        n=4 if e in _ED16 else 2
        fetch(op_pc,n)
        if e in (0x45,0x4d):return Instruction(n,'return',mnemonic='RETN/RETI',effects={'stack_pop':True})
        if e in (0xa0,0xa8,0xb0,0xb8):
            return Instruction(n,mnemonic='ED_BLOCK_COPY',effects={'unknown_memory_write':True,'mem_addr_from':'DE','repeat_write':e in (0xb0,0xb8),'clear_hl':True,'clear_de':True})
        if e in _ED16 and e&8==0:
            addr=int.from_bytes(fetch(op_pc+2,2),'little')
            return Instruction(n,mnemonic='ED_MEM_WRITE',effects={'mem_addr':addr,'mem_width':2})
        return Instruction(n,mnemonic='ED')
    disp=0
    if prefix is not None:
        x=(opcode>>6)&3;y=(opcode>>3)&7;z=opcode&7
        uses_indexed_memory=(x==1 and opcode!=0x76 and (y==6 or z==6)) or (x==2 and z==6) or (x==0 and y==6 and z in (4,5,6))
        if uses_indexed_memory:disp=1
    data_bytes=2 if opcode in _IMM16 else 1 if opcode in _IMM8 else 0
    length=leading+1+disp+data_bytes
    buf=fetch(start,length)
    data_offset=leading+1+disp
    imm=(int.from_bytes(buf[data_offset:data_offset+2],'little') if data_bytes==2 else
         buf[data_offset] if data_bytes==1 else None)
    effects={}
    if opcode==0x31 and imm is not None:effects['set_sp']=imm
    if opcode==0x21 and imm is not None and prefix is None:effects['set_hl']=imm
    if opcode==0x11 and imm is not None:effects['set_de']=imm
    if opcode==0x23 and prefix is None:effects['adjust_hl']=1
    if opcode==0x2b and prefix is None:effects['adjust_hl']=-1
    if opcode==0x13:effects['adjust_de']=1
    if opcode==0x1b:effects['adjust_de']=-1
    if prefix is None and opcode in (0x2a,0xe1,0xeb,0x09,0x19,0x29,0x39,0x24,0x25,0x2c,0x2d,0x26,0x2e):
        effects['clear_hl']=True
    if opcode in (0xd1,0xeb):effects['clear_de']=True
    if opcode in (0xed,) or (opcode==0xed):effects['clear_hl']=True
    if opcode==0x3e and prefix is None:effects['set_a']=imm
    if opcode==0xaf:effects['set_a']=0
    if opcode==0x32 and imm is not None and prefix is None:
        effects['mem_addr']=imm;effects['mem_from_a']=True
    if opcode==0x22 and imm is not None and prefix is None:
        effects['mem_addr']=imm;effects['mem_width']=2
    if opcode in (0x02,0x12):
        effects['unknown_memory_write']=True
        effects['mem_addr_from']='BC' if opcode==0x02 else 'DE'
    if opcode in (0x34,0x35) and prefix is None:
        effects['unknown_memory_write']=True;effects['mem_addr_from']='HL'
    if opcode==0xe3:effects['unknown_memory_write']=True;effects['mem_addr_from']='SP'
    if opcode==0xf9:effects['clear_sp']=True
    if opcode==0x08:effects['clear_a']=True
    if opcode==0x36 and prefix is None:
        effects['unknown_memory_write']=True;effects['mem_addr_from']='HL'
    if opcode in (0x77,0x70,0x71,0x72,0x73,0x74,0x75) and prefix is None:
        effects['unknown_memory_write']=True;effects['mem_addr_from']='HL'
    if opcode in (0xcd,0xc4,0xcc,0xd4,0xdc,0xe4,0xec,0xf4,0xfc) or opcode&0xc7==0xc7:
        effects['stack_push']=True
    if opcode in (0xc9,0xc0,0xc8,0xd0,0xd8,0xe0,0xe8,0xf0,0xf8):
        effects['stack_pop']=True
    if opcode==0xc3:return Instruction(length,'jump',imm,effects=effects,mnemonic='JP')
    if opcode in (0xc2,0xca,0xd2,0xda,0xe2,0xea,0xf2,0xfa):
        return Instruction(length,'branch',imm,True,effects=effects,mnemonic='JP_cc')
    if opcode==0xcd:return Instruction(length,'call',imm,effects=effects,mnemonic='CALL')
    if opcode in (0xc4,0xcc,0xd4,0xdc,0xe4,0xec,0xf4,0xfc):
        return Instruction(length,'call',imm,True,effects=effects,mnemonic='CALL_cc')
    if opcode in (0x18,0x20,0x28,0x30,0x38,0x10):
        offset=imm-256 if imm&0x80 else imm
        target=(start+length+offset)&0xffff
        return Instruction(length,'jump' if opcode==0x18 else 'branch',target,
                           opcode!=0x18,effects=effects,mnemonic='JR/DJNZ')
    if opcode in (0xc9,0xc0,0xc8,0xd0,0xd8,0xe0,0xe8,0xf0,0xf8):
        return Instruction(length,'return',conditional=(opcode!=0xc9),effects=effects,mnemonic='RET')
    if opcode==0xe9:return Instruction(length,'indirect',effects=effects,mnemonic='JP_HL/IX/IY')
    if opcode==0x76:return Instruction(length,'stop',effects=effects,mnemonic='HALT')
    if opcode&0xc7==0xc7:return Instruction(length,'call',opcode&0x38,effects=effects,mnemonic='RST')
    # When A may be overwritten, drop the known value; don't invent a mapper
    # bank identity from a register value that has gone stale. The list is
    # intentionally broad, so incomplete dataflow costs coverage, not safety.
    x=(opcode>>6)&3;y=(opcode>>3)&7;z=opcode&7
    writes_a=(x==1 and y==7 and z!=7) or x==2 or (x==0 and z in (4,5,6) and y==7) or opcode in (0x3a,0xdb,0xf1,0xc6,0xce,0xd6,0xde,0xe6,0xee,0xf6,0xfe)
    if writes_a and 'set_a' not in effects:effects['clear_a']=True
    if prefix is None and x==1 and z!=6 and y in (4,5):effects['clear_hl']=True
    # Indirect memory writes cannot certify bank persistence with the basic
    # register abstraction. A more precise CPU plugin can replace this one.
    if prefix is not None and disp and x==1 and z!=6 and y==6:
        effects['unknown_memory_write']=True
    return Instruction(length,effects=effects,mnemonic='Z80')
