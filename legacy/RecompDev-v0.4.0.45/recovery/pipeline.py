"""RecompDev v0.3.2 function recovery -> strict P-code -> native C++.

Trust policy: SHA-match owner-local binary; independently compare every Ghidra
instruction's bytes with mapped original; no recovered boundary becomes VERIFIED;
compilation never implies original-machine execution parity.
"""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from adapters.formats import open_image
from native_batch import sha_file, index_sources
from recovery.codegen import generate, Blocked

DDL='''
CREATE TABLE IF NOT EXISTS conversion_v031(
 target_id TEXT NOT NULL,source_sha256 TEXT NOT NULL,entry INTEGER NOT NULL,
 export_sha256 TEXT NOT NULL,attempted_utc TEXT NOT NULL,analyzer TEXT NOT NULL,
 reconcile_status TEXT NOT NULL,boundary_status TEXT NOT NULL,
 pcode_status TEXT NOT NULL,compile_status TEXT NOT NULL,verification_status TEXT NOT NULL,
 blocker TEXT NOT NULL,cpp_sha256 TEXT,relative_manifest TEXT,
 PRIMARY KEY(target_id,source_sha256,entry,export_sha256));
CREATE INDEX IF NOT EXISTS conversion_v031_status ON conversion_v031(compile_status,verification_status);
'''


def read_export(filename, max_bytes=128*1024*1024):
    p=Path(filename)
    if not p.is_file() or p.stat().st_size>max_bytes:raise ValueError('missing/oversized Ghidra export: '+str(p))
    doc=json.loads(p.read_text(encoding='utf-8-sig'))
    if doc.get('schema')!='recomp-function-pcode-v1' or doc.get('analyzer')!='ghidra-raw-pcode':
        raise ValueError('requires ExportFunctionBodies.java output')
    if not isinstance(doc.get('functions'),list):raise ValueError('missing functions')
    if len(doc['functions'])>20000:raise ValueError('too many functions')
    return doc


def check_source_bytes(func,image):
    """Do not trust import metadata or filenames: verify every recovered instruction byte."""
    ins=func.get('instructions')
    if not isinstance(ins,list) or not ins:return 'missing_function_instructions'
    if len(ins)>10000:return 'function_instruction_limit'
    for i in ins:
        addr=i.get('address');length=i.get('length');expected=i.get('bytes_sha256')
        if type(addr)!=int or type(length)!=int or not (1<=length<=16):return 'invalid_instruction_extent'
        if addr<image.start or addr+length>image.stop:return 'instruction_outside_mapped_source'
        start=image.offset(addr)
        original=image.data[start:start+length]
        if len(original)!=length:return 'incomplete_source_bytes'
        if hashlib.sha256(original).hexdigest()!=expected:return 'GHIDRA_BYTES_DIFFER_FROM_AUTHENTICATED_SOURCE'
    return ''


def detect_overlap(func,other_functions):
    ours={i['address'] for i in func.get('instructions',[]) if type(i.get('address'))==int}
    for o in other_functions:
        if o is func:continue
        if ours & {i['address'] for i in o.get('instructions',[]) if type(i.get('address'))==int}:
            return True
    return False


def rizin_index(path):
    """Explicit aflj observations; address matches must be exact to be called agreeing."""
    if path is None:return None
    obj=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if isinstance(obj,dict):obj=obj.get('functions',[])
    if not isinstance(obj,list):raise ValueError('Rizin evidence must be an aflj JSON array')
    result={}
    for f in obj:
        if type(f.get('offset'))==int and type(f.get('size'))==int and f['size']>0:
            result[f['offset']]=(f['offset'],f['offset']+f['size'])
    return result


def reconcile(f,rizin):
    if rizin is None:return 'GHIDRA_ONLY_UNCORROBORATED'
    e=f['entry']; entry=rizin.get(e)
    if entry is None:return 'RIZIN_NO_MATCH'
    last=max(i['address']+i['length'] for i in f['instructions'])
    if entry[1]<last:return 'RIZIN_BOUNDARY_CONFLICT'
    if entry[1]==last:return 'GHIDRA_RIZIN_RANGE_AGREEMENT_UNVERIFIED'
    return 'RIZIN_EXTENDS_FUNCTION'


