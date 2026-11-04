"""Static Z80 Ghidra P-code -> C++ *statements*, no CPU interpreter fallback.

Every generated instruction is authenticated to the user's original ROM.
No console ROM bytes or recovered proprietary C++ are shipped in the release.
"""
import hashlib
import json
import re
import shutil
from pathlib import Path

SUPPORTED={'COPY','INT_AND','INT_OR','INT_LEFT','INT_ADD','INT_EQUAL','INT_RIGHT','INT_SRIGHT',
 'INT_SUB','INT_SLESS','INT_XOR','INT_NOTEQUAL','INT_ZEXT','INT_2COMP',
 'INT_CARRY','INT_SCARRY','INT_LESSEQUAL','INT_SBORROW','BOOL_OR','BOOL_XOR',
 'INT_LESS','BOOL_NEGATE','INT_NEGATE','LOAD','STORE','BRANCH','CBRANCH',
 'CALL','RETURN','BRANCHIND','CALLOTHER'}
VALID_SPACES={'register','unique','ram','const','io'}

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def verify_export(doc,rom_path):
    """Bind every instruction to a *physical* ROM address, never an ambiguous CPU PC.

    Bank overlays use explicit provenance: mapped slot, physical bank and image base.
    Original (v0.4.0.3) evidence has no overlay and maps CPU addresses 0..0xbfff
    to physical offsets 0..0xbfff. All instructions are byte-attested.
    """
    if doc.get('language')!='z80:LE:16:default':raise ValueError('Not an authenticated Z80 Ghidra export')
    if doc.get('source_sha256')!=sha256(rom_path):raise ValueError('ROM differs from exported instruction evidence')
    if not isinstance(doc.get('functions'),list) or len(doc['functions'])>2000:raise ValueError('Unbounded function export')
    meta=doc.get('bank_context')
    if meta is not None:
        if not isinstance(meta,dict):raise ValueError('Invalid bank context')
        slot=meta.get('slot');bank=meta.get('bank')
        if type(slot)!=int or slot not in (0,1,2) or type(bank)!=int or not 0<=bank<256:
            raise ValueError('Invalid bank overlay identity')
        if meta.get('base')!=slot*0x4000 or meta.get('physical_start')!=bank*0x4000:
            raise ValueError('Invalid bank overlay physical mapping')
    by_physical={};conflicts=set();bytes_seen=set()
    stat={'candidates':len(doc['functions']),'rejected_padding_functions':0,'ambiguous_addresses':0}
    with open(rom_path,'rb') as rom:raw=rom.read()
    if len(raw)>64*1024*1024:raise ValueError('ROM exceeds native pilot size limit')
    for f in doc['functions']:
        instructions=f.get('instructions',[])
        if not isinstance(instructions,list) or len(instructions)>12000:raise ValueError('Unbounded function body')
        if len(instructions)>=6 and all(i.get('length')==1 and i.get('bytes_sha256')==hashlib.sha256(b'\xff').hexdigest() for i in instructions):
            stat['rejected_padding_functions']+=1;continue
        for i in instructions:
            addr=i.get('address');sz=i.get('length')
            if type(addr)!=int or type(sz)!=int or not 0<=addr<0xc000 or not 1<=sz<=8:
                raise ValueError('Instruction outside Z80 ROM address range')
            if meta:
                base=meta['base'];end=base+0x4000
                if not base<=addr<end or addr+sz>end:raise ValueError('Instruction outside bank overlay window')
                # Slot 0's first 0x400 bytes always come from physical bank 0.
                phys=(addr if meta['slot']==0 and addr<0x400 else meta['physical_start']+(addr-base))
            else:
                if addr+sz>0xc000:raise ValueError('Instruction outside initial 48KB window')
                phys=addr
            if phys+sz>len(raw):raise ValueError('Instruction maps beyond original ROM')
            if hashlib.sha256(raw[phys:phys+sz]).hexdigest()!=i.get('bytes_sha256'):
                raise ValueError('Ghidra instruction bytes mismatch at '+hex(addr)+' physical '+hex(phys))
            if not isinstance(i.get('pcode'),list) or len(i['pcode'])>500:raise ValueError('Unbounded instruction P-code')
            for p in i['pcode']:
                if p.get('op') not in SUPPORTED:continue
                for v in p.get('inputs',[])+([p['output']] if p.get('output') is not None else []):
                    if v.get('space') not in VALID_SPACES or type(v.get('offset'))!=int or type(v.get('size'))!=int or not 1<=v['size']<=8 or v['offset']<0 or v['offset']>2**32:
                        raise ValueError('Invalid P-code varnode')
            i={**i,'physical_offset':phys}
            if phys in by_physical and (by_physical[phys]['length']!=sz or by_physical[phys].get('bytes_sha256')!=i.get('bytes_sha256') or by_physical[phys].get('pcode')!=i.get('pcode')):
                conflicts.add(phys)
            else:by_physical.setdefault(phys,i)
    for a in conflicts:by_physical.pop(a,None)
    stat['ambiguous_addresses']=len(conflicts)
    intervals=set()
    for a,i in by_physical.items():intervals.update(range(a,a+i['length']))
    stat['source_bytes_covered']=len(intervals)
    return by_physical,stat,raw[:0xc000]

