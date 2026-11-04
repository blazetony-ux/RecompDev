"""Separately written Python test oracle; not a production independent emulator.

Intentionally decodes opcodes independently from the C++ static lowerer.
"""
def run(raw,base=0):
    if not raw or len(raw)%2:raise ValueError('Invalid words')
    d=[0]*8;pc=base;steps=0
    while pc<base+len(raw):
        op=(raw[pc-base]<<8)|raw[pc-base+1];steps+=1
        if op==0x4e75:
            if pc!=base+len(raw)-2:raise ValueError('Unreachable trailing data')
            return {'pc':pc,'steps':steps,'registers':d}
        if op>>12==7 and (op&0x100)==0:
            n=op&255
            if n&128:n-=256
            d[(op>>9)&7]=n&0xffffffff
        elif (op&0xf1f8)==0x5080:
            amount=((op>>9)&7) or 8
            d[op&7]=(d[op&7]+amount)&0xffffffff
        elif (op&0xf1f8)==0x5180:
            amount=((op>>9)&7) or 8
            d[op&7]=(d[op&7]-amount)&0xffffffff
        else:raise ValueError('Unsupported oracle opcode '+hex(op))
        pc+=2
    raise ValueError('Missing RTS')
