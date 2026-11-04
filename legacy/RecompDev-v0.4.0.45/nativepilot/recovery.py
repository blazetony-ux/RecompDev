"""Targeted, bounded Z80 cartridge-region recovery from an *owner-local* cartridge.

No ROM data are included in distribution; the temporary window is deleted after
Ghidra exits. Original exported instruction hashes are checked by generator.
"""
import json
import subprocess
import tempfile
from pathlib import Path
from nativeprep.engine import LANG,locate_ghidra
from nativepilot.generator import verify_export,sha256
from nativecore.instruction_evidence import inspect_entry

BANK=0x4000

def bank_context(rom_size,pc,mapper):
    if type(pc)!=int or not 0<=pc<0xc000:raise ValueError('Not a ROM program counter')
    if not isinstance(mapper,(list,tuple)) or len(mapper)!=4 or any(type(x)!=int or not 0<=x<=255 for x in mapper):
        raise ValueError('Invalid cartridge mapper state')
    slot=pc//BANK
    count=(rom_size+BANK-1)//BANK
    if not count:raise ValueError('Empty cartridge')
    bank=(0 if pc<0x400 else mapper[slot+1]%count)
    start=bank*BANK
    phys=pc if pc<0x400 else start+(pc%BANK)
    if phys>=rom_size:raise ValueError('Unmapped physical cartridge address')
    return {'slot':slot,'bank':bank,'base':slot*BANK,'physical_start':start,
            'entry_pc':pc,'entry_physical':phys}

def recover_bank(rom_path,source_sha,target_id,pc,mapper,output,ghidra_exe='',timeout=240):
    rom_path=Path(rom_path);output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    if sha256(rom_path)!=source_sha:raise ValueError('ROM SHA-256 changed before bank recovery')
    meta=bank_context(rom_path.stat().st_size,pc,mapper)
    source_diagnostic=inspect_entry(rom_path,meta['entry_physical'])
    (output/'entry-diagnostics.json').write_text(json.dumps(source_diagnostic,indent=2)+'\n',encoding='utf-8')
    if not source_diagnostic['translation_allowed']:
        raise RuntimeError('RECOVERY_UNSAFE_PADDING_SUSPECTED: '+source_diagnostic['classification']+' at '+hex(pc))
    executable=locate_ghidra(ghidra_exe)
    if not executable:raise RuntimeError('GHIDRA_UNAVAILABLE: configure RECOMPDEV_GHIDRA or GHIDRA_HOME')
    with tempfile.TemporaryDirectory(prefix='recompdev-bank-recovery-') as td:
        work=Path(td);base=meta['base'];physical=meta['physical_start']
        with rom_path.open('rb') as f:
            f.seek(physical);raw=f.read(BANK)
            if len(raw)!=BANK:raise ValueError('Incomplete cartridge bank')
            # SMS vectors at 0x0000..0x03ff are bank-0 even when slot 0 changes.
            if meta['slot']==0 and meta['bank']!=0:
                f.seek(0);raw=f.read(0x400)+raw[0x400:]
        image=work/'mapped-window.bin';image.write_bytes(raw)
        export=output/'bank-functions.json'
        exact=output/'exact-entry.json'
        scripts=Path(__file__).resolve().parents[1]/'ghidra'
        cmd=[str(executable),str(work),'RecompDevBankRecovery','-import',str(image),
             '-loader','BinaryLoader','-loader-baseAddr',hex(base),
             '-processor',LANG['z80'],'-scriptPath',str(scripts),
             '-preScript','SeedRecompEntry.java',hex(pc),
             '-postScript','ExportFunctionBodies.java',str(export),target_id,source_sha,'200',
             '-postScript','ExportExactInstruction.java',str(exact),hex(pc),
             '-readOnly','-analysisTimeoutPerFile','120']
        try:run=subprocess.run(cmd,capture_output=True,text=True,errors='replace',timeout=timeout)
        except subprocess.TimeoutExpired as e:raise RuntimeError('GHIDRA_BANK_TIMEOUT') from e
        (output/'ghidra.log').write_text((run.stdout+'\n'+run.stderr)[-100000:],encoding='utf-8')
        if run.returncode!=0 or not export.is_file():raise RuntimeError('GHIDRA_BANK_FAILED: inspect local ghidra.log')
    doc=json.loads(export.read_text(encoding='utf-8'))
    if doc.get('target_id')!=target_id or doc.get('source_sha256')!=source_sha:
        raise ValueError('Bank export identity mismatch')
    doc['bank_context']={k:meta[k] for k in ('slot','bank','base','physical_start')}
    # Exact-address evidence is separate from Ghidra Function discovery. It
    # uses the same per-instruction source SHA-256 verification before lowering.
    exact_count=0
    if exact.is_file():
        direct=json.loads(exact.read_text(encoding='utf-8'))
        if direct.get('schema')!='recomp-exact-instruction-v1' or direct.get('entry')!=pc or direct.get('language')!=doc.get('language'):
            raise ValueError('Exact entry export identity mismatch')
        instructions=direct.get('instructions')
        if not isinstance(instructions,list) or len(instructions)>64:
            raise ValueError('Unbounded exact entry export')
        if instructions:
            if instructions[0].get('address')!=pc:raise ValueError('Exact instruction entry mismatch')
            doc['functions'].append({'entry':pc,'name':'recomp_exact_entry',
                                     'instructions':instructions,'recovery_method':'exact-address'})
            exact_count=len(instructions)
        source_diagnostic['ghidra_exact_status']=direct.get('status')
    else:
        source_diagnostic['ghidra_exact_status']='EXACT_EXPORT_NOT_EMITTED'
    source_diagnostic['exact_instructions']=exact_count
    (output/'entry-diagnostics.json').write_text(json.dumps(source_diagnostic,indent=2)+'\n',encoding='utf-8')
    if sha256(rom_path)!=source_sha:raise ValueError('ROM modified while analysing bank')
    recovered,_,_=verify_export(doc,rom_path)
    if meta['entry_physical'] not in recovered:
        raise RuntimeError('EXACT_ENTRY_NOT_RECOVERED: no attested instruction at '+hex(pc)+
                           ' ('+source_diagnostic['ghidra_exact_status']+'); see entry-diagnostics.json')
    # Record physical/slot evidence as JSON, not an original ROM dump.
    export.write_text(json.dumps(doc,separators=(',',':'))+'\n',encoding='utf-8')
    return doc,{'slot':meta['slot'],'bank':meta['bank'],'pc':pc,
                'physical_offset':meta['entry_physical'],'instructions':len(recovered),
                'export':str(export),'status':'SOURCE_BYTES_VERIFIED',
                'exact_instructions':exact_count,'entry_diagnostics':str(output/'entry-diagnostics.json')}