def read(v):
    sp=v['space'];a=v['offset'];n=v['size']
    if sp=='const':return str(a)
    if sp=='register':return f's.get_register({a},{n})'
    if sp=='unique':return f's.get_unique({a},{n})'
    if sp=='ram':return f's.memory({a},{n})'
    raise ValueError('Reading unmodelled P-code varnode space '+sp)

def write(v,expr):
    sp=v['space'];a=v['offset'];n=v['size']
    if sp=='register':return f's.set_register({a},{n},{expr});'
    if sp=='unique':return f's.set_unique({a},{n},{expr});'
    if sp=='ram':return f's.write_memory({a},{n},{expr});'
    raise ValueError('Writing unmodelled P-code varnode space '+sp)

def emit_instruction(ins):
    # Z80 DAA is one instruction with internal Ghidra P-code branches; keep
    # these branches local by using the explicit Z80 operation, not CPU jumps.
    # DAA behavioural parity remains unverified without aligned independent reference traces.
    if ins.get('mnemonic')=='DAA':return ['s.decimal_adjust_accumulator();']
    lines=[]
    # Ghidra models conditional CALL/RET with an intra-instruction CBRANCH
    # that skips the remaining stack operations. A linear P-code emitter must
    # guard those operations, not emit them unconditionally.
    control_pcode=ins.get('pcode',[])
    guarded_control=ins.get('mnemonic') in ('CALL','RET') and any(
        p.get('op')=='CBRANCH' for p in control_pcode)
    if guarded_control:
        conditional=[(idx,p) for idx,p in enumerate(control_pcode) if p.get('op')=='CBRANCH']
        next_pc=ins.get('fallthrough')
        branch_index,branch=conditional[0]
        trailing=control_pcode[branch_index+1:]
        expected='CALL' if ins.get('mnemonic')=='CALL' else 'RETURN'
        if (len(conditional)!=1 or len(branch.get('inputs',[]))!=2
            or branch['inputs'][0].get('space')!='ram'
            or branch['inputs'][0].get('offset')!=next_pc
            or not trailing or trailing[-1].get('op')!=expected):
            raise ValueError('Unsupported conditional CALL/RET internal P-code CFG')
    for p in control_pcode:
        op=p['op'];args=p.get('inputs',[]);out=p.get('output')
        if op not in SUPPORTED:
            raise ValueError('P-code operation not supported: '+str(op))
        if op in ('COPY','INT_AND','INT_OR','INT_LEFT','INT_ADD','INT_EQUAL','INT_RIGHT','INT_SRIGHT','INT_SUB','INT_SLESS','INT_XOR','INT_NOTEQUAL','INT_ZEXT','INT_2COMP','INT_CARRY','INT_SCARRY','INT_LESSEQUAL','INT_SBORROW','BOOL_OR','BOOL_XOR','INT_LESS','BOOL_NEGATE','INT_NEGATE'):
            if out is None or not args:raise ValueError('Incomplete P-code ALU output')
            a=read(args[0]);b=read(args[1]) if len(args)>1 else '0'
            lines.append(write(out,f'rd::evaluate(rd::Op::{op}, {a}, {b}, {out["size"]}, {args[0]["size"]}, {args[1]["size"] if len(args)>1 else 1})'))
        elif op=='LOAD':
            if len(args)<2 or out is None:raise ValueError('Bad P-code LOAD')
            addr=read(args[1]);space=p.get('memory_space')
            if space=='ram':expression=f's.memory(static_cast<std::uint16_t>({addr}),{out["size"]})'
            elif space=='io':expression=f's.in(static_cast<std::uint16_t>({addr}))'
            else:raise ValueError('Unsupported memory space in LOAD: '+str(space))
            lines.append(write(out,expression))
        elif op=='STORE':
            if len(args)<3:raise ValueError('Bad P-code STORE')
            addr=read(args[1]);val=read(args[2]);space=p.get('memory_space')
            if space=='ram':lines.append(f's.write_memory(static_cast<std::uint16_t>({addr}),{args[2]["size"]},{val});')
            elif space=='io':lines.append(f's.out(static_cast<std::uint16_t>({addr}), static_cast<std::uint8_t>({val}));')
            else:raise ValueError('Unsupported memory space in STORE: '+str(space))
        elif op in ('BRANCH','CALL','CBRANCH','BRANCHIND','RETURN'):
            if not args:raise ValueError('Missing P-code branch target')
            target= str(args[0]['offset']) if args[0]['space']=='ram' and op!='RETURN' else read(args[0])
            if args[0]['space']=='const':
                raise ValueError('Intra-instruction P-code branching needs instruction-local CFG lowering')
            if op=='CBRANCH':
                if len(args)!=2:raise ValueError('Bad conditional branch')
                if guarded_control:
                    # Branch-to-fallthrough means: condition TRUE skips the
                    # rest of this instruction. Preserve the full conditional
                    # side-effect block, including stack and target-PC updates.
                    lines.append(f'if (!({read(args[1])})) {{')
                else:
                    lines.append(f'if ({read(args[1])}) next = static_cast<std::uint16_t>({target});')
            else:lines.append(f'next = static_cast<std::uint16_t>({target});')
        elif op=='CALLOTHER':
            other=args[0]['offset'] if args and args[0]['space']=='const' else None
            if ins['mnemonic']=='HALT' and other==9:lines.append('s.halted=true;')
            elif ins['mnemonic']=='DI' and other==4:lines.append('s.on_di();')
            elif ins['mnemonic']=='EI' and other==5:lines.append('s.on_ei();')
            elif ins['mnemonic']=='IM' and other==6 and len(args)>1 and args[1]['space']=='const':
                lines.append(f's.interrupt_mode={args[1]["offset"]};')
            else:raise ValueError(f'Unmodelled Z80 user operation {other}: {ins["mnemonic"]}')
    if guarded_control:lines.append('}')
    return lines