def check_pypcode(f,image,language,enabled=False):
    """Advisory first-instruction lift in a separate process.

    A native crash is kept as explicit evidence and never interpreted as
    semantic agreement; the parent conversion process remains alive.
    """
    if not enabled:return 'NOT_REQUESTED'
    from recovery.native_workers import run_isolated
    ins=f['instructions'][0]
    start=image.offset(ins['address'])
    raw=image.data[start:start+ins['length']]
    evidence=run_isolated('pypcode',{'language':language,'address':ins['address'],
                                    'hex':raw.hex()},timeout=20)
    if evidence['status']=='NATIVE_WORKER_CRASH_OR_ERROR':
        return 'PYPCODE_WORKER_FAILED_'+evidence['exit_hex']
    if evidence['status'] in ('NATIVE_WORKER_TIMEOUT','NATIVE_WORKER_LAUNCH_FAILED',
                               'NATIVE_WORKER_INVALID_OUTPUT'):
        return 'PYPCODE_'+evidence['status']
    return evidence['status']


def find_cpp_compiler(supplied=None):
    if supplied:
        path=Path(supplied)
        return str(path) if path.is_file() else shutil.which(supplied)
    available=shutil.which('g++') or shutil.which('clang++') or shutil.which('cl')
    if available:return available
    # In a normal Windows PowerShell, cl.exe is often absent from PATH even
    # when the VS Build Tools are installed. Locate and activate vcvars64.
    if os.name=='nt':
        program_files=os.environ.get('ProgramFiles(x86)',r'C:\Program Files (x86)')
        vswhere=Path(program_files)/'Microsoft Visual Studio'/'Installer'/'vswhere.exe'
        if vswhere.is_file():
            try:
                p=subprocess.run([str(vswhere),'-latest','-products','*',
                    '-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
                    '-property','installationPath'],capture_output=True,text=True,timeout=8)
                install=Path(p.stdout.strip())
                vcvars=install/'VC'/'Auxiliary'/'Build'/'vcvars64.bat'
                if p.returncode==0 and vcvars.is_file():return 'vcvars:'+str(vcvars)
            except (OSError,subprocess.TimeoutExpired):pass
    return None


