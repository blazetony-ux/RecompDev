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

SOURCE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SOURCE))
from runtime_host.bridge import install
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
                SOURCE/'runtime_host/include/rd_runtime_host.h']:
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
            elif sha256(candidate)!=sha256(original):
                raise ValueError('Cached native-project source has been changed: '+str(rel))
        for filename in ('rd_host_loader.hpp','win32_window.hpp','win32_audio.hpp'):
            if sha256(target/'hardware'/filename)!=sha256(SOURCE/'runtime_host/bridge'/filename):
                raise ValueError('Cached runtime host bridge was changed: '+filename)
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


def run(args):
    roots=manager.roots(SOURCE)
    output=roots['evidence']/'v0.4.8'/'runtime-host'
    output.mkdir(parents=True,exist_ok=True)
    runid=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    dest=output/runid;dest.mkdir(exist_ok=False)
    rom_digest=None
    record={'schema':'recompdev-generic-native-host-v0.1.0',
            'mode':args.mode,'frames_requested':args.frames,'steps_requested':args.steps,
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
        flag=['--video','window' if args.mode=='window' else 'capture',
              '--audio',args.audio if args.mode=='window' else 'capture',
              '--input','live' if args.mode=='window' else 'neutral']
        if args.snapshot_every:flag+=['--snapshot-every',str(args.snapshot_every)]
        if args.mode=='window' and args.hold_window:flag.append('--hold-window')
        cmd=[str(app),str(rom),str(prefix),str(args.frames),str(args.steps),'-',*flag]
        env=os.environ.copy();env['RECOMPDEV_RUNTIME_HOST_DLL']=str(dll)
        if args.mode=='window':
            env['RECOMPDEV_RUNTIME_HOST_INPUT_EVENTS']=str(dest/'input-events.jsonl')
        print('RECOMPDEV_RUNTIME_HOST launching generated native game application',flush=True)
        with (dest/'native-stdout.log').open('w',encoding='utf8') as stdout, (dest/'native-stderr.log').open('w',encoding='utf8') as stderr:
            proc=subprocess.run(cmd,env=env,stdout=stdout,stderr=stderr,timeout=args.timeout)
        # The process exit code alone does not establish guest execution success.
        # Extract the preserved native host's bounded structured result.
        observed=None
        for line in (dest/'native-stdout.log').read_text(encoding='utf8',errors='replace').splitlines():
            if line.startswith('NATIVE_APP_RESULT='):
                observed=json.loads(line.partition('=')[2]);break
        if not isinstance(observed,dict):
            raise ValueError('Native application produced no structured guest result; inspect logs')
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
                      runtime_host={'component':'rd_runtime_host','version':active['version'],
                                    'sha256':active['sha256'],'abi':'0x00010000'},
                      return_code=proc.returncode,
                      input_mode='live' if args.mode=='window' else 'neutral',
                      status=('NATIVE_PROCESS_FAILED' if proc.returncode else
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
    p.add_argument('--mode',choices=['window','headless'],default='window')
    p.add_argument('--audio',choices=['speaker','null'],default='null',help='Native audio remains silent in current Shinobi evidence')
    p.add_argument('--frames',type=int,default=1800)
    p.add_argument('--steps',type=int,default=12000000)
    p.add_argument('--snapshot-every',type=int,default=120)
    p.add_argument('--timeout',type=int,default=420)
    p.add_argument('--hold-window',action='store_true')
    a=p.parse_args(argv)
    if not 1<=a.frames<=36000 or not 1<=a.steps<=20000000 or not 0<=a.snapshot_every<=600 or not 30<=a.timeout<=900:
        p.error('Bounded runtime limits exceeded')
    return a

if __name__=='__main__':
    try:raise SystemExit(run(parse_args()))
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as exc:
        print('RECOMPDEV_RUNTIME_HOST_BLOCKED: '+str(exc),file=sys.stderr);raise SystemExit(2)
