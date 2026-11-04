"""Source-authenticated analysis-to-recovery queue. Claims are hints, not codegen truth.

The native Z80 generator requires independently attested Ghidra P-code; an
analyzer's function-boundary guess must NEVER be laundered into executable IR.
"""
import hashlib
import json
from pathlib import Path

SCHEMA = 'recomp-recovery-handoff-v0421'
MAX = 20000

def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def convert(source, reconciliation, output):
    source=Path(source).resolve(strict=True)
    analysis=Path(reconciliation).resolve(strict=True)
    if not source.is_file() or not 0<source.stat().st_size<=32*1024*1024:
        raise ValueError('Invalid bounded original binary')
    if not analysis.is_file() or analysis.is_symlink() or analysis.stat().st_size>32*1024*1024:
        raise ValueError('Invalid analysis file')
    raw=source.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    doc=json.loads(analysis.read_text(encoding='utf-8'))
    if doc.get('schema')!='recomp-analysis-reconciliation-v1' or doc.get('source_sha256')!=sha or doc.get('source_size')!=len(raw):
        raise ValueError('Analyzer handoff source provenance mismatch')
    # Re-run source-byte attestation against the ORIGINAL analyzer exports.
    # A forged reconciliation JSON with a plausible source hash is insufficient.
    from tooling.analysis import reconcile
    engines=doc.get('analysis_engines',[])
    if not isinstance(engines,list) or not engines or any(e not in ('ghidra','rizin') for e in engines):
        raise ValueError('Missing original analyzer export identities')
    paths={'ghidra':analysis.parent/'ghidra-functions.json',
           'rizin':analysis.parent/'rizin-aflj.json'}
    for engine in engines:
        if not paths[engine].is_file() or paths[engine].is_symlink():
            raise ValueError('Missing original analyzer source evidence: '+engine)
        expected=doc.get('provenance',{}).get('tool_exports_sha256',{}).get(engine)
        if expected is not None and expected!=sha256(paths[engine]):
            raise ValueError('Analyzer export provenance digest mismatch')
    independently=reconcile(source,doc.get('base'),doc.get('isa'),
        ghidra=paths['ghidra'] if 'ghidra' in engines else None,
        rizin=paths['rizin'] if 'rizin' in engines else None)
    if doc.get('candidates')!=independently['candidates'] or doc.get('warnings')!=independently['warnings']:
        raise ValueError('Reconciliation claims not supported by original exports')
    isa=doc.get('isa');base=doc.get('base');candidates=doc.get('candidates')
    if isa not in ('z80','m68k','mips') or type(base)!=int or base<0 or not isinstance(candidates,list) or len(candidates)>MAX:
        raise ValueError('Malformed analysis mapping')
    tasks=[];seen=set();suppressed=0
    for candidate in candidates:
        if not isinstance(candidate,dict):raise ValueError('Invalid candidate')
        pc=candidate.get('entry');status=candidate.get('status')
        if type(pc)!=int or not base<=pc<base+len(raw) or pc in seen:
            raise ValueError('Duplicate or unmapped analyzer candidate')
        seen.add(pc)
        gh=candidate.get('ghidra');rz=candidate.get('rizin')
        if status not in ('AGREED_ENTRY_AND_EXTENT','AGREED_ENTRY_DIFFERENT_EXTENT','GHIDRA_ONLY','RIZIN_ONLY'):
            raise ValueError('Unrecognized analyzer agreement status')
        if status.startswith('AGREED') and not (isinstance(gh,dict) and isinstance(rz,dict)):
            raise ValueError('Forged dual-engine agreement')
        if status=='GHIDRA_ONLY' and (not isinstance(gh,dict) or rz is not None):raise ValueError('Inconsistent Ghidra claim')
        if status=='RIZIN_ONLY' and (not isinstance(rz,dict) or gh is not None):raise ValueError('Inconsistent Rizin claim')
        if gh is not None:
            if type(gh.get('verified_instruction_bytes'))!=int or gh['verified_instruction_bytes']<=0 or gh.get('entry')!=pc:
                raise ValueError('Ghidra candidate lacks instruction provenance')
        if rz is not None and rz.get('entry')!=pc:raise ValueError('Rizin entry mismatch')
        # Check all input bytes again; claims are not allowed to provide invented instructions.
        phys=pc-base;fingerprint=hashlib.sha256(raw[phys:phys+min(8,len(raw)-phys)]).hexdigest()
        priority=0 if status.startswith('AGREED') else 1 if gh else 2
        tasks.append({'logical_entry':pc,'physical_offset':phys,'source_byte_window_sha256':fingerprint,
            'status':status,'priority':priority,'action':'ATTEST_EXACT_INSTRUCTIONS_AND_CONTROL_FLOW',
            'trusted_as_native_code':False,'qualified':False,
            'mapping':'RAW_ADDRESS_ONLY_UNMAPPED_BANKS_REMAIN_UNKNOWN',
            'reason':'Analyzer boundary evidence cannot substitute for source-authenticated instruction semantics'})
    tasks.sort(key=lambda x:(x['priority'],x['physical_offset']))
    result={'schema':SCHEMA,'source_sha256':sha,'reconciliation_sha256':sha256(analysis),
        'isa':isa,'base':base,'status':'SOURCE_ATTESTED_RECOVERY_QUEUE' if tasks else 'NO_CANDIDATES',
        'recovery_tasks':tasks,'candidate_count':len(tasks),'suppressed_candidates':suppressed,
        'automatic_codegen':False,'native_parity':'NOT_TESTED','game_specific_rules':False}
    dest=Path(output)
    if dest.exists():raise ValueError('Immutable recovery queue already exists')
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return result
