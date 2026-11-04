"""One source-attested bounded campaign: analysis -> translation -> execution -> diagnosis.

Never labels an unaligned reference comparison as parity, never auto-patches the
original source, and never silently runs third-party executables. Separate
architecture plugins share the same immutable evidence/stage contract.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from nativecore.alignment import compare_anchors
from nativecore.hardware_gate import compare as compare_hardware
from nativecore.m68k_fixture import lower as lower_68k
from campaign.m68k_oracle import run as python_68k_oracle
from tooling.orchestrator import analyze as analyzer_run

SCHEMA='recomp-unified-campaign-v1'

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def atomic_json(path,obj):
    path=Path(path)
    if path.exists():raise ValueError('Immutable evidence exists: '+str(path))
    temp=path.with_suffix(path.suffix+'.tmp')
    try:
        temp.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        os.replace(temp,path)
    finally:
        if temp.exists():temp.unlink()

def run(source,output,isa,base=0,entry=None,db=None,rom_roots=(),steps=50000,
        rizin=None,ghidra=None,approved_tool_roots=(),reference_anchors=None,
        reference_hardware=None,synthetic=False,compiler=None):
    source=Path(source).resolve(strict=True);output=Path(output).resolve()
    if not source.is_file() or source.is_symlink() or not 0<source.stat().st_size<=32*1024*1024:
        raise ValueError('Missing, symlinked or oversized owner input')
    if isa not in ('z80','m68k'):raise ValueError('No executable campaign backend for '+str(isa))
    if output.exists():raise ValueError('Refusing to alter an existing campaign directory')
    if type(base)!=int or base<0 or type(steps)!=int or not 1<=steps<=2000000:
        raise ValueError('Invalid raw base or bounded execution budget')
    if not synthetic and isa=='m68k':
        raise ValueError('Restricted m68k backend requires explicit --synthetic-fixture consent')
    if isa=='m68k' and source.stat().st_size>65536:raise ValueError('Restricted m68k fixture too large')
    if any((rizin,ghidra)) and not approved_tool_roots:
        raise ValueError('External tools require explicit approved roots')
    if entry is None:entry=base
    sha=digest(source);output.mkdir(parents=True,exist_ok=False)
    report={'schema':SCHEMA,'version':'0.4.0.21','status':'RUNNING',
       'source_sha256':sha,'isa':isa,'source_bytes':source.stat().st_size,
       'started_utc':datetime.now(timezone.utc).isoformat(),'stages':[],
       'reference_parity':'NOT_TESTED','native_qualified':False,'gameplay':'NOT_ESTABLISHED',
       'tool_execution_opt_in':bool(rizin or ghidra),'repair_performed':False,
       'release_milestones':{'unified_campaign':'RUNNING','reference_alignment':'NOT_TESTED',
                             'semantic_repair':'NOT_TESTED','hardware_qualification':'NOT_TESTED',
                             'standalone_game':'NOT_ESTABLISHED','second_isa':'NOT_TESTED'}}
    def stage(name,status,details=None):
        report['stages'].append({'stage':name,'status':status,'details':details or {}})
    try:
        stage('SOURCE_AUTHENTICATED','PASS',{'sha256':sha})
        if rizin or ghidra:
            outcome=analyzer_run(source,output/'static-analysis',isa,base,entry,rizin=rizin,ghidra=ghidra,
                                 allow_tool_roots=approved_tool_roots,timeout=180)
            stage('MULTI_TOOL_ANALYSIS',outcome.get('status','UNKNOWN'),{
                    'report':'static-analysis/analysis-job.json',
                    'source_sha256':outcome.get('source_sha256_at_completion')})
            if outcome.get('status') not in ('ANALYSIS_RECONCILED','SINGLE_ENGINE_ONLY'):
                stage('ANALYZER_HANDOFF','BLOCKED','Untrusted or incomplete analyzer output')
            else:
                stage('ANALYZER_HANDOFF','HYPOTHESES_ONLY',{'note':'Tool results are not executable P-code or CPU parity'})
        else:stage('MULTI_TOOL_ANALYSIS','SKIPPED_NO_OWNER_OPT_IN')
        if digest(source)!=sha:raise ValueError('Source bytes changed during analysis')
        if isa=='m68k':
            cpp=output/'generated'/'fixture.cpp'
            translation=lower_68k(source,cpp,base)
            stage('NATIVE_TRANSLATION','PASS_RESTRICTED_SYNTHETIC',translation)
            exe=output/'generated'/('fixture.exe' if os.name=='nt' else 'fixture')
            # Executing a host compiler is owner-opt-in via --compiler. Nothing
            # is run through a shell; source size and process budget are bounded.
            if not compiler:
                stage('COMPILE_AND_RUN','BLOCKED_NO_COMPILER_APPROVAL',{'note':'Pass --compiler absolute path to run the generated fixture'})
            else:
                requested=Path(compiler)
                comp=requested.resolve(strict=True)
                import re
                if not comp.is_file() or not re.fullmatch(r'(?:[a-z0-9_+-]*-)?(?:g\+\+|clang\+\+)(?:-\d+)?|cl(?:\.exe)?|cmake(?:\.exe)?',requested.name.lower()):
                    raise ValueError('Unsupported explicit compiler/build tool entrypoint')
                if requested.name.lower() in ('cmake','cmake.exe'):
                    # CMake can find the installed MSVC toolchain on the owner's
                    # Windows host without invoking arbitrary user commands.
                    (cpp.parent/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.16)\nproject(RecompFixture LANGUAGES CXX)\nadd_executable(fixture fixture.cpp)\nset_property(TARGET fixture PROPERTY CXX_STANDARD 17)\n',encoding='utf-8')
                    build=cpp.parent/'build'
                    configure=subprocess.run([str(comp),'-S',str(cpp.parent),'-B',str(build)],capture_output=True,text=True,timeout=70)
                    if configure.returncode:
                        proc=configure
                    else:
                        proc=subprocess.run([str(comp),'--build',str(build),'--config','Release','--parallel','2'],
                             capture_output=True,text=True,timeout=90)
                        if proc.returncode==0:
                            found=list(build.glob('**/fixture.exe'))+list(build.glob('**/fixture'))
                            if found:exe=found[0]
                elif requested.name.lower() in ('cl.exe','cl'):
                    proc=subprocess.run([str(comp),'/nologo','/EHsc','/O2',str(cpp),'/Fe:'+str(exe)],
                         cwd=cpp.parent,capture_output=True,text=True,timeout=90,check=False)
                else:
                    proc=subprocess.run([str(comp),'-std=c++17','-O2',str(cpp),'-o',str(exe)],
                         capture_output=True,text=True,timeout=90,check=False)
                (output/'compiler.log').write_text((proc.stdout+proc.stderr)[-100000:],encoding='utf-8')
                if proc.returncode or not exe.is_file():
                    stage('COMPILE_AND_RUN','COMPILER_FAILED',{'return_code':proc.returncode})
                else:
                    proc=subprocess.run([str(exe)],capture_output=True,text=True,timeout=10)
                    if proc.returncode:raise ValueError('Compiled fixture exited nonzero')
                    observed=json.loads(proc.stdout)
                    independent=python_68k_oracle(source.read_bytes(),base)
                    agree=observed==independent
                    atomic_json(output/'native-oracle-comparison.json',{
                      'schema':'recomp-restricted-isa-comparison-v1', 'status':'MATCHED_RESTRICTED_FIXTURE' if agree else 'DIVERGED',
                      'native':observed,'oracle':independent,'source_sha256':sha,
                      'reference_kind':'AUTHOR_CREATED_PYTHON_TEST_ORACLE_NOT_EXTERNAL_CPU_ENGINE',
                      'general_native_parity':False,'flags_memory_interrupts_tested':False})
                    stage('COMPILE_AND_RUN','MATCHED_RESTRICTED_FIXTURE' if agree else 'DIVERGED',
                          {'report':'native-oracle-comparison.json','native_executable_sha256':digest(exe),
                           'compiler_sha256':digest(comp)})
                    report['release_milestones']['second_isa']='RESTRICTED_FIXTURE_PASS' if agree else 'BLOCKED_DIVERGENCE'
        else:
            if not db or not rom_roots:
                stage('NATIVE_TRANSLATION','BLOCKED_NEEDS_PREPARED_CATALOGUE',
                      {'reason':'Z80 requires the existing source-attested discovery/preparation catalogue and allowed ROM roots'})
            else:
                from nativepilot.engine import pilot
                p=pilot(db,sha,output/'z80-native-pilot',rom_roots,max_steps=steps,adaptive=True)
                stage('NATIVE_TRANSLATION_AND_EXECUTION',p['status'],{
                    'report':'z80-native-pilot/pilot-report.json','translated_instructions':p.get('translated_instructions',0),
                    'native_steps':p.get('native_steps',0),'reference_parity':p.get('reference_parity')})
        if reference_anchors:
            bundle=json.loads(Path(reference_anchors).read_text(encoding='utf-8'))
            if bundle.get('schema')!='recomp-explicit-anchor-pair-v1':raise ValueError('Invalid alignment bundle')
            alignment=compare_anchors(bundle['reference'],bundle['native'],source)
            atomic_json(output/'alignment.json',alignment)
            stage('REFERENCE_ALIGNMENT',alignment['status'],{'report':'alignment.json'})
            report['release_milestones']['reference_alignment']=alignment['status']
        else:
            alignment={'status':'NOT_TESTED','hardware_aligned':False}
            stage('REFERENCE_ALIGNMENT','BLOCKED_NO_COMPARABLE_REFERENCE')
        if reference_hardware:
            bundle=json.loads(Path(reference_hardware).read_text(encoding='utf-8'))
            hw=compare_hardware(bundle['reference'],bundle['native'],alignment)
            atomic_json(output/'hardware-comparison.json',hw)
            stage('HARDWARE_QUALIFICATION',hw['status'],{'report':'hardware-comparison.json'})
            report['release_milestones']['hardware_qualification']=hw['status']
        else:stage('HARDWARE_QUALIFICATION','BLOCKED_NO_ALIGNED_HARDWARE_EVIDENCE')
        stage('REPAIR','NOT_PERFORMED_REQUIRES_SEPARATE_APPROVED_HOLDOUTS')
        stage('STANDALONE_GAME','NOT_QUALIFIED_NO_GAMEPLAY_PARITY')
        report['release_milestones']['unified_campaign']='IMPLEMENTED_BOUNDED'
        report['status']='FINISHED_WITH_EXPLICIT_GATES'
    except (ValueError,RuntimeError,OSError,KeyError,TypeError,subprocess.SubprocessError) as exc:
        stage('PIPELINE_ERROR','BLOCKED',{'error':type(exc).__name__+': '+str(exc)[:500]})
        report['status']='BLOCKED'
    finally:
        report['finished_utc']=datetime.now(timezone.utc).isoformat()
        report['source_unchanged']=source.is_file() and digest(source)==sha
        if not report['source_unchanged']:report['status']='BLOCKED_SOURCE_MUTATED'
        atomic_json(output/'campaign-report.json',report)
    return report

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True);p.add_argument('--output',required=True)
    p.add_argument('--isa',required=True,choices=('z80','m68k'))
    p.add_argument('--base',type=lambda x:int(x,0),default=0)
    p.add_argument('--entry',type=lambda x:int(x,0))
    p.add_argument('--db');p.add_argument('--rom-root',action='append',default=[])
    p.add_argument('--steps',type=int,default=50000)
    p.add_argument('--rizin');p.add_argument('--ghidra');p.add_argument('--allow-tool-root',action='append',default=[])
    p.add_argument('--reference-anchors');p.add_argument('--reference-hardware')
    p.add_argument('--synthetic-fixture',action='store_true')
    p.add_argument('--compiler',help='Explicit host C++ compiler entrypoint (required to compile restricted m68k fixtures)')
    a=p.parse_args(argv)
    r=run(a.input,a.output,a.isa,a.base,a.entry,a.db,a.rom_root,a.steps,a.rizin,a.ghidra,a.allow_tool_root,
          a.reference_anchors,a.reference_hardware,a.synthetic_fixture,a.compiler)
    print(json.dumps({'status':r['status'],'report':str(Path(a.output)/'campaign-report.json'),
                      'stages':[(s['stage'],s['status']) for s in r['stages']]},indent=2))
    return 0 if r['status']=='FINISHED_WITH_EXPLICIT_GATES' else 2
if __name__=='__main__':raise SystemExit(main())
