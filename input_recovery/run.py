#!/usr/bin/env python3
"""Source-verified, bounded input-driven native recovery; no game-specific rules.

An earlier interactive capture is converted into a guest-cycle replay and
checked against the SAME compiled game before being used by the untouched
production recovery engine. Actual code recovery remains hash/source verified.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

SOURCE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SOURCE))
from input_recovery.replay import create_replay
from runtime_host.launch import sha256
from modular.evidence_bundle import create_evidence_bundle
from workspace.manager import roots,manifest,read_state


def original_evidence(root:Path,rom_hash:str)->Path:
    matches=[]
    for v in sorted(root.glob('v*')):
        for file in (v/'runtime-host').glob('*-evidence.zip'):
            try:
                import zipfile
                with zipfile.ZipFile(file) as z:
                    info=z.getinfo('evidence/runtime-host-report.json')
                    if info.file_size>2*1048576:continue
                    doc=json.loads(z.read(info))
                if doc.get('source_rom_sha256')==rom_hash and doc.get('input_event_capture')!='NOT_AVAILABLE':
                    matches.append(file)
            except (OSError,ValueError,KeyError,zipfile.BadZipFile):continue
    if not matches:raise FileNotFoundError('No previous input-enabled native-runtime evidence ZIP matches the ROM; provide --evidence-zip')
    return max(matches,key=lambda p:p.stat().st_mtime)


def execute(cmd:list[str],log:Path,timeout:int,*,env=None)->dict:
    log.parent.mkdir(parents=True,exist_ok=True)
    try:
        with log.open('w',encoding='utf8') as out:
            # Command line contains owner-local paths only; it is not a shell.
            out.write('EXECUTABLE: '+str(cmd[0])+'\n')
            out.flush()
            proc=subprocess.run([str(x) for x in cmd],cwd=SOURCE,env=env,
                                stdout=out,stderr=subprocess.STDOUT,
                                timeout=timeout,check=False)
        return {'return_code':proc.returncode,'timeout':False,'log':str(log)}
    except subprocess.TimeoutExpired:
        with log.open('a',encoding='utf8') as out:out.write('\nRECOMPDEV_CHILD_TIMEOUT\n')
        return {'return_code':None,'timeout':True,'log':str(log)}


def matching_native_report(evidence_root:Path,version:str,replay_hash:str,rom_hash:str,
                           project:Path,*,since:float)->tuple[Path,dict]:
    """Only accept a newly generated report for the exact source project.

    A stale preflight with the same input file hash must never count as the
    outcome of a failed or timed-out new subprocess.
    """
    directory=evidence_root/version/'runtime-host'
    reports=sorted(directory.glob('*/runtime-host-report.json'),
                   key=lambda p:p.stat().st_mtime,reverse=True)
    for p in reports:
        if p.stat().st_mtime<since-2:continue
        try:
            doc=read_review(p)
            if (doc.get('input_replay_sha256')==replay_hash
                    and doc.get('source_rom_sha256')==rom_hash
                    and Path(doc.get('original_project') or '').resolve()==Path(project).resolve()):
                return p,doc
        except (OSError,ValueError,KeyError):pass
    raise ValueError('No matching new native execution report for replay and project')


def read_review(output:Path)->dict:
    if not output.is_file():raise ValueError('Missing native replay runtime report')
    return json.loads(output.read_text(encoding='utf8'))


def reproduce(previous:dict,observed:dict)->dict:
    """Fail closed when the replay does not recreate the original stop.

    Exact input timing cannot imply hardware parity; only matching *observed*
    guest stop and frame count is asserted here.
    """
    same_stop=previous.get('prior_status')==observed.get('guest_status')
    old_pc=previous.get('prior_pc')
    new_pc=observed.get('guest_stop_pc')
    same_pc=old_pc is not None and new_pc is not None and int(old_pc)==int(new_pc)
    old_frames=previous.get('prior_frames')
    new_frames=observed.get('frames_observed')
    same_frames=(type(old_frames)==int and type(new_frames)==int and abs(old_frames-new_frames)<=2)
    result={'status':'STOP_REPRODUCED' if same_stop and same_pc and same_frames else 'REPLAY_DIVERGED',
            'same_stop_kind':same_stop,'same_pc':same_pc,'frames_within_two':same_frames,
            'previous_stop':previous.get('prior_status'),'replay_stop':observed.get('guest_status'),
            'previous_pc':old_pc,'replay_pc':new_pc,
            'previous_frames':old_frames,'replay_frames':new_frames,
            'input_timing':previous.get('method'),
            'gameplay_parity':'NOT_ESTABLISHED'}
    return result


def copy_native_build_logs(recovery_dir: Path, destination: Path) -> list[str]:
    """Include CMake diagnostics in the upload ZIP, not the compiler build tree.

    Generated native-project folders are intentionally omitted by the generic
    ZIP packager. Copy only small named text logs from the verified project.
    """
    copied = []
    for project in sorted((recovery_dir / 'recovery').glob('round-*/native-project')):
        if project.is_symlink():
            continue
        for name in ('configure.log', 'build.log', 'external-native-build.json'):
            original = project / 'compiler-evidence' / name
            if not original.is_file() or original.is_symlink() or original.stat().st_size > 4 * 1024 * 1024:
                continue
            target = destination / project.parent.name / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target)
            copied.append(str(target))
    return copied


def recovery_build_failed(controller: dict) -> bool:
    """Never launch a partial native project after a failed CMake build."""
    if controller.get('legacy_recovery_status') in ('BUILD_FAILED', 'BUILD_TIMEOUT'):
        return True
    # A controller failure can precede a legacy structured status.
    return controller.get('recovery_stop_reason') in ('LEGACY_REPORT_MISSING', 'LEGACY_SERVICE_EXIT_1')


def select_project(run_dir:Path)->Path|None:
    candidates=list((run_dir/'recovery').glob('round-*/native-project'))
    valid=[p for p in candidates if (p/'translated.cpp').is_file() and (p/'generation.json').is_file()]
    return sorted(valid,key=lambda p:p.parent.name)[-1] if valid else None


def run(args)->int:
    cfg=roots(SOURCE)
    rom=Path(args.rom).resolve(strict=True)
    if rom.stat().st_size>64*1024*1024 or not rom.is_file():raise ValueError('Invalid owner-local ROM')
    rom_hash=sha256(rom)
    archive=Path(args.evidence_zip).resolve(strict=True) if args.evidence_zip else original_evidence(cfg['evidence'],rom_hash)
    runid=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    version=manifest(SOURCE)['workspace_release']
    out=cfg['evidence']/version/'input-recovery'/runid
    out.mkdir(parents=True,exist_ok=False)
    report={'schema':'recompdev-input-driven-recovery-v0.4.9','status':'NOT_STARTED',
            'input_recovery_component_version':'0.1.0','source_rom_sha256':rom_hash,
            'original_evidence_zip':str(archive),'source_rom_copied':False,
            'original_recovery_engine_unchanged':True,
            'controller_and_unrelated_plugins_rebuilt':False,
            'gameplay_parity':'NOT_ESTABLISHED'}
    started=time.monotonic()
    try:
        replay_path=out/'input-replay.csv'
        info=create_replay(archive,rom_hash,replay_path,guest_hz=args.guest_hz)
        report['input_capture']=info
        (out/'replay-manifest.json').write_text(json.dumps(info,indent=2,sort_keys=True)+'\n',encoding='utf8')
        prior=Path(info.get('prior_generated_project') or '')
        if not prior.is_dir() or not (prior/'translated.cpp').is_file():
            raise FileNotFoundError('Original generated native project is unavailable; restore its external evidence directory')
        if not prior.resolve().is_relative_to(cfg['evidence'].resolve()):
            raise ValueError('Previous native project must be inside external evidence root')
        # Deterministic preflight: no recompilation recovery until prior code stop
        # has been reproduced from same initial state, ROM and logical inputs.
        preflight_cmd=[sys.executable,'-B','-m','runtime_host.launch',
            '--rom',str(rom),'--project',str(prior),'--mode','headless',
            '--input-events',str(replay_path),'--frames',str(args.frames),
            '--steps',str(args.steps),'--timeout',str(min(900,args.timeout)),
            '--snapshot-every','120']
        preflight_started=time.time()
        report['replay_preflight_execution']=execute(preflight_cmd,out/'replay-preflight.log',min(900,args.timeout))
        if report['replay_preflight_execution']['timeout']:
            raise RuntimeError('Replay preflight timed out')
        replay_report_path,preflight=matching_native_report(
            cfg['evidence'],version,sha256(replay_path),rom_hash,prior,since=preflight_started)
        report['replay_evidence_report']=str(replay_report_path)
        match=reproduce(info,preflight)
        report['replay_validation']=match
        if match['status']!='STOP_REPRODUCED':
            report['status']='REPLAY_NOT_REPRODUCED'
            report['next_action']='Capture exact guest-cycle input using the v0.4.9 interactive launcher; approximate wall-time input may diverge.'
        else:
            original_run=prior.parent.parent.parent  # run/recovery/round-N/native-project
            export=original_run/'preparation'/'functions.json'
            if not export.is_file():export=None
            recovery_out=out/'production-recovery'
            entry=cfg['runtime']/'RecompDev.exe'
            if not entry.is_file():raise FileNotFoundError('Compiled controller not installed: '+str(entry))
            command=[str(entry),'--rom',str(rom),'--stage','recover',
                     '--cpu-plugin','required','--frames',str(args.frames),
                     '--steps',str(args.steps),'--max-recoveries',str(args.max_recoveries),
                     '--max-rounds',str(args.max_rounds),'--timeout',str(args.timeout),
                     '--capture-hardware','--input-events',str(replay_path),
                     '--history-root',str(original_run),'--out',str(recovery_out)]
            if export:command+=['--export',str(export)]
            report['recovery_execution']=execute(command,out/'recovery-command.log',args.timeout+60)
            report['compiler_diagnostics']=copy_native_build_logs(recovery_out,out/'compiler-logs')
            controller_report=recovery_out/'controller-report.json'
            if not controller_report.is_file():
                raise RuntimeError('Production recovery produced no structured report; consult recovery-command.log')
            rec=json.loads(controller_report.read_text(encoding='utf8'))
            if report['recovery_execution']['timeout']:
                raise RuntimeError('Production recovery timed out; postflight not started')
            report['recovery_status']=rec.get('status')
            report['recovery_stop_reason']=rec.get('recovery_stop_reason')
            report['recovery_report']=str(controller_report)
            report['new_recovered_entries']=rec.get('recovered_entries')
            report['recovery_frames']=rec.get('maximum_frames_observed')
            report['recovery_history'] = None
            summary = recovery_out / 'recovery' / 'continuous-recovery-report.json'
            if summary.is_file():
                summary_data=json.loads(summary.read_text(encoding='utf8'))
                report['recovery_history'] = []
                for summary_round in summary_data.get('rounds', []):
                    try:
                        round_json = Path(summary_round['report'])
                        round_dir = recovery_out / 'recovery' / ('round-%02d' % summary_round['index'])
                        if not round_json.is_file() or not round_json.resolve().is_relative_to(round_dir.resolve()):
                            continue
                        round_data=json.loads(round_json.read_text(encoding='utf8'))
                        report['recovery_history'].append({
                            'round':summary_round['index'],
                            'coverage_cache':round_data.get('coverage_cache'),
                            'status':round_data.get('status')})
                    except (OSError,KeyError,ValueError,TypeError):
                        continue
            report['post_recovery_frame_advance_confirmed']=False
            if recovery_build_failed(rec):
                # No execution of stale/incomplete generated projects. Previous
                # preflight success remains recorded as the verified baseline.
                report['status']='RECOVERY_BUILD_FAILED'
                report['post_recovery_skipped_reason']='NATIVE_COMPILATION_FAILED'
                report['gameplay_parity']='NOT_ESTABLISHED'
                fresh=None
            else:
                fresh=select_project(recovery_out)
            baseline=int(info.get('prior_frames') or 0)
            if fresh:
                # Only game-code app objects are rebuilt. Old controller/DLLs
                # and archived source-verified native projects stay unchanged.
                post_cmd=[sys.executable,'-B','-m','runtime_host.launch',
                   '--rom',str(rom),'--project',str(fresh),'--mode','headless',
                   '--input-events',str(replay_path),'--frames',str(args.frames),
                   '--steps',str(args.steps),'--timeout',str(min(900,args.timeout))]
                post_started=time.time()
                report['post_recovery_execution']=execute(post_cmd,out/'post-recovery.log',min(900,args.timeout))
                if not report['post_recovery_execution']['timeout']:
                    try:
                        post_path,post=matching_native_report(
                            cfg['evidence'],version,sha256(replay_path),rom_hash,fresh,since=post_started)
                        report['post_recovery_native_report']=str(post_path)
                        report['post_recovery_guest_status']=post.get('guest_status')
                        report['post_recovery_guest_pc']=post.get('guest_stop_pc')
                        report['post_recovery_frames']=post.get('frames_observed')
                        report['post_recovery_frame_advance_confirmed']=int(post.get('frames_observed') or 0)>baseline
                    except (OSError,ValueError,RuntimeError,TypeError) as post_error:
                        report['post_recovery_validation_error']=str(post_error)
            if report['status']=='RECOVERY_BUILD_FAILED':
                pass
            elif report['post_recovery_frame_advance_confirmed']:
                report['status']='SOURCE_VERIFIED_RECOVERY_ADVANCED'
            else:
                report['status']='RECOVERY_ATTEMPTED_NO_CONFIRMED_ADVANCE'
            report['gameplay_parity']='NOT_ESTABLISHED'
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as exc:
        report.update(status='INPUT_RECOVERY_BLOCKED',error=type(exc).__name__+': '+str(exc)[:1000])
    finally:
        report['elapsed_wall_seconds']=round(time.monotonic()-started,3)
        (out/'input-recovery-report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf8')
        try:
            bundle=create_evidence_bundle(out,source_sha256=rom_hash,status=report['status'])
            report['evidence_zip']=bundle['path']
            print('RECOMPDEV_EVIDENCE_ZIP='+bundle['path'],flush=True)
        except (OSError,ValueError,RuntimeError) as exc:
            report['evidence_zip_error']=str(exc)
        print(json.dumps(report,indent=2,sort_keys=True),flush=True)
    return 0 if report['status']=='SOURCE_VERIFIED_RECOVERY_ADVANCED' else 2


def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',required=True)
    p.add_argument('--evidence-zip',default='',help='Previous native window-run evidence ZIP; default newest matching capture')
    p.add_argument('--guest-hz',type=int,help='Needed only to estimate older wall-clock input; supplied by machine configuration')
    p.add_argument('--frames',type=int,default=1800)
    p.add_argument('--steps',type=int,default=15000000)
    p.add_argument('--max-recoveries',type=int,default=4)
    p.add_argument('--max-rounds',type=int,default=8)
    p.add_argument('--timeout',type=int,default=3600)
    args=p.parse_args(argv)
    if not 1<=args.frames<=36000 or not 1<=args.steps<=20000000 or not 0<=args.max_recoveries<=24 or not 1<=args.max_rounds<=12 or not 60<=args.timeout<=7200:
        p.error('Recovery limits are outside supported bounds')
    try:return run(args)
    except (OSError,ValueError,RuntimeError) as exc:
        print('RECOMPDEV_INPUT_RECOVERY_FAILED: '+str(exc),file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