def timing_estimate(ins):
    """Approximate T-states only; intentionally not a reference timing oracle."""
    mnemonic=ins.get('mnemonic','')
    if mnemonic in ('LDIR','LDDR','OTIR','OTDR','CPIR','CPDR'):return 21
    if mnemonic in ('LDI','LDD','OUTI','OUTD','CPI','CPD'):return 16
    if mnemonic in ('CALL','RST'):return 17
    if mnemonic in ('RET','RETI','RETN'):return 10
    if mnemonic in ('JR','DJNZ'):return 12
    if mnemonic in ('OUT','IN','PUSH','POP'):return 11
    if mnemonic in ('JP','JP_RESET_SOURCE_ATTESTED'):return 10
    if mnemonic in ('HALT','DI','EI','NOP','INC','DEC'):return 4
    if mnemonic=='IM':return 8
    return 7

def write_if_changed(destination, data):
    """Preserve modification time for byte-identical generated source files.

    CMake can safely reuse unchanged translation units instead of rebuilding
    the entire generated native program after a newly recovered bank overlay.
    """
    destination=Path(destination)
    payload=data.encode('utf-8') if isinstance(data,str) else data
    if destination.is_file() and destination.read_bytes()==payload:
        return False
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_bytes(payload)
    return True


def copy_if_changed(source,destination):
    source=Path(source)
    return write_if_changed(destination,source.read_bytes())


