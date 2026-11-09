#!/usr/bin/env python3
"""v0.4.9.28 controller-owned, single-process native gameplay recovery.

The guest owns its state and window. This controller owns source-attested
translation, compilation, diagnostics, and module approval. A missing-code
request pauses execution but NEVER restarts or replays the native game.
SMS/Z80 discovery lives in this adapter, not in the compiled controller or
universal native module loader. Other machines require separate adapters.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analysis_integration.cli import checked_process, app_stop_seed, RecoveryBlocked
from analysis_integration.providers import acquire, analyze_observed_bank_region
from analysis_integration.tool_authorization import authorize_tool
from controller.diagnostics import ControllerDiagnostics
from execution_monitor.job_preview import launch_viewer
from analysis_integration import native_library as library
from analysis_integration import generated_source_sync as source_sync

SCHEMA='recompdev.native.live.session.v1'
RESPONSE_SCHEMA='recompdev.native.live.response.v1'
MAX_RECOVERIES=512
MAX_TELEMETRY=12*1024*1024

def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda:stream.read(1024*1024),b''):h.update(data)
    return h.hexdigest()

def log_status(code:str,detail=''):
    print('RECOMPDEV_LIVE_'+code+('='+str(detail) if detail!='' else ''),flush=True)

def atomic_json(path:Path,content:dict):
    if path.exists():raise RecoveryBlocked('IMMUTABLE_LIVE_MESSAGE_ALREADY_EXISTS')
    data=(json.dumps(content,sort_keys=True,separators=(',',':'))+'\n').encode('utf8')
    if len(data)>8192:raise RecoveryBlocked('LIVE_MESSAGE_SIZE_LIMIT')
    temp=path.with_name(path.name+'.pending')
    with temp.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    os.replace(temp,path)

def original_home()->Path:
    if os.getenv('RECOMPDEV_HOME'):return Path(os.environ['RECOMPDEV_HOME']).resolve()
    if os.name=='nt':return Path(os.environ['LOCALAPPDATA'])/'RecompDev'
    return Path(os.getenv('XDG_STATE_HOME',str(Path.home()/'.local/state')))/'recompdev'

def get_config(source:Path,home:Path,test:bool):
    file=home/'config.json'
    if test and not file.exists():return {'ghidra':'','rizin':'','allow_tool_roots':[],
        'evidence_root':str(home/'RecompDev-Evidence'),'workspace':''}
    if not file.is_file():raise RecoveryBlocked('RUN_RECOMPDEV_CONFIGURE_FIRST')
    config=json.loads(file.read_text(encoding='utf8'))
    if config.get('schema')!='recompdev.controller.config.v1':raise RecoveryBlocked('CONFIG_SCHEMA_MISMATCH')
    roots=tuple(Path(p).resolve(strict=True) for p in config.get('allow_tool_roots',[]))
    if not roots or len(roots)>16:raise RecoveryBlocked('CONFIG_TOOL_ROOTS_INVALID')
    config['ghidra']=str(authorize_tool(Path(config['ghidra']),roots,'ghidra'))
    config['rizin']=str(authorize_tool(Path(config['rizin']),roots,'rizin'))
    return config

def evidence_root(source:Path,config:dict)->Path:
    root=config.get('evidence_root')
    if not root:
        root=config.get('workspace')
        if root and Path(root).name.startswith('v0.4.'):root=str(Path(root).parent)
    target=Path(root or source.parent/'RecompDev-Evidence').resolve()
    if not target.is_absolute() or target==target.anchor or source==target or source in target.parents or target in source.parents:
        raise RecoveryBlocked('EVIDENCE_ROOT_LOCATION_UNSAFE')
    return target

def checked(args:list[str],timeout:int,log:Path,cancelled=None):
    if cancelled is None:
        rc,_=checked_process(args,timeout,log,'RECOMPDEV_LIVE_UNUSED=')
    else:
        # Compilation is a process tree (controller -> CMake -> MSBuild/cc).
        # A closed guest must cancel that tree, not leave an orphan linker
        # writing incomplete objects into a scratch directory being removed.
        with log.open('xb') as output:
            kwargs={'stdin':subprocess.DEVNULL,'stdout':output,'stderr':subprocess.STDOUT}
            if os.name=='nt':kwargs['creationflags']=getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0)
            else:kwargs['start_new_session']=True
            process=subprocess.Popen(args,**kwargs)
            deadline=time.monotonic()+timeout
            try:
                while process.poll() is None:
                    if cancelled():
                        raise RecoveryBlocked('NATIVE_GAME_CLOSED_WHILE_COMPILING')
                    if time.monotonic()>deadline:
                        raise RecoveryBlocked('NATIVE_COMPILATION_TIMEOUT')
                    time.sleep(.1)
                rc=process.returncode
            except BaseException:
                if process.poll() is None:
                    if os.name=='nt':
                        subprocess.run(['taskkill','/T','/F','/PID',str(process.pid)],
                            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                            timeout=20,check=False)
                    else:
                        import signal
                        try:os.killpg(process.pid,signal.SIGTERM)
                        except ProcessLookupError:pass
                    try:process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        if os.name=='nt':process.kill()
                        else:
                            try:os.killpg(process.pid,signal.SIGKILL)
                            except ProcessLookupError:pass
                        process.wait(timeout=5)
                raise
    if rc:
        # Keep the exact command and full output in the immutable stage log.
        # Surface a short single-line excerpt so Windows validation failures
        # explain the native error instead of reporting an opaque exit code.
        lines=log.read_text(encoding='utf8',errors='replace').splitlines() if log.is_file() else []
        markers=('ERROR','FAILED','error ','fatal error','CMake Error','rejected','REJECTED')
        diagnostic=[line.strip() for line in lines if any(m in line for m in markers)]
        excerpt=' | '.join((diagnostic or lines)[-5:]).replace('\r',' ').replace('\n',' ')
        raise RecoveryBlocked('NATIVE_COMMAND_FAILED_'+str(rc)+'_'+log.stem+
                              (' | '+excerpt[-900:] if excerpt else ' | EMPTY_STAGE_LOG'))

def windows_native_build_workspace():
    """Short, owner-writable MSVC scratch root, independent of evidence paths.

    MSBuild's nested CMake VCTargetsPath.lastbuildstate can add about 100
    characters to the CMake build root. Versioned evidence paths, especially
    those in long isolated CTest HOME folders, must NEVER be CMake build roots.
    Source/translation logs and SHA-bound manifests remain in the evidence
    session. Scratch files are private and removed at the end of the session.
    """
    local=os.environ.get('LOCALAPPDATA') or tempfile.gettempdir()
    root=Path(local)/'RecompDev'/'nb'
    # Fail before compilation with a specific actionable status on pathological
    # Windows profile paths, rather than opaque MSB3491 after CMake starts.
    extra=Path('r27-0123456789')/'recovery-0001'/'build'/'CMakeFiles'/'4.4.4'/\
        'VCTargetsPath'/'x64'/'Debug'/'VCTargetsPath.tlog'/'VCTargetsPath.lastbuildstate'
    if len(str(root/extra))>=240:
        raise RecoveryBlocked('WINDOWS_NATIVE_BUILD_ROOT_TOO_LONG')
    root.mkdir(parents=True,exist_ok=True)
    if root.is_symlink() or not root.is_dir():
        raise RecoveryBlocked('WINDOWS_NATIVE_BUILD_ROOT_UNSAFE')
    scratch=tempfile.TemporaryDirectory(prefix='r27-',dir=root)
    if len(str(Path(scratch.name)/extra.relative_to('r27-0123456789')))>=240:
        scratch.cleanup()
        raise RecoveryBlocked('WINDOWS_NATIVE_BUILD_ROOT_TOO_LONG')
    return scratch

def retain_translation_manifest(compilation:Path,session:Path,name:str):
    """Retain an immutable translation audit even after scratch is removed."""
    original=compilation/'translation-manifest.json'
    target=session/'compilations'/(name+'-translation-manifest.json')
    with original.open('rb') as src, target.open('xb') as dst:
        shutil.copyfileobj(src,dst)
    if sha(original)!=sha(target):
        raise RecoveryBlocked('NATIVE_TRANSLATION_MANIFEST_RETENTION_MISMATCH')

def native_binary(build:Path,name:str):
    for f in (build/'Release'/(name+'.exe'),build/(name+'.exe'),build/name):
        if f.is_file():return f.resolve()
    raise RecoveryBlocked('NATIVE_BINARY_MISSING_'+name)

def native_module(build:Path):
    ext='.dll' if os.name=='nt' else '.dylib' if sys.platform=='darwin' else '.so'
    for f in (build/'Release'/('rd_generated_translation_hot'+ext),build/('rd_generated_translation_hot'+ext)):
        if f.is_file():return f.resolve()
    raise RecoveryBlocked('NATIVE_HOT_MODULE_MISSING')

def stage_module(original:Path,control:Path,n:int,dependencies:Path|None=None)->Path:
    dest=control/'modules'/('round-%04d'%n)
    dest.mkdir(parents=True,exist_ok=False)
    module=dest/original.name
    shutil.copyfile(original,module)
    if sha(original)!=sha(module):raise RecoveryBlocked('COPIED_MODULE_DIGEST_MISMATCH')
    # On Windows a newly compiled module may need the machine runtime and VDP
    # DLLs alongside it. These are source-built dependencies, not guest code.
    if os.name=='nt':
        for name in ('rd_sms_native_runtime.dll','rd_video_sms_mode4.dll'):
            for folder in (original.parent,original.parent.parent,dependencies) if dependencies else (original.parent,original.parent.parent):
                candidate=folder/name
                if candidate.is_file():shutil.copyfile(candidate,dest/name);break
    return module.resolve()

# Persist executable modules only within an exact, attested controller/runtime
# binary identity. This is compiled game-code reuse, NOT cross-ROM semantic reuse.
# The CPU ISA implementation itself is already shared by all compatible ROMs.
COMPILED_CACHE_SCHEMA='recompdev.native.compiled.module-cache.v1'
def compiled_cache_fingerprint(exe:Path, source:Path)->str:
    # Any rebuilt controller, CPU, translator, machine, video or host invalidates
    # the old cache. This intentionally favours correctness over cache hit rate.
    names=('RecompDev', 'rd_cpu_z80', 'rd_translation_pcode',
           'rd_sms_native_runtime', 'rd_video_sms_mode4', 'rd_runtime_host')
    suffix='.dll' if os.name=='nt' else '.dylib' if sys.platform=='darwin' else '.so'
    binaries=[]
    for name in names:
        binary=exe if name=='RecompDev' else exe.parent/(name+suffix)
        if not binary.is_file() or binary.is_symlink():
            raise RecoveryBlocked('COMPILED_CACHE_BINARY_IDENTITY_UNAVAILABLE_'+name)
        binaries.append([name,sha(binary)])
    contract=source/'native_runtime/include/rd_native_module_set.hpp'
    if not contract.is_file():raise RecoveryBlocked('NATIVE_MODULE_ABI_SOURCE_MISSING')
    record={'schema':COMPILED_CACHE_SCHEMA,'source_abi':sha(contract),
            'operating_system':os.name,'host_arch':platform.machine(),
            'native_binaries':binaries}
    return hashlib.sha256(json.dumps(record,sort_keys=True).encode()).hexdigest()

def cache_key(fingerprint:str,rom_sha:str,seed:dict)->str:
    record={'schema':COMPILED_CACHE_SCHEMA,'fingerprint':fingerprint,
            'source_sha256':rom_sha,'pc':seed['pc'],
            'physical_offset':seed['physical_offset'],'mapper':seed['mapper']}
    return hashlib.sha256(json.dumps(record,sort_keys=True).encode()).hexdigest()

def cache_fetch(root:Path,key:str,fingerprint:str,rom_sha:str):
    return library.fetch_cache(root,key,fingerprint,rom_sha)

def cache_commit(root:Path,key:str,fingerprint:str,rom_sha:str,module:Path,source:Path,emitted:int):
    return library.commit_cache(root,key,fingerprint,rom_sha,module,source,emitted)

def activation_ack(control:Path,index:int,rom_sha:str,request_hash:str,module_hash:str):
    path=control/('activation-%04d.json'%index)
    if not path.is_file():return False
    doc=library.read_json(path,8192)
    if (doc.get('schema'),doc.get('sequence'),doc.get('source_sha256'),
        doc.get('request_sha256'),doc.get('module_sha256')) != (
        'recompdev.native.live.activation.v1',index,rom_sha,request_hash,module_hash):
        raise RecoveryBlocked('NATIVE_ACTIVATION_RECEIPT_IDENTITY_MISMATCH')
    fp=doc.get('guest_state_fingerprint')
    if not isinstance(fp,str) or not fp or len(fp)>16 or any(c not in '0123456789abcdef' for c in fp):
        raise RecoveryBlocked('NATIVE_ACTIVATION_RECEIPT_STATE_INVALID')
    return True

def stage_preload(source:Path,control:Path,dependencies:Path):
    # Keep the verified base out of the active app directory. The loader will
    # validate the native block identity and SHA again inside the game process.
    folder=control/'modules'/'preload'
    folder.mkdir(exist_ok=False)
    path=folder/source.name
    shutil.copyfile(source,path)
    if sha(path)!=sha(source):raise RecoveryBlocked('NATIVE_PRELOAD_COPY_CHANGED')
    if os.name=='nt':
        for name in ('rd_sms_native_runtime.dll','rd_video_sms_mode4.dll'):
            dependency=dependencies/name
            if dependency.is_file():shutil.copyfile(dependency,folder/name)
    return path.resolve()

def validate_stop(request:dict,rom:Path,source_sha:str):
    if request.get('schema')!='recompdev.native.app.stop.v1':raise RecoveryBlocked('LIVE_REQUEST_SCHEMA_MISMATCH')
    seed=app_stop_seed(request,rom,source_sha)
    if any(type(seed.get(k)) is not int for k in ('pc','physical_offset','native_steps','rom_bytes')):
        raise RecoveryBlocked('LIVE_REQUEST_INTEGER_TYPES_INVALID')
    if not 0<=seed['pc']<0xc000 or not 0<=seed['physical_offset']<rom.stat().st_size:
        raise RecoveryBlocked('LIVE_REQUEST_ADDRESS_INVALID')
    if any(type(n) is not int or not 0<=n<256 for n in seed['mapper']):
        raise RecoveryBlocked('LIVE_REQUEST_MAPPER_INVALID')
    if not isinstance(request.get('guest_state_fingerprint'),str) or len(request['guest_state_fingerprint'])>16 or not request['guest_state_fingerprint'] or any(c not in '0123456789abcdef' for c in request['guest_state_fingerprint']):
        raise RecoveryBlocked('LIVE_REQUEST_STATE_FINGERPRINT_MISSING')
    return seed

def drain_telemetry(path:Path,position:int,broker:ControllerDiagnostics,record:list,limit:int):
    if not path.is_file():return position
    size=path.stat().st_size
    if size>MAX_TELEMETRY:raise RecoveryBlocked('NATIVE_TELEMETRY_SIZE_LIMIT')
    if size<position:raise RecoveryBlocked('NATIVE_TELEMETRY_TRUNCATED')
    if size==position:return position
    with path.open('rb') as f:f.seek(position);data=f.read(size-position)
    if not data.endswith(b'\n'):return position  # writer flushes complete lines
    for raw in data.splitlines():
        if not raw:continue
        event=json.loads(raw)
        if event.get('type') not in ('session','frame','instruction'):
            raise RecoveryBlocked('NATIVE_TELEMETRY_EVENT_UNSUPPORTED')
        broker.publish(event)
        if len(record)<limit:record.append(event)
    return size

def run(opts):
    test=opts.allow_synthetic_test_export and os.environ.get('RECOMPDEV_TEST_MODE')=='1'
    if opts.allow_synthetic_test_export and not test:raise RecoveryBlocked('SYNTHETIC_EXPORT_ONLY_IN_TEST_MODE')
    if opts.no_monitor and not test:raise RecoveryBlocked('MONITOR_REQUIRED_FOR_LIVE_PLAY')
    if opts.video!='window' or opts.input!='live':
        if not (test and opts.video=='capture' and opts.input=='neutral'):
            raise RecoveryBlocked('LIVE_PLAY_REQUIRES_WINDOW_AND_LIVE_INPUT')
    rom=Path(opts.rom or opts.rom_positional).resolve(strict=True)
    if not rom.is_file() or rom.stat().st_size>32*1024*1024 or not rom.stat().st_size:
        raise RecoveryBlocked('ROM_SIZE_UNSUPPORTED')
    source=Path(opts.source_root).resolve(strict=True)
    exe=Path(opts.controller_exe).resolve(strict=True)
    sha_rom=sha(rom)
    home=original_home()
    config=get_config(source,home,test)
    evidence_base=evidence_root(source,config)/'v0.4.9.28'
    target=evidence_base/'live'
    # Durable artifacts belong to a compact independent per-user store, not
    # deeply nested evidence paths that exceed Win32 MAX_PATH during Git/copy.
    generated_history,cache_root,consolidated_root=library.storage_roots(home,sha_rom)
    cache_fingerprint=compiled_cache_fingerprint(exe,source)
    source_publisher=source_sync.AutoPublisher(home)
    cache_root.mkdir(parents=True,exist_ok=True)
    if cache_root.is_symlink():raise RecoveryBlocked('COMPILED_CACHE_ROOT_SYMLINK')
    target.mkdir(parents=True,exist_ok=True)
    # A live run has one immutable evidence directory, no inherited job ID.
    session=target/('live-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+sha_rom[:8]+'-'+str(os.getpid()))
    session.mkdir(mode=0o700,parents=False,exist_ok=False)
    control=session/'control';control.mkdir();(control/'modules').mkdir()
    (session/'compilations').mkdir()
    report={'schema':SCHEMA,'release':'workspace/v0.4.9.28','rom_sha256':sha_rom,
            'target_frames':opts.frames,'status':'INITIALIZING','same_guest_process':True,
            'window_qualified':False,'semantic_parity_qualified':False,
            'hot_activations':[],'source_root':str(source),'session':str(session)}
    def snapshot():
        temp=session/'session.json.pending';temp.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');os.replace(temp,session/'session.json')
    def notice(broker,msg):
        broker.publish({'type':'notice','message':msg[:120]})
        print('RECOMPDEV_LIVE_PROGRESS='+msg,flush=True)
    viewer=None;viewer_log=None;game=None;game_log=None;build_workspace=None
    with ControllerDiagnostics(history_limit=512) as broker:
        try:
            # On Windows MSBuild cannot compile beneath a long CTest/evidence
            # directory (MAX_PATH). Keep evidence there; use compact scratch
            # only for generated CMake source/intermediates and binaries.
            if os.name=='nt':
                build_workspace=windows_native_build_workspace()
                compile_root=Path(build_workspace.name)
            else:
                compile_root=session/'compilations'
            report['native_compile_root']=str(compile_root)
            report['native_compile_scratch']=build_workspace is not None
            if not opts.no_monitor:
                viewer,viewer_log=launch_viewer(broker,session,exe.parent/'RecompDevMonitor.exe')
            notice(broker,'Analysing source and generating initial native code')
            format_dir=session/'format-discovery'
            checked([str(exe),'--stage','discover','--rom',str(rom),'--plugin-dir',str(exe.parent),
                     '--out',str(format_dir)],opts.timeout,session/'format.log')
            discovery=json.loads((format_dir/'native-discovery.json').read_text())
            if (discovery.get('platform'),discovery.get('cpu'))!=('sms','z80'):
                raise RecoveryBlocked('LIVE_EXECUTION_ADAPTER_UNAVAILABLE_'+str(discovery.get('platform')))
            # Here the SMS-specific analysis adapter begins. All load/resume
            # messaging uses the machine-neutral native module contract.
            if test:
                gh,reconciliation,analysis=acquire(rom,session/'analysis',export=Path(opts.test_export),
                    ghidra=None,rizin=None,tool_roots=(),timeout=opts.timeout,allow_synthetic=True)
            else:
                roots=tuple(Path(p) for p in config['allow_tool_roots'])
                gh,reconciliation,analysis=acquire(rom,session/'analysis',export=None,
                    ghidra=Path(config['ghidra']),rizin=Path(config['rizin']),
                    tool_roots=roots,timeout=opts.timeout)
            report['analysis']=analysis;snapshot()
            first=compile_root/'initial'
            command=[str(exe),'--stage','native-translate','--rom',str(rom),'--export',str(gh),
                     '--backend','full','--source-root',str(source),'--plugin-dir',str(exe.parent),
                     '--out',str(first),'--discover-source']
            if test:command.append('--allow-synthetic-export')
            if reconciliation:command+=['--analysis-candidates',str(reconciliation)]
            checked(command,opts.timeout*3,session/'initial-translation.log')
            retain_translation_manifest(first,session,'initial')
            app=native_binary(first/'build','RecompDevNativeApp')
            initial_doc=library.read_json(first/'translation-manifest.json')
            emitted=int(initial_doc['emitted'])
            known=library.Coverage(sha_rom)
            known.add(library.coverage_from_manifest(initial_doc,sha_rom))
            report['initial_emitted']=emitted
            preloaded=library.fetch_library(consolidated_root,sha_rom,cache_fingerprint)
            if not preloaded:
                # Compatibility-safe upgrade: the user's previously verified
                # generated-source history survives a change to the controller
                # or VDP DLL fingerprint. Re-translate old *evidence* against
                # this ROM and the current plugins once, rather than replaying
                # dozens of live recompilations or hot-loading an old DLL.
                old_frontiers=sorted((generated_history/'frontiers').glob('*.json')) if (generated_history/'frontiers').is_dir() else []
                old_banks=sorted((generated_history/'exports').glob('*.json')) if (generated_history/'exports').is_dir() else []
                if old_frontiers and len(old_frontiers)<=MAX_RECOVERIES and len(old_banks)<=MAX_RECOVERIES:
                    try:
                        required=library.Coverage(sha_rom)
                        required.add(known.entries())
                        saved_modules=generated_history/'m'
                        if saved_modules.is_dir():
                            for manifest_path in sorted(saved_modules.glob('*/translation-manifest.json')):
                                required.add(library.coverage_from_manifest(
                                    library.read_json(manifest_path),sha_rom))
                        recovered=compile_root/'history-rebuilt'
                        stop_index=session/'compilations'/'history-frontiers.txt'
                        bank_index=session/'compilations'/'history-exports.txt'
                        library.write_evidence_index(stop_index,old_frontiers)
                        library.write_evidence_index(bank_index,old_banks)
                        rebuild=[str(exe),'--stage','native-translate','--rom',str(rom),
                            '--export',str(gh),'--source-root',str(source),'--plugin-dir',str(exe.parent),
                            '--backend','full','--module-only','--discover-source','--out',str(recovered),
                            '--runtime-gap-index',str(stop_index),'--bank-export-index',str(bank_index)]
                        if test:rebuild.append('--allow-synthetic-export')
                        if reconciliation:rebuild+=['--analysis-candidates',str(reconciliation)]
                        checked(rebuild,opts.timeout*3,session/'historical-translation.log')
                        retain_translation_manifest(recovered,session,'historical')
                        doc=library.read_json(recovered/'translation-manifest.json')
                        coverage=library.coverage_from_manifest(doc,sha_rom)
                        by_physical={i['physical']:i for i in coverage}
                        if any(by_physical.get(i['physical'])!=i for i in required.entries()):
                            raise RecoveryBlocked('NATIVE_HISTORY_REBUILD_COVERAGE_INCOMPLETE')
                        rebuilt_module=native_module(recovered/'build')
                        archive=generated_history/'consolidated'/sha(rebuilt_module)
                        if not archive.exists():
                            archive.mkdir(parents=True)
                            for generated_file in recovered.iterdir():
                                if generated_file.is_file() and (library.SAFE_SOURCE.fullmatch(generated_file.name)
                                                                or generated_file.name=='translation-manifest.json'):
                                    shutil.copyfile(generated_file,archive/generated_file.name)
                        commit=library.git_checkpoint(generated_history,sha_rom,cache_fingerprint)
                        try:source_publisher.queued(sha_rom,commit)
                        except (OSError,RuntimeError) as error:report['generated_sync_warning']=str(error)[:300]
                        library.publish_library(consolidated_root,sha_rom,cache_fingerprint,
                            rebuilt_module,recovered,required.entries(),commit)
                        preloaded=library.fetch_library(consolidated_root,sha_rom,cache_fingerprint)
                        report['historical_source_rebuild']={'frontiers':len(old_frontiers),
                            'emitted':len(coverage),'source_commit':commit}
                        log_status('HISTORY_REBUILT_FROM_SOURCE',len(old_frontiers))
                    except (OSError,RuntimeError,ValueError,subprocess.TimeoutExpired) as error:
                        # An incompatible archive never prevents clean execution.
                        # Preserve it, leave old DLLs unloaded and recover afresh.
                        report['historical_rebuild_warning']=str(error)[:600]
                        log_status('HISTORY_REBUILD_WARNING',str(error)[:180])
            if preloaded:
                base_path,base_coverage,base_doc=preloaded
                known.add(base_coverage)
                preloaded=stage_preload(base_path,control,exe.parent)
                report['consolidated_preload']={'module_sha256':sha(preloaded),
                    'emitted':len(base_coverage),'generation':base_doc['generation']}
                log_status('CONSOLIDATED_LIBRARY','HIT')
            else:
                log_status('CONSOLIDATED_LIBRARY','MISS')
            notice(broker,'Native code ready - launching persistent game session')
            game_log=(session/'native-game.log').open('xb')
            app_args=[str(app),str(rom),str(session/'game'),str(opts.frames),str(opts.steps),
                      '--video',opts.video,'--audio','null','--input',opts.input,
                      '--live-control',str(control),'--live-max-recoveries',str(opts.max_recoveries),
                      '--live-wait-seconds',str(min(7200,opts.timeout*4))]
            if preloaded:app_args+=['--preload-module',str(preloaded)]
            if opts.hold_window:app_args.append('--hold-window')
            game=subprocess.Popen(app_args,stdin=subprocess.DEVNULL,stdout=game_log,stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0))
            report['game_pid']=game.pid;report['status']='EXECUTING';snapshot()
            log_status('GAME_PROCESS',game.pid)
            seen=set();seeds=[];banks=[];monitor_events=[];telemetry_pos=0;index=1
            pending_cache={}
            activated_count=0
            report['cached_activations']=0
            report['generated_source_commit']=None
            def collect_acks():
                nonlocal activated_count
                # An offered module is not a trusted artifact until the guest
                # has checked the SHA/ABI, resumed its frozen state and
                # independently published a source-bound activation receipt.
                for seq in sorted(list(pending_cache)):
                    item=pending_cache[seq]
                    if not activation_ack(control,seq,sha_rom,item['request_sha256'],item['module_sha256']):
                        break
                    known.add(item['coverage'])
                    if item['source'] is not None:
                        capsule=cache_commit(cache_root,item['key'],cache_fingerprint,sha_rom,
                            item['candidate'],item['source'],item['emitted'])
                        library.save_generated(generated_history,item['key'],capsule,
                            item['bank_exports'],item['seeds'])
                    report['hot_activations'][seq-1]['activation_confirmed']=True
                    report['cached_activations']+=1
                    activated_count+=1
                    del pending_cache[seq]
                    snapshot()
                    log_status('VERIFIED_MODULE_PERSISTED',seq)
                    # Every ACKed native region receives a durable Git commit,
                    # not just one out of four. Remote publication is queued
                    # independently so GitHub latency cannot pause guest input.
                    try:
                        report['generated_source_commit']=library.git_checkpoint(
                            generated_history,sha_rom,cache_fingerprint)
                        try:source_publisher.queued(sha_rom,report['generated_source_commit'])
                        except (OSError,RuntimeError) as error:
                            report['generated_sync_warning']=str(error)[:300]
                    except (OSError,RuntimeError,subprocess.TimeoutExpired) as error:
                        report['source_control_warning']=str(error)[:300]
                    snapshot()
            def consolidate_verified():
                # Source control / consolidation are opportunistic and deliberately
                # separate from guest playability acceptance. Failed optimisation
                # NEVER discards SHA-verified modules already activated and saved.
                if activated_count:
                    try:
                        report['generated_source_commit']=library.git_checkpoint(
                            generated_history,sha_rom,cache_fingerprint)
                        try:source_publisher.queued(sha_rom,report['generated_source_commit'])
                        except (OSError,RuntimeError) as error:report['generated_sync_warning']=str(error)[:300]
                    except (OSError,RuntimeError,subprocess.TimeoutExpired) as error:
                        report['source_control_warning']=str(error)[:300]
                    try:
                        prior_exports=list((generated_history/'exports').glob('*.json')) if (generated_history/'exports').is_dir() else []
                        prior_stops=list((generated_history/'frontiers').glob('*.json')) if (generated_history/'frontiers').is_dir() else []
                        all_banks={sha(p):p for p in [*banks,*prior_exports]}
                        all_stops={sha(p):p for p in [*seeds,*prior_stops]}
                        if len(all_banks)>MAX_RECOVERIES or len(all_stops)>MAX_RECOVERIES:
                            raise RecoveryBlocked('NATIVE_CONSOLIDATION_EVIDENCE_LIMIT')
                        merged=compile_root/'consolidated'
                        cmd=[str(exe),'--stage','native-translate','--rom',str(rom),'--export',str(gh),
                             '--source-root',str(source),'--plugin-dir',str(exe.parent),
                             '--backend','full','--module-only','--discover-source','--out',str(merged)]
                        if test:cmd.append('--allow-synthetic-export')
                        if reconciliation:cmd+=['--analysis-candidates',str(reconciliation)]
                        # Bounded UTF-8 index files avoid CreateProcessW's 32K
                        # command-line limit for large source histories. Each
                        # indexed report is still independently source-verified.
                        stop_index=session/'compilations'/'consolidation-frontiers.txt'
                        bank_index=session/'compilations'/'consolidation-exports.txt'
                        library.write_evidence_index(stop_index,all_stops.values())
                        library.write_evidence_index(bank_index,all_banks.values())
                        cmd+=['--runtime-gap-index',str(stop_index),
                              '--bank-export-index',str(bank_index)]
                        checked(cmd,opts.timeout*3,session/'consolidation-translation.log')
                        retain_translation_manifest(merged,session,'consolidated')
                        merged_module=native_module(merged/'build')
                        merged_manifest=library.read_json(merged/'translation-manifest.json')
                        merged_coverage=library.coverage_from_manifest(merged_manifest,sha_rom)
                        if any({i['physical']:i for i in merged_coverage}.get(i['physical'])!=i for i in known.entries()):
                            raise RecoveryBlocked('NATIVE_CONSOLIDATION_COVERAGE_INCOMPLETE')
                        archived=generated_history/'consolidated'/sha(merged_module)
                        if not archived.exists():
                            archived.mkdir(parents=True)
                            for file in merged.iterdir():
                                if file.is_file() and (library.SAFE_SOURCE.fullmatch(file.name) or file.name=='translation-manifest.json'):
                                    shutil.copyfile(file,archived/file.name)
                        # A new commit references precisely these generated sources.
                        report['generated_source_commit']=library.git_checkpoint(generated_history,sha_rom,cache_fingerprint)
                        try:source_publisher.queued(sha_rom,report['generated_source_commit'])
                        except (OSError,RuntimeError) as error:report['generated_sync_warning']=str(error)[:300]
                        record=library.publish_library(consolidated_root,sha_rom,cache_fingerprint,
                            merged_module,merged,known.entries(),report['generated_source_commit'])
                        report['consolidated_library']={'module_sha256':record['module_sha256'],
                            'emitted':record['emitted'],'generated_source_commit':record['generated_source_commit']}
                        log_status('CONSOLIDATED_LIBRARY','PUBLISHED')
                    except (OSError,RuntimeError,ValueError,subprocess.TimeoutExpired) as error:
                        report['consolidation_warning']=str(error)[:600]
                        log_status('CONSOLIDATION_WARNING',str(error)[:180])
                    snapshot()
            while True:
                collect_acks()
                telemetry_pos=drain_telemetry(control/'telemetry.jsonl',telemetry_pos,broker,monitor_events,2048)
                if game.poll() is not None:break
                request=control/('request-%04d.json'%index)
                if not request.is_file():
                    time.sleep(.08);continue
                raw=request.read_bytes()
                if len(raw)>8192:raise RecoveryBlocked('LIVE_REQUEST_TOO_LARGE')
                data=json.loads(raw)
                seed=validate_stop(data,rom,sha_rom)
                key=(seed['pc'],seed['physical_offset'],tuple(seed['mapper']))
                if key in seen:raise RecoveryBlocked('REPEATED_LIVE_GAP_NO_NEW_CODE')
                if index>opts.max_recoveries:raise RecoveryBlocked('LIVE_RECOVERY_LIMIT')
                seen.add(key)
                position=seed['pc']; notice(broker,'Paused guest at PC 0x%04X - compiling verified native code'%position)
                # Keep exact original request immutable; the native source
                # discovery independently verifies ROM/mapper/PC at this stop.
                seeds.append(request)
                # Each request is persisted individually; a session is bounded by the
                # configurable recovery budget rather than a hidden 64-item cap.
                key_hash=cache_key(cache_fingerprint,sha_rom,seed)
                cached=cache_fetch(cache_root,key_hash,cache_fingerprint,sha_rom)
                cache_status='HIT' if cached else 'MISS'
                if not cached:
                    if test:
                        # A synthetic regression may provide pre-generated exports
                        # for an observed frontier, never used in owner gameplay.
                        focused=None
                        synthetic_bank=Path(opts.test_bank_export) if opts.test_bank_export else None
                        if synthetic_bank and index==1:banks.append(synthetic_bank.resolve(strict=True))
                    else:
                        focused=session/'compilations'/('focused-%04d'%index)
                        region,audit=analyze_observed_bank_region(rom,focused,
                            ghidra=Path(config['ghidra']),tool_roots=tuple(Path(p) for p in config['allow_tool_roots']),
                            base_export=gh,observed=seed,timeout=opts.timeout)
                        banks.append(region)
                if len(banks)>MAX_RECOVERIES:raise RecoveryBlocked('LIVE_BANK_EXPORT_LIMIT')
                # A hit skips repeated Ghidra focused analysis and native C++
                # compilation, never the source/ABI/runtime activation checks.
                if cached:
                    candidate,new_emitted,new_coverage=cached
                    if not any(item['physical']==seed['physical_offset'] for item in new_coverage):
                        raise RecoveryBlocked('CACHED_MODULE_DOES_NOT_COVER_OBSERVED_FRONTIER')
                    translated_source=None
                else:
                    dest=compile_root/('recovery-%04d'%index)
                    cmd=[str(exe),'--stage','native-translate','--rom',str(rom),'--export',str(gh),
                         '--source-root',str(source),'--plugin-dir',str(exe.parent),
                         '--backend','full','--module-only','--discover-source','--out',str(dest)]
                    if test:cmd.append('--allow-synthetic-export')
                    if reconciliation:cmd+=['--analysis-candidates',str(reconciliation)]
                    # Delta translation needs the current source-attested
                    # frontier and its bank export; already activated regions
                    # are attested by the exclusion manifest. Do not replay the
                    # growing history in every native compile command.
                    cmd+=['--runtime-gap-report',str(request)]
                    if banks:cmd+=['--bank-export',str(banks[-1])]
                    exclusion=known.exclusion(session/'compilations'/('covered-before-%04d.json'%index))
                    cmd+=['--exclude-coverage-manifest',str(exclusion)]
                    checked(cmd,opts.timeout*3,session/('recovery-%04d-translation.log'%index),
                            cancelled=lambda:game.poll() is not None)
                    retain_translation_manifest(dest,session,'recovery-%04d'%index)
                    translated=json.loads((dest/'translation-manifest.json').read_text())
                    new_emitted=int(translated['emitted'])
                    new_coverage=library.coverage_from_manifest(translated,sha_rom)
                    translated_source=dest
                    # A later independently compiled module may contain fewer
                    # total instructions than an earlier overlay. The relevant
                    # proof is verified *coverage of this exact observed gap*,
                    # not monotonically increasing project-wide block counts.
                    accepted=translated.get('accepted_instructions',[])
                    if not any(type(item)==dict and item.get('physical')==seed['physical_offset']
                               for item in accepted):
                        raise RecoveryBlocked('LIVE_FRONTIER_NOT_IN_VERIFIED_NATIVE_MODULE')
                    candidate=native_module(dest/'build')
                emitted=max(emitted,new_emitted)
                module=stage_module(candidate,control,index,exe.parent)
                # A READY message alone proves no execution: persist only
                # after the independent in-process activation acknowledgement.
                log_status('COMPILED_MODULE_CACHE',cache_status)
                module_digest=sha(module)
                response=control/('response-%04d.json'%index)
                atomic_json(response,{'schema':RESPONSE_SCHEMA,'status':'READY',
                                     'source_sha256':sha_rom,'request_sha256':hashlib.sha256(raw).hexdigest(),
                                     'module':str(module),'module_sha256':module_digest})
                report['hot_activations'].append({'sequence':index,'pc':seed['pc'],'physical_offset':seed['physical_offset'],
                   'observed_frame':data.get('guest_frames'),'emitted':new_emitted,'cache':cache_status,
                   'module_sha256':module_digest,'activation_confirmed':False})
                pending_cache[index]={'key':key_hash,'candidate':candidate,'source':translated_source,
                    'emitted':new_emitted,'coverage':new_coverage,'module_sha256':module_digest,
                    'request_sha256':hashlib.sha256(raw).hexdigest(),
                    # Older evidence is already immutable in generated history.
                    # Persist only this new frontier and its focused bank;
                    # hashing every previous report on every activation grows
                    # quadratically during long real-ROM sessions.
                    'bank_exports':([banks[-1]] if banks and not cached else []),
                    'seeds':[request]}
                snapshot();notice(broker,'Module %d verified - resuming same game process'%index)
                index+=1
            collect_acks()
            telemetry_pos=drain_telemetry(control/'telemetry.jsonl',telemetry_pos,broker,monitor_events,2048)
            game_log.flush();game_log.close();game_log=None
            consolidate_verified()
            native=None
            if (session/'native-game.log').stat().st_size>MAX_TELEMETRY:
                raise RecoveryBlocked('NATIVE_RESULT_LOG_TOO_LARGE')
            for line in (session/'native-game.log').read_text(errors='replace').splitlines():
                if line.startswith('NATIVE_APP_RESULT='):
                    native=json.loads(line[len('NATIVE_APP_RESULT='):])
            if game.returncode!=0 or not native:raise RecoveryBlocked('NATIVE_GAME_EXIT_OR_RESULT_INVALID_'+str(game.returncode))
            if native.get('rom_bytes')!=rom.stat().st_size:raise RecoveryBlocked('NATIVE_RESULT_SOURCE_SIZE_MISMATCH')
            if native.get('hot_activations')!=len(report['hot_activations']):
                raise RecoveryBlocked('NATIVE_HOT_ACTIVATION_COUNT_MISMATCH')
            report['native_result']={key:native.get(key) for key in ('status','frames','guest_frames','native_steps',
                    'pc','physical_offset','guest_state_fingerprint','hot_activations')}
            if pending_cache:
                raise RecoveryBlocked('NATIVE_ACTIVATIONS_UNACKNOWLEDGED')
            if activated_count!=native.get('hot_activations'):
                raise RecoveryBlocked('NATIVE_ACTIVATION_RECEIPT_COUNT_MISMATCH')
            report['window_launch_attempted']=os.name=='nt' and opts.video=='window' and not opts.no_monitor
            # A process launch does not prove that either Win32 window was visible,
            # responsive, or continuously rendered during a recovery.
            report['window_qualified']=False
            report['status']='FRAME_BUDGET_REACHED_PARITY_UNVERIFIED' if native.get('status')=='FRAME_BUDGET_REACHED' and native.get('frames',0)>=opts.frames else 'GUEST_BLOCKED_'+str(native.get('status'))
            broker.publish({'type':'native_result','status':native.get('status'),'pc':native.get('pc'),
                'physical_offset':native.get('physical_offset'),'host_frame':native.get('frames'),
                'guest_frame':native.get('guest_frames')})
            notice(broker,report['status'])
            snapshot()
            log_status('RESULT',report['status'])
            log_status('EVIDENCE',session)
            return 0 if report['status']=='FRAME_BUDGET_REACHED_PARITY_UNVERIFIED' else 2
        except (OSError,ValueError,RuntimeError,KeyError,TypeError,json.JSONDecodeError) as exc:
            if 'pending_cache' in locals():
                try:collect_acks()
                except Exception as recovery_error:report['activation_audit_warning']=str(recovery_error)[:300]
            message=type(exc).__name__+': '+str(exc)[:300]
            report['status']='BLOCKED';report['reason']=message;snapshot()
            notice(broker,'BLOCKED: '+message[:100])
            # Reply to the currently outstanding request so the game cannot
            # wait indefinitely after a failed compilation/verification.
            if game is not None and game.poll() is None:
                control_files=sorted(control.glob('request-*.json'))
                for request in control_files:
                    response=control/request.name.replace('request-','response-')
                    if response.exists():continue
                    atomic_json(response,{'schema':RESPONSE_SCHEMA,'status':'BLOCKED',
                        'source_sha256':sha_rom,'request_sha256':sha(request),'reason':'CONTROLLER_COMPILE_BLOCKED'})
            # A guest that has been told to stop can exit without losing its
            # already activated code. Consolidation is best-effort, SHA- and
            # source-controlled, and cannot mask the original failure.
            if ('activated_count' in locals() and activated_count and 'consolidate_verified' in locals()
                    and 'consolidated_library' not in report and 'consolidation_warning' not in report):
                try:
                    if game is not None and game.poll() is None:
                        try:game.wait(timeout=5)
                        except subprocess.TimeoutExpired:pass
                    consolidate_verified()
                except (OSError,RuntimeError,ValueError,subprocess.TimeoutExpired) as recovery_error:
                    report['blocked_consolidation_warning']=str(recovery_error)[:600]
                snapshot()
            log_status('BLOCKED',message)
            log_status('EVIDENCE',session)
            return 2
        finally:
            if game and game.poll() is None:
                try:game.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    game.terminate()
                    try:game.wait(timeout=5)
                    except subprocess.TimeoutExpired:game.kill();game.wait(timeout=5)
            if game_log:game_log.close()
            if viewer:
                try:viewer.wait(timeout=1)
                except subprocess.TimeoutExpired:viewer.terminate()
            if viewer_log:viewer_log.close()
            source_publisher.finish()  # do not block on GitHub/network failures
            if build_workspace is not None:build_workspace.cleanup()

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('play','run'))
    p.add_argument('rom_positional',nargs='?')
    p.add_argument('--rom')
    p.add_argument('--auto-native',action='store_true')
    p.add_argument('--frames','--target-frames',type=int,default=2400)
    p.add_argument('--steps','--step-budget',type=int,default=20000000)
    p.add_argument('--max-recoveries',type=int,default=512)
    p.add_argument('--timeout',type=int,default=900)
    p.add_argument('--video',default='window');p.add_argument('--input',default='live')
    p.add_argument('--hold-window',action='store_true')
    p.add_argument('--no-monitor',action='store_true')
    p.add_argument('--test-export');p.add_argument('--test-bank-export');p.add_argument('--allow-synthetic-test-export',action='store_true')
    p.add_argument('--controller-exe',required=True);p.add_argument('--source-root',required=True)
    opts=p.parse_args(argv)
    if not opts.rom and not opts.rom_positional:p.error('ROM path required')
    if opts.rom and opts.rom_positional:p.error('Provide ROM only once')
    if opts.action=='run' and not opts.auto_native:p.error('run requires --auto-native for live session')
    if not 1<=opts.frames<=36000 or not 1<=opts.steps<=20000000 or not 1<=opts.max_recoveries<=MAX_RECOVERIES or not 30<=opts.timeout<=7200:
        p.error('Live session bounds exceeded')
    try:return run(opts)
    except Exception as exc:
        print('RECOMPDEV_LIVE_FATAL='+type(exc).__name__+': '+str(exc)[:300],file=sys.stderr)
        return 2
if __name__=='__main__':raise SystemExit(main())
