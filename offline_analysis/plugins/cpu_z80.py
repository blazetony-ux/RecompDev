"""Conservative, instruction-length-attested Z80 static decoder.

It follows immediate/relative transfers and recognises selected register and
memory writes for the machine mapping plugin; it is not a semantics-certified
Z80 recompiler. Unusual/ambiguous prefixed forms remain explicit gaps.
"""
from offline_analysis.model import Instruction,Unresolved,AbstractFacts
ANALYSIS_ABI=2

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
            e=fetch(op_pc+1,1)[0];return Instruction(leading+2,mnemonic='CB_BIT_ROTATE',effects={'unknown_memory_write':True,'mem_addr_from':'HL'} if (e&7)==6 and (e>>6)!=1 else {'clear_reg':('HL','DE','BC','A')})
        fetch(op_pc+1,2);return Instruction(leading+3,mnemonic='INDEXED_CB',effects={'unknown_memory_write':True,'clear_reg':('IX','IY','A','BC','DE','HL')})
    if opcode==0xed:
        if prefix is not None:raise Unresolved('Z80_INDEX_PREFIX_WITH_ED_UNQUALIFIED')
        e=fetch(op_pc+1,1)[0]
        n=4 if e in _ED16 else 2
        fetch(op_pc,n)
        if e in (0x45,0x4d):return Instruction(n,'return',mnemonic='RETN/RETI',effects={'stack_pop':True,'interrupt_return':True})
        if e in (0x67,0x6f):
            return Instruction(n,mnemonic='RRD/RLD',
                               effects={'unknown_memory_write':True,'mem_addr_from':'HL','clear_a':True})
        if e in (0xa0,0xa8,0xb0,0xb8):
            # LDI/LDD/LDIR/LDDR write a counted destination interval. The
            # machine plugin tests that interval for mapper overlap. Unknown
            # BC/DE remain unknown, including BC=0's 65536-step repeat.
            return Instruction(n,mnemonic='ED_BLOCK_COPY',effects={
                'unknown_memory_write':True,'mem_addr_from':'DE',
                'copy_count_from':'BC' if e in (0xb0,0xb8) else None,
                'mem_count':None if e in (0xb0,0xb8) else 1,
                'mem_direction':-1 if e in (0xa8,0xb8) else 1,
                'block_copy':True})
        if e in _ED16 and e&8==0:
            addr=int.from_bytes(fetch(op_pc+2,2),'little')
            return Instruction(n,mnemonic='ED_MEM_WRITE',effects={'mem_addr':addr,'mem_width':2})
        return Instruction(n,mnemonic='ED',effects={'clear_reg':('A','BC','DE','HL','SP')})
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
    if opcode in (0x01,0x11,0x21,0x31) and imm is not None:
        effects['set_reg']={0x01:'BC',0x11:'DE',0x21:'IX' if prefix==0xdd else 'IY' if prefix==0xfd else 'HL',0x31:'SP'}[opcode]
        effects['set_value']=imm
    if opcode==0x31 and imm is not None:effects['set_sp']=imm
    if opcode==0x21 and imm is not None and prefix is None:effects['set_hl']=imm
    if opcode==0x11 and imm is not None:effects['set_de']=imm
    if opcode==0x23 and prefix is None:effects['adjust_hl']=1
    if opcode==0x2b and prefix is None:effects['adjust_hl']=-1
    if opcode==0x03:effects['adjust_bc']=1
    if opcode==0x0b:effects['adjust_bc']=-1
    if opcode==0x13:effects['adjust_de']=1
    if opcode==0x1b:effects['adjust_de']=-1
    if prefix is None and opcode in (0x2a,0xe1,0xeb,0x09,0x19,0x29,0x39,0x24,0x25,0x2c,0x2d,0x26,0x2e):
        effects['clear_hl']=True
    if opcode==0xd1:effects['clear_de']=True
    if opcode==0xeb:effects['swap_reg']=('DE','HL')
    if opcode==0xd9:effects['clear_reg']=('BC','DE','HL')
    if opcode in (0xed,) or (opcode==0xed):effects['clear_hl']=True
    if opcode==0x3e and prefix is None:effects['set_a']=imm
    if opcode==0xaf:effects['set_a']=0
    if opcode==0x32 and imm is not None and prefix is None:
        effects['mem_addr']=imm;effects['mem_from_a']=True;effects['mem_value_from']='A'
    if opcode==0x22 and imm is not None and prefix is None:
        effects['mem_addr']=imm;effects['mem_width']=2
    if opcode in (0x02,0x12):
        effects['unknown_memory_write']=True
        effects['mem_value_from']='A'
        effects['mem_addr_from']='BC' if opcode==0x02 else 'DE'
    if opcode in (0x34,0x35) and prefix is None:
        effects['unknown_memory_write']=True;effects['mem_addr_from']='HL'
    if opcode==0xe3:effects['unknown_memory_write']=True;effects['mem_addr_from']='SP';effects['mem_width']=2
    if opcode==0x10:effects['clear_reg']=('BC',)
    if opcode==0xf9:effects['clear_sp']=True
    if opcode in (0x33,0x3b):effects['adjust_sp']=1 if opcode==0x33 else -1
    if opcode==0xe3:effects['clear_hl']=True
    if opcode==0x08:effects['clear_a']=True
    if opcode==0x36:
        effects['unknown_memory_write']=True
        effects['mem_addr_from']='HL' if prefix is None else 'IX' if prefix==0xdd else 'IY'
        effects['mem_value']=imm
        if prefix is not None:effects['mem_displacement']=buf[leading+1]-256 if buf[leading+1]&0x80 else buf[leading+1]
    if opcode in (0x77,0x70,0x71,0x72,0x73,0x74,0x75) and prefix is None:
        effects['unknown_memory_write']=True;effects['mem_addr_from']='HL'
        if opcode==0x77:effects['mem_value_from']='A'
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
    if opcode==0xe9:
        effects['indirect_reg']='HL' if prefix is None else 'IX' if prefix==0xdd else 'IY'
        return Instruction(length,'indirect',effects=effects,mnemonic='JP_HL/IX/IY')
    if opcode==0x76:return Instruction(length,'stop',effects=effects,mnemonic='HALT')
    if opcode in (0xc5,0xd5,0xe5,0xf5):effects['stack_push']=True
    if opcode in (0xc1,0xd1,0xe1,0xf1):
        effects['stack_pop']=True
        effects['clear_reg']=tuple(set(effects.get('clear_reg',()))|{{0xc1:'BC',0xd1:'DE',0xe1:'HL' if prefix is None else 'IX' if prefix==0xdd else 'IY',0xf1:'A'}[opcode]})
    if opcode==0xf9:effects['copy_sp_from']='HL' if prefix is None else 'IX' if prefix==0xdd else 'IY'
    if opcode&0xc7==0xc7:return Instruction(length,'call',opcode&0x38,effects=effects,mnemonic='RST')
    # When A may be overwritten, drop the known value; don't invent a mapper
    # bank identity from a register value that has gone stale. The list is
    # intentionally broad, so incomplete dataflow costs coverage, not safety.
    x=(opcode>>6)&3;y=(opcode>>3)&7;z=opcode&7
    writes_a=(x==1 and y==7 and z!=7) or (x==2 and y!=7) or (x==0 and z in (4,5,6) and y==7) or opcode in (0x3a,0xdb,0xf1,0xc6,0xce,0xd6,0xde,0xe6,0xee,0xf6)
    if (writes_a or opcode in (0x07,0x0a,0x0f,0x17,0x1a,0x1f,0x27,0x2f)) and 'set_a' not in effects:effects['clear_a']=True
    if prefix is None and x==1 and z!=6 and y in (4,5):effects['clear_hl']=True
    if prefix is None and x==1 and z!=6 and y in (0,1,2,3):
        effects['clear_reg']=tuple(set(effects.get('clear_reg',()))|{{0:'BC',1:'BC',2:'DE',3:'DE'}[y]})
    if prefix is None and x==0 and z in (4,5,6) and y in (0,1,2,3):
        effects['clear_reg']=tuple(set(effects.get('clear_reg',()))|{{0:'BC',1:'BC',2:'DE',3:'DE'}[y]})
    if prefix is not None:
        name='IX' if prefix==0xdd else 'IY'
        if opcode in (0x23,0x2b):
            effects['adjust_index']=(name,1 if opcode==0x23 else -1)
        elif opcode not in (0x21,0xe9,0xe5,0xf9) and not (
            disp or (x==1 and y not in (4,5)) or x==2):
            # Only narrow, explicitly understood indexed forms retain IX/IY;
            # unknown writes to IXH/IXL or indexed arithmetic drop the fact.
            effects['clear_reg']=tuple(set(effects.get('clear_reg',()))|{name})
    # Indirect memory writes cannot certify bank persistence with the basic
    # register abstraction. A more precise CPU plugin can replace this one.
    if prefix is not None and disp and (
        (x==1 and z!=6 and y==6) or (x==0 and y==6 and z in (4,5,6))):
        # A known IX/IY plus a signed displacement yields an exact write
        # address. Otherwise the machine plugin still invalidates mapping.
        effects['unknown_memory_write']=True
        effects['mem_addr_from']='IX' if prefix==0xdd else 'IY'
        effects['mem_displacement']=buf[leading+1]-256 if buf[leading+1]&0x80 else buf[leading+1]
    return Instruction(length,effects=effects,mnemonic='Z80')


