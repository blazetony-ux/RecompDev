"""Bounded owner-authorized multi-engine static analysis coordinator.

No network/download, no arbitrary shell commands, no hidden title-specific fallbacks.
Only raw mappings with explicit ISA/base/entry. Tool output remains untrusted until
independently checked against original bytes. No native semantics qualification.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from tooling.analysis import reconcile,sha256_file,load_json
from tooling.triage import decide

ROOT=Path(__file__).resolve().parents[1]
MAX_LOG=2*1024*1024
MAX_OUTPUT=32*1024*1024
ISAS={
    'z80':{'rizin_arch':'z80','rizin_bits':'8','ghidra':None},
    'm68k':{'rizin_arch':'m68k','rizin_bits':'32','ghidra':'68000:BE:32:default'},
    'mips':{'rizin_arch':'mips','rizin_bits':'32','ghidra':'MIPS:LE:32:default'},
}
TOOLS={
    'ghidra':{'role':'function discovery, P-code and instruction-byte provenance','features':['static','functions','pcode'],'architectures':['m68k','mips'],'integration':'RUNNABLE_OPTIONAL'},
    'rizin':{'role':'independent disassembly and function boundary hypotheses','features':['static','functions'],'architectures':['z80','m68k','mips'],'integration':'RUNNABLE_OPTIONAL'},
    'mame':{'role':'external hardware reference, separate bounded capture tool','features':['reference'],'architectures':['z80'],'integration':'SEPARATE_EXISTING_ADAPTER'},
    'capstone':{'role':'instruction decoder, not wired as evidence producer','features':['decode'],'architectures':['m68k','mips'],'integration':'NOT_CONNECTED'},
    'unicorn':{'role':'CPU emulator, not wired as independent oracle','features':['cpu'],'architectures':['m68k','mips'],'integration':'NOT_CONNECTED'},
    'angr':{'role':'symbolic analysis, not integrated','features':['symbolic'],'architectures':[],'integration':'NOT_CONNECTED'},
    'z3':{'role':'semantic constraints, not integrated','features':['symbolic'],'architectures':[],'integration':'NOT_CONNECTED'},
}

class Blocked(ValueError):pass

def authorize_tool(path,approved_roots,kind):
    if not approved_roots:raise Blocked('Tool execution requires --allow-tool-root')
    f=Path(path).resolve(strict=True)
    if not f.is_file():raise Blocked('Tool is not a file: '+str(f))
    roots=[Path(p).resolve(strict=True) for p in approved_roots]
    if not any(f==root or root in f.parents for root in roots):
        raise Blocked('Executable outside approved tool roots: '+str(f))
    if kind=='ghidra' and f.name.lower() not in ('analyzeheadless.bat','analyzeheadless','analyzeheadless.sh'):
        raise Blocked('Ghidra executable must be analyzeHeadless')
    if kind=='rizin' and f.name.lower() not in ('rizin.exe','rizin','rz.exe','rz'):
        raise Blocked('Rizin executable must be rizin')
    return f

def _terminate_tree(proc):
    if proc.poll() is not None:return
    if os.name=='nt':
        try:subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True,timeout=8,check=False)
        except (OSError,subprocess.TimeoutExpired):proc.kill()
    else:
        try:os.killpg(proc.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        except OSError:proc.kill()
    try:proc.wait(timeout=8)
    except subprocess.TimeoutExpired:proc.kill()

def _bounded_run(argv,cwd,timeout,logfile):
    """Stream bounded stdout/stderr; terminate on log overflow or timeout."""
    if not 1<=timeout<=3600:raise Blocked('Timeout out of bounds')
    outcome={'status':'BLOCKED','return_code':None,'log_sha256':None,'log_bytes':0}
    overflow=threading.Event()
    flags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0
    with open(logfile,'wb') as log:
        proc=subprocess.Popen([str(a) for a in argv],cwd=str(cwd),stdin=subprocess.DEVNULL,
             stdout=subprocess.PIPE,stderr=subprocess.STDOUT,shell=False,
             creationflags=flags,start_new_session=os.name!='nt')
        def pump():
            total=0
            try:
                while True:
                    chunk=proc.stdout.read(32768)
                    if not chunk:break
                    total+=len(chunk)
                    if total>MAX_LOG:overflow.set();break
                    log.write(chunk)
            finally:
                proc.stdout.close()
        thread=threading.Thread(target=pump,daemon=True);thread.start()
        started=time.monotonic()
        while proc.poll() is None:
            if overflow.is_set():
                _terminate_tree(proc);outcome['status']='OUTPUT_LIMIT';break
            if time.monotonic()-started>timeout:
                _terminate_tree(proc);outcome['status']='TIMEOUT';break
            time.sleep(.05)
        thread.join(timeout=5)
        if overflow.is_set():outcome['status']='OUTPUT_LIMIT'
        elif outcome['status'] not in ('TIMEOUT','OUTPUT_LIMIT'):
            outcome['status']='EXITED' if proc.returncode==0 else 'TOOL_ERROR'
        outcome['return_code']=proc.returncode
    outcome['log_sha256']=sha256_file(logfile)
    outcome['log_bytes']=Path(logfile).stat().st_size
    return outcome

def _write_json(path,doc):
    path=Path(path)
    if path.exists():raise Blocked('Refusing to replace prior evidence: '+str(path))
    temp=path.with_suffix(path.suffix+'.tmp')
    try:
        temp.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        os.replace(temp,path)
    finally:
        if temp.exists():temp.unlink()

def _attempt_rizin(executable,source,base,isa,workspace,timeout):
    # -m sets raw load address. -n suppresses user config; -q quiet; -A does
    # analysis; aflj exports machine-readable function hypotheses.
    argv=[str(executable),'-N','-n','-q','-a',ISAS[isa]['rizin_arch'],
          '-b',ISAS[isa]['rizin_bits'],'-m',hex(base),'-A','-c','aflj',str(source)]
    # This output is JSON, not an unrestricted analysis-script interface.
    with tempfile.TemporaryDirectory(prefix='recompdev-rizin-') as wd:
        out=_bounded_run(argv,wd,timeout,workspace/'rizin-output.log')
    out['tool_sha256']=sha256_file(executable)
    out['tool_version']='NOT_QUERIED'
    if out['status']=='EXITED':
        txt=(workspace/'rizin-output.log').read_text(encoding='utf-8',errors='replace').strip()
        try:
            value=json.loads(txt)
            if not isinstance(value,list):raise ValueError('aflj not a list')
            _write_json(workspace/'rizin-aflj.json',value)
            out['export_sha256']=sha256_file(workspace/'rizin-aflj.json')
        except (ValueError,json.JSONDecodeError) as exc:
            out['status']='UNPARSABLE_JSON';out['error']=str(exc)[:160]
    return out

def _attempt_ghidra(executable,source,base,entry,isa,source_sha,workspace,timeout):
    processor=ISAS[isa]['ghidra']
    if not processor:raise Blocked('Ghidra raw loader integration not enabled for this ISA')
    # Existing export script emits a source SHA *claim*; every exported instruction
    # is independently re-hashed in reconcile() against the owner input.
    with tempfile.TemporaryDirectory(prefix='recompdev-ghidra-') as wd:
        wd=Path(wd);out_file=workspace/'ghidra-functions.json'
        args=[str(executable),str(wd),'RecompDevIndependent', '-import',str(source),
              '-loader','BinaryLoader','-loader-baseAddr',format(base,'x'),'-processor',processor,
              '-scriptPath',str(ROOT/'ghidra'),'-preScript','SeedRecompEntry.java',hex(entry),
              '-postScript','ExportFunctionBodies.java',str(out_file),'source-'+source_sha[:16],source_sha,'500',
              '-analysisTimeoutPerFile',str(max(1,min(timeout-10,timeout//2))),'-readOnly']
        result=_bounded_run(args,wd,timeout,workspace/'ghidra-output.log')
    result['tool_sha256']=sha256_file(executable)
    result['tool_version']='NOT_QUERIED'
    if result['status']=='EXITED':
        if not out_file.is_file() or out_file.stat().st_size>MAX_OUTPUT:
            result['status']='MISSING_OR_OVERSIZED_EXPORT'
        else:
            try:
                data=load_json(out_file)
                if data.get('schema')!='recomp-function-pcode-v1':raise ValueError('unexpected export schema')
                result['export_sha256']=sha256_file(out_file)
            except (ValueError,json.JSONDecodeError) as exc:
                result['status']='UNPARSABLE_EXPORT';result['error']=str(exc)[:160]
    return result

def _validate_source(source,base,entry,isa):
    source=Path(source).resolve(strict=True)
    if not source.is_file() or not 0<source.stat().st_size<=32*1024*1024:
        raise Blocked('Only owner-local raw files up to 32 MiB supported')
    if isa not in ISAS:raise Blocked('Unsupported architecture')
    if type(base) is not int or base<0 or base>=2**63:raise Blocked('Invalid base')
    if type(entry) is not int or not base<=entry<base+source.stat().st_size:
        raise Blocked('Entry is outside raw input mapping')
    return source

def analyze(source,output,isa,base,entry,rizin=None,ghidra=None,allow_tool_roots=(),timeout=180,require_dual=False):
    source=_validate_source(source,base,entry,isa)
    if not rizin and not ghidra:raise Blocked('Select at least one installed analysis tool')
    if require_dual and not (rizin and ghidra):raise Blocked('Dual analysis requires both engines')
    approved={}
    for name,path in [('rizin',rizin),('ghidra',ghidra)]:
        if path:approved[name]=authorize_tool(path,allow_tool_roots,name)
    # Full identity before work. Also verify after each tool run; outputs are
    # never accepted if the source or an approved executable changes.
    sha=sha256_file(source)
    tool_hashes={k:sha256_file(v) for k,v in approved.items()}
    output=Path(output).resolve()
    if output.exists():raise Blocked('Refusing to modify an existing evidence directory')
    if output==source.parent or output in source.parents:raise Blocked('Invalid evidence path')
    output.mkdir(parents=True)
    evidence={'schema':'recomp-multitool-job-v1','source_sha256':sha,
        'source_size':source.stat().st_size,'isa':isa,'base':base,'entry':entry,
        'engines':{},'status':'INCOMPLETE','native_parity':'NOT_TESTED',
        'autorepair':'DISABLED','tool_roots':[str(Path(p).resolve()) for p in allow_tool_roots]}
    try:
        if 'rizin' in approved:
            evidence['engines']['rizin']=_attempt_rizin(approved['rizin'],source,base,isa,output,timeout)
        if 'ghidra' in approved:
            evidence['engines']['ghidra']=_attempt_ghidra(approved['ghidra'],source,base,entry,isa,sha,output,timeout)
        if sha256_file(source)!=sha:raise Blocked('Source changed during analysis; all evidence rejected')
        if any(sha256_file(approved[k])!=v for k,v in tool_hashes.items()):
            raise Blocked('Analyzer executable changed during analysis; evidence rejected')
        exports={k:(output/('rizin-aflj.json' if k=='rizin' else 'ghidra-functions.json'))
            for k,report in evidence['engines'].items() if report['status']=='EXITED'}
        if require_dual and len(exports)!=2:
            evidence['status']='BLOCKED_DUAL_EVIDENCE'
        elif exports:
            summary=reconcile(source,base,isa,ghidra=exports.get('ghidra'),rizin=exports.get('rizin'))
            summary['provenance']={'tool_entry_sha256':tool_hashes,
               'tool_exports_sha256':{k:sha256_file(v) for k,v in exports.items()}}
            _write_json(output/'reconciliation.json',summary)
            evidence['status']='ANALYSIS_RECONCILED' if len(exports)==2 else 'SINGLE_ENGINE_ONLY'
            evidence['reconciliation_sha256']=sha256_file(output/'reconciliation.json')
        else:evidence['status']='BLOCKED_NO_VALID_EVIDENCE'
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        evidence['status']='BLOCKED_AUTHENTICATION_OR_EXECUTION'
        evidence['error']=type(exc).__name__+': '+str(exc)[:260]
    finally:
        evidence['source_sha256_at_completion']=sha256_file(source)
        plan=decide(evidence)
        _write_json(output/'investigation-plan.json',plan)
        evidence['investigation_plan_sha256']=sha256_file(output/'investigation-plan.json')
        _write_json(output/'analysis-job.json',evidence)
    return evidence

def discover(approved_roots):
    """Non-executing, bounded filesystem inventory of owner-specified directories."""
    names={'rizin':{'rizin','rizin.exe','rz','rz.exe'},
           'ghidra':{'analyzeheadless','analyzeheadless.bat','analyzeheadless.sh'},
           'mame':{'mame','mame.exe'}}
    result=[]
    for root in approved_roots:
        folder=Path(root).resolve(strict=True)
        if not folder.is_dir():raise Blocked('Tool inventory root must be a directory')
        todo=[(folder,0)];seen=0
        while todo:
            current,depth=todo.pop()
            for f in current.iterdir():
                seen+=1
                if seen>20000:raise Blocked('Tool inventory size cap exceeded')
                if f.is_symlink():continue
                if f.is_dir() and depth<3:
                    todo.append((f,depth+1))
                elif f.is_file() and f.name.lower() in set().union(*names.values()):
                    for name,aliases in names.items():
                        if f.name.lower() in aliases:
                            result.append({'tool':name,'path':str(f.resolve()),'sha256':sha256_file(f),
                                'status':'DISCOVERED_NOT_EXECUTED','architecture_coverage':'NOT_PROBED'})
    return {'schema':'recomp-tool-discovery-v1','tools':sorted(result,key=lambda x:(x['tool'],x['path'])),
            'no_executables_ran':True}

def capabilities():
    return {'schema':'recomp-tool-capabilities-v1','tools':TOOLS,'source_formats':['raw explicitly mapped'],
       'architecture_support':ISAS,'no_tool_installation':True,'no_game_specific_knowledge':True,
       'note':'Capability catalogue is not proof tools are installed or an architecture is implemented in native code.'}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('capabilities')
    d=sub.add_parser('discover',help='Inventory tool entrypoints without running them')
    d.add_argument('--tool-root',action='append',required=True)
    c=sub.add_parser('analyze',help='Run explicitly approved optional tools, verify outputs and reconcile')
    c.add_argument('--input',required=True);c.add_argument('--output',required=True)
    c.add_argument('--isa',choices=sorted(ISAS),required=True)
    c.add_argument('--base',type=lambda s:int(s,0),required=True)
    c.add_argument('--entry',type=lambda s:int(s,0),required=True)
    c.add_argument('--rizin');c.add_argument('--ghidra')
    c.add_argument('--allow-tool-root',action='append',default=[])
    c.add_argument('--timeout',type=int,default=180)
    c.add_argument('--require-dual',action='store_true')
    r=sub.add_parser('reconcile',help='Reconcile external exports without executing tools')
    r.add_argument('--input',required=True);r.add_argument('--isa',choices=sorted(ISAS),required=True)
    r.add_argument('--base',type=lambda s:int(s,0),required=True)
    r.add_argument('--ghidra');r.add_argument('--rizin');r.add_argument('--output',required=True)
    args=p.parse_args(argv)
    if args.command=='capabilities':result=capabilities()
    elif args.command=='discover':result=discover(args.tool_root)
    elif args.command=='analyze':
        result=analyze(args.input,args.output,args.isa,args.base,args.entry,args.rizin,args.ghidra,args.allow_tool_root,args.timeout,args.require_dual)
    else:
        result=reconcile(args.input,args.base,args.isa,args.ghidra,args.rizin)
        _write_json(Path(args.output).resolve(),result)
    print(json.dumps(result,indent=2))
    return 0 if result.get('status','OK') not in ('BLOCKED_DUAL_EVIDENCE','BLOCKED_NO_VALID_EVIDENCE','BLOCKED_AUTHENTICATION_OR_EXECUTION') else 2

if __name__=='__main__':
    try:raise SystemExit(main())
    except (Blocked, ValueError, OSError, json.JSONDecodeError) as exc:
        import sys
        print(json.dumps({'schema':'recomp-tool-error-v1','status':'BLOCKED',
                          'error':type(exc).__name__+': '+str(exc)[:300]}),file=sys.stderr)
        raise SystemExit(2)

