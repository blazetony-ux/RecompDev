#!/usr/bin/env python3
"""Native controller's read-only preview and input-stop evidence service.

Builds an instrumented COPY of an authenticated generated native game. Neither
this service nor its viewer edits the production translated project, recovery
state, owner ROM, or active DLL directory. ROM bytes never enter diagnostic ZIPs.
"""
from __future__ import annotations
import argparse
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from controller.diagnostics import ControllerDiagnostics
from execution_monitor.bridge import HEADER, live_transform
from execution_monitor.stream import NativeEventReader

JOB = re.compile(r'^job-[A-Za-z0-9_-]{1,96}$')
CYCLE = re.compile(r'^cycle-(?:0[1-9]|1[0-6])$')
ROUND = re.compile(r'^round-0[1-8]$')
NATIVE_PART = re.compile(r'^native_part_\d{1,2}\.cpp$')
FILES = frozenset({'CMakeLists.txt', 'interactive.cpp', 'live_sms.hpp', 'main.cpp',
                   'translated.cpp', 'z80_cycles.hpp', 'rd_sha256.hpp'})
MAX_PROJECT_BYTES = 120 * 1024 * 1024
MAX_FILE_BYTES = 12 * 1024 * 1024
MAX_EVENTS_ZIP = 5000
MAX_LOG = 512 * 1024


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        while data := f.read(1024 * 1024): h.update(data)
    return h.hexdigest()


def inside(path, root):
    p = Path(path)
    return not p.is_symlink() and p.resolve(strict=True).is_relative_to(Path(root).resolve(strict=True))


def verified_json(path, root, cap=2*1024*1024):
    p = Path(path)
    if not inside(p, root) or p.stat().st_size > cap: raise ValueError('UNSAFE_PREVIEW_JSON')
    return json.loads(p.read_text(encoding='utf8'))


def select_source(job_dir, cycle=0):
    job_dir = Path(job_dir).resolve(strict=True)
    if not JOB.fullmatch(job_dir.name): raise ValueError('INVALID_JOB_ID')
    job = verified_json(job_dir/'job.json', job_dir)
    rom = Path(job['rom']).resolve(strict=True)
    if not rom.is_file() or rom.stat().st_size > 64*1024*1024 or digest(rom) != job['rom_sha256']:
        raise ValueError('ROM_IDENTITY_MISMATCH')
    if cycle:
        candidates = [job_dir/'sessions'/f'cycle-{cycle:02d}']
    else:
        candidates = sorted(job_dir.joinpath('sessions').glob('cycle-*'),reverse=True)
    for session in candidates:
        if not CYCLE.fullmatch(session.name) or not session.is_dir() or not inside(session,job_dir): continue
        report = verified_json(session/'orchestration.json',job_dir)
        if report.get('schema') != 'recompdev.native.orchestrator.v1' or report.get('source_sha256') != job['rom_sha256']:
            raise ValueError('PREVIEW_ORCHESTRATION_IDENTITY_MISMATCH')
        rounds = sorted((p for p in session.glob('round-*') if ROUND.fullmatch(p.name) and p.is_dir()),reverse=True)
        for project in rounds:
            if not inside(project,job_dir): raise ValueError('PREVIEW_SYMLINKED_PROJECT')
            manifest = project/'translation-manifest.json'
            if not manifest.is_file():continue
            translation = verified_json(manifest,job_dir,MAX_FILE_BYTES)
            if (translation.get('schema') != 'recompdev.native.pcode.generated.v1' or
                translation.get('source_sha256') != job['rom_sha256'] or
                translation.get('backend') != 'dll_sms_native_runtime' or
                not translation.get('full_CPU_state_port') or
                not isinstance(translation.get('emitted'),int) or translation['emitted'] < 1):
                raise ValueError('PREVIEW_TRANSLATION_IDENTITY_MISMATCH')
            for name in FILES:
                if not (project/name).is_file() or not inside(project/name,job_dir):
                    raise ValueError('PREVIEW_GENERATED_SOURCE_MISSING_'+name)
            if (project/'interactive.cpp').read_bytes() != (ROOT/'runtime_sms/templates/interactive.cpp').read_bytes():
                raise ValueError('PREVIEW_FRONTEND_SOURCE_NOT_ATTESTED')
            if (project/'live_sms.hpp').read_bytes() != (ROOT/'runtime_sms/templates/live_sms.hpp').read_bytes():
                raise ValueError('PREVIEW_CPU_ADAPTER_SOURCE_NOT_ATTESTED')
            return job,rom,session,project,translation
    raise ValueError('PREVIEW_NO_SOURCE_ATTESTED_COMPILED_ROUND')


