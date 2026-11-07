#!/usr/bin/env python3
"""Compiled-controller entrypoint for bounded native analyzer/recovery orchestration.

This script is an isolated compatibility adapter, NOT a production runtime or
translator. All emitted C++ is still created by the compiled controller and DLLs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analysis_integration.providers import acquire,ProviderBlocked,analyze_observed_bank_region
from analysis_integration.recovery_history import import_previous, RecoveryHistoryError

GAPS={'UNTRANSLATED_INITIAL_CODE','BANKED_CODE_NOT_TRANSLATED','UNTRANSLATED_PHYSICAL_ROM_OFFSET'}
SUCCESS={'FRAME_BUDGET_REACHED'}
MAX_LOG=16*1024*1024

class RecoveryBlocked(RuntimeError):pass

def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def checked_process(command:list[str],timeout:int,log:Path,prefix:str)->tuple[int,dict|None]:
    """Run an external native job without a shell; bound time, bytes and process tree.

    Per-round logs are immutable. A timeout/overflow terminates descendants on
    Windows with taskkill /T and on POSIX by killing the child's process group.
    """
    if log.exists():raise RecoveryBlocked('EVIDENCE_OVERWRITE_FORBIDDEN')
    flags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0
    with log.open('xb') as output:
        try:
            proc=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=output,
                stderr=subprocess.STDOUT,shell=False,creationflags=flags,
                start_new_session=os.name!='nt')
        except OSError as exc:raise RecoveryBlocked('PROCESS_LAUNCH_FAILED: '+str(exc)[:200]) from exc
        start=time.monotonic();reason=None
        while proc.poll() is None:
            if time.monotonic()-start>timeout:reason='CHILD_TIMEOUT';break
            if log.stat().st_size>MAX_LOG:reason='CHILD_OUTPUT_SIZE_EXCEEDED';break
            time.sleep(0.08)
        if reason:
            if os.name=='nt':
                try:subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10,check=False)
                except (OSError,subprocess.TimeoutExpired):proc.kill()
            else:
                try:os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                except OSError:proc.kill()
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
            raise RecoveryBlocked(reason+' '+Path(command[0]).name)
        code=proc.returncode
    if log.stat().st_size>MAX_LOG:raise RecoveryBlocked('CHILD_OUTPUT_SIZE_EXCEEDED')
    answer=None
    for line in log.read_bytes().splitlines():
        if line.startswith(prefix.encode('ascii')):
            answer=json.loads(line[len(prefix):])
    return code,answer

def app_stop_seed(doc:dict,rom:Path,source_sha:str)->dict:
    """Record an actual continuous-app stop as *app* evidence, not a fake pilot.

    Source/map/ROM bytes are independently checked again by native discovery.
    The stack pointer is recorded at the actual failing instruction by v0.4.9.11.
    """
    if doc.get('status') not in GAPS:raise RecoveryBlocked('NOT_A_TRANSLATION_GAP')
    if doc.get('rom_bytes')!=rom.stat().st_size or source_sha!=sha(rom):
        raise RecoveryBlocked('APP_SOURCE_IDENTITY_UNVERIFIED')
    required=('native_steps','pc','physical_offset','sp','mapper')
    if any(k not in doc for k in required):raise RecoveryBlocked('APP_STOP_MISSING_OBSERVED_STATE')
    if not isinstance(doc['mapper'],list) or len(doc['mapper'])!=4:
        raise RecoveryBlocked('APP_MAPPER_MISSING')
    return {k:doc[k] for k in ('status','native_steps','pc','physical_offset','sp','mapper','rom_bytes')} | {
        'source_sha256':source_sha,
        'schema':'recompdev.native.app.stop.v1', 'observed_run':'NATIVE_APP_RESULT',
        'source_verification':'RECHECK_BY_NATIVE_DISCOVERY', 'qualification':'UNTRANSLATED_CODE_STOP_ONLY'}

def run(args)->dict:
    rom=Path(args.rom).resolve(strict=True)
    source=Path(args.source_root).resolve(strict=True)
    exe=Path(args.controller_exe).resolve(strict=True)
    plug=Path(args.plugin_dir).resolve(strict=True)
    if not (source/'harness/include/rd_pcode_bridge.hpp').is_file():raise RecoveryBlocked('INVALID_SOURCE_ROOT')
    if (source/'legacy').resolve() in Path(args.out).resolve().parents:
        raise RecoveryBlocked('PROTECTED_EVIDENCE_LOCATION')
    output=Path(args.out).resolve()
    if output.exists():raise RecoveryBlocked('EVIDENCE_ALREADY_EXISTS')
    if output==source or source in output.parents:raise RecoveryBlocked('SOURCE_OUTPUT_OVERLAP')
    if output==rom.parent:raise RecoveryBlocked('ROM_DIRECTORY_OUTPUT_REFUSED')
    if not 1<=args.max_rounds<=8 or not 1<=args.target_frames<=36000 or not 1<=args.step_budget<=20000000 or not 30<=args.timeout<=7200:
        raise RecoveryBlocked('INVALID_BOUNDS')
    original_sha=sha(rom)
    # Verify format through an actual native format provider before selecting
    # hardware-specific analysis adapters; no guessing from ROM filename.
    out_probe=output/'format-discovery'
    output.mkdir(parents=True,exist_ok=False)
    rounds=[]
    state={'schema':'recompdev.native.orchestrator.v1','status':'INITIALIZING',
           'source_sha256':original_sha,'controller_exe':str(exe),
           'max_rounds':args.max_rounds,'target_frames':args.target_frames,
           'provider_api':'analysis_integration.providers.v1',
           'legacy_runtime_fallback':False,'rounds':rounds}
    def snapshot():
        (output/'orchestration.json').write_text(json.dumps(state,indent=2,sort_keys=True)+'\n',encoding='utf8')
    try:
        rc,discovery=checked_process([str(exe),'--stage','discover','--rom',str(rom),
             '--plugin-dir',str(plug),'--out',str(out_probe)],args.timeout,output/'format-discovery.log','UNUSED=')
        if rc:raise RecoveryBlocked('NATIVE_FORMAT_DISCOVERY_FAILED')
        observed=json.loads((out_probe/'native-discovery.json').read_text(encoding='utf8'))
        if observed.get('platform')!='sms' or observed.get('cpu')!='z80':
            raise RecoveryBlocked('NATIVE_TRANSLATION_PROVIDER_NOT_AVAILABLE_FOR_'+str(observed.get('platform')))
        state['native_format_provider']=observed['provider']
        gh,reconcile,analysis=acquire(rom,output/'analysis',export=Path(args.export) if args.export else None,
             ghidra=Path(args.ghidra) if args.ghidra else None,
             rizin=Path(args.rizin) if args.rizin else None,
             tool_roots=tuple(Path(p) for p in args.allow_tool_root),timeout=args.timeout,
             allow_synthetic=args.allow_synthetic_test_export)
        state['analysis']=analysis
        seeds=[];bank_exports=[];seen=set();last_coverage=-1
        if args.resume_from:
            history_seeds,history_banks,history_audit=import_previous(Path(args.resume_from),output/'imported-history',rom,gh)
            seeds.extend(history_seeds);bank_exports.extend(history_banks)
            for report in history_seeds:
                prior=json.loads(report.read_text(encoding='utf8'))
                seen.add((prior['pc'],prior['physical_offset'],tuple(prior['mapper'])))
            state['recovery_history']=history_audit
            snapshot()
        for supplied in args.runtime_gap_report:
            report=Path(supplied).resolve(strict=True)
            if not report.is_file() or report.stat().st_size>8*1024*1024:
                raise RecoveryBlocked('EXTERNAL_GAP_REPORT_INVALID')
            # Each supplied seed is individually re-attested against the ROM
            # and mapper by rd_native_discover in the first translation round.
            seeds.append(report)
        if len(seeds)>64:raise RecoveryBlocked('EXTERNAL_GAP_REPORT_COUNT_LIMIT')
        for index in range(args.max_rounds):
            if sha(rom)!=original_sha:raise RecoveryBlocked('SOURCE_CHANGED_DURING_RECOVERY')
            rd=output/('round-%02d'%(index+1))
            command=[str(exe),'--stage','native-translate','--rom',str(rom),
              '--export',str(gh),'--source-root',str(source),'--plugin-dir',str(plug),
              '--backend','full','--discover-source','--out',str(rd)]
            if args.allow_synthetic_test_export:command.append('--allow-synthetic-export')
            if reconcile is not None:command.extend(('--analysis-candidates',str(reconcile)))
            for p in seeds:command.extend(('--runtime-gap-report',str(p)))
            for p in bank_exports:command.extend(('--bank-export',str(p)))
            for path in args.history_root:command.extend(('--history-root',str(Path(path).resolve(strict=True))))
            if args.no_compile:command.append('--no-compile')
            rc,_=checked_process(command,args.timeout*3,output/('round-%02d-translation.log'%(index+1)), 'UNUSED=')
            if rc:raise RecoveryBlocked('NATIVE_TRANSLATION_OR_BUILD_FAILED_ROUND_'+str(index+1))
            manifest=json.loads((rd/'translation-manifest.json').read_text(encoding='utf8'))
            coverage=manifest.get('emitted',-1)
            record={'round':index+1,'emitted':coverage,'rejected':manifest.get('rejected'),
                    'translation_project':str(rd),'runtime_gap_seeds':len(seeds),
                    'focused_ghidra_bank_exports':len(bank_exports)}
            rounds.append(record);snapshot()
            if coverage<=last_coverage:raise RecoveryBlocked('NO_NEW_VERIFIED_CODE_COVERAGE')
            last_coverage=coverage
            if args.no_execute or args.no_compile:
                state['status']='TRANSLATED_NOT_EXECUTED';break
            app=rd/'build'/'Release'/'RecompDevNativeApp.exe'
            if not app.is_file():app=rd/'build'/'RecompDevNativeApp'
            if not app.is_file():raise RecoveryBlocked('NATIVE_APP_BINARY_NOT_FOUND')
            capture=rd/'run'
            rc,result=checked_process([str(app),str(rom),str(capture),str(args.target_frames),str(args.step_budget),
                 '--mode','HEADLESS_AUTONOMOUS','--video','null','--audio','null',
                 '--input','neutral'],args.timeout,output/('round-%02d-execution.log'%(index+1)), 'NATIVE_APP_RESULT=')
            if rc or result is None:raise RecoveryBlocked('NATIVE_EXECUTION_FAILED_OR_REPORT_MISSING')
            record.update(status=result.get('status'),frames=result.get('frames'),
                          native_steps=result.get('native_steps'),pc=result.get('pc'),
                          physical_offset=result.get('physical_offset'),mapper=result.get('mapper'))
            if sha(rom)!=original_sha:raise RecoveryBlocked('SOURCE_CHANGED_DURING_EXECUTION')
            if result['status'] in SUCCESS and result.get('frames',0)>=args.target_frames:
                state['status']='FRAME_BUDGET_REACHED_PARITY_UNVERIFIED';break
            if result['status'] not in GAPS:
                state['status']='EXECUTION_STOPPED_'+str(result['status']);break
            seed=app_stop_seed(result,rom,original_sha)
            key=(seed['pc'],seed['physical_offset'],tuple(seed['mapper']))
            if key in seen:raise RecoveryBlocked('REPEATED_UNTRANSLATED_STOP_NO_PROGRESS')
            if len(seeds)>=64:raise RecoveryBlocked('RECOVERY_EVIDENCE_LIMIT_REACHED')
            seen.add(key)
            report=output/('round-%02d-observed-stop.json'%(index+1))
            report.write_text(json.dumps(seed,sort_keys=True,indent=2)+'\n',encoding='utf8')
            record['recovery_seed']=str(report)
            seeds.append(report)
            if args.ghidra:
                # The observed bank/PC are rechecked against original ROM bytes.
                # This invokes a real approved Ghidra backend, not an opcode patch.
                bank_file,audit=analyze_observed_bank_region(rom,output/('round-%02d-ghidra-recovery'%(index+1)),
                    ghidra=Path(args.ghidra),tool_roots=tuple(Path(p) for p in args.allow_tool_root),
                    base_export=gh,observed=seed,timeout=args.timeout)
                bank_exports.append(bank_file)
                record['ghidra_focused_region']=audit
            snapshot()
        else:
            state['status']='MAX_RECOVERY_ROUNDS_REACHED'
        state['total_rounds']=len(rounds)
    except (ProviderBlocked,RecoveryBlocked,RecoveryHistoryError,ValueError,OSError,KeyError,json.JSONDecodeError) as exc:
        state['status']='BLOCKED'
        state['reason']=type(exc).__name__+': '+str(exc)[:400]
    snapshot()
    return state

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage',choices=['native-orchestrate'],required=True)
    p.add_argument('--rom',required=True);p.add_argument('--out',required=True)
    p.add_argument('--controller-exe',required=True);p.add_argument('--source-root',required=True)
    p.add_argument('--plugin-dir',required=True)
    p.add_argument('--export');p.add_argument('--ghidra');p.add_argument('--rizin')
    p.add_argument('--allow-tool-root',action='append',default=[])
    p.add_argument('--history-root',action='append',default=[])
    p.add_argument('--resume-from',help='Re-attest observed stops and focused Ghidra exports from a previous orchestration; does not restore binaries')
    p.add_argument('--runtime-gap-report',action='append',default=[])
    p.add_argument('--max-rounds',type=int,default=4);p.add_argument('--target-frames',type=int,default=1800)
    p.add_argument('--step-budget',type=int,default=20000000);p.add_argument('--timeout',type=int,default=600)
    p.add_argument('--no-execute',action='store_true');p.add_argument('--no-compile',action='store_true')
    p.add_argument('--allow-synthetic-test-export',action='store_true',help=argparse.SUPPRESS)
    args=p.parse_args(argv)
    try:result=run(args)
    except Exception as e:
        # Pre-creation blockers still produce a nonzero exit; no success is claimed.
        print('RECOMPDEV_NATIVE_ORCHESTRATION_BLOCKED='+type(e).__name__+': '+str(e),file=sys.stderr)
        return 2
    print('RECOMPDEV_NATIVE_ORCHESTRATION_RESULT='+json.dumps({
        'status':result['status'],'rounds':len(result['rounds']),
        'report':str(Path(args.out).resolve()/'orchestration.json'),
        'reason':result.get('reason','')},sort_keys=True))
    return 0 if result['status'] in ('FRAME_BUDGET_REACHED_PARITY_UNVERIFIED','TRANSLATED_NOT_EXECUTED') else 2
if __name__=='__main__':raise SystemExit(main())
