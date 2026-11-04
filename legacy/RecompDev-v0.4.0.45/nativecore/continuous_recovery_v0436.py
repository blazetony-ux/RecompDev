"""Bounded owner-local continuous native-code recovery, rebuild and reset-replay.

Only attested Z80 P-code is translated. ROM, Ghidra and CMake remain local. No
emulator fallback, no inferred bank state, no game-name rules, no parity claim.
"""
import hashlib
import importlib.util
import json
import subprocess
import time
from pathlib import Path
from nativecore.recovery import RecoveryPlanner, classify, MISSING_CODE
from nativecore.adapters import provider_for
from nativecore.verified_coverage_v0443 import VerifiedCoverageCache
from nativepilot.generator import generate_project, verify_export, sha256
from nativepilot.engine import _build

ROOT=Path(__file__).resolve().parents[1]
SCHEMA='recomp-continuous-recovery-v0440'

def native_session(project,rom,source_hash,out,frames,steps,input_events,*,capture_hardware=False):
    spec=importlib.util.spec_from_file_location('recomp_continuous_native',ROOT/'tools'/'Run-Continuous-Native.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run(project,rom,source_hash,out,frames=frames,steps=steps,
                      input_events=input_events,mode='HEADLESS_AUTONOMOUS',
                      video_backend='capture' if capture_hardware else 'null',
                      audio_backend='capture' if capture_hardware else 'null')

