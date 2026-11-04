"""Owner-operated, source-attested Z80 native compilation → continuous host campaign.

The orchestration is target-generic. Machine adapters remain per-system; unimplemented
systems return a blocker instead of falling back to an interpreter or fake device.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import importlib.util
import json
import re
import secrets
import sqlite3
import sys
from datetime import datetime,timezone
from pathlib import Path
from nativepilot.engine import in_roots
from nativecore.host_registry import host_for
from nativepilot.generator import sha256
from platform424.evidence import inspect_native_job,inspect_session

ROOT=Path(__file__).resolve().parents[1]
SHA=re.compile('[0-9a-f]{64}\\Z')

def run(db,source_id,rom_roots,output_root,steps=500000,frames=120,window=False,input_events=None,max_recoveries=2,pilot_function=None,session_function=None,repeat_headless=True,mode=None,video_backend=None,audio_backend=None,input_backend=None):
    if mode not in (None,'HEADLESS_AUTONOMOUS'):raise ValueError('Invalid execution mode')
    if mode and window:raise ValueError('Autonomous mode cannot open a window')
    if not isinstance(source_id,str) or not SHA.fullmatch(source_id):raise ValueError('Expected 64-character source SHA-256')
    if type(steps) is not int or not 1<=steps<=2000000 or type(frames) is not int or not 1<=frames<=1000:
        raise ValueError('Invalid bounded native execution budget')
    if type(max_recoveries) is not int or not 0<=max_recoveries<=5:raise ValueError('Invalid recovery budget')
    db=Path(db).resolve(strict=True)
    if not db.is_file():raise ValueError('Database missing')
    with closing(sqlite3.connect(str(db))) as con:
        row=con.execute('SELECT path,system,bytes FROM discovery_sources WHERE source_id=?',(source_id,)).fetchone()
    if not row:raise ValueError('Source not registered in Discovery')
    rom=Path(row[0]).resolve(strict=True)
    if not rom.is_file() or not in_roots(rom,rom_roots) or rom.stat().st_size!=row[2] or sha256(rom)!=source_id:
        raise ValueError('Source ROM no longer matches catalogue or permitted owner roots')
    adapter=host_for(row[1])
    output_root=Path(output_root).resolve()
    output_root.mkdir(parents=True,exist_ok=True)
    if output_root.is_symlink():raise ValueError('Invalid output root')
    # Never delete/rewrite old job evidence.
    job=output_root/secrets.token_hex(8)
    job.mkdir(exist_ok=False)
    outcome={'schema':'recomp-end-to-end-campaign-v0424','source_sha256':source_id,
             'system':row[1],'job_id':job.name,'status':'PENDING','stages':[],
             'native_qualified':False,'independent_parity':'NOT_ESTABLISHED',
             'gameplay':'NOT_ESTABLISHED','job_directory':str(job),
             'execution_mode':mode or 'SELECTABLE'}
    def stage(name,status,**kwargs):outcome['stages'].append({'stage':name,'status':status,**kwargs})
    try:
        stage('source_authentication','PASS',sha256=source_id)
        pdir=job/'pilot'
        if pilot_function is None:
            import importlib
            pilot_function=getattr(importlib.import_module(adapter.pilot_module),adapter.pilot_function)
        doc=pilot_function(db,source_id,pdir,rom_roots,max_steps=steps,max_recoveries=max_recoveries,adaptive=True,batch_prefetch=1,input_events=input_events)
        stage('compile_and_trace',str(doc.get('status','UNKNOWN')),translated=doc.get('translated_instructions',0),
              steps=doc.get('native_steps',0),recovery_attempts=len(doc.get('recovery_attempts',[])))
        generated=pdir/'native-project'
        if not (generated/'generation.json').is_file() or not (doc.get('native_app') or {}).get('executable'):
            outcome['status']='BLOCKED_NATIVE_APPLICATION_NOT_COMPILED'
            return outcome
        report=inspect_native_job(pdir,source_id)
        stage('verified_native_observations','PASS',event_integrity=report['event_integrity'],
              unresolved_dependency_edges=report['unresolved_dependency_edges'])
        if session_function is None:
            spec=importlib.util.spec_from_file_location('owner_native_session',ROOT/adapter.session_script)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            session_function=module.run
        options={}
        if mode is not None:options['mode']=mode
        if video_backend is not None:options['video_backend']=video_backend
        if audio_backend is not None:options['audio_backend']=audio_backend
        if input_backend is not None:options['input_backend']=input_backend
        sdir=job/'host'
        session=session_function(generated,rom,source_id,sdir,frames=frames,steps=min(20000000,max(steps*4,500000)),window=window,input_events=input_events,**options)
        checked=inspect_session(sdir,source_id)
        if not window and repeat_headless:
            second_dir=job/'host-repeat'
            rerun=session_function(generated,rom,source_id,second_dir,frames=frames,
                steps=min(20000000,max(steps*4,500000)),window=False,input_events=input_events,**options)
            rechecked=inspect_session(second_dir,source_id)
            keys=('status','native_steps','guest_cycles','frames','frame_hashes','audio_samples','guest_state_fingerprint','guest_vdp_writes','guest_psg_writes','discarded_frames','discarded_audio_samples')
            if any(session.get(k)!=rerun.get(k) for k in keys) or session.get('assets')!=rerun.get('assets'):
                stage('deterministic_native_replay','DIVERGED')
                outcome['status']='DETERMINISTIC_REPLAY_DIVERGENCE'
                return outcome
            stage('deterministic_native_replay','PASS',sha256_verified_assets=True,
                frames=rechecked['frames'])
            # A null host must not alter translated CPU execution or guest
            # hardware. Independently rerun with non-null capture sinks.
            if mode=='HEADLESS_AUTONOMOUS' and video_backend in (None,'null') and audio_backend in (None,'null'):
                differential_dir=job/'host-capture-control'
                ctrl_options={'video_backend':'capture','audio_backend':'capture',
                              'input_backend':'replay' if input_events else 'neutral'}
                control=session_function(generated,rom,source_id,differential_dir,frames=frames,
                    steps=min(20000000,max(steps*4,500000)),window=False,
                    input_events=input_events,**ctrl_options)
                inspected=inspect_session(differential_dir,source_id)
                comparison=('status','native_steps','guest_cycles','frames','audio_samples',
                            'guest_state_fingerprint','guest_vdp_writes','guest_psg_writes')
                if any(control.get(k)!=session.get(k) for k in comparison):
                    stage('null_capture_guest_state_equivalence','DIVERGED')
                    outcome['status']='NULL_BACKEND_CHANGED_GUEST_EXECUTION'
                    return outcome
                stage('null_capture_guest_state_equivalence','PASS',
                    guest_state_fingerprint=session.get('guest_state_fingerprint'),
                    control_assets_verified=inspected['asset_integrity'])
        stage('continuous_native_host',checked['status'],frames=checked['frames'],native_steps=checked['native_steps'],
              rendered_output_verified=checked['asset_integrity'],audio_samples=checked['audio_samples'])
        completed = session['status'] in ('FRAME_BUDGET_REACHED','HOST_STOP')
        outcome.update(status='EXPERIMENTAL_NATIVE_APPLICATION_EXECUTED' if completed else 'NATIVE_APPLICATION_BLOCKED',
                       native_steps=session['native_steps'],frames=session['frames'],
                       guest_cycles=session['guest_cycles'],host_assets=session['assets'],
                       guest_state_fingerprint=session.get('guest_state_fingerprint'),
                       timing_qualified_steps=session.get('timing_qualified_steps'),
                       timing_unqualified_steps=session.get('timing_unqualified_steps'),
                       vcounter_reads=session.get('vcounter_reads'),
                       first_vcounter_read_step=session.get('first_vcounter_read_step'),
                       guest_vdp_writes=session.get('guest_vdp_writes'),guest_psg_writes=session.get('guest_psg_writes'),
                       host_backends={'video':session.get('video_backend'),'audio':session.get('audio_backend'),
                                      'input':session.get('input_backend')},
                       last_pilot_status=doc['status'])
        return outcome
    except (OSError,ValueError,RuntimeError,KeyError,TypeError,sqlite3.Error) as exc:
        outcome['status']='BLOCKED'
        stage('failure','BLOCKED',reason=str(exc)[:700])
        return outcome
    finally:
        outcome['completed_utc']=datetime.now(timezone.utc).isoformat()
        (job/'campaign-result.json').write_text(json.dumps(outcome,indent=2)+'\n',encoding='utf-8')

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',required=True);p.add_argument('--source-id',required=True)
    p.add_argument('--rom-root',action='append',required=True);p.add_argument('--output-root',required=True)
    p.add_argument('--steps',type=int,default=500000);p.add_argument('--frames',type=int,default=120)
    p.add_argument('--recoveries',type=int,default=2);p.add_argument('--window',action='store_true')
    p.add_argument('--mode',choices=['HEADLESS_AUTONOMOUS'])
    p.add_argument('--video',choices=['null','capture','window'])
    p.add_argument('--audio',choices=['null','capture','speaker'])
    p.add_argument('--input',choices=['neutral','replay','live'])
    p.add_argument('--no-repeat',action='store_true',help='Disable second headless run (no deterministic replay claim)')
    p.add_argument('--input-events',help='Optional source-owned replay CSV; cannot combine with --window')
    a=p.parse_args(argv)
    if a.window and a.input_events:p.error('Live window and deterministic input replay are mutually exclusive')
    if a.window and a.mode:p.error('Autonomous null mode cannot use --window')
    try:doc=run(a.db,a.source_id,a.rom_root,a.output_root,a.steps,a.frames,a.window,a.input_events,a.recoveries,repeat_headless=not a.no_repeat,mode=a.mode,video_backend=a.video,audio_backend=a.audio,input_backend=a.input)
    except (OSError,ValueError,sqlite3.Error) as exc:p.error(str(exc))
    print(json.dumps(doc,indent=2))
    return 0 if doc['status']=='EXPERIMENTAL_NATIVE_APPLICATION_EXECUTED' else 2
