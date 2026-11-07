"""Optional, bounded Ghidra/Rizin *analysis* adapters for the native controller.

Analyzer invocations, byte verification and reconciliation use maintained providers.
No historical recovery executor or source generator is used in the production path.
Rizin only proposes function boundaries. Ghidra supplies byte-attested source IR;
all native instructions must separately pass the active source-checking DLL.
"""
from __future__ import annotations
import hashlib
import json
import tempfile
from pathlib import Path

from analysis_integration.reconciliation import reconcile,sha256_file
from analysis_integration.tool_authorization import authorize_tool
from analysis_integration.rizin_provider import execute_rizin, RizinProviderError
from analysis_integration.ghidra_provider import execute_initial, run_headless, GhidraProviderError, SCRIPTS
from analysis_integration.ghidra_evidence import candidate_rows, read_export, LANG

class ProviderBlocked(ValueError):pass

def acquire(rom:Path,output:Path,*,export:Path|None,ghidra:Path|None,
            rizin:Path|None,tool_roots:tuple[Path,...],timeout:int,
            allow_synthetic:bool=False)->tuple[Path,Path|None,dict]:
    """Return authentic, audited Ghidra export and optional reconciliation report.

    Installed tools must be explicitly selected and confined to allowlisted roots;
    no PATH search, downloads, shell, fuzzy source lookup or automatic legacy fallback.
    """
    rom=rom.resolve(strict=True)
    if not (0<rom.stat().st_size<=32*1024*1024):raise ProviderBlocked('UNSUPPORTED_SOURCE_SIZE')
    output.mkdir(parents=True,exist_ok=False)
    digest=sha256_file(rom)
    target='mastersystem-'+digest[:12]
    approved={}
    for name,path in (('ghidra',ghidra),('rizin',rizin)):
        if path is not None:
            approved[name]=authorize_tool(path,tool_roots,name)
    result={'schema':'recompdev.analysis.providers.v1','source_sha256':digest,
            'source_size':rom.stat().st_size,'architecture':'z80','platform':'sms',
            'selected_providers':['native-source-discovery'],
            'external_tools_executed':[],'native_semantics_qualified':False,
            'historical_runtime_fallback':False}
    if export is None:
        if 'ghidra' not in approved:raise ProviderBlocked('GHIDRA_SOURCE_EXPORT_REQUIRED: provide --export or approved --ghidra')
        ghexport=output/'ghidra-functions.json'
        gh_audit=execute_initial(rom,target,digest,ghexport,approved['ghidra'],timeout)
        result['ghidra_execution']=gh_audit
        result['selected_providers'].append('ghidra-headless-maintained-v1')
        result['external_tools_executed'].append('ghidra')
    else:
        ghexport=export.resolve(strict=True)
        result['selected_providers'].append('source-verified-ghidra-export')
    doc=read_export(ghexport)
    if doc.get('schema')!='recomp-function-pcode-v1' or doc.get('source_sha256')!=digest:
        raise ProviderBlocked('GHIDRA_EXPORT_SOURCE_IDENTITY_MISMATCH')
    if not allow_synthetic and doc.get('language')!=LANG['z80']:
        raise ProviderBlocked('GHIDRA_EXPORT_Z80_LANGUAGE_REQUIRED')
    if not allow_synthetic:
        functions=candidate_rows(doc,rom,'z80')
        if not functions:raise ProviderBlocked('NO_GHIDRA_SOURCE_VERIFIED_FUNCTIONS')
        result['ghidra_verified_functions']=len(functions)
        result['ghidra_verified_instructions']=sum(f[2] for f in functions)
    else:
        # Only the explicit synthetic regression route may supply an empty export.
        result['synthetic_export_test_only']=True
    result['ghidra_export_sha256']=sha256_file(ghexport)
    reconciliation=None
    if 'rizin' in approved:
        rz_folder=output/'rizin';rz_folder.mkdir()
        try:
            rz=execute_rizin(approved['rizin'],rom,0,'z80',rz_folder,timeout)
        except RizinProviderError as exc:
            raise ProviderBlocked('RIZIN_PROVIDER_REJECTED: '+str(exc)) from exc
        result['external_tools_executed'].append('rizin')
        result['rizin_execution']=rz
        if rz['status']!='EXITED' or not (rz_folder/'rizin-aflj.json').is_file():
            raise ProviderBlocked('RIZIN_ANALYSIS_FAILED: '+str(rz['status']))
        # Rizin operates on the initial fixed ROM window only for evidence
        # reconciliation; banked addresses remain hypotheses and are not
        # directly converted into physical instruction identities.
        reconciliation=output/'reconciled-functions.json'
        merged=reconcile(rom,0,'z80',ghexport,rz_folder/'rizin-aflj.json')
        reconciliation.write_text(json.dumps(merged,sort_keys=True,indent=2)+'\n',encoding='utf8')
        result['selected_providers'].append('rizin-direct-v1')
        result['reconciliation_candidates']=len(merged['candidates'])
        result['reconciliation_sha256']=sha256_file(reconciliation)
    if sha256_file(rom)!=digest:raise ProviderBlocked('SOURCE_CHANGED_DURING_EXTERNAL_ANALYSIS')
    (output/'provider-manifest.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n',encoding='utf8')
    return ghexport,reconciliation,result