def copy_and_instrument(project, target):
    """Copy only expected generated native source, keeping original immutable."""
    target.mkdir(parents=True,exist_ok=False)
    total = 0
    selected = []
    for p in project.iterdir():
        if p.name in FILES or NATIVE_PART.fullmatch(p.name):
            if not p.is_file() or p.is_symlink() or p.stat().st_size > MAX_FILE_BYTES:
                raise ValueError('PREVIEW_GENERATED_SOURCE_UNSAFE')
            total += p.stat().st_size
            if total > MAX_PROJECT_BYTES: raise ValueError('PREVIEW_SOURCE_SIZE_LIMIT')
            shutil.copyfile(p, target/p.name)
            selected.append(p.name)
    if not any(NATIVE_PART.fullmatch(x) for x in selected):
        raise ValueError('PREVIEW_PARTITIONED_TRANSLATION_REQUIRED')
    before = digest(target/'translated.cpp')
    original = (target/'live_sms.hpp').read_text(encoding='utf8')
    converted = live_transform(original)
    (target/'live_sms.hpp').write_text(converted,encoding='utf8',newline='\n')
    (target/'hardware').mkdir()
    shutil.copyfile(HEADER,target/'hardware/rd_execution_events.hpp')
    if digest(target/'translated.cpp') != before or digest(project/'translated.cpp') != before:
        raise ValueError('PREVIEW_TRANSLATED_CPP_MODIFIED')
    return {'translated_cpp_sha256': before,'source_file_count':len(selected),
            'instrumented_live_sms_sha256':digest(target/'live_sms.hpp'),
            'instrumentation_header_sha256':digest(HEADER)}


def reuse_compiled_translation(project, target, job_dir):
    """Prefer the already-built native translation library: avoid recompiling
    thousands of identical source-generated instructions just to add telemetry.

    The library is pinned by its SHA-256 and copied into private preview evidence.
    This is recorded as reused owner evidence, NOT an independent binary rebuild.
    The new frontend and replaceable presentation providers remain freshly built.
    """
    suffix = '.lib' if os.name == 'nt' else '.a'
    choices = ([project/'build'/'Release'/'rd_generated_translation.lib',
                project/'build'/'rd_generated_translation.lib'] if os.name == 'nt' else
               [project/'build'/'librd_generated_translation.a'])
    lib = next((p for p in choices if p.is_file() and inside(p,job_dir)),None)
    if lib is None:
        return None
    if lib.stat().st_size > 256*1024*1024 or lib.stat().st_size < 100:
        raise ValueError('PREVIEW_TRANSLATION_LIBRARY_SIZE_INVALID')
    # Reuse an immutable local compiled-translation artifact only when its
    # corresponding native source and ROM were already attested by select_source.
    frozen = target.parent / ('translation-reuse'+suffix)
    shutil.copyfile(lib, frozen)
    if digest(lib) != digest(frozen):
        raise ValueError('PREVIEW_COMPILED_TRANSLATION_CHANGED_DURING_COPY')
    recipe = (target/'CMakeLists.txt').read_text(encoding='utf8')
    anchor = '\nadd_library(rd_generated_translation STATIC translated.cpp'
    if (recipe.count(anchor)!=1 or
        not recipe.startswith((ROOT/'runtime_sms/templates/CMakeLists.txt').read_text(encoding='utf8'))):
        raise ValueError('PREVIEW_UNKNOWN_GENERATED_CMAKE_RECIPE')
    recipe = recipe.split(anchor,1)[0]
    recipe += ('\n# Isolated preview: reuse only source-matched native translation archive.\n'
               'add_library(rd_generated_translation STATIC IMPORTED)\n'
               'set_target_properties(rd_generated_translation PROPERTIES IMPORTED_LOCATION "'
               + frozen.as_posix() + '")\n'
               'target_link_libraries(RecompDevNativeApp PRIVATE rd_generated_translation)\n')
    (target/'CMakeLists.txt').write_text(recipe,encoding='utf8',newline='\n')
    return {'reused_translation_library_sha256':digest(frozen),
            'translation_binary_rebuilt':False,
            'binary_provenance':'REUSED_SOURCE_MATCHED_OWNER_NATIVE_ARCHIVE_NOT_INDEPENDENTLY_RECOMPILED'}


