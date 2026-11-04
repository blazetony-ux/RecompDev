"""Optional, independent original-M68K vs generated-C++ sample comparison.

This compares named general registers and changed memory bytes for ONE deterministic
starting state. It cannot establish full CPU-state, temporal or gameplay parity.
MIPS is intentionally blocked pending validated delay/load-delay handling.
"""
from __future__ import annotations
import sys
from pathlib import Path as _Path
sys.path.insert(0,str(_Path(__file__).resolve().parents[1]))
import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
from adapters.formats import open_image
from native_batch import sha_file


def verify(dbfile, source, manifest_path, stack=0xff8000, max_instructions=1000):
    manifest_path=Path(manifest_path).resolve();d=json.loads(manifest_path.read_text(encoding='utf-8'))
    if d['schema'] not in ('recomp-function-job-v0.3.1','recomp-function-job-v0.3.2','recomp-function-job-v0.3.2.3'):raise ValueError('not a function job manifest')
    if d['compile_status']=='COMPILED_HARDWARE_TRACE_SMOKE_ONLY':
        return {'status':'HARDWARE_EVENT_TRACE_ONLY_NOT_CPU_PARITY'}
    if d['compile_status'] not in ('COMPILED_RUNNER_SMOKE_ONLY','COMPILED_SEEDED_SMOKE_ONLY'):return {'status':'NOT_COMPILED'}
    if not d['source_instruction_hashes_verified']:return {'status':'SOURCE_BYTES_NOT_VERIFIED'}
    if sha_file(source)!=d['source_sha256']:raise ValueError('original source SHA256 changed')
    con=sqlite3.connect(str(dbfile));con.row_factory=sqlite3.Row
    try:target=con.execute('SELECT * FROM targets WHERE target_id=?',(d['target_id'],)).fetchone()
    finally:con.close()
    if target is None or target['source_sha256']!=d['source_sha256']:raise ValueError('catalogue identity mismatch')
    if target['isa']!='m68k':return {'status':'MIPS_DELAY_OR_OTHER_ISA_NOT_QUALIFIED'}
    if target['system_tag']!='megadrive':return {'status':'M68K_CONTAINER_NOT_QUALIFIED'}
    image=open_image(Path(source).read_bytes(),'megadrive')
    fields=d.get('register_fields',[])
    if not fields:return {'status':'NO_NAMED_REGISTER_FIELDS'}
    try:
        from unicorn import Uc,UC_ARCH_M68K,UC_MODE_BIG_ENDIAN,UC_HOOK_MEM_WRITE
        from unicorn import m68k_const
    except ImportError:return {'status':'UNICORN_DEPENDENCY_NOT_INSTALLED'}
    initial={}; unsupported=[]
    for r in fields:
        name=r['name'].upper()
        if r['size']!=4 or (name!='SR' and not (len(name)==2 and name[0] in ('D','A') and name[1] in '01234567')):
            unsupported.append(name);continue
        key='UC_M68K_REG_'+name
        reg=getattr(m68k_const,key,None)
        if reg is None:unsupported.append(name);continue
        initial[name]=r
    if not initial:return {'status':'NO_COMPARABLE_FULL_WIDTH_GPR'}
    uc=Uc(UC_ARCH_M68K,UC_MODE_BIG_ENDIAN)
    # Mega Drive ROM is mapped from zero, not from its first executable instruction.
    mapping=((len(image.data)+4095)//4096)*4096
    uc.mem_map(0,max(mapping,4096));uc.mem_write(0,image.data)
    # Owner-independent scratch RAM, not the real Mega Drive hardware bus.
    # Match the same deterministic, explicitly zero-seeded 64 KiB RAM
    # window used by the standalone C++ sample runner. NOT a console bus.
    stack_region=stack & ~4095
    uc.mem_map(0xff0000,0x10000)
    stop=stack_region+0x80  # Unexecuted return sentinel, mapped in scratch RAM.
    uc.mem_write(stack,stop.to_bytes(4,'big'))
    for name in initial:
        reg=getattr(m68k_const,'UC_M68K_REG_'+name)
        if name=='A7':uc.reg_write(reg,stack)
        elif name=='SR':
            # Unicorn starts in supervisor mode; use its actual initial SR.
            pass
        else:uc.reg_write(reg,0)
    uc.reg_write(m68k_const.UC_M68K_REG_A7,stack)
    base_values={}
    for name in initial:
        base_values[name]=int(uc.reg_read(getattr(m68k_const,'UC_M68K_REG_'+name)))
    # Generated CPU-state has Ghidra register offsets, not Unicorn register IDs.
    runner=manifest_path.with_name('function.exe' if os.name=='nt' else 'function')
    if not runner.is_file():return {'status':'GENERATED_RUNNER_NOT_FOUND','path':str(runner)}
    args=[str(runner),'--image',str(Path(source).resolve()),'0','0',str(len(image.data)),
          '--megadrive-bus',f'm:{stack}:4:{stop}']
    for name,r in initial.items():args.append(f'{r["offset"]}:{r["size"]}:{base_values[name]}')
    try:
        cpp=subprocess.run(args,capture_output=True,text=True,timeout=10,check=False,errors='replace')
    except (subprocess.TimeoutExpired,OSError) as exc:return {'status':'NATIVE_RUNTIME_FAILED','reason':type(exc).__name__}
    if cpp.returncode:return {'status':'NATIVE_RUNTIME_FAILED','reason':cpp.stderr[-500:]}
    native_reg={};native_mem={}
    for line in cpp.stdout.splitlines():
        parts=line.split()
        if len(parts)!=4:continue
        if parts[0]=='MEM':native_mem[int(parts[1])]=int(parts[3]);continue
        if parts[0] in initial and int(parts[1])==initial[parts[0]]['offset'] and int(parts[2])==4:
            native_reg[parts[0]]=int(parts[3])
    observed_mem=set()
    def watch(_uc,_access,address,size,value,_user):
        observed_mem.update(range(address,address+size))
    uc.hook_add(UC_HOOK_MEM_WRITE,watch)
    try:
        uc.emu_start(d['entry'],stop,timeout=2*1000*1000,count=max_instructions)
        if int(uc.reg_read(m68k_const.UC_M68K_REG_PC))!=stop:
            return {'status':'ORIGINAL_DID_NOT_REACH_RETURN_SENTINEL'}
    except Exception as exc:
        return {'status':'ORIGINAL_EXECUTION_FAILED','reason':type(exc).__name__+':'+str(exc)[:180]}
    diffs=[]
    for name,r in initial.items():
        original=int(uc.reg_read(getattr(m68k_const,'UC_M68K_REG_'+name)))
        actual=native_reg.get(name)
        if actual is None or original!=actual:diffs.append({'field':name,'original':original,'native':actual})
    all_mem=observed_mem|set(native_mem)
    for addr in sorted(all_mem)[:10000]:
        try:original=uc.mem_read(addr,1)[0]
        except Exception:original=None
        native=native_mem.get(addr)
        if original!=native:diffs.append({'memory_address':addr,'original':original,'native':native})
    if len(all_mem)>10000:return {'status':'MEMORY_WRITE_COMPARISON_LIMIT'}
    changed_regs=sum(int(uc.reg_read(getattr(m68k_const,'UC_M68K_REG_'+name)))!=base_values[name]
                     for name in initial)
    if not diffs and not changed_regs and not all_mem:
        status='SAMPLE_NO_OBSERVABLE_EFFECT_INSUFFICIENT_EVIDENCE'
    else:
        status='SAMPLE_SUBSET_MATCH_NO_FULL_PARITY' if not diffs else 'SAMPLE_DIFFERENTIAL_MISMATCH'
    return {'status':status,'compared_named_registers':sorted(initial),
            'unmodelled_register_fields':sorted(set(unsupported)),
            'written_memory_bytes_compared':len(all_mem),'changed_named_registers':changed_regs,'diffs':diffs[:30],
            'limits':'One CPU state with synthetic zeroed 64KiB RAM; only named GPRs and changed RAM bytes compared. No interrupts, timing, other CPU flags or gameplay parity.'}


def main():
    p=argparse.ArgumentParser(description='Compare one original M68K function sample against its C++ output')
    p.add_argument('--db',required=True);p.add_argument('--source',required=True)
    p.add_argument('--manifest',required=True);p.add_argument('--output')
    a=p.parse_args();result=verify(a.db,a.source,a.manifest)
    if a.output:Path(a.output).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    con=sqlite3.connect(a.db)
    try:
        d=json.loads(Path(a.manifest).read_text(encoding='utf-8'))
        with con:con.execute('''UPDATE conversion_v031 SET verification_status=?
          WHERE target_id=? AND source_sha256=? AND entry=? AND export_sha256=?''',(
             result['status'],d['target_id'],d['source_sha256'],d['entry'],d['ghidra_export_sha256']))
    finally:con.close()
    print(json.dumps(result,indent=2))
    return 0 if result['status']=='SAMPLE_SUBSET_MATCH_NO_FULL_PARITY' else 1

if __name__=='__main__':raise SystemExit(main())
