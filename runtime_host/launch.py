#!/usr/bin/env python3
"""Launch an already source-attested, compiled native project with the generic host.

Copies the previously generated project into the external cache, installs only
presentation shims and incrementally compiles the native game application.
No original-ROM bytes, source-code changes, catalogue writes or game-specific rules.

Interactive mode on Windows: arrow keys, Z/X, Enter (Start), Esc (close).
This currently requires the owner's ROM at runtime; it is NOT standalone/ROM-free.
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
import tempfile
import uuid
import time

SOURCE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SOURCE))
from runtime_host.bridge import install
from video_sms.bridge import HEADER as SMS_HEADER, BRIDGE as SMS_BRIDGE, transform as sms_video_transform
from movement_trace.bridge import (HEADER as MOVEMENT_HEADER, STATE_HEADER, SMS_MEMORY_ADAPTER,
                                    live_sms_transform, runtime_transform)
from execution_monitor.bridge import HEADER as EXECUTION_HEADER, live_transform as execution_live_transform
from modular.evidence_bundle import create_evidence_bundle
from workspace import manager


def sha256(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for data in iter(lambda:f.read(1048576),b''):h.update(data)
    return h.hexdigest()


def find_project(evidence_root, source_sha256=None):
    """Find the most recently modified complete generated native project."""
    found=[]
    root=Path(evidence_root)
    if not root.is_dir():raise FileNotFoundError('Evidence root does not exist: '+str(root))
    # Search only the central evidence root, not arbitrary user directories.
    for version in root.glob('v*'):
        if not version.is_dir():continue
        for run in version.iterdir():
            if not run.is_dir():continue
            for project in (run/'recovery').glob('round-*/native-project'):
                if (project/'translated.cpp').is_file() and (project/'generation.json').is_file():
                    try:
                        identity=json.loads((project/'generation.json').read_text(encoding='utf8'))
                    except (ValueError,OSError):continue
                    if source_sha256 is None or identity.get('original_source_sha256')==source_sha256:
                        found.append(project)
    if not found:raise FileNotFoundError('No matching authenticated native project found; run native recovery first')
    return max(found,key=lambda p:p.stat().st_mtime)


def verify_project(project,rom):
    project=Path(project).resolve(strict=True);rom=Path(rom).resolve(strict=True)
    if not (project/'translated.cpp').is_file() or not (project/'generation.json').is_file():
        raise ValueError('Generated project is incomplete')
    if not rom.is_file() or rom.stat().st_size>64*1024*1024:raise ValueError('Invalid owner ROM')
    doc=json.loads((project/'generation.json').read_text(encoding='utf8'))
    digest=sha256(rom)
    if doc.get('original_source_sha256')!=digest:
        raise ValueError('Generated native code is for a different source SHA-256; refusing to run')
    return digest


def stage(project,cache):
    project=Path(project).resolve(strict=True)
    files=[];size=0
    for p in sorted(project.rglob('*')):
        if 'build' in p.relative_to(project).parts or not p.is_file():continue
        if p.is_symlink():raise ValueError('Generated project contains a symbolic link')
        rel=p.relative_to(project)
        # Limit copied material to known compiler source/build metadata.
        if p.name!='CMakeLists.txt' and p.suffix.lower() not in ('.cpp','.hpp','.h','.json'):
            continue
        size+=p.stat().st_size
        if size>32*1024*1024:raise ValueError('Native project exceeds source staging limit')
        files.append((p,rel))
    if not files:raise ValueError('Missing source project files')
    h=hashlib.sha256(b'rd_runtime_host_stage_v1\0')
    for p,rel in files:
        h.update(rel.as_posix().encode());h.update(bytes.fromhex(sha256(p)))
    for src in [SOURCE/'runtime_host/bridge.py',SOURCE/'runtime_host/bridge/rd_host_loader.hpp',
                SOURCE/'runtime_host/bridge/win32_window.hpp',SOURCE/'runtime_host/bridge/win32_audio.hpp',
                SOURCE/'runtime_host/bridge/rd_guest_input_tap.hpp',SOURCE/'runtime_host/guest_input_tap.py',
                SOURCE/'runtime_host/include/rd_runtime_host.h',
                SOURCE/'video_sms/bridge.py',SMS_HEADER,SMS_BRIDGE,
                SOURCE/'movement_trace/bridge.py',MOVEMENT_HEADER,STATE_HEADER,SMS_MEMORY_ADAPTER,
                SOURCE/'execution_monitor/bridge.py',EXECUTION_HEADER,
                SOURCE/'state_observer/analyze.py']:
        h.update(bytes.fromhex(sha256(src)))
    ident=h.hexdigest()[:24]
    cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    target=cache/ident
    if not target.exists():
        temp=Path(tempfile.mkdtemp(prefix='candidate-',dir=cache))
        try:
            for p,rel in files:
                q=temp/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
            install(temp)
            (temp/'runtime-host-stage.json').write_text(json.dumps({
                'schema':'recompdev-native-host-staging-v1',
                'original_generated_project':str(project),'staging_id':ident,
                'translated_cpp_sha256':sha256(project/'translated.cpp'),
                'original_generation_sha256':sha256(project/'generation.json')},indent=2)+'\n')
            temp.rename(target)
        finally:
            if temp.exists():shutil.rmtree(temp)
    else:
        info=json.loads((target/'runtime-host-stage.json').read_text())
        if info.get('staging_id')!=ident or info.get('translated_cpp_sha256')!=sha256(project/'translated.cpp'):
            raise ValueError('Cached native-project staging identity mismatch')
        # The cache is executable source, not trusted just because its directory
        # exists. Compare each staged input and all bridge source before use.
        for original,rel in files:
            candidate=target/rel
            if not candidate.is_file():
                raise ValueError('Cached native-project source is missing: '+str(rel))
            if rel.as_posix() in ('hardware/win32_window.hpp','hardware/win32_audio.hpp'):
                continue  # Compared with original bridge files below, not vendor headers.
            if rel.as_posix()=='CMakeLists.txt':
                expected=original.read_text(encoding='utf8')
                if 'target_link_libraries(RecompDevNativeApp PRIVATE ${CMAKE_DL_LIBS})' not in expected:
                    expected=expected.rstrip()+(
                        '\n\n# Generic runtime host: dynamic presentation adapter only.\n'
                        'target_link_libraries(RecompDevNativeApp PRIVATE ${CMAKE_DL_LIBS})\n')
                if candidate.read_text(encoding='utf8')!=expected:
                    raise ValueError('Cached native-project build recipe was changed')
            elif rel.as_posix()=='live_sms.hpp':
                if candidate.read_text(encoding='utf8')!=execution_live_transform(live_sms_transform(original.read_text(encoding='utf8'))):
                    raise ValueError('Cached native guest-input diagnostics changed')
            elif rel.as_posix()=='runtime.cpp':
                if candidate.read_text(encoding='utf8')!=runtime_transform(original.read_text(encoding='utf8')):
                    raise ValueError('Cached native controller-port diagnostics changed')
            elif rel.as_posix()=='hardware/adapters/sms.hpp':
                if candidate.read_text(encoding='utf8')!=sms_video_transform(original.read_text(encoding='utf8')):
                    raise ValueError('Cached native SMS video plugin bridge was changed')
            elif rel.as_posix()!='interactive.cpp' and sha256(candidate)!=sha256(original):
                raise ValueError('Cached native-project source has been changed: '+str(rel))
            elif rel.as_posix()=='interactive.cpp':
                from runtime_host.guest_input_tap import MARKER
                if MARKER not in candidate.read_text(encoding='utf8'):
                    raise ValueError('Cached input frontend lacks guest-cycle capture marker')
        for filename in ('rd_host_loader.hpp','win32_window.hpp','win32_audio.hpp','rd_guest_input_tap.hpp'):
            if sha256(target/'hardware'/filename)!=sha256(SOURCE/'runtime_host/bridge'/filename):
                raise ValueError('Cached runtime host bridge was changed: '+filename)
        # Recreate instrumented frontend in-memory and verify its exact bytes.
        from runtime_host.guest_input_tap import instrument
        import tempfile as _tmp, shutil as _shutil
        with tempfile.TemporaryDirectory(prefix='guest-input-integrity-') as tmp:
            c=Path(tmp);_shutil.copy2(project/'interactive.cpp',c/'interactive.cpp')
            instrument(c)
            if sha256(c/'interactive.cpp')!=sha256(target/'interactive.cpp'):
                raise ValueError('Cached native input frontend has been changed')
        for name,header in [('rd_movement_trace.hpp',MOVEMENT_HEADER),
                            ('rd_state_observer.hpp',STATE_HEADER),
                            ('rd_sms_memory_adapter.hpp',SMS_MEMORY_ADAPTER)]:
            if sha256(target/'hardware'/name)!=sha256(header):
                raise ValueError('Cached guest-observer bridge changed: '+name)
        if sha256(target/'hardware/rd_sms_mode4.h')!=sha256(SMS_HEADER) or sha256(target/'hardware/rd_sms_mode4_bridge.hpp')!=sha256(SMS_BRIDGE):
            raise ValueError('Cached SMS video plugin API/adapter was changed')
        if sha256(target/'hardware/rd_runtime_host.h')!=sha256(SOURCE/'runtime_host/include/rd_runtime_host.h'):
            raise ValueError('Cached runtime host ABI header changed')
    return target,ident


def host_binary(source=SOURCE):
    roots=manager.roots(source)
    dll='rd_runtime_host.dll' if os.name=='nt' else 'rd_runtime_host.dylib' if sys.platform=='darwin' else 'rd_runtime_host.so'
    active=roots['runtime']/'active'/dll
    state=manager.read_state(source).get('active',{}).get('rd_runtime_host')
    if not state or state.get('version')!='0.1.0':
        raise ValueError('Runtime host v0.1.0 not activated; install the component first')
    if not active.is_file() or sha256(active)!=state.get('sha256'):
        raise ValueError('Runtime host binary missing or fails active SHA-256 lock')
    return active,state


def sms_video_binary(source=SOURCE):
    """Resolve source-independent ABI-checked active SMS video plugin."""
    roots=manager.roots(source)
    ext='.dll' if os.name=='nt' else '.dylib' if sys.platform=='darwin' else '.so'
    path=roots['runtime']/'active'/('rd_video_sms_mode4'+ext)
    state=manager.read_state(source).get('active',{}).get('rd_video_sms_mode4')
    if not state or state.get('version')!='0.1.0':
        raise ValueError('SMS video plugin v0.1.0 not activated; install v0.4.9.2')
    if not path.is_file() or sha256(path)!=state.get('sha256'):
        raise ValueError('SMS video plugin missing or fails active SHA-256 lock')
    return path,state



def launch_monitor(broker, evidence_dir):
    """Start independent read-only viewer; all data comes via controller ABI."""
    python = Path(sys.executable)
    if os.name == 'nt':
        windowed = python.with_name('pythonw.exe')
        if windowed.is_file():
            python = windowed
    cmd = [str(python), '-B', '-m', 'execution_monitor.viewer', '--port', str(broker.port), '--token', broker.token]
    outfile = (Path(evidence_dir)/'execution-monitor-viewer.log').open('w', encoding='utf8')
    try:
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0
        proc = subprocess.Popen(cmd, cwd=str(SOURCE), stdout=outfile, stderr=subprocess.STDOUT,
                                creationflags=flags)
        return proc, outfile
    except BaseException:
        outfile.close()
        raise


def run_with_monitor(cmd, env, dest, timeout, sample_every):
    """Controller owns the fanout; the monitor sees only its subscription endpoint."""
    from controller.diagnostics import ControllerDiagnostics
    from execution_monitor.stream import NativeEventReader
    with ControllerDiagnostics() as broker:
        broker.publish({'type': 'session', 'status': 'Starting native game', 'sample_every': sample_every})
        viewer, logfile = launch_monitor(broker, dest)
        events = Path(dest)/'controller-execution-events.jsonl'
        env['RECOMPDEV_CONTROLLER_DIAGNOSTIC_EVENTS'] = str(events)
        env['RECOMPDEV_MONITOR_SAMPLE_EVERY'] = str(sample_every)
        reader = NativeEventReader(events, broker.publish)
        proc = None
        try:
            with (Path(dest)/'native-stdout.log').open('w',encoding='utf8') as stdout, \
                 (Path(dest)/'native-stderr.log').open('w',encoding='utf8') as stderr:
                proc = subprocess.Popen(cmd, env=env, stdout=stdout, stderr=stderr)
                started = time.monotonic()
                while proc.poll() is None:
                    reader.poll()
                    if time.monotonic()-started > timeout:
                        proc.kill()
                        proc.wait()
                        raise subprocess.TimeoutExpired(cmd, timeout)
                    time.sleep(0.035)
                for _ in range(2000):
                    if not reader.poll():
                        break
            # Preserve the exact guest stop reason before the controller stream closes.
            # This is read from the existing structured native report, not guessed from
            # the process exit code (native execution can stop with exit code zero).
            guest_result = None
            for line in (Path(dest)/'native-stdout.log').read_text(encoding='utf8',errors='replace').splitlines():
                if line.startswith('NATIVE_APP_RESULT='):
                    try:
                        guest_result = json.loads(line.partition('=')[2])
                    except json.JSONDecodeError:
                        pass
                    break
            if isinstance(guest_result,dict):
                broker.publish({'type': 'stop',
                                'status': str(guest_result.get('status', 'UNKNOWN')),
                                'pc': guest_result.get('pc', 0),
                                'frame': guest_result.get('frames', 0),
                                'steps': guest_result.get('native_steps', 0)})
            else:
                broker.publish({'type':'notice','message':'Native game produced no structured guest result'})
            # Viewer stays open with last events after the controller closes.

            time.sleep(0.15)
            return proc.returncode, {'events_forwarded': reader.delivered,
                                     'events_rejected': reader.rejected,
                                     'controller_schema': 'recompdev.controller.diagnostics.v1',
                                     'viewer_started': viewer.poll() is None,
                                     'sample_every': sample_every,
                                     'events_file': events.name,
                                     'viewer_log': 'execution-monitor-viewer.log'}
        finally:
            logfile.close()
            if proc is not None and proc.poll() is None:
                proc.kill()
                proc.wait()


def run(args):
    roots=manager.roots(SOURCE)
    output=roots['evidence']/manager.manifest(SOURCE)['workspace_release']/'runtime-host'
    output.mkdir(parents=True,exist_ok=True)
    runid=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    dest=output/runid;dest.mkdir(exist_ok=False)
    rom_digest=None
    record={'schema':'recompdev-generic-native-host-v0.1.0',
            'mode':args.mode,'movement_trace_requested':args.movement_trace,
            'execution_monitor_requested':args.execution_monitor,'frames_requested':args.frames,'steps_requested':args.steps,
            'original_rom_required_at_runtime':True,
            'system_independent_host':True,
            'actual_gameplay_parity':'NOT_ESTABLISHED','status':'NOT_STARTED'}
    try:
        if args.mode=='window' and os.name!='nt':
            raise ValueError('Window/speaker backend currently requires Windows; use --mode headless')
        rom=Path(args.rom).resolve(strict=True);rom_digest=sha256(rom)
        project=Path(args.project).resolve() if args.project else find_project(roots['evidence'],rom_digest)
        verify_project(project,rom)
        dll,active=host_binary()
        video_dll,video_state=sms_video_binary()
        staged,cacheid=stage(project,roots['cache']/'runtime-host')
        build=roots['build']/'native-runtime'/cacheid
        build.mkdir(parents=True,exist_ok=True)
        build_log=dest/'native-compiler.log'
        def build_command(command,timeout):
            with build_log.open('a',encoding='utf8') as log:
                log.write('COMMAND: '+' '.join(map(str,command))+'\n');log.flush()
                result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,
                                      timeout=timeout,check=False)
                if result.returncode:
                    raise RuntimeError('NATIVE_GAME_BUILD_FAILED exit='+str(result.returncode)+
                                       '; consult native-compiler.log in automatic evidence ZIP')
        if not (build/'CMakeCache.txt').exists():
            command=['cmake','-S',str(staged),'-B',str(build),'-DCMAKE_BUILD_TYPE=Release']
            if os.name=='nt':command+=['-A','x64']
            build_command(command,180)
        build_command(['cmake','--build',str(build),'--config','Release',
                       '--target','RecompDevNativeApp','--parallel','2'],600)
        candidates=[build/'Release'/'RecompDevNativeApp.exe',build/'RecompDevNativeApp.exe',build/'RecompDevNativeApp']
        app=next((p for p in candidates if p.is_file()),None)
        if app is None:raise ValueError('Compiled native game application missing')
        prefix=dest/'native-frame'
        replay_source=Path(args.input_events).resolve(strict=True) if args.input_events else None
        if replay_source:
            if replay_source.stat().st_size>1048576:raise ValueError('Input replay exceeds 1 MiB')
            from input_recovery.replay import validate_replay
            validate_replay(replay_source)
            shutil.copy2(replay_source,dest/'guest-input-replay.csv')
        flag=['--video','window' if args.mode=='window' else 'capture',
              '--audio',args.audio if args.mode=='window' else 'capture',
              '--input','live' if args.mode=='window' else 'replay' if replay_source else 'neutral']
        if replay_source:flag+=['--input-events',str(dest/'guest-input-replay.csv')]
        if args.snapshot_every:flag+=['--snapshot-every',str(args.snapshot_every)]
        if args.mode=='window' and args.hold_window:flag.append('--hold-window')
        cmd=[str(app),str(rom),str(prefix),str(args.frames),str(args.steps),'-',*flag]
        env=os.environ.copy();env['RECOMPDEV_RUNTIME_HOST_DLL']=str(dll)
        env['RECOMPDEV_SMS_MODE4_DLL']=str(video_dll)
        env['RECOMPDEV_SMS_VIDEO_STATS']=str(dest/'sms-sprite-stats.csv')
        if args.movement_trace:
            env['RECOMPDEV_MOVEMENT_TRACE_DIR']=str(dest)
            env['RECOMPDEV_STATE_TRACE_DIR']=str(dest)
        if args.mode=='window':
            env['RECOMPDEV_RUNTIME_HOST_INPUT_EVENTS']=str(dest/'input-events.jsonl')
            env['RECOMPDEV_GUEST_INPUT_REPLAY']=str(dest/'guest-input-cycles.csv')
        print('RECOMPDEV_RUNTIME_HOST launching generated native game application',flush=True)
        monitor_report=None
        if args.execution_monitor:
            return_code, monitor_report = run_with_monitor(cmd, env, dest, args.timeout, args.monitor_every)
            record['execution_monitor'] = monitor_report
        else:
            with (dest/'native-stdout.log').open('w',encoding='utf8') as stdout, (dest/'native-stderr.log').open('w',encoding='utf8') as stderr:
                proc=subprocess.run(cmd,env=env,stdout=stdout,stderr=stderr,timeout=args.timeout)
            return_code = proc.returncode
        # The process exit code alone does not establish guest execution success.
        # Extract the preserved native host's bounded structured result.
        observed=None
        for line in (dest/'native-stdout.log').read_text(encoding='utf8',errors='replace').splitlines():
            if line.startswith('NATIVE_APP_RESULT='):
                observed=json.loads(line.partition('=')[2]);break
        if not isinstance(observed,dict):
            raise ValueError('Native application produced no structured guest result; inspect logs')
        if args.movement_trace:
            from movement_trace.analyze import write_report
            report=write_report(dest)
            record['movement_diagnostics']='movement-diagnostics.json'
            record['movement_trace_validity']=report['trace_validity']
            if 'state_memory_diagnostics' in report:
                record['state_memory_diagnostics']=report['state_memory_diagnostics']
                record['state_memory_status']=report['state_memory_status']
        record.update(guest_status=observed.get('status'),
                      input_event_capture='input-events.jsonl' if (dest/'input-events.jsonl').is_file() else 'NOT_AVAILABLE',
                      native_steps_observed=observed.get('native_steps'),
                      frames_observed=observed.get('frames'),
                      guest_vdp_writes=observed.get('guest_vdp_writes'),
                      guest_psg_writes=observed.get('guest_psg_writes'),
                      audio_nonzero_samples=observed.get('audio_nonzero_samples'),
                      guest_state_fingerprint=observed.get('guest_state_fingerprint'))
        record.update(native_game_code=str(app),native_app_sha256=sha256(app),
                      source_rom_sha256=rom_digest,staged_project=str(staged),
                      original_project=str(project),
                      sms_video={'component':'rd_video_sms_mode4','version':video_state['version'],
                                 'sha256':video_state['sha256'],'abi':'0x00010000',
                                 'stats':'sms-sprite-stats.csv' if (dest/'sms-sprite-stats.csv').is_file() else 'NOT_AVAILABLE'},
                      runtime_host={'component':'rd_runtime_host','version':active['version'],
                                    'sha256':active['sha256'],'abi':'0x00010000'},
                      return_code=return_code,
                      input_mode='live' if args.mode=='window' else 'replay' if replay_source else 'neutral',
                      guest_cycle_input_capture='guest-input-cycles.csv' if args.mode=='window' and (dest/'guest-input-cycles.csv').is_file() else 'NOT_AVAILABLE',
                      input_replay_sha256=sha256(dest/'guest-input-replay.csv') if replay_source else None,
                      guest_stop_pc=observed.get('pc'),guest_stop_physical_offset=observed.get('physical_offset'),
                      guest_cycles_observed=observed.get('guest_cycles'),
                      status=('NATIVE_PROCESS_FAILED' if return_code else
                              'FRAME_BUDGET_REACHED' if observed.get('status')=='FRAME_BUDGET_REACHED' else
                              'STEP_BUDGET_REACHED' if observed.get('status')=='STEP_BUDGET_REACHED' else
                              'GUEST_EXECUTION_STOPPED'))
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as exc:
        record.update(status='RUNTIME_HOST_BLOCKED',error=type(exc).__name__+': '+str(exc)[:1000])
        (dest/'runtime-error.log').write_text(record['error']+'\n',encoding='utf8')
    (dest/'runtime-host-report.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    try:
        evidence=create_evidence_bundle(dest,source_sha256=rom_digest,status=record['status'])
        record['evidence_zip']=evidence['path']
        print('RECOMPDEV_EVIDENCE_ZIP='+evidence['path'],flush=True)
    except (OSError,ValueError,RuntimeError) as exc:
        record['evidence_error']=str(exc)
    print(json.dumps(record,indent=2),flush=True)
    return 0 if record['status'] in ('FRAME_BUDGET_REACHED','STEP_BUDGET_REACHED') else 2

def parse_args(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',required=True)
    p.add_argument('--project',help='Previously recovered native-project; default newest complete project in central evidence')
    p.add_argument('--input-events',help='Existing source-owned RECOMP_INPUT_CYCLES_V1 replay; headless mode only')
    p.add_argument('--mode',choices=['window','headless'],default='window')
    p.add_argument('--audio',choices=['speaker','null'],default='null',help='Native audio remains silent in current Shinobi evidence')
    p.add_argument('--frames',type=int,default=1800)
    p.add_argument('--steps',type=int,default=12000000)
    p.add_argument('--snapshot-every',type=int,default=120)
    p.add_argument('--timeout',type=int,default=420)
    p.add_argument('--hold-window',action='store_true')
    p.add_argument('--execution-monitor',action='store_true',help='Open separate read-only controller diagnostics window')
    p.add_argument('--monitor-every',type=int,default=256,help='Emit sampled instruction event every N guest steps, 1..65536')
    p.add_argument('--movement-trace',action='store_true',help='Capture guest controller-port reads and VDP/sprite-position diagnostics')
    a=p.parse_args(argv)
    if a.input_events and a.mode!='headless':p.error('Replay and physical/live input are mutually exclusive')
    if not 1<=a.frames<=36000 or not 1<=a.steps<=20000000 or not 0<=a.snapshot_every<=600 or not 30<=a.timeout<=900 or not 1<=a.monitor_every<=65536:
        p.error('Bounded runtime limits exceeded')
    return a

if __name__=='__main__':
    try:raise SystemExit(run(parse_args()))
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as exc:
        print('RECOMPDEV_RUNTIME_HOST_BLOCKED: '+str(exc),file=sys.stderr);raise SystemExit(2)