def run_checked(command, log, timeout):
    try:
        with Path(log).open('wb') as out:
            proc = subprocess.run(command,stdout=out,stderr=subprocess.STDOUT,timeout=timeout,check=False)
        if proc.returncode:
            raise RuntimeError('PREVIEW_NATIVE_BUILD_FAILED_'+str(proc.returncode))
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('PREVIEW_BUILD_TIMEOUT') from exc


def native_binary(build, name):
    for suffix in (f'Release/{name}.exe',f'{name}.exe',name):
        p=build/suffix
        if p.is_file():return p
    raise ValueError('PREVIEW_NATIVE_ARTIFACT_MISSING_'+name)


def launch_viewer(broker,out):
    interpreter = Path(sys.executable)
    if os.name == 'nt' and interpreter.with_name('pythonw.exe').is_file():
        interpreter = interpreter.with_name('pythonw.exe')
    log = (out/'viewer.log').open('wb')
    try:
        flags = getattr(subprocess,'CREATE_NO_WINDOW',0) if os.name == 'nt' else 0
        proc=subprocess.Popen([str(interpreter),'-B','-m','execution_monitor.viewer',
            '--port',str(broker.port),'--token',broker.token],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=flags)
        return proc,log
    except BaseException:
        log.close()
        raise


def safe_excerpt(obj):
    """No paths, raw ROM, environment, native stdout or full generated code."""
    fields=('type','cpu','pc','next_pc','physical_offset','opcode','opcode_class',
            'sp','frame','guest_cycles','steps','buttons','status')
    return {key:obj[key] for key in fields if key in obj and
            (type(obj[key]) in (int,bool) or
             type(obj[key]) is str and re.fullmatch(r'[A-Za-z0-9_.:-]{1,80}',obj[key]))}


def collect_input_stop(events, native):
    last_input = None
    last_nonzero_input = None
    last_stop = None
    recent = deque(maxlen=64)
    total = 0
    for event in events:
        total += 1
        if event.get('type') == 'input':
            last_input = safe_excerpt(event)
            if type(event.get('buttons')) is int and event['buttons'] != 0:
                last_nonzero_input = safe_excerpt(event)
        if event.get('type') == 'stop':last_stop = safe_excerpt(event)
        if event.get('type') in ('input','stop','instruction'):recent.append(safe_excerpt(event))
    native_status = native.get('status','NO_NATIVE_RESULT') if isinstance(native,dict) else 'NO_NATIVE_RESULT'
    if type(native_status) is not str or not re.fullmatch(r'[A-Z0-9_]{1,80}',native_status):
        native_status = 'UNRECOGNIZED_NATIVE_STATUS'
    stop = {'status':native_status,
            'pc':native.get('pc') if isinstance(native,dict) else None,
            'physical_offset':native.get('physical_offset') if isinstance(native,dict) else None,
            'frames':native.get('frames') if isinstance(native,dict) else None,
            'steps':native.get('native_steps') if isinstance(native,dict) else None,
            'preceding_input':last_input,'last_nonzero_input':last_nonzero_input,
            'nonneutral_input_observed':last_nonzero_input is not None,'published_stop':last_stop,
            'interpretation':'TEMPORAL_CORRELATION_ONLY_NOT_CAUSAL_PROOF',
            'sampled_recent_transitions':list(recent)}
    if last_input is not None and isinstance(native,dict):
        last_cycle=last_input.get('guest_cycles')
        now=native.get('guest_cycles')
        if type(last_cycle) is int and type(now) is int:
            stop['guest_cycles_since_input']=max(0,now-last_cycle)
    return stop,total


