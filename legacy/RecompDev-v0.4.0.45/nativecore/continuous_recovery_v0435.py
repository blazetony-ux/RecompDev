"""Bounded owner-local continuous native-code recovery, rebuild and reset-replay.

Only attested Z80 P-code is translated. ROM, Ghidra and CMake remain local. No
emulator fallback, no inferred bank state, no game-name rules, no parity claim.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
from nativecore.recovery import RecoveryPlanner, classify, MISSING_CODE
from nativecore.adapters import provider_for
from nativepilot.generator import generate_project, verify_export, sha256
from nativepilot.engine import _build

ROOT=Path(__file__).resolve().parents[1]
SCHEMA='recomp-continuous-recovery-v0435'

def native_session(project,rom,source_hash,out,frames,steps,input_events):
    spec=importlib.util.spec_from_file_location('recomp_continuous_native',ROOT/'tools'/'Run-Continuous-Native.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run(project,rom,source_hash,out,frames=frames,steps=steps,
                      input_events=input_events,mode='HEADLESS_AUTONOMOUS')

def run(rom,export,output,*,frames=120,steps=2000000,max_recoveries=3,
        input_events=None,recover=None,build=None,session=None):
    rom=Path(rom).resolve(strict=True);export=Path(export).resolve(strict=True)
    output=Path(output).resolve()
    if not rom.is_file() or rom.is_symlink() or not 0<rom.stat().st_size<=64*1024*1024:
        raise ValueError('Invalid owner-local cartridge')
    if not export.is_file() or export.is_symlink() or export.stat().st_size>128*1024*1024:
        raise ValueError('Invalid initial Ghidra export')
    if type(frames)!=int or not 1<=frames<=36000 or type(steps)!=int or not 1<=steps<=20000000:
        raise ValueError('Invalid bounded continuous runtime budget')
    planner=RecoveryPlanner(max_recoveries)
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
    report={'schema':SCHEMA,'source_sha256':source,'target_id':target_id,'system':'mastersystem',
            'frames_requested':frames,'steps_requested':steps,'max_recoveries':max_recoveries,
            'input_sha256':input_hash,'attempts':[],'status':'NOT_STARTED','blocker':'',
            'independent_reference_parity':'NOT_TESTED','gameplay':'NOT_ESTABLISHED',
            'same_initial_state_replay':True,'recovery_method':'SOURCE_VERIFIED_RESET_REPLAY',
            'original_rom_not_copied':True}
    analyzer=recover or provider_for('mastersystem').recover
    builder=build or _build
    launcher=session or native_session
    previous=None
    try:
        for index in range(max_recoveries+1):
            if sha256(rom)!=source or (input_file and sha256(input_file)!=input_hash):
                raise ValueError('Owner source or replay changed during recovery')
            gen=generate_project(doc,rom,project,overlays)
            if gen['translated_instructions']<1:raise ValueError('No translated instructions')
            executable,_=builder(project)
            evidence=output/'sessions'/f'attempt-{index:02d}'
            observed=launcher(project,rom,source,evidence,frames,steps,input_file)
            if observed.get('source_sha256')!=source:
                raise ValueError('Continuous host source identity mismatch')
            if observed.get('reference_parity')!='NOT_TESTED' or observed.get('gameplay')!='NOT_ESTABLISHED':
                raise ValueError('Unexpected native qualification claim')
            item={'index':index,'translated_instructions':gen['translated_instructions'],
                  'executable_sha256':sha256(executable),'status':observed.get('status'),
                  'pc':observed.get('pc'),'mapper':observed.get('mapper'),
                  'physical_offset':observed.get('physical_offset'),
                  'native_steps':observed.get('native_steps'),'frames':observed.get('frames'),
                  'session_path':str((evidence/'continuous-session.json').relative_to(output)),
                  'guest_state_fingerprint':observed.get('guest_state_fingerprint')}
            report['attempts'].append(item)
            if previous is not None:
                item['replayed_after_source_attested_rebuild']=True
                item['previous_stop_reached_or_surpassed']=(
                    type(observed.get('native_steps'))==int and
                    observed['native_steps']>previous['native_steps'])
            status=observed.get('status')
            if status not in MISSING_CODE:
                report['status']='CONTINUOUS_SESSION_COMPLETE' if status=='FRAME_BUDGET_REACHED' else 'STOPPED_WITHOUT_RECOVERABLE_CODE'
                report['blocker']='' if status=='FRAME_BUDGET_REACHED' else str(status)
                break
            context=classify('mastersystem',rom.stat().st_size,observed)
            decision=planner.claim(context)
            item['recovery_target']=context.record()
            if decision!='RECOVERY_QUEUED':
                item['recovery_status']=decision;report.update(status='RECOVERY_BLOCKED',blocker=decision);break
            recovery_dir=output/'recovery'/f'attempt-{index+1:02d}'
            recovery_dir.mkdir(parents=True,exist_ok=False)
            recovered,meta=analyzer(rom,source,target_id,context.entry_pc,observed['mapper'],recovery_dir)
            if recovered.get('source_sha256')!=source or recovered.get('target_id')!=target_id:
                raise ValueError('Recovered document source or target changed')
            if not recovered.get('bank_context'):raise ValueError('Recovered entry lacks mapped bank provenance')
            verified,_,_=verify_export(recovered,rom)
            if context.physical_offset not in verified:
                raise ValueError('Recovered entry not source-attested at observed physical stop')
            old={}
            for part in [doc]+overlays:
                old.update(verify_export(part,rom)[0])
            newly=set(verified)-set(old)
            if not newly:raise ValueError('Recovery provided no new physical instruction addresses')
            overlays.append(recovered)
            item['recovery_status']='SOURCE_BYTES_VERIFIED'
            item['new_instruction_addresses']=len(newly)
            item['recovery_details']={k:v for k,v in (meta or {}).items() if k in
                        ('slot','bank','pc','physical_offset','instructions','status','exact_instructions')}
            previous=item
        else:
            report.update(status='RECOVERY_BLOCKED',blocker='RECOVERY_BUDGET_EXHAUSTED')
    except (OSError,ValueError,RuntimeError,KeyError,TypeError) as exc:
        report.update(status='RECOVERY_BLOCKED',blocker=str(exc)[:600])
    finally:
        report['attempt_count']=len(report['attempts'])
        report['recovered_entries']=sum(x.get('new_instruction_addresses',0) for x in report['attempts'])
        report['maximum_frames_observed']=max((x['frames'] for x in report['attempts'] if type(x['frames'])==int),default=0)
        report['maximum_steps_observed']=max((x['native_steps'] for x in report['attempts'] if type(x['native_steps'])==int),default=0)
        (output/'continuous-recovery-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report