def generate_project(doc,rom_path,out,bank_docs=()):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    by_pc,stat,head=verify_export(doc,rom_path)
    bank_summaries=[]
    for bank_doc in bank_docs:
        if not bank_doc.get('bank_context'):raise ValueError('Bank document missing mapped overlay provenance')
        if bank_doc.get('source_sha256')!=doc.get('source_sha256') or bank_doc.get('target_id')!=doc.get('target_id'):
            raise ValueError('Bank export source/target identity mismatch')
        recovered,bstats,_=verify_export(bank_doc,rom_path)
        for physical,ins in recovered.items():
            if physical in by_pc and (by_pc[physical].get('bytes_sha256')!=ins.get('bytes_sha256') or by_pc[physical].get('pcode')!=ins.get('pcode')):
                raise ValueError('Conflicting bank evidence at physical '+hex(physical))
            by_pc.setdefault(physical,ins)
        bank_summaries.append({'slot':bank_doc['bank_context']['slot'],'bank':bank_doc['bank_context']['bank'],
            'instructions':len(recovered),'candidate_functions':bstats['candidates']})
    # Source-attested reset JP -- initial Ghidra may not export the reset vector.
    reset_added=False
    if 0 not in by_pc and len(head)>=3 and head[0]==0xc3:
        target=head[1]|(head[2]<<8)
        by_pc[0]={'address':0,'physical_offset':0,'length':3,'fallthrough':None,'mnemonic':'JP_RESET_SOURCE_ATTESTED',
                  'pcode':[{'op':'BRANCH','inputs':[{'space':'ram','offset':target,'size':1}]}]}
        reset_added=True
    code=['#include "runtime.hpp"','#include "z80_cycles.hpp"','#include <array>','#include <cstdint>','#include <string>',
          'bool execute_native_instruction(rd::State &s){',
          'const auto physical=s.rom_offset(s.pc);',
          'switch(physical){']
    supported=0;unsupported=[];emitted_offsets=[]
    for physical,i in sorted(by_pc.items()):
        try:lines=emit_instruction(i)
        except (ValueError,KeyError,TypeError) as exc:
            unsupported.append({'pc':i['address'],'physical_offset':physical,'reason':str(exc),'mnemonic':i.get('mnemonic','')})
            continue
        supported+=1;emitted_offsets.append(physical)
        pc=i['address'];nextpc=i.get('fallthrough')
        if nextpc is None:nextpc=(pc+i['length'])&0xffff
        code.append(f'case 0x{physical:x}u: {{std::uint16_t next=0x{nextpc:04x};s.last_instruction_cycles={timing_estimate(i)};')
        code.append(f'std::array<std::uint8_t,8> source_bytes{{}};for(unsigned b=0;b<{i["length"]};++b)source_bytes[b]=s.read_byte(std::uint16_t(0x{pc:04x} + b));')
        code.extend(lines)
        if i.get('mnemonic')=='RETN':code.append('s.iff1=s.iff2;')
        code.append(f'const auto t=recomp::z80::decode([&](std::uint16_t a){{return source_bytes[std::uint16_t(a-0x{pc:04x})&7];}},std::uint16_t(0x{pc:04x}),next,std::uint16_t(0x{nextpc:04x}));')
        code.append('if(t.known){s.last_instruction_cycles=t.tstates;++s.qualified_timing_instructions;}else{++s.unqualified_timing_instructions;}')
        code.append('s.pc=next;return true;}')
    code+=['default: s.stopped="UNTRANSLATED_PHYSICAL_ROM_OFFSET";return false;', '}}']
    write_if_changed(out/'translated.cpp','\n'.join(code)+'\n')
    origin=Path(__file__).resolve().parent
    hardware=origin.parent/'systems'/'mastersystem'
    # Hardware implementation is a console plug-in, not part of shared P-code
    # lowering. Other systems must supply their own runtime, not reuse SMS.
    for name in ('runtime.hpp','runtime.cpp','counters.hpp','main.cpp','interactive.cpp','live_sms.hpp','z80_cycles.hpp','CMakeLists.txt'):
        src=(hardware if name.startswith('runtime.') or name=='counters.hpp' else origin)/name
        copy_if_changed(src,out/name)
    # The portable hardware contract is vendored with each generated project;
    # no machine-local source-tree dependency and no original ROM bytes.
    shared_hardware=origin.parent/'hardware'
    for relative in ('core.hpp','image_io.hpp','wav.hpp','input_replay.hpp','runtime.hpp','continuous.hpp','backends.hpp','win32_window.hpp','win32_audio.hpp','adapters/sms.hpp'):
        destination=out/'hardware'/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        copy_if_changed(shared_hardware/relative,destination)
    intervals=set()
    for phys,i in by_pc.items():intervals.update(range(phys,phys+i['length']))
    stat.update(schema='recomp-native-pilot-generator-v0.4.0.9',original_source_sha256=doc['source_sha256'],
                source_size=Path(rom_path).stat().st_size,all_candidate_instructions=len(by_pc),
                translated_instructions=supported,unsupported_instructions=len(unsupported),
                sample_unsupported=unsupported[:60],source_attested_reset_jp=reset_added,
                synthetic_reset_jump=False,source_bytes_covered=len(intervals),
                initial_window_bytes=min(0xc000,Path(rom_path).stat().st_size),
                bank_count=(Path(rom_path).stat().st_size+0x3fff)//0x4000,
                recovered_bank_overlays=bank_summaries,
                report_caveat='Physical bank-qualified C++ dispatch. Unsupported/missing code stops. Approximate NTSC IM0/IM1 IRQ; no reference parity, precise frame timing or verified gameplay.')
    write_if_changed(out/'unsupported-offsets.json',json.dumps({'source_sha256':doc['source_sha256'],'unsupported':unsupported},separators=(',',':'))+'\n')
    write_if_changed(out/'emitted-offsets.json',json.dumps({'source_sha256':doc['source_sha256'],'physical_offsets':emitted_offsets},separators=(',',':'))+'\n')
    write_if_changed(out/'generation.json',json.dumps(stat,indent=2)+'\n')
    return stat
