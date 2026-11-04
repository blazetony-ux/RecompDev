"""ISA-specific decode and flow adapters, independent of the shared catalogue."""
import re

def make_capstone(isa, endian):
    try:
        import capstone as cs
    except ImportError as err:
        raise ValueError('Capstone Python binding missing; install with: py -3 -m pip install capstone') from err
    if isa == 'm68k' and endian == 'big':
        engine = cs.Cs(cs.CS_ARCH_M68K, cs.CS_MODE_M68K_000 | cs.CS_MODE_BIG_ENDIAN)
    elif isa == 'mips' and endian == 'little':
        # MIPS32 disassembly is a permissive discovery oracle. PS1 ISA subset
        # and execution semantics require separate validation.
        engine = cs.Cs(cs.CS_ARCH_MIPS, cs.CS_MODE_MIPS32 | cs.CS_MODE_LITTLE_ENDIAN)
    else:
        raise ValueError('no decoder adapter for this ISA/endian pair')
    engine.detail = False
    return engine


def signed(x,bits):
    return x-(1<<bits) if x & (1<<(bits-1)) else x


def m68k_flow(image, ins):
    """Conservative direct-flow identification based on encoded forms.

    Never extrapolate an indirect edge, unknown exception, or code/data boundary.
    Returns flow_kind, list[(target,kind)], unresolved_reason.
    """
    word = int.from_bytes(ins.bytes[:2],'big')
    next_pc=ins.address+ins.size
    # Short / word-displacement branch family, 68000 base-PC is opcode+2.
    if (word & 0xF000) == 0x6000:
        if (word & 0xff) == 0:
            if ins.size != 4 or len(ins.bytes) < 4:
                return 'branch', [], 'malformed branch extension'
            disp=signed(int.from_bytes(ins.bytes[2:4],'big'),16)
        elif ins.size == 2:
            disp=signed(word & 0xff,8)
        else:
            return 'branch', [], 'unsupported branch encoding'
        target=ins.address+2+disp
        cond=(word>>8)&0xf
        if cond == 0: return 'jump', [(target,'direct_jump')], None
        if cond == 1: return 'call', [(target,'direct_call'),(next_pc,'return_site')], None
        return 'conditional', [(target,'taken'),(next_pc,'fallthrough')], None
    if word in (0x4e75, 0x4e73, 0x4e77):
        return 'return', [], None
    if word in (0x4e72,0x4afc) or (word & 0xfff0) == 0x4e40:
        return 'terminator', [], 'exception or processor stop requires runtime evidence'
    # DBcc: DBcc Dn,d16 ; PC base = opcode+2
    if (word & 0xf0f8)==0x50c8 and ins.size==4:
        disp=signed(int.from_bytes(ins.bytes[2:4],'big'),16)
        return 'conditional', [(ins.address+2+disp,'taken'),(next_pc,'fallthrough')], None
    # JMP/JSR: only direct absolute address candidates.
    if (word & 0xffc0) in (0x4ec0, 0x4e80):
        is_call=(word & 0xffc0)==0x4e80
        mode=(word>>3)&7; reg=word&7
        target=None
        if mode==7 and reg==0 and len(ins.bytes)>=4:
            target=signed(int.from_bytes(ins.bytes[2:4],'big'),16)&0xffffffff
        elif mode==7 and reg==1 and len(ins.bytes)>=6:
            target=int.from_bytes(ins.bytes[2:6],'big')
        if target is None:
            return ('indirect_call' if is_call else 'indirect_jump'),[], 'indirect transfer target unknown'
        return ('call' if is_call else 'jump'), ([(target,'direct_call'),(next_pc,'return_site')] if is_call else [(target,'direct_jump')]), None
    return 'sequential',[(next_pc,'fallthrough')],None


def mips_flow(image, ins):
    # No invented delay-slot traversal. The generic pipeline must eventually
    # supply proper delay-slot semantics from a MIPS-specific adapter.
    w=int.from_bytes(ins.bytes[:4],'little')
    op=w>>26
    if op in (2,3,4,5,6,7,1) or (op==0 and (w&63) in (8,9)):
        return 'control_transfer',[], 'MIPS branch/jump delay slot not yet traversed'
    if op==0 and (w&63) in (12,13):
        return 'exception',[], 'MIPS trap/syscall execution not modelled'
    return 'sequential',[(ins.address+ins.size,'fallthrough')],None


def classify_operands(opstr):
    # Lexical operand shapes ONLY: not calling convention / semantics.
    if not opstr.strip():
        return []
    pieces=[]; depth=0; buf=''
    for c in opstr:
        if c==',' and depth==0:
            pieces.append(buf.strip());buf='';continue
        buf+=c
        if c=='(':depth+=1
        elif c==')':depth=max(0,depth-1)
    if buf.strip():pieces.append(buf.strip())
    def kind(t):
        t=t.lower().strip()
        if re.fullmatch(r'[%$]?(?:d|a)[0-7]',t):return 'register'
        if re.fullmatch(r'\$?(?:zero|at|v[01]|a[0-3]|t[0-9]|s[0-8]|sp|gp|fp|ra|k[01])',t):return 'register'
        if t.startswith('#'):return 'immediate'
        if re.search(r'\(.*\)',t):return 'memory_or_pc_relative'
        if re.fullmatch(r'\$?(?:0x)?[0-9a-f]+(?:\.[bwl])?',t):return 'absolute_or_displacement'
        if re.fullmatch(r'\$?(?:d|a)\d[-/](?:d|a)\d',t):return 'register_list'
        if t in ('ccr','sr','usp','pc'):return 'special_register'
        return 'unclassified'
    return [kind(x) for x in pieces]




def flow_for(isa):
    plugins={'m68k':m68k_flow,'mips':mips_flow}
    try:return plugins[isa]
    except KeyError as e:raise ValueError(f'ISA flow plugin unavailable: {isa}') from e