def analyze_observed_bank_region(rom:Path,output:Path,*,ghidra:Path,tool_roots:tuple[Path,...],
                                 base_export:Path,observed:dict,timeout:int)->tuple[Path,dict]:
    """Re-analyse a runtime-observed ROM *bank window*, never an invented bank.

    All source bytes in Ghidra's temporary 48 KiB view are derived from the
    original ROM and the observed mapper. Only instructions from the stop's
    exact 16 KiB slot are exported as a bank-context P-code overlay. Other
    windows are context for interprocedural analysis, not admitted source IR.
    """
    ghidra=authorize_tool(ghidra,tool_roots,'ghidra')
    rom=rom.resolve(strict=True)
    source=rom.read_bytes()
    if not source or len(source)%0x4000 or len(source)>32*1024*1024:
        raise ProviderBlocked('FOCUSED_ANALYSIS_UNSUPPORTED_ROM_LAYOUT')
    digest=hashlib.sha256(source).hexdigest()
    base=read_export(base_export)
    if base.get('source_sha256')!=digest or base.get('schema')!='recomp-function-pcode-v1':
        raise ProviderBlocked('FOCUSED_ANALYSIS_BASE_IDENTITY_MISMATCH')
    if observed.get('source_sha256')!=digest or observed.get('rom_bytes')!=len(source):
        raise ProviderBlocked('FOCUSED_ANALYSIS_STOP_SOURCE_IDENTITY_MISMATCH')
    mapper=observed.get('mapper')
    pc=observed.get('pc');physical=observed.get('physical_offset')
    if type(pc)!=int or not 0<=pc<0xc000 or not isinstance(mapper,list) or len(mapper)!=4 or any(type(x)!=int or not 0<=x<256 for x in mapper):
        raise ProviderBlocked('FOCUSED_ANALYSIS_STOP_MAPPING_UNVERIFIED')
    if type(physical)!=int or not 0<=physical<len(source):
        raise ProviderBlocked('FOCUSED_ANALYSIS_PHYSICAL_OFFSET_INVALID')
    if pc>=0x8000 and mapper[0]&8:
        raise ProviderBlocked('FOCUSED_ANALYSIS_UPPER_WINDOW_IS_RAM')
    bank_count=len(source)//0x4000
    slot=pc//0x4000
    banks=[mapper[1]%bank_count,mapper[2]%bank_count,mapper[3]%bank_count]
    expect=pc if pc<0x400 else banks[slot]*0x4000+(pc&0x3fff)
    if physical!=expect:raise ProviderBlocked('FOCUSED_ANALYSIS_STOP_PHYSICAL_MISMATCH')
    window=bytearray(b''.join(source[b*0x4000:(b+1)*0x4000] for b in banks))
    window[:0x400]=source[:0x400] # SMS fixed reset/interrupt page, even if slot-0 bank switches
    if len(window)!=0xc000:raise ProviderBlocked('FOCUSED_ANALYSIS_WINDOW_INCOMPLETE')
    output.mkdir(parents=True,exist_ok=False)
    exported=output/'raw-ghidra.json'
    with tempfile.TemporaryDirectory(prefix='recompdev-ghidra-banked-') as td:
        work=Path(td);image=work/'observed-bank-view.bin';image.write_bytes(window)
        cmd=[str(ghidra),str(work),'RecompDevRuntimeObservedBank','-import',str(image),
             '-loader','BinaryLoader','-loader-baseAddr','0x0',
             '-processor',LANG['z80'],'-scriptPath',str(SCRIPTS),
             '-preScript','SeedRecompEntry.java',hex(pc),
             '-postScript','ExportFunctionBodies.java',str(exported),base['target_id'],digest,'1000',
             '-readOnly','-analysisTimeoutPerFile',str(min(180,timeout))]
        run_headless(cmd,output/'analyzer.log',exported,timeout)
    if exported.stat().st_size>64*1024*1024:raise ProviderBlocked('FOCUSED_GHIDRA_EXPORT_OVERSIZED')
    doc=read_export(exported)
    if doc.get('schema')!='recomp-function-pcode-v1' or doc.get('analyzer')!='ghidra-raw-pcode' or doc.get('language')!=LANG['z80'] or doc.get('target_id')!=base['target_id'] or doc.get('source_sha256')!=digest:
        raise ProviderBlocked('FOCUSED_GHIDRA_EXPORT_IDENTITY_INVALID')
    verified=[];seen=set();focus_included=False
    bottom=slot*0x4000;top=bottom+0x4000
    for function in doc.get('functions',[]):
        filtered=[]
        for ins in function.get('instructions',[]):
            address=ins.get('address');length=ins.get('length');bytes_hash=ins.get('bytes_sha256')
            if type(address)!=int or type(length)!=int:raise ProviderBlocked('FOCUSED_GHIDRA_INVALID_INSTRUCTION')
            if address<bottom or address>=top:continue
            if not 1<=length<=8 or address+length>top or type(bytes_hash)!=str:
                raise ProviderBlocked('FOCUSED_GHIDRA_INSTRUCTION_WINDOW_INVALID')
            off=address if slot==0 and address<0x400 else banks[slot]*0x4000+address-bottom
            if hashlib.sha256(source[off:off+length]).hexdigest()!=bytes_hash:
                raise ProviderBlocked('FOCUSED_GHIDRA_SOURCE_BYTES_MISMATCH')
            if off in seen:raise ProviderBlocked('FOCUSED_GHIDRA_DUPLICATE_PHYSICAL_INSTRUCTION')
            seen.add(off)
            filtered.append(ins)
            if address==pc:focus_included=True
        if filtered:
            filtered_func=dict(function);filtered_func['instructions']=filtered
            verified.append(filtered_func)
    if not focus_included:raise ProviderBlocked('FOCUSED_GHIDRA_STOP_NOT_VERIFIED_IN_FUNCTION')
    doc['functions']=verified
    doc['bank_context']={'slot':slot,'bank':banks[slot], 'base':bottom, 'physical_start':banks[slot]*0x4000}
    out=output/'source-verified-bank-functions.json'
    out.write_text(json.dumps(doc,sort_keys=True,separators=(',',':'))+'\n',encoding='utf8')
    evidence={'schema':'recompdev.ghidra.observed_bank.v1','source_sha256':digest,'observed_pc':pc,
              'observed_physical':physical,'observed_mapper':mapper,'slot':slot,
              'bank':banks[slot],'verified_instructions':len(seen),
              'observed_instruction_verified':focus_included,
              'observed_bank_source_hash':hashlib.sha256(window).hexdigest(),
              'backend':'ghidra-headless','native_execution_fallback':False}
    (output/'recovery-audit.json').write_text(json.dumps(evidence,sort_keys=True,indent=2)+'\n',encoding='utf8')
    if hashlib.sha256(rom.read_bytes()).hexdigest()!=digest:
        raise ProviderBlocked('SOURCE_CHANGED_DURING_FOCUSED_GHIDRA')
    return out,evidence