def diagnostic_zip(out,diagnostics,summary,events):
    diagnostics=Path(diagnostics);diagnostics.mkdir(parents=True,exist_ok=True)
    payload={'preview.json':(json.dumps(summary,indent=2,sort_keys=True)+'\n').encode('utf8'),
             'monitor-events.jsonl':(''.join(json.dumps(safe_excerpt(e),sort_keys=True)+'\n' for e in list(events)[-MAX_EVENTS_ZIP:])).encode('utf8')}
    manifest={'schema':'recompdev.preview.diagnostics.v1',
              'files':{name:{'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)} for name,data in payload.items()},
              'rom_included':False,'native_binary_included':False,'host_paths_included':False}
    payload['manifest.json']=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode('utf8')
    dest=diagnostics/(out.name+'-diagnostics.zip')
    if dest.exists():raise ValueError('PREVIEW_DIAGNOSTICS_ALREADY_EXISTS')
    with zipfile.ZipFile(dest,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted(payload.items()):z.writestr(name,data)
    return dest


def preview(opts):
    job_dir=Path(opts.job_dir).resolve(strict=True)
    job,rom,session,project,translation=select_source(job_dir,opts.cycle)
    source=Path(opts.source_root).resolve(strict=True)
    if source != ROOT: raise ValueError('PREVIEW_SOURCE_ROOT_MISMATCH')
    out_root=Path(opts.out_dir).resolve(strict=True) if Path(opts.out_dir).exists() else Path(opts.out_dir).resolve()
    if not out_root.is_absolute() or out_root == source or out_root.is_relative_to(source):
        raise ValueError('PREVIEW_OUTPUT_ROOT_UNSAFE')
    out_root.mkdir(parents=True,exist_ok=True)
    out=out_root/(job_dir.name+'-'+session.name+'-'+uuid.uuid4().hex[:12])
    out.mkdir(mode=0o700)
    state={'schema':'recompdev.preview.session.v1', 'job_id':job_dir.name,
           'source_sha256':job['rom_sha256'],'cycle':session.name,'round':project.name,
           'monitor_sample_every':opts.sample_every,'requested_video':opts.video,
           'requested_input':opts.input,'status':'STARTING',
           'gameplay_qualified':False,'recovery_state_modified':False}
    events=[]
    native=None
    proc_rc=None
    error=None
    viewer_state='DISABLED' if opts.no_viewer else 'NOT_STARTED'
    try:
        copy=copy_and_instrument(project,out/'source')
        state.update(copy)
        reuse=reuse_compiled_translation(project,out/'source',job_dir)
        if reuse:state.update(reuse)
        else:state.update({'translation_binary_rebuilt':True,'binary_provenance':'FRESH_GENERATED_SOURCE_COMPILE'})
        cmd=['cmake','-S',str(out/'source'),'-B',str(out/'build'),
             '-DRECOMPDEV_SOURCE_ROOT='+str(source),'-DCMAKE_BUILD_TYPE=Release']
        run_checked(cmd,out/'configure.log',120)
        run_checked(['cmake','--build',str(out/'build'),'--target','RecompDevNativeApp','--config','Release','--parallel','2'],out/'build.log',240)
        game=native_binary(out/'build','RecompDevNativeApp')
        env=os.environ.copy()
        env['RECOMPDEV_CONTROLLER_DIAGNOSTIC_EVENTS']=str(out/'monitor-events.jsonl')
        env['RECOMPDEV_MONITOR_SAMPLE_EVERY']=str(opts.sample_every)
        # Native game CMake builds its private presentation providers. No active plugin mutation.
        dll={'nt':('.dll','Release'),'posix':('.so','')}
        for key,name in (('RECOMPDEV_RUNTIME_HOST_DLL','rd_runtime_host'),('RECOMPDEV_SMS_MODE4_DLL','rd_video_sms_mode4')):
            ext='.dll' if os.name=='nt' else '.dylib' if sys.platform=='darwin' else '.so'
            locations=[out/'build'/'Release'/(name+ext),out/'build'/(name+ext),out/'build'/('lib'+name+ext)]
            entry=next((p for p in locations if p.is_file()),None)
            if entry is None:raise ValueError('PREVIEW_PRESENTATION_PROVIDER_NOT_BUILT_'+name)
            env[key]=str(entry)
        with ControllerDiagnostics() as broker:
            broker.publish({'type':'session','status':'Starting separate preview','sample_every':opts.sample_every})
            log_handle=None
            if not opts.no_viewer:
                try:
                    viewer,log_handle=launch_viewer(broker,out)
                    time.sleep(0.25)
                    viewer_state='LAUNCHED_UNVERIFIED' if viewer.poll() is None else 'UNAVAILABLE_CHECK_VIEWER_LOG'
                except OSError:
                    viewer_state='UNAVAILABLE_CHECK_VIEWER_LOG'
            try:
                args=[str(game),str(rom),str(out/'frame'),str(opts.frames),str(opts.steps),
                     '--video',opts.video,'--audio','null','--input',opts.input,'--snapshot-every','60']
                if opts.hold_window:args.append('--hold-window')
                reader=NativeEventReader(out/'monitor-events.jsonl',lambda event:(events.append(event),broker.publish(event)))
                with (out/'native-stdout.log').open('wb') as stdout,(out/'native-stderr.log').open('wb') as stderr:
                    p=subprocess.Popen(args,env=env,stdout=stdout,stderr=stderr)
                    started=time.monotonic()
                    try:
                        while p.poll() is None:
                            reader.poll()
                            if time.monotonic()-started>opts.timeout:
                                p.kill();p.wait();error='PREVIEW_EXECUTION_TIMEOUT';break
                            time.sleep(0.035)
                        for _ in range(100):
                            if not reader.poll():break
                    finally:
                        if p.poll() is None:p.kill();p.wait()
                    proc_rc=p.returncode
                if (out/'native-stdout.log').stat().st_size > MAX_LOG:
                    error=error or 'PREVIEW_NATIVE_REPORT_OVERSIZED'
                else:
                    for line in (out/'native-stdout.log').read_text(encoding='utf8',errors='replace').splitlines():
                        if line.startswith('NATIVE_APP_RESULT='):
                            native=json.loads(line.partition('=')[2]);break
                broker.publish({'type':'stop','status':str(native.get('status','NO_NATIVE_RESULT')) if native else 'NO_NATIVE_RESULT',
                                'pc':native.get('pc',0) if native else 0,'frame':native.get('frames',0) if native else 0,
                                'physical_offset':native.get('physical_offset',0) if native else 0})
                time.sleep(0.15)
            finally:
                if log_handle is not None:log_handle.close()
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError,json.JSONDecodeError) as exc:
        explanation=str(exc)
        safe=explanation if re.fullmatch(r'[A-Z0-9_]+',explanation) else 'REDACTED_EXCEPTION_DETAILS'
        error=type(exc).__name__+': '+safe
    stop,n=collect_input_stop(events,native)
    state['status']='PREVIEW_CAPTURE_COMPLETE' if proc_rc==0 and native and not error else 'PREVIEW_INCOMPLETE'
    state['process_exit_code']=proc_rc
    state['native_stop']=stop
    state['observed_events']=n
    state['viewer']=viewer_state
    if error:state['failure_code']=error
    (out/'preview-summary.json').write_text(json.dumps(state,indent=2,sort_keys=True)+'\n',encoding='utf8')
    diagnostics=diagnostic_zip(out,opts.diagnostics_dir,state,events)
    print('RECOMPDEV_PREVIEW_RESULT='+state['status'])
    print('RECOMPDEV_PREVIEW_NATIVE_STATUS='+stop['status'])
    print('RECOMPDEV_PREVIEW_LAST_INPUT='+json.dumps(stop['preceding_input'],sort_keys=True))
    print('RECOMPDEV_PREVIEW_LAST_NONZERO_INPUT='+json.dumps(stop['last_nonzero_input'],sort_keys=True))
    print('RECOMPDEV_PREVIEW_STOP='+json.dumps({k:stop[k] for k in ('status','pc','physical_offset','frames','steps')},sort_keys=True))
    print('RECOMPDEV_PREVIEW_VIEWER='+viewer_state)
    print('RECOMPDEV_PREVIEW_EVIDENCE='+str(out))
    print('RECOMPDEV_DIAGNOSTICS_ZIP='+str(diagnostics))
    print('RECOMPDEV_DIAGNOSTICS_SHA256='+digest(diagnostics))
    return 0 if state['status']=='PREVIEW_CAPTURE_COMPLETE' else 2


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage',choices=['job-preview'],required=True)
    p.add_argument('--job-dir',required=True);p.add_argument('--source-root',required=True)
    p.add_argument('--out-dir',required=True);p.add_argument('--diagnostics-dir',required=True)
    p.add_argument('--cycle',type=int,default=0);p.add_argument('--frames',type=int,default=1200)
    p.add_argument('--steps',type=int,default=12000000);p.add_argument('--sample-every',type=int,default=128)
    p.add_argument('--video',choices=['window','capture'],default='window')
    p.add_argument('--input',choices=['live','neutral'],default='live')
    p.add_argument('--timeout',type=int,default=600)
    p.add_argument('--no-viewer',action='store_true');p.add_argument('--hold-window',action='store_true')
    a=p.parse_args(argv)
    if not (0<=a.cycle<=16 and 1<=a.frames<=36000 and 1<=a.steps<=20000000 and
            1<=a.sample_every<=65536 and 30<=a.timeout<=1800):
        p.error('Invalid preview bounds')
    if a.input=='live' and a.video!='window':p.error('Live input requires a window')
    if a.hold_window and a.video!='window':p.error('Hold-window requires a window')
    try:return preview(a)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print('RECOMPDEV_PREVIEW_ERROR='+type(exc).__name__+': '+str(exc),file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