def run(rom,export,output,*,frames=120,steps=2000000,max_recoveries=3,
        input_events=None,recover=None,build=None,session=None,compile_timeout=480,capture_hardware=False,coverage_cache=None,history_roots=()):
    rom=Path(rom).resolve(strict=True);export=Path(export).resolve(strict=True)
    output=Path(output).resolve()
    if not rom.is_file() or rom.is_symlink() or not 0<rom.stat().st_size<=64*1024*1024:
        raise ValueError('Invalid owner-local cartridge')
    if not export.is_file() or export.is_symlink() or export.stat().st_size>128*1024*1024:
        raise ValueError('Invalid initial Ghidra export')
    if type(frames)!=int or not 1<=frames<=36000 or type(steps)!=int or not 1<=steps<=20000000:
        raise ValueError('Invalid bounded continuous runtime budget')
    if type(compile_timeout)!=int or not 30<=compile_timeout<=1800:raise ValueError('Invalid bounded compilation timeout')
    if type(capture_hardware)!=bool:raise ValueError('Invalid capture policy')
    planner=RecoveryPlanner(max_recoveries)
    checkpoints=[f for f in (120,300,600,1800) if f<frames]+[frames]
    checkpoints=sorted(set(checkpoints))
    # A short caller-requested run is never automatically lengthened.
    if frames<120:checkpoints=[frames]
    source=sha256(rom)
    doc=json.loads(export.read_text(encoding='utf-8'))
    initial,_,_=verify_export(doc,rom)
    target_id=doc.get('target_id')
    if not isinstance(target_id,str) or not target_id or len(target_id)>256:
        raise ValueError('Initial export lacks bounded target identity')
    if doc['source_sha256']!=source:raise ValueError('Initial export source identity mismatch')
    if not initial:raise ValueError('Initial export has no attested instructions')
    input_file=None;input_hash=None
    if input_events is not None:
        input_file=Path(input_events).resolve(strict=True)
        if not input_file.is_file() or input_file.is_symlink() or input_file.stat().st_size>1048576:
            raise ValueError('Invalid bounded input replay')
        input_hash=sha256(input_file)
    if output.exists() and any(output.iterdir()):raise ValueError('Evidence directory must be empty for a new attempt')
    output.mkdir(parents=True,exist_ok=True)
    project=output/'native-project';overlays=[]
    known_offsets=set(initial)
    cache=None
    cache_stats={'mode':'DISABLED','loaded_documents':0,'loaded_instruction_offsets':0,
                 'imported_history_documents':0,'new_documents_saved':0}
    if coverage_cache is not None:
        cache=VerifiedCoverageCache(coverage_cache,source,target_id,doc['language'])
        overlays,loaded,retained=cache.load(rom,doc)
        # One-time import of historic source-attested recovery exports only.
        # Subsequent owner runs reuse SQLite without scanning old jobs.
        if history_roots and not retained:
            stats=cache.import_history(rom,history_roots)
            cache_stats['imported_history_documents']=stats['matching_exports_imported']
            cache_stats['history_files_examined']=stats['files_examined']
            overlays,loaded,retained=cache.load(rom,doc)
        known_offsets.update(loaded)
        cache_stats.update(mode='SOURCE_REATTESTED_SQLITE',loaded_documents=len(overlays),
                           loaded_instruction_offsets=len(loaded),stored_documents=retained,
                           cache_path=str(cache.path))
    report={'schema':SCHEMA,'source_sha256':source,'target_id':target_id,'system':'mastersystem',
            'frames_requested':frames,'steps_requested':steps,'max_recoveries':max_recoveries,'compile_timeout_seconds':compile_timeout,
            'frame_checkpoints':checkpoints,'recovery_budget_mode':'BOUNDED_PROGRESS_AWARE',
            'capture_hardware':capture_hardware,
            'input_sha256':input_hash,'attempts':[],'status':'NOT_STARTED','blocker':'',
            'independent_reference_parity':'NOT_TESTED','gameplay':'NOT_ESTABLISHED',
            'same_initial_state_replay':True,'recovery_method':'SOURCE_VERIFIED_RESET_REPLAY',
            'original_rom_not_copied':True,'coverage_cache':cache_stats}
    analyzer=recover or provider_for('mastersystem').recover
    builder=build or (lambda project:_build(project,timeout=compile_timeout))
    launcher=session or native_session
    previous=None
    run_started=time.monotonic()
    try:
        for index in range(max_recoveries+1):
            if sha256(rom)!=source or (input_file and sha256(input_file)!=input_hash):
                raise ValueError('Owner source or replay changed during recovery')
            started=time.monotonic()
            gen=generate_project(doc,rom,project,overlays)
            generated_seconds=time.monotonic()-started
            started=time.monotonic()
            if gen['translated_instructions']<1:raise ValueError('No translated instructions')
            try:
                executable,compiler_log=builder(project)
            except subprocess.TimeoutExpired as exc:
                report.update(status='BUILD_TIMEOUT',blocker=f'CMake step timed out after {exc.timeout}s ({exc.cmd!s})'[:600])
                break
            except (RuntimeError,OSError) as exc:
                report.update(status='BUILD_FAILED',blocker=str(exc)[:600])
                break
            build_seconds=time.monotonic()-started
            started=time.monotonic()
            app=next((p for p in (project/'build'/'Release'/'RecompDevNativeApp.exe',
                 project/'build'/'RecompDevNativeApp.exe',project/'build'/'RecompDevNativeApp') if p.is_file()),None)
            if app is None and build is None:
                report.update(status='BUILD_FAILED',blocker='Native CMake build did not emit RecompDevNativeApp')
                break
            (output/'compiler-last.log').write_text(str(compiler_log)[-20000:],encoding='utf-8')
            # Each stage reset-replays the original cartridge with unchanged inputs.
            # We only extend after the previous frame budget was genuinely reached.
            stage_evidence=[]
            for checkpoint in checkpoints:
                stage_steps=min(20_000_000,max(steps,(steps*checkpoint+119)//120))
                evidence=output/'sessions'/f'attempt-{index:02d}'/f'frame-{checkpoint:05d}'
                if capture_hardware:
                    observed=launcher(project,rom,source,evidence,checkpoint,stage_steps,input_file,capture_hardware=True)
                else:
                    observed=launcher(project,rom,source,evidence,checkpoint,stage_steps,input_file)
                if observed.get('source_sha256')!=source:
                    raise ValueError('Continuous host source identity mismatch')
                stage_evidence.append({'frames_requested':checkpoint,'steps_requested':stage_steps,
                         'frames_observed':observed.get('frames'),'steps_observed':observed.get('native_steps'),
                         'status':observed.get('status'),
                         'source_sha256':source,
                         'session_path':str((evidence/'continuous-session.json').relative_to(output))})
                if observed.get('status')!='FRAME_BUDGET_REACHED':
                    break
            replay_seconds=time.monotonic()-started
            if observed.get('reference_parity')!='NOT_TESTED' or observed.get('gameplay')!='NOT_ESTABLISHED':
                raise ValueError('Unexpected native qualification claim')
            item={'index':index,'translated_instructions':gen['translated_instructions'],
                  'executable_sha256':sha256(executable),
                  'native_app_sha256':sha256(app) if app is not None else None,
                  'status':observed.get('status'),
                  'pc':observed.get('pc'),'mapper':observed.get('mapper'),
                  'physical_offset':observed.get('physical_offset'),
                  'native_steps':observed.get('native_steps'),'frames':observed.get('frames'),
                  'session_path':str((evidence/'continuous-session.json').relative_to(output)),
                  'frame_checkpoints':stage_evidence,
                  'guest_state_fingerprint':observed.get('guest_state_fingerprint'),
                  'vdp_writes':observed.get('guest_vdp_writes'),
                  'psg_writes':observed.get('guest_psg_writes'),
                  'audio_nonzero_samples':observed.get('audio_nonzero_samples'),
                  'audio_signal_status':('SILENT_WITH_GUEST_PSG_WRITES' if observed.get('guest_psg_writes',0)>0 and observed.get('audio_nonzero_samples')==0 and capture_hardware else 'NOT_QUALIFIED'),
                  'cram_nonzero_bytes':observed.get('cram_nonzero_bytes'),
                  'maskable_interrupts':observed.get('maskable_interrupts'),
                  'timings_seconds':{'generation':round(generated_seconds,3),'build':round(build_seconds,3),
                                     'reset_replays':round(replay_seconds,3)},
                  'frame_hashes_count':len(observed.get('frame_hashes') or []),
                  'trace_tail_count':len(observed.get('trace_tail') or [])}
            report['attempts'].append(item)
            if previous is not None:
                item['replayed_after_source_attested_rebuild']=True
                item['previous_stop_reached_or_surpassed']=(
                    type(observed.get('native_steps'))==int and
                    observed['native_steps']>previous['native_steps'])
            status=observed.get('status')
            # A later build may expose an earlier native stop despite adding
            # source-attested code. Fail closed rather than spending the entire
            # remaining recovery budget on a nonprogressing path.
            if previous is not None and (observed.get('native_steps') is not None) and (
                 observed['native_steps']<=previous.get('native_steps',-1)) and (
                 observed.get('frames',0)<=previous.get('frames',0)) and (
                 observed.get('physical_offset')==previous.get('physical_offset')):
                report.update(status='RECOVERY_BLOCKED',blocker='RECOVERY_NO_EXECUTION_PROGRESS')
                item['recovery_status']='RECOVERY_NO_EXECUTION_PROGRESS'
                break
            if status not in MISSING_CODE:
                report['status']='CONTINUOUS_SESSION_COMPLETE' if status=='FRAME_BUDGET_REACHED' else 'STOPPED_WITHOUT_RECOVERABLE_CODE'
                report['blocker']='' if status=='FRAME_BUDGET_REACHED' else str(status)
                break
            context=classify('mastersystem',rom.stat().st_size,observed)
            decision=planner.claim(context)
            item['recovery_target']=context.record()
            if decision!='RECOVERY_QUEUED':
                item['recovery_status']=decision;report.update(status='RECOVERY_BLOCKED',blocker=decision);break
            started=time.monotonic()
            recovery_dir=output/'recovery'/f'attempt-{index+1:02d}'
            recovery_dir.mkdir(parents=True,exist_ok=False)
            recovered,meta=analyzer(rom,source,target_id,context.entry_pc,observed['mapper'],recovery_dir)
            if recovered.get('source_sha256')!=source or recovered.get('target_id')!=target_id:
                raise ValueError('Recovered document source or target changed')
            if not recovered.get('bank_context'):raise ValueError('Recovered entry lacks mapped bank provenance')
            verified,_,_=verify_export(recovered,rom)
            if context.physical_offset not in verified:
                raise ValueError('Recovered entry not source-attested at observed physical stop')
            item['timings_seconds']['source_recovery']=round(time.monotonic()-started,3)
            old=known_offsets
            newly=set(verified)-old
            if not newly:
                emitted=json.loads((project/'emitted-offsets.json').read_text(encoding='utf-8'))
                lowered=set(emitted['physical_offsets'])
                unsupported=json.loads((project/'unsupported-offsets.json').read_text(encoding='utf-8'))
                reasons=[x for x in unsupported['unsupported'] if x['physical_offset']==context.physical_offset]
                diagnosis=('ALREADY_EMITTED_DISPATCH_OR_MAPPER_MISMATCH' if context.physical_offset in lowered
                           else 'SOURCE_ATTESTED_BUT_NOT_EMITTED' if context.physical_offset in old
                           else 'RECOVERY_NO_NEW_ATTESTED_INSTRUCTIONS')
                item['recovery_status']=diagnosis
                item['emission_diagnosis']={'physical_offset':context.physical_offset,
                    'source_attested':context.physical_offset in old,
                    'emitted':context.physical_offset in lowered,
                    'unsupported_reason':reasons[0]['reason'] if reasons else None}
                report.update(status='RECOVERY_BLOCKED',blocker=diagnosis)
                break
            if cache is not None:
                if cache.put(recovered,rom,context.physical_offset):
                    cache_stats['new_documents_saved']+=1
            overlays.append(recovered)
            known_offsets.update(newly)
            item['recovery_status']='SOURCE_BYTES_VERIFIED'
            item['new_instruction_addresses']=len(newly)
            item['recovery_details']={k:v for k,v in (meta or {}).items() if k in
                        ('slot','bank','pc','physical_offset','instructions','status','exact_instructions')}
            previous=item
        else:
            report.update(status='RECOVERY_BLOCKED',blocker='RECOVERY_BUDGET_EXHAUSTED')
    except (OSError,ValueError,RuntimeError,KeyError,TypeError,subprocess.SubprocessError) as exc:
        report.update(status='RECOVERY_BLOCKED',blocker=str(exc)[:600])
    finally:
        report['elapsed_wall_seconds']=round(time.monotonic()-run_started,3)
        report['attempt_count']=len(report['attempts'])
        report['compiled_successfully']=any('executable_sha256' in x for x in report['attempts'])
        report['initial_cached_instruction_offsets']=cache_stats['loaded_instruction_offsets']
        report['recovered_entries']=sum(x.get('new_instruction_addresses',0) for x in report['attempts'])
        report['maximum_frames_observed']=max((p['frames_observed'] for x in report['attempts'] for p in x.get('frame_checkpoints',[]) if type(p.get('frames_observed'))==int),default=0)
        report['maximum_steps_observed']=max((p['steps_observed'] for x in report['attempts'] for p in x.get('frame_checkpoints',[]) if type(p.get('steps_observed'))==int),default=0)
        (output/'continuous-recovery-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report