def compile_cpp(path,compiler,timeout=40,runner_args=None,evidence_path=None):
    if not compiler:return 'COMPILER_NOT_FOUND',''
    compiler=str(compiler)
    via_vcvars=compiler.startswith('vcvars:')
    is_msvc=via_vcvars or Path(compiler).stem.lower()=='cl'
    output=path.with_suffix('.exe' if os.name=='nt' else '')
    if via_vcvars:
        script=compiler[len('vcvars:'):]
        cmdline=f'call "{script}" >nul && cl.exe /nologo /EHsc /std:c++17 /DRECOMP_STANDALONE_TEST "{path}" /Fe:"{output}"'
        cmd=['cmd.exe','/d','/c',cmdline]
    elif is_msvc:
        cmd=[compiler,'/nologo','/EHsc','/std:c++17','/DRECOMP_STANDALONE_TEST',str(path),'/Fe:'+str(output)]
    else:
        cmd=[compiler,'-std=c++17','-O2','-DRECOMP_STANDALONE_TEST',str(path),'-o',str(output)]
    try:ret=subprocess.run(cmd,text=True,capture_output=True,timeout=timeout,check=False,errors='replace')
    except subprocess.TimeoutExpired:return 'COMPILER_TIMEOUT',''
    if ret.returncode or not output.is_file():return 'COMPILER_ERROR',(ret.stdout+'\n'+ret.stderr)[-2500:]
    try:
        ret=subprocess.run([str(output),*(runner_args or [])],text=True,capture_output=True,
                           timeout=10,check=False,errors='replace')
        stdout,stderr=ret.stdout,ret.stderr
        exit_code=ret.returncode
        hardware_events=[line for line in stdout.splitlines() if line.startswith('IO ')]
        if exit_code:
            status=('COMPILED_SEEDED_RUNTIME_FAILED' if runner_args is not None else
                    'COMPILED_RUNTIME_SMOKE_FAILED')
            detail=(stdout+'\n'+stderr)[-2500:]
        elif hardware_events:
            status='COMPILED_HARDWARE_TRACE_SMOKE_ONLY';detail=''
        else:
            status=('COMPILED_SEEDED_SMOKE_ONLY' if runner_args is not None else
                    'COMPILED_RUNNER_SMOKE_ONLY');detail=''
    except (subprocess.TimeoutExpired,OSError) as exc:
        status=('COMPILED_SEEDED_RUNTIME_FAILED' if runner_args is not None else
                'COMPILED_RUNTIME_SMOKE_FAILED')
        stdout='';stderr=type(exc).__name__;exit_code=None;hardware_events=[];detail=stderr
    if evidence_path is not None:
        Path(evidence_path).write_text(json.dumps({
            'schema':'recomp-native-run-evidence-v0323',
            'compile_status':status,'return_code':exit_code,
            'hardware_event_count':len(hardware_events),
            'hardware_event_lines':hardware_events[:500],
            'stdout_tail':stdout[-16000:], 'stderr_tail':stderr[-4000:],
            'statement':'This is native smoke evidence; IO events are not hardware simulation or original-CPU parity.'
        },indent=2)+'\n',encoding='utf-8')
    return status,detail



def seeded_runner_args(t, function, built, original, image):
    """Deliberately incomplete sample state, never parity or hardware emulation.

    Mega Drive ROM is identity mapped, with an explicit zero-seeded 64 KiB
    RAM window; unknown I/O addresses remain rejected. PS1 is intentionally
    excluded until R3000A delay/load handling has been validated.
    """
    if t['system_tag']!='megadrive' or t['isa']!='m68k':return None
    args=['--image',str(original),'0','0',str(len(image.data)),
          '--megadrive-bus']
    # A7 must be seeded by the *Ghidra-reported* register offset, never a
    # guessed offset. This fixture does not simulate an actual call frame.
    for reg in built['registers']:
        if reg['name'].upper()=='A7' and reg['size']==4:
            args.append(f"{reg['offset']}:4:0xfffef8")
            break
    return args