def initial(image):return AbstractFacts()
def key(state):return state.pairs

def advance(ins,state:AbstractFacts):
    e=ins.effects;cleared=set(e.get('clear_reg',()))
    if e.get('clear_a'):cleared.add('A')
    if e.get('clear_hl'):cleared.add('HL')
    if e.get('clear_de'):cleared.add('DE')
    if e.get('clear_sp'):cleared.add('SP')
    if 'adjust_sp' in e:
        old=state.get('SP');cleared.add('SP')
        if old is not None:update_sp=(old+e['adjust_sp'])&0xffff
        else:update_sp=None
    update={}
    if 'adjust_sp' in e and update_sp is not None:update['SP']=update_sp
    if 'swap_reg' in e:
        a,b=e['swap_reg'];v1=state.get(a);v2=state.get(b)
        cleared.update((a,b))
        if v1 is not None:update[b]=v1
        if v2 is not None:update[a]=v2
    if e.get('copy_sp_from'):
        source=state.get(e['copy_sp_from']);cleared.add('SP')
        if source is not None:update['SP']=source
    if 'set_reg' in e:update[e['set_reg']]=e['set_value']
    if 'set_a' in e:update['A']=e['set_a']
    for reg,effect in (('HL','adjust_hl'),('DE','adjust_de'),('BC','adjust_bc')):
        if effect in e:
            old=state.get(reg);cleared.add(reg)
            if old is not None:update[reg]=(old+e[effect])&0xffff
    if 'adjust_index' in e:
        name,delta=e['adjust_index'];old=state.get(name);cleared.add(name)
        if old is not None:update[name]=(old+delta)&0xffff
    if e.get('block_copy'):
        direction=e['mem_direction'];old_count=state.get('BC')
        count=old_count if e.get('copy_count_from') and old_count is not None else (
            e.get('mem_count') if not e.get('copy_count_from') else None)
        if count==0 and e.get('copy_count_from'):count=65536
        for name in ('HL','DE'):
            old=state.get(name);cleared.add(name)
            if old is not None and count is not None:update[name]=(old+direction*count)&0xffff
        cleared.add('BC')
        if old_count is not None and count is not None:update['BC']=(old_count-count)&0xffff
    if e.get('stack_push') or e.get('stack_pop'):
        old=state.get('SP');cleared.add('SP')
        if old is not None:update['SP']=(old+(-2 if e.get('stack_push') else 2))&0xffff
    return state.change(set_values=update,clear=tuple(cleared))

def indirect(ins,state:AbstractFacts):
    name=ins.effects.get('indirect_reg')
    return state.get(name) if name else None

def lift_probe(raw:bytes,pc:int):
    """A *tiny* independent native-control-flow subset, never complete Z80."""
    if raw==b'\x00':return {'kind':'next'}
    if raw==b'\x76':return {'kind':'stop'}
    if len(raw)==3 and raw[0]==0xc3:
        return {'kind':'jump','target':int.from_bytes(raw[1:],'little')}
    if len(raw)==2 and raw[0]==0x18:
        disp=raw[1]-256 if raw[1]&0x80 else raw[1]
        return {'kind':'jump','target':(pc+2+disp)&0xffff}
    return None
