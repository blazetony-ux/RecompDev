#!/usr/bin/env python3
"""Protected local Git workspace, independent component builds and atomic runtime activation.

The stable workspace is source only; build products, runtime binaries, caches,
logs, catalogue, historical archives and execution evidence are siblings.
Never auto-delete existing versioned installations or owner-local data.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SOURCE))
VERSION_RE = re.compile(r'^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)$')
NAME_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_.-]{0,79}$')


def roots(source: Path = SOURCE):
    base = Path(os.environ.get('RECOMPDEV_PROJECTS_ROOT', str(source.parent))).resolve()
    return {
        'source': source.resolve(),
        'build': base/'RecompDev-Build',
        'runtime': base/'RecompDev-Runtime',
        'cache': base/'RecompDev-Cache',
        'data': base/'RecompDev-Data',
        'evidence': base/'RecompDev-Evidence',
        'archive': base/'RecompDev-Archive',
    }


def sha256(path: Path):
    h = hashlib.sha256()
    with open(path,'rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024), b''):h.update(chunk)
    return h.hexdigest()


def cmd(args, cwd=None, *, output=False):
    p = subprocess.run([str(a) for a in args], cwd=cwd, text=True,
                       capture_output=True, check=False)
    if p.returncode:
        raise RuntimeError(f"Command failed ({p.returncode}): {' '.join(map(str,args))}\n{p.stdout[-1200:]}\n{p.stderr[-1500:]}")
    if output:return p.stdout.strip()
    return p


def manifest(source: Path = SOURCE):
    doc=json.loads((source/'workspace/components.json').read_text(encoding='utf8'))
    if doc.get('schema')!='recompdev-components-v1':raise ValueError('Unsupported component schema')
    for name,spec in doc['components'].items():
        if not NAME_RE.fullmatch(name) or not (VERSION_RE.fullmatch(spec['version']) or (spec['kind']=='legacy-service' and re.fullmatch(r'\d+\.\d+\.\d+\.\d+',spec['version']))):
            raise ValueError('Invalid component name/version: '+name)
    return doc


def git_clean(source: Path = SOURCE):
    if not (source/'.git').exists():raise ValueError('Git repository has not been initialised')
    status=cmd(['git','status','--porcelain','--untracked-files=all'],cwd=source,output=True)
    if status:raise ValueError('Source checkout has uncommitted changes; refusing automatic release/update: '+status[:350])


def git_head(source: Path = SOURCE):
    if not (source/'.git').exists():return None
    return cmd(['git','rev-parse','HEAD'],cwd=source,output=True)


def migrate_original_archives(source: Path = SOURCE):
    """Move original ZIP baselines outside source; verify byte identity first.

    For an existing workspace, never overwrite an external file with differing bytes.
    The preserved extracted historical *source tree* remains unchanged.
    """
    p=roots(source)['archive']/'original-archives'
    p.mkdir(parents=True,exist_ok=True)
    original=source/'original-archives'
    moved=[]
    if original.is_dir():
        for item in original.iterdir():
            if not item.is_file():raise ValueError('Unexpected historical archive entry')
            target=p/item.name
            if target.exists():
                if sha256(target)!=sha256(item):raise ValueError('Baseline archive conflicts with existing external copy: '+item.name)
                item.unlink()
            else:
                shutil.copy2(item,target)
                if sha256(target)!=sha256(item):
                    target.unlink(missing_ok=True)
                    raise ValueError('Baseline archive verification failed')
                item.unlink()
            moved.append(item.name)
        original.rmdir()
    return moved


def init(source: Path = SOURCE, *, bootstrap_git=True):
    p=roots(source)
    # Existing sources, old versioned releases, user-owned databases and evidence
    # must never be deleted or overwritten by bootstrap.
    for key in ('build','runtime','cache','evidence','archive'):
        p[key].mkdir(parents=True,exist_ok=True)
    moved=migrate_original_archives(source)
    from migration import controller as preservation
    check=preservation.verify()
    if check['status']!='PASS':raise ValueError('Historical source verification failed')
    if bootstrap_git and not (source/'.git').exists():
        cmd(['git','init','-b','main'],cwd=source)
        # Respect existing global identity; supply a local fallback only when absent.
        for field,fallback in [('user.name','RecompDev Local'),('user.email','recompdev@localhost')]:
            setting=subprocess.run(['git','config','--get',field],cwd=source,text=True,capture_output=True)
            if setting.returncode or not setting.stdout.strip():
                cmd(['git','config','--local',field,fallback],cwd=source)
        cmd(['git','add','-A'],cwd=source)
        cmd(['git','commit','-m','Import verified RecompDev v0.4.3 preservation baseline and workspace infrastructure'],cwd=source)
        # Formal release tag is intentionally deferred until build/tests pass.
    elif bootstrap_git:
        # No silent mutation of existing repositories.
        git_clean(source)
    return {'status':'READY','roots':{k:str(v) for k,v in p.items()},
            'original_archives_externalized':moved,'preserved_original_files':check['unchanged_original_files'],
            'git_head':git_head(source)}


def configure(source: Path = SOURCE):
    path=roots(source)['build']/'cmake'
    path.parent.mkdir(parents=True,exist_ok=True)
    if not (path/'CMakeCache.txt').is_file():
        args=['cmake','-S',source/'harness','-B',path]
        if os.name=='nt':args+=['-A','x64']
        cmd(args)
    return path


def build(component: str, source: Path = SOURCE):
    spec=manifest(source)['components'].get(component)
    if not spec or spec['kind'] not in ('compiled-plugin','controller'):
        raise ValueError('Unknown/noncompiled component: '+component)
    path=configure(source)
    cmd(['cmake','--build',path,'--config','Release','--target',spec['target'],'--parallel'])
    file=binary_path(component,source)
    if not file.is_file():raise ValueError('Target built but binary not found: '+str(file))
    return {'component':component,'version':spec['version'],'binary':str(file),'sha256':sha256(file),
            'build_target':spec['target'],'status':'BUILT'}


def full_build(source: Path = SOURCE):
    path=configure(source)
    cmd(['cmake','--build',path,'--config','Release','--parallel'])
    return str(path)


def binary_path(component: str, source: Path = SOURCE):
    path=roots(source)['build']/'cmake'/'bin'
    if os.name=='nt':path=path/'Release'
    ext='.dll' if os.name=='nt' else '.dylib' if sys.platform=='darwin' else '.so'
    name='RecompDev.exe' if component=='controller' and os.name=='nt' else 'RecompDev' if component=='controller' else component+ext
    return path/name


def targeted_tests(component: str, source: Path = SOURCE):
    """Relevant CTest gates only, not synthetic-parity claims for production."""
    if component=='controller':pattern='v042_compiled_controller|v043_compiled_offline|v044_workspace'
    elif component=='rd_cpu_z80':pattern='modules_load|hybrid_|native_only_|unsupported_opcode|production_pcode_'
    elif component.startswith('rd_machine_'):pattern='modules_load|hybrid_|alternate_machine|production_pcode_'
    elif component=='rd_audio_wav':pattern='modules_load|hybrid_main_parity|inspect_generated_reports'
    elif component=='rd_display_ppm':pattern='modules_load|hybrid_main_parity|inspect_generated_reports'
    else:pattern='modules_load|hybrid_main_parity|production_pcode_hybrid_parity'
    if component=='production_cpu_bridge':
        cmd([sys.executable,'-B','-m','unittest','modular.tests.test_production_cpu','-q'],cwd=source)
        return {'status':'PASSED','component':component,'pattern':'modular.tests.test_production_cpu'}
    cmd(['ctest','--test-dir',configure(source),'-C','Release','--output-on-failure','-R',pattern])
    if component=='rd_cpu_z80':
        cmd([sys.executable,'-B','-m','unittest','modular.tests.test_production_cpu','-q'],cwd=source)
    return {'status':'PASSED','component':component,'pattern':pattern}


def full_tests(source: Path = SOURCE):
    cmd(['ctest','--test-dir',configure(source),'-C','Release','--output-on-failure','--parallel','4'])
    return {'status':'PASSED','suite':'all'}


def state_file(source: Path = SOURCE):
    return roots(source)['runtime']/'active-components.json'


def read_state(source: Path = SOURCE):
    p=state_file(source)
    return json.loads(p.read_text(encoding='utf8')) if p.is_file() else {'schema':'recompdev-runtime-lock-v1','active':{},'history':{}}


def atomic_json(path, payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf8',dir=path.parent,suffix='.tmp',delete=False) as stream:
        temp=Path(stream.name)
        json.dump(payload,stream,indent=2,sort_keys=True)
        stream.write('\n')
    try:os.replace(temp,path)
    finally:temp.unlink(missing_ok=True)


def atomic_copy(source: Path, target: Path):
    target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_name(target.name+'.candidate-'+str(os.getpid()))
    try:
        shutil.copy2(source,temp)
        if sha256(source)!=sha256(temp):raise ValueError('Staged binary SHA-256 mismatch')
        os.replace(temp,target)
    finally:temp.unlink(missing_ok=True)


def install_candidate(component: str, source: Path = SOURCE, *, validated=False):
    """Publish only built, tested candidate; preserve old binary for immediate rollback.

    This replaces the harness plugin, not the legacy production recovery service.
    """
    if not validated:targeted_tests(component,source)
    doc=manifest(source)
    if component not in doc['components']:raise ValueError('Unknown component: '+component)
    spec=doc['components'][component]
    if spec['kind'] not in ('controller','compiled-plugin'):raise ValueError('Cannot install legacy service as compiled DLL')
    file=binary_path(component,source)
    if not file.is_file():raise FileNotFoundError('Build the component first: '+str(file))
    digest=sha256(file)
    p=roots(source)['runtime'];version=spec['version']
    stored=p/'versions'/component/version/file.name
    if stored.exists():
        if sha256(stored)!=digest:
            raise ValueError('IMMUTABLE_VERSION_CONFLICT: '+component+' '+version+' already has a different binary; bump only this component')
    else:
        atomic_copy(file,stored)
    state=read_state(source)
    prior=state['active'].get(component)
    target=(p/file.name) if component=='controller' else (p/'active'/file.name)
    # A failed lockfile write must NEVER leave the active DLL and its recorded
    # hash pointing at different bytes. Restore the previously approved binary.
    try:
        atomic_copy(stored,target)
        if prior and (prior['sha256']!=digest or prior['version']!=version):
            history=state['history'].setdefault(component,[])
            history.append(prior)
        state['active'][component]={'version':version,'sha256':digest,'binary':str(stored),
                                   'active_path':str(target),'scope':spec['scope'],'git_commit':git_head(source)}
        atomic_json(state_file(source),state)
        if component=='controller':
            (p/'source-root.txt').write_text(str(source.resolve())+'\n',encoding='utf8')
    except Exception:
        if prior:
            previous_stored=Path(prior['binary'])
            if previous_stored.is_file() and sha256(previous_stored)==prior['sha256']:
                atomic_copy(previous_stored,target)
            else:
                raise RuntimeError('Activation failed and previous binary cannot be restored; lock verification required')
        else:
            target.unlink(missing_ok=True)
        raise
    return {'status':'ACTIVATED','component':component,'version':version,'sha256':digest,
            'active_binary':str(target),'previous_version':prior['version'] if prior else None,
            'scope':spec['scope']}


def rollback(component: str, source: Path = SOURCE):
    state=read_state(source)
    history=state['history'].get(component,[])
    if not history:raise ValueError('No previously activated version for '+component)
    old=history[-1]
    stored=Path(old['binary'])
    if not stored.is_file() or sha256(stored)!=old['sha256']:
        raise ValueError('Previously activated binary missing or changed')
    now=state['active'].get(component)
    target=Path(old['active_path'])
    atomic_copy(stored,target)
    history.pop()
    if now:history.append(now)
    state['active'][component]=old
    atomic_json(state_file(source),state)
    return {'status':'ROLLED_BACK','component':component,'version':old['version'],'sha256':old['sha256']}


def deploy_all(source: Path = SOURCE):
    p=roots(source)['runtime']
    p.mkdir(parents=True,exist_ok=True)
    # Harness runtime uses the exact active plugins, not the CMake build output.
    harness=roots(source)['build']/'cmake'/'bin'/('Release' if os.name=='nt' else '')/('RecompDevHarness.exe' if os.name=='nt' else 'RecompDevHarness')
    if not harness.is_file():raise FileNotFoundError('Build the full harness first: '+str(harness))
    atomic_copy(harness,p/harness.name)
    doc=manifest(source)
    report=[]
    for name,spec in doc['components'].items():
        if spec['kind'] in ('compiled-plugin','controller'):
            report.append(install_candidate(name,source,validated=True))
    return {'status':'DEPLOYED','components':report,'harness':str(p/harness.name)}


def bump(component: str, part: str, source: Path = SOURCE):
    path=source/'workspace/components.json'
    d=manifest(source)
    if component not in d['components']:raise ValueError('Unknown component: '+component)
    sem=[int(x) for x in d['components'][component]['version'].split('.')]
    if part=='major':sem=[sem[0]+1,0,0]
    elif part=='minor':sem=[sem[0],sem[1]+1,0]
    elif part=='patch':sem[2]+=1
    else:raise ValueError('Unknown bump part')
    d['components'][component]['version']='.'.join(map(str,sem))
    atomic_json(path,d)
    return {'status':'CHANGED_UNCOMMITTED','component':component,'version':d['components'][component]['version']}


def release(tag: str, source: Path = SOURCE):
    if not re.fullmatch(r'workspace/v\d+\.\d+\.\d+(?:[-.][A-Za-z0-9.-]+)?',tag):
        raise ValueError('Release tag must be workspace/vN.N.N')
    git_clean(source)
    from workspace import docs_governance
    docs_governance.check(source, release=tag)
    full_tests(source)
    from migration import controller as preservation
    check=preservation.verify()
    if check['status']!='PASS':raise ValueError('Historical preservation gate failed')
    existing=subprocess.run(['git','tag','--list',tag],cwd=source,text=True,capture_output=True).stdout.strip()
    if existing:
        tagged_commit=cmd(['git','rev-list','-n','1',tag],cwd=source,output=True)
        if tagged_commit!=git_head(source):raise ValueError('Existing release tag points to a different commit: '+tag)
    else:
        cmd(['git','tag','-a',tag,'-m','Validated RecompDev workspace '+tag],cwd=source)
    # A separate Git bundle is a recoverable source-history snapshot, outside
    # the managed checkout. A second-drive/offsite copy remains recommended.
    store=roots(source)['archive']/'git-backups'
    store.mkdir(parents=True,exist_ok=True)
    path=store/(tag.replace('/','_')+'-'+git_head(source)[:12]+'.bundle')
    if not path.exists():
        cmd(['git','bundle','create',path,'--all'],cwd=source)
    cmd(['git','bundle','verify',path],cwd=source)
    return {'status':'ALREADY_TAGGED' if existing else 'TAGGED','tag':tag,
            'commit':git_head(source),'git_bundle':str(path),'git_bundle_sha256':sha256(path)}



def component_sources(component: str):
    """Restrict routine plugin updates to their published source boundary."""
    fixed={
        'controller':{'controller/main.cpp','controller/recompdev_python_config.h.in',
                      'modular/cli.py','modular/controller.py',
                      'modular/evidence_bundle.py','modular/hardware_review.py',
                      'modular/recovery_manager.py'},
        'workspace_governance':{'workspace/manager.py','workspace/docs_governance.py',
                                'workspace/tests/test_docs_governance.py',
                                'workspace/provenance.py','tools/apply_workspace_docs.py'},
        'rd_game_recomp_v0445':{'harness/generated/rd_game_recomp_v0445.cpp'},
        'rd_cpu_z80':{'harness/plugins/cpu_z80.cpp','harness/include/rd_production_cpu_v1.h',
                      'modular/tests/test_production_cpu.py'},
        'production_cpu_bridge':{'modular/cpu_production.py','modular/controller.py',
                                  'modular/cli.py','workspace/provenance.py',
                                  'modular/tests/test_production_cpu.py'},
    }
    if component in fixed:return fixed[component]
    if not component.startswith('rd_'):return set()
    return {'harness/plugins/'+component[3:]+'.cpp'}


def validate_component_diff(component: str, before: dict, after: dict, changed: set, source: Path = SOURCE):
    if component not in before['components']:
        raise ValueError('Unknown component: '+component)
    if before['components'][component]['kind'] not in ('compiled-plugin','controller','tooling'):
        raise ValueError('Legacy production services are frozen; use a separate source migration')
    b=before['components'][component]
    a=after['components'][component]
    if not VERSION_RE.fullmatch(a['version']) or tuple(map(int,a['version'].split('.'))) <= tuple(map(int,b['version'].split('.'))):
        raise ValueError('Published component version must increase monotonically: '+component)
    if a['kind']!=b['kind'] or a['target']!=b['target'] or a['scope']!=b['scope']:
        raise ValueError('Component kind, build target and scope are protected by the core API gate')
    for name,spec in before['components'].items():
        if name!=component and after['components'].get(name)!=spec:
            raise ValueError('Unrelated component version/descriptor changed: '+name)
    if set(before['components'])!=set(after['components']):
        raise ValueError('Component add/remove requires a separate core migration')
    allowed=component_sources(component)|{'workspace/components.json',f'docs/components/{component}/CHANGELOG.md'}
    if changed - allowed:
        raise ValueError('Update crosses component boundary: '+repr(sorted(changed-allowed)))
    if not (changed & component_sources(component)):
        raise ValueError('No source change for component: '+component)
    from workspace import docs_governance
    docs_governance.validate_component_update(source,component,a['version'],changed)


def docs_accept(source: Path = SOURCE):
    """Commit documentation-only edits after validation; no component version bumps."""
    if not (source/'.git').is_dir():raise ValueError('Local Git repository required')
    status=subprocess.run(['git','status','--porcelain','--untracked-files=all'],
                          cwd=source,text=True,capture_output=True,check=True).stdout.rstrip('\n')
    if not status:raise ValueError('No documentation edits to accept')
    changed=set()
    for line in status.splitlines():
        if len(line)<4 or line[:2].strip() not in ('M','A','??','D'):
            raise ValueError('Unsupported source state (rename/conflict): '+line)
        path=line[3:]
        if not (path.startswith('docs/') or path in ('README.md','CHANGELOG.md','workspace/components.json')):
            raise ValueError('Documentation commit touches non-documentation source: '+path)
        changed.add(path)
    before=json.loads(cmd(['git','show','HEAD:workspace/components.json'],cwd=source,output=True))
    after=manifest(source)
    if before['components']!=after['components']:
        raise ValueError('Documentation-only commit may not alter independent component versions')
    from workspace import docs_governance
    result=docs_governance.check(source)
    cmd([sys.executable,'-B','-m','unittest','workspace.tests.test_docs_governance','-q'],cwd=source)
    from migration import controller as preservation
    report=preservation.verify()
    if report['status']!='PASS':raise ValueError('Historical source preservation failed')
    cmd(['git','add','-A','--']+sorted(changed),cwd=source)
    cmd(['git','commit','-m','docs: accept validated documentation updates'],cwd=source)
    return {'status':'DOCS_COMMITTED','git_commit':git_head(source),
            'changed_files':len(changed),'component_versions_changed':0,
            'compiled_binaries_rebuilt':0,'validation':result}


def accept(component: str, source: Path = SOURCE):
    """Accept manually replaced files: validate -> build -> test -> commit -> activate.

    This is the ordinary local Git workflow. Failed build/test leaves the local
    developer edits intact but never creates a release commit or changes runtime.
    """
    if not (source/'.git').is_dir():raise ValueError('Local Git repository required')
    before=json.loads(cmd(['git','show','HEAD:workspace/components.json'],cwd=source,output=True))
    after=manifest(source)
    status_proc=subprocess.run(['git','status','--porcelain','--untracked-files=all'],
                               cwd=source,text=True,capture_output=True,check=True)
    # Porcelain's leading status columns are significant: str.strip() loses
    # the first status-column space and corrupts filenames ('harness'->'arness').
    status=status_proc.stdout.rstrip('\n')
    if not status:raise ValueError('No source changes to accept')
    changed=set()
    for line in status.splitlines():
        if len(line)<4 or line[:2].strip() not in ('M','A','??'):
            raise ValueError('Unsupported source state (rename/delete/conflict): '+line)
        changed.add(line[3:])
    validate_component_diff(component,before,after,changed,source=source)
    if after['components'][component]['kind']=='tooling':
        from workspace import docs_governance
        docs_governance.check(source)
        cmd([sys.executable,'-B','-m','unittest','workspace.tests.test_docs_governance','-q'],cwd=source)
        if component=='production_cpu_bridge':
            targeted_tests(component,source)
        from migration import controller as preservation
        report=preservation.verify()
        if report['status']!='PASS':raise ValueError('Preservation gate failed')
        cmd(['git','add','--']+sorted(changed),cwd=source)
        cmd(['git','commit','-m',f'Update {component} to {after["components"][component]["version"]} (validated tooling)'],cwd=source)
        return {'status':'ACCEPTED_TOOLING','component':component,
                'version':after['components'][component]['version'],
                'git_commit':git_head(source),'compiled_binaries_rebuilt':0}
    compiled=build(component,source)
    targeted_tests(component,source)
    from workspace import docs_governance
    docs_governance.check(source)
    from migration import controller as preservation
    preservation.verify()
    cmd(['git','add','--']+sorted(changed),cwd=source)
    cmd(['git','commit','-m',f'Update {component} to {after["components"][component]["version"]} (validated)'],cwd=source)
    try:
        deployed=install_candidate(component,source,validated=True)
    except Exception as exc:
        return {'status':'COMMITTED_NOT_ACTIVATED','reason':str(exc),
                'component':component,'commit':git_head(source),'build':compiled}
    return {'status':'ACCEPTED','component':component,'version':after['components'][component]['version'],
            'commit':git_head(source),'build':compiled,'activation':deployed}


def apply_update(archive: Path, source: Path = SOURCE):
    """Small-source-patch transaction. No unrestricted extracts, no silent Git add -A."""
    git_clean(source)
    archive=Path(archive).resolve(strict=True)
    with zipfile.ZipFile(archive) as z:
        if 'update.json' not in z.namelist():raise ValueError('Missing update.json')
        doc=json.loads(z.read('update.json'))
        if doc.get('schema')!='recompdev-update-v1':raise ValueError('Wrong update schema')
        component=doc.get('component','')
        if component not in manifest(source)['components']:raise ValueError('Unknown update component')
        files=doc.get('files',[])
        if not 1<=len(files)<=100:raise ValueError('Invalid update file count')
        old={};new={}
        for item in files:
            rel=item['path'];p=Path(rel)
            if (p.is_absolute() or '..' in p.parts or '\\' in rel or ':' in rel or
                    not all(part and part!='.' for part in p.parts) or
                    rel.startswith(('legacy/','baselines/','migration/source-integrity-manifest.json','original-archives/','.git/'))):
                raise ValueError('Unsafe/immutable update path: '+rel)
            target=(source/p).resolve()
            if not target.is_relative_to(source.resolve()):raise ValueError('Escaping source checkout')
            if rel not in z.namelist():raise ValueError('Missing changed file: '+rel)
            contents=z.read(rel)
            if hashlib.sha256(contents).hexdigest()!=item['new_sha256']:
                raise ValueError('Update file hash mismatch: '+rel)
            if target.exists():
                previous=target.read_bytes()
                if hashlib.sha256(previous).hexdigest()!=item['old_sha256']:
                    raise ValueError('Installed source mismatch: '+rel)
            else:
                previous=None
                if item['old_sha256'] is not None:raise ValueError('Expected existing source: '+rel)
            old[target]=previous;new[target]=contents
        # Any change to a compiled component must include a matching version bump.
        current=manifest(source)['components'][component]['version']
        if doc.get('new_version')==current:
            raise ValueError('Refusing release without new component version: '+component)
        if not VERSION_RE.fullmatch(doc.get('new_version','')):
            raise ValueError('Invalid update new_version')
        if source/'workspace/components.json' not in old:
            raise ValueError('Update must include independent component versions manifest')
        next_spec=json.loads(new[source/'workspace/components.json'])['components'][component]
        if next_spec['version']!=doc['new_version']:
            raise ValueError('Version update manifest does not match declared component version')
        previous_manifest=json.loads(old[source/'workspace/components.json'])
        updated_manifest=json.loads(new[source/'workspace/components.json'])
        validate_component_diff(component,previous_manifest,updated_manifest,
                                {str(target.relative_to(source)) for target in new},source=source)
    backup=roots(source)['archive']/'update-backups'/f'{int(time.time())}-{os.getpid()}'
    backup.mkdir(parents=True,exist_ok=False)
    for target,content in old.items():
        if content is not None:
            dest=backup/target.relative_to(source)
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(content)
    try:
        for target,content in new.items():
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(content)
        if manifest(source)['components'][component]['kind']=='tooling':
            result={'status':'SOURCE_ONLY','component':component}
            cmd([sys.executable,'-B','-m','unittest','workspace.tests.test_docs_governance','-q'],cwd=source)
        else:
            result=build(component,source)
            targeted_tests(component,source)
        from workspace import docs_governance
        docs_governance.check(source)
        from migration import controller as preservation
        preservation.verify()
    except Exception:
        for target,content in old.items():
            if content is None:target.unlink(missing_ok=True)
            else:target.write_bytes(content)
        raise
    cmd(['git','add','--']+[str(p.relative_to(source)) for p in new],cwd=source)
    cmd(['git','commit','-m',f'Update {component} to {doc["new_version"]} (tested)'],cwd=source)
    if manifest(source)['components'][component]['kind']=='tooling':
        return {'status':'UPDATED_TOOLING','component':component,
                'version':doc['new_version'],'commit':git_head(source),
                'build':result,'backup':str(backup),'compiled_binaries_rebuilt':0}
    try:
        promoted=install_candidate(component,source,validated=True)
    except Exception as exc:
        # Source commit is valid; runtime is still on the previous known-good
        # plugin, or fails closed. Never silently discard a tested source commit.
        return {'status':'COMMITTED_NOT_ACTIVATED','reason':str(exc),'component':component,
                'commit':git_head(source),'backup':str(backup)}
    return {'status':'UPDATED','component':component,'version':doc['new_version'],
            'commit':git_head(source),'build':result,'activation':promoted,'backup':str(backup)}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    for a in ('paths','status','init','full-build','full-test','deploy-all','docs-check','docs-accept'):
        sub.add_parser(a)
    for a in ('build','test','activate','rollback','accept'):
        pp=sub.add_parser(a);pp.add_argument('component')
    pp=sub.add_parser('bump');pp.add_argument('component');pp.add_argument('part',choices=('major','minor','patch'))
    pp=sub.add_parser('release');pp.add_argument('tag')
    pp=sub.add_parser('apply-update');pp.add_argument('archive')
    args=parser.parse_args(argv)
    try:
        if args.action=='paths':result={k:str(v) for k,v in roots().items()}
        elif args.action=='init':result=init()
        elif args.action=='status':result={'roots':{k:str(v) for k,v in roots().items()},
                                          'components':manifest()['components'],
                                          'active':read_state()['active'],'git_head':git_head()}
        elif args.action=='full-build':result={'status':'BUILT','build_dir':full_build()}
        elif args.action=='full-test':result=full_tests()
        elif args.action=='deploy-all':result=deploy_all()
        elif args.action=='docs-check':
            from workspace import docs_governance
            result=docs_governance.check(SOURCE)
        elif args.action=='docs-accept':result=docs_accept()
        elif args.action=='build':result=build(args.component)
        elif args.action=='test':result=targeted_tests(args.component)
        elif args.action=='activate':result=install_candidate(args.component)
        elif args.action=='rollback':result=rollback(args.component)
        elif args.action=='accept':result=accept(args.component)
        elif args.action=='bump':result=bump(args.component,args.part)
        elif args.action=='release':result=release(args.tag)
        elif args.action=='apply-update':result=apply_update(args.archive)
        print(json.dumps(result,indent=2,sort_keys=True))
        return 0
    except (OSError,subprocess.SubprocessError,RuntimeError,ValueError,KeyError,TypeError,zipfile.BadZipFile) as exc:
        print(json.dumps({'status':'ERROR','reason':str(exc)},indent=2),file=sys.stderr)
        return 2


if __name__=='__main__':raise SystemExit(main())