def run(dbfile,source_files=(),source_roots=(),ghidra_exports=(),output=None,
        limit=50,rizin_json=None,require_dual=False,compiler=None,compile_native=True,pypcode_check=False,progress=None):
    if not (1<=limit<=10000):raise ValueError('limit must be 1..10000')
    if not ghidra_exports:raise ValueError('provide at least one Ghidra body export; no function boundaries fabricated')
    dbfile=Path(dbfile); root=Path(output or (dbfile.parent/'evidence'/'functions-v031')).resolve()
    root.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(str(dbfile));con.row_factory=sqlite3.Row
    try:
        con.execute(DDL.split(';')[0]+';')
        con.execute('CREATE INDEX IF NOT EXISTS conversion_v031_status ON conversion_v031(compile_status,verification_status)')
        lookup,scan_errors=index_sources(con,source_files,source_roots)
        targets={r['target_id']:dict(r) for r in con.execute('SELECT * FROM targets')}
        recent={}
        for row in con.execute('SELECT run_id,target_id FROM graph_runs ORDER BY rowid'):
            recent[row['target_id']]=row['run_id']
        existing={}
        for tid,rid in recent.items():
            existing[tid]={r['entry'] for r in con.execute('SELECT entry FROM graph_functions WHERE run_id=?',(rid,))}
        rizin=rizin_index(rizin_json)
        candidates=[];exports=[]
        for file in ghidra_exports:
            d=read_export(file);tid=d['target_id']; t=targets.get(tid)
            if t is None:raise ValueError('export target not registered in catalogue: '+str(tid))
            sha=t['source_sha256']
            if d.get('source_sha256')!=sha:raise ValueError('export source SHA does not match catalogue: '+tid)
            if not lookup.get(sha):raise ValueError('SHA-matching owner-local original not supplied: '+tid)
            if t['isa'] not in ('m68k','mips'):raise ValueError('unimplemented CPU adapter: '+t['isa'])
            if t['system_tag'] not in ('megadrive','psx-exe'):raise ValueError('unimplemented binary mapping for '+t['system_tag'])
            data=Path(lookup[sha]).read_bytes()
            image=open_image(data,fmt=t['system_tag'])
            export_sha=sha_file(file)
            exports.append({'file':str(file),'target':tid,'export_sha256':export_sha,'sha256_verified':True})
            for f in d['functions']:
                if type(f.get('entry'))!=int or not isinstance(f.get('instructions'),list):
                    raise ValueError('malformed function record')
                issue=check_source_bytes(f,image)
                conflict=detect_overlap(f,d['functions']) if not issue else False
                match=reconcile(f,rizin)
                priority=(0 if f['entry'] in existing.get(tid,set()) else 1,
                          len(f.get('instructions',[])),f['entry'])
                candidates.append((priority,t,d,f,image,issue,conflict,match,export_sha))
        # Deterministic round-robin across systems/targets, rather than letting
        # a single game's small functions consume the entire campaign budget.
        from collections import defaultdict, deque
        per_target=defaultdict(list)
        for item in candidates:per_target[item[1]['target_id']].append(item)
        for group in per_target.values():group.sort(key=lambda x:x[0])
        queues={tid:deque(group) for tid,group in sorted(per_target.items())}
        candidates=[]
        while len(candidates)<limit and any(queues.values()):
            for tid,q in queues.items():
                if q and len(candidates)<limit:candidates.append(q.popleft())
        jobs=[];compiled=0
        for _,t,d,f,image,issue,conflict,match,export_sha in candidates:
            tid=t['target_id'];entry=f['entry']; sha=t['source_sha256']
            if progress:progress('function_begin',target_id=tid,entry=entry)
            stem=f'{tid}-{entry:08x}-{export_sha[:10]}'
            folder=root/stem;folder.mkdir(parents=True,exist_ok=True)
            # A retried job must never inherit compiled artifacts from an earlier run.
            for obsolete in ('function.cpp','function.exe','function','native-smoke.json','comparison.json'):
                candidate=folder/obsolete
                if candidate.is_file() or candidate.is_symlink():candidate.unlink()
            built=None
            test_profile=None
            status='NOT_STARTED';code_status='NOT_LIFTED';boundary='ANALYZER_CANDIDATE';pcode_status='NOT_ATTEMPTED'; reason=''
            if issue:reason=issue;boundary='SOURCE_BYTE_MISMATCH' if 'DIFFER' in issue else 'UNUSABLE_FUNCTION_BODY'
            elif conflict:reason='ghidra_function_instruction_ownership_overlap';boundary='OVERLAPPING_GHIDRA_BODIES'
            elif require_dual and match!='GHIDRA_RIZIN_RANGE_AGREEMENT_UNVERIFIED':reason='independent_boundary_agreement_required'
            if not reason:
                if progress:progress('pypcode_worker',target_id=tid,entry=entry)
                pcode_status=check_pypcode(f,image,d['language'],pypcode_check)
                if progress:progress('codegen_and_compiler',target_id=tid,entry=entry)
                try:
                    built=generate(f,t['isa'],d['language'])
                    code_status='LOWERED_RAW_PCODE_UNVERIFIED'
                    cpp=folder/'function.cpp';cpp.write_text(built['cpp'],encoding='utf-8')
                    test_args=seeded_runner_args(t,f,built,lookup[sha],image)
                    test_profile=('MEGADRIVE_24BIT_ROM_RAM_MIRRORS_HW_WRITE_TRACE_UNVERIFIED'
                                  if test_args is not None else 'UNSEEDED_CPU_STATE_NO_ORIGINAL_REFERENCE')
                    status,detail=compile_cpp(cpp,find_cpp_compiler(compiler),runner_args=test_args,evidence_path=folder/'native-smoke.json') if compile_native else ('CPP_EMITTED_NOT_COMPILED','')
                    reason=detail if detail else ''
                    if status in ('COMPILED_SEEDED_SMOKE_ONLY','COMPILED_RUNNER_SMOKE_ONLY','COMPILED_HARDWARE_TRACE_SMOKE_ONLY'):compiled+=1
                except (Blocked,KeyError,TypeError) as err:
                    reason=str(err);status='BLOCKED_UNSUPPORTED_SEMANTICS';built=None
            if reason and status=='NOT_STARTED':status='BLOCKED_BEFORE_LOWERING'
            manifest={
              'schema':'recomp-function-job-v0.3.2.3','target_id':tid,'source_sha256':sha,
              'entry':entry,'name':f.get('name'),'analyzer':d['analyzer'],
              'ghidra_export_sha256':export_sha,'source_instruction_hashes_verified':not bool(issue),
              'catalogue_candidate_entry':entry in existing.get(tid,set()),
              'boundary_status':boundary,'reconciliation':match,
              'pypcode_crosscheck':pcode_status,'lowering_status':code_status,
              'compile_status':status,'test_profile':test_profile,
              'verification_status':'ORIGINAL_VS_NATIVE_NOT_RUN',
              'blocker':reason,'function_instruction_count':len(f.get('instructions',[])),
              'generated_cpp_sha256':sha_file(folder/'function.cpp') if (folder/'function.cpp').is_file() else None,
              'native_smoke_evidence':'native-smoke.json' if (folder/'native-smoke.json').is_file() else None,
              'register_fields':built['registers'] if built else [],
              'toolchain':'pcode-ghidra-export-checked-cpp-v0323',
              'statement':'Synthetic CPU state and bounded RAM are not real gameplay or CPU parity; whole-function provenance is an analyzer hypothesis.'
            }
            (folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
            jobs.append(manifest)
            with con:
                con.execute('''INSERT OR REPLACE INTO conversion_v031 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
                  tid,sha,entry,export_sha,datetime.now(timezone.utc).isoformat(),d['analyzer'],match,boundary,
                  pcode_status,status,'ORIGINAL_VS_NATIVE_NOT_RUN',reason,manifest['generated_cpp_sha256'],
                  str((folder/'manifest.json').relative_to(root))))
            if progress:progress('function_recorded',target_id=tid,entry=entry,compile_status=status,pypcode_status=pcode_status)
        summary={
          'schema':'recomp-function-campaign-v0.3.2.3','created_utc':datetime.now(timezone.utc).isoformat(),
          'source_scan_errors':scan_errors,'exports':exports,
          'functions_submitted':len(jobs),'cpp_compiled_runner_smoke':compiled,
          'statuses':dict(Counter(j['compile_status'] for j in jobs)),
          'cpp_compiled_total':sum(j['compile_status'].startswith('COMPILED_') for j in jobs),
          'cpp_seeded_smoke_only':sum(j['compile_status']=='COMPILED_SEEDED_SMOKE_ONLY' for j in jobs),
          'cpp_hardware_trace_smoke_only':sum(j['compile_status']=='COMPILED_HARDWARE_TRACE_SMOKE_ONLY' for j in jobs),
          'original_vs_native_parity_passed':0,
          'jobs':[{k:j[k] for k in ('target_id','entry','name','compile_status','reconciliation','blocker','verification_status')} for j in jobs],
          'disclaimer':'No original machine execution parity has been demonstrated. This is function-candidate lowering with compiler smoke only.'
        }
        (root/'campaign.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
        return summary
    finally:con.close()
