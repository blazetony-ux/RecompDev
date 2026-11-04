"""Tiny Motorola 68000 static-lowering backend for owner-authored fixtures.

Supported: MOVEQ Dn,#imm; ADDQ.L/SUBQ.L #n,Dn; RTS. No flags,
interrupts, memory, subroutines, or general ROM recompilation. Unknown opcodes
are refused. The native binary contains one C++ statement per decoded guest
instruction (not an interpreter or opcode-dispatch loop).
"""
import hashlib
import json
from pathlib import Path

SCHEMA='recomp-m68k-restricted-static-v1'

def decode(raw,base=0):
    if not raw or len(raw)%2:raise ValueError('M68K fixture must contain complete big-endian words')
    instructions=[]
    for off in range(0,len(raw),2):
        op=int.from_bytes(raw[off:off+2],'big');pc=base+off
        if op==0x4e75:cmd=('RTS',0,0)
        elif op & 0xf100==0x7000:
            imm=op&255
            if imm>=128:imm-=256
            cmd=('MOVEQ',(op>>9)&7,imm)
        elif op&0xf1f8 in (0x5080,0x5180):
            count=(op>>9)&7 or 8
            cmd=('SUBQ' if op&0x0100 else 'ADDQ',op&7,count)
        else:raise ValueError('Unsupported m68k instruction at '+hex(pc)+': '+hex(op))
        instructions.append((pc,*cmd))
    if instructions[-1][1]!='RTS':raise ValueError('Fixture must end in RTS')
    if any(x[1]=='RTS' for x in instructions[:-1]):raise ValueError('No unreachable trailing words supported')
    return instructions

def lower(source,output,base=0):
    source=Path(source).resolve(strict=True);raw=source.read_bytes()
    if len(raw)>65536:raise ValueError('Fixture too large')
    ins=decode(raw,base)
    dest=Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
    statements=[]
    for pc,op,reg,val in ins:
        if op=='MOVEQ':stat=f'd[{reg}]=static_cast<uint32_t>({val});'
        elif op=='ADDQ':stat=f'd[{reg}]+=uint32_t({val});'
        elif op=='SUBQ':stat=f'd[{reg}]-=uint32_t({val});'
        else:stat=''
        if stat:statements.append(f'  {stat} // m68k PC=0x{pc:x}')
    # Generated source includes no original ROM bytes, only lowering statements.
    code='''// Generated restricted 68000 native instruction lowering. No external ROM embedded.
#include <cstdint>
#include <iostream>
int main(){
  uint32_t d[8]={};
'''+'\n'.join(statements)+f'''\n  std::cout << "{{\\"pc\\":{ins[-1][0]},\\"steps\\":{len(ins)},\\"registers\\":[";
  for(int i=0;i<8;i++){{if(i)std::cout<<","; std::cout<<d[i];}}
  std::cout<<"]}}\\n";
  return 0;
}}
'''
    dest.write_text(code,encoding='utf-8')
    return {'schema':SCHEMA,'source_sha256':hashlib.sha256(raw).hexdigest(),
            'source_bytes':len(raw),'instructions':len(ins),'output':str(dest),
            'status':'STATIC_LOWERING_GENERATED_NOT_EXECUTED',
            'limitations':'No flags, memory, jumps, interrupts, peripherals or arbitrary code. Synthetic fixtures only.'}
