#!/usr/bin/env python3
"""Apply one guarded documentation/governance update to an existing Git checkout.

The whole patch is verified against known old source hashes, applied only in
approved paths, and rolled back on any failure before Git commit. The C++
controller and all active DLLs are left untouched; full tests run against the
already-built external tree. A release tag and Git bundle are created only
once the test gate passes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile


SCHEMA = 'recompdev-docs-update-v1'
ALLOWED_OLD_ROOT_DOCS = frozenset((
    'RECOMPDEV-ARCHITECTURE-CONTRACT.md',
    'WORKSPACE-v0.4.4.md',
    'MIGRATION_STATUS.md',
    'DIRECT-EXE-QUICKSTART.md',
    'AUTO-EVIDENCE-HOTFIX2.md',
    'WINDOWS-CONTROLLER-HOTFIX1.md',
    'INSTALLER-README.md',
    'V043-HARDWARE-VALIDATION.md',
    'RELEASE_PROVENANCE-v0.4.json',
    'RELEASE_PROVENANCE-v0.4.1.json',
    'RELEASE_PROVENANCE-v0.4.2.json',
    'RELEASE_PROVENANCE-v0.4.3.json',
    'VALIDATION_RESULTS-v0.4.1.json',
    'VALIDATION_RESULTS-v0.4.2.json',
    'VALIDATION_RESULTS-v0.4.3.json',
))
ALLOWED_EXACT = frozenset((
    'README.md', 'CHANGELOG.md',
    'workspace/components.json', 'workspace/manager.py',
    'workspace/docs_governance.py',
    'workspace/tests/test_docs_governance.py',
    'tools/apply_workspace_docs.py',
    'tools/RecompDev-Workspace.ps1',
))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def command(args: list[str], cwd: Path, *, required: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True,
                          text=True, errors='replace', check=False,
                          env={**os.environ, 'PYTHONDONTWRITEBYTECODE':'1'})
    if required and proc.returncode:
        raise RuntimeError(f'{" ".join(map(str, args))} failed (exit {proc.returncode}):\n'
                           +proc.stdout[-2500:]+'\n'+proc.stderr[-2500:])
    return proc


def safely_relative(rel: str, source: Path) -> Path:
    if not rel or '\\' in rel or ':' in rel or rel.startswith('/') or '\0' in rel:
        raise ValueError('Unsafe path in update manifest: '+repr(rel))
    parts=Path(rel).parts
    if any(p in ('.','..','') for p in parts) or not parts:
        raise ValueError('Traversal path in update manifest: '+repr(rel))
    if not (rel in ALLOWED_EXACT or rel in ALLOWED_OLD_ROOT_DOCS or rel.startswith('docs/')):
        raise ValueError('Update targets a non-documentation component: '+rel)
    target=source / rel
    if not target.resolve().is_relative_to(source.resolve()):
        raise ValueError('Update target resolves outside the source checkout: '+rel)
    for parent in (target, *target.parents):
        if parent == source.parent:
            break
        if parent.is_symlink():
            raise ValueError('Update refused through symbolic link: '+rel)
    return target


def parse_package(package: Path, source: Path) -> tuple[dict, list[tuple[str, Path, bytes|None, bytes|None]]]:
    with zipfile.ZipFile(package) as z:
        if len(z.namelist()) != len(set(z.namelist())):
            raise ValueError('Duplicate ZIP paths')
        if 'update-manifest.json' not in z.namelist():
            raise ValueError('Missing source update manifest')
        meta=json.loads(z.read('update-manifest.json'))
        if meta.get('schema')!=SCHEMA:
            raise ValueError('Unsupported update schema')
        if meta.get('target_release')!='workspace/v0.4.5':
            raise ValueError('Unexpected target release; this patch is v0.4.5 only')
        files=meta.get('files')
        if not isinstance(files,list) or not 2<=len(files)<=160:
            raise ValueError('Invalid changed-file list')
        permitted={'update-manifest.json'}|{x['path'] for x in files if x['new_sha256'] is not None}
        if set(z.namelist())!=permitted:
            raise ValueError('Extra, missing or unlisted ZIP entries')
        changed=[]
        for item in files:
            rel=item['path'];target=safely_relative(rel,source)
            if target.is_dir():
                raise ValueError('Expected a source file but found a directory: '+rel)
            old=target.read_bytes() if target.is_file() else None
            before_sha=sha256(old) if old is not None else None
            if before_sha!=item['old_sha256']:
                raise ValueError('Pre-existing source file hash mismatch: '+rel)
            new=z.read(rel) if item['new_sha256'] is not None else None
            if (sha256(new) if new is not None else None)!=item['new_sha256']:
                raise ValueError('Package payload checksum mismatch: '+rel)
            if old is None and new is None:
                raise ValueError('Empty file operation: '+rel)
            changed.append((rel,target,old,new))
        return meta,changed


def ensure_before(source: Path, meta: dict):
    git=source/'.git'
    if not git.is_dir():
        raise ValueError('Local Git-managed v0.4.4 workspace required at '+str(source))
    actual=command(['git','rev-parse','HEAD'],source).stdout.strip()
    if actual!=meta['expected_git_head']:
        tag=command(['git','tag','--list','workspace/v0.4.5'],source).stdout.strip()
        if tag:
            tagged=command(['git','rev-list','-n','1','workspace/v0.4.5'],source).stdout.strip()
            if tagged==actual:
                return 'ALREADY_APPLIED'
        raise ValueError('Git HEAD differs from the validated v0.4.4 baseline; refusing to overwrite local development')
    status=command(['git','status','--porcelain','--untracked-files=all'],source).stdout.strip()
    if status:
        raise ValueError('Working tree is not clean; commit or review existing edits before applying this update')
    tag=command(['git','rev-list','-n','1','workspace/v0.4.4'],source).stdout.strip()
    if tag!=actual:
        raise ValueError('Original workspace/v0.4.4 release tag does not match installed baseline')
    return None


def verify_runtime(source: Path) -> tuple[dict, dict]:
    parent=Path(os.environ.get('RECOMPDEV_PROJECTS_ROOT',str(source.parent))).resolve()
    state=parent/'RecompDev-Runtime'/'active-components.json'
    if not state.is_file():
        raise ValueError('Cannot locate versioned runtime state; refusing documentation update')
    lock=json.loads(state.read_text(encoding='utf8'))
    hashes={}
    for name,item in lock['active'].items():
        binary=Path(item['active_path'])
        if not binary.is_file():
            raise ValueError('Runtime component missing: '+name)
        digest=sha256(binary.read_bytes())
        if digest!=item['sha256']:
            raise ValueError('Runtime binary disagrees with active-lock checksum: '+name)
        hashes[name]=digest
    return lock,hashes


def validate_protected(source: Path) -> dict:
    sys.path.insert(0,str(source))
    try:
        from migration import controller as preservation
        result=preservation.verify()
        if result['status']!='PASS' or result['unchanged_original_files']!=642:
            raise ValueError('Frozen historical sources no longer match 642-file baseline')
        return result
    finally:
        sys.path.pop(0)


def report_file(source: Path) -> Path:
    parent=Path(os.environ.get('RECOMPDEV_PROJECTS_ROOT',str(source.parent))).resolve()
    path=parent/'RecompDev-Archive'/'update-backups'/('docs-v045-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+f'-{os.getpid()}')
    path.mkdir(parents=True,exist_ok=False)
    return path


def restore(changes, source: Path):
    for rel,target,old,_ in reversed(changes):
        if old is None:
            target.unlink(missing_ok=True)
        else:
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(old)
    for rel,target,old,_ in reversed(changes):
        parent=target.parent
        while parent!=source and parent.is_relative_to(source):
            try:parent.rmdir()
            except OSError:break
            parent=parent.parent
    # Stage no changes on a precommit failure; ensure any index state from a
    # previous interrupted trial never masks what was restored.


def apply(package: Path, source: Path) -> dict:
    source=source.resolve(strict=True)
    if str(source) not in sys.path:sys.path.insert(0,str(source))
    if source.name.lower()!='recompdev':
        raise ValueError('Expected permanent RecompDev checkout, not a version-numbered installation')
    with zipfile.ZipFile(package) as z:
        meta=json.loads(z.read('update-manifest.json'))
    if ensure_before(source,meta)=='ALREADY_APPLIED':
        return {'status':'ALREADY_APPLIED','release':'workspace/v0.4.5',
                'source':str(source),'compiled_binaries_rebuilt':0}
    lock_before,hashes_before=verify_runtime(source)
    validate_protected(source)
    meta,changes=parse_package(package,source)
    backup=report_file(source)
    for rel,_,old,_ in changes:
        if old is not None:
            p=backup/'prior'/rel
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(old)
    (backup/'source-update-manifest.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf8')
    print('RECOMPDEV_DOCS_PROGRESS verified old hashes and protected sources; applying source-only patch',flush=True)
    committed=False
    try:
        for rel,target,old,new in changes:
            if new is None:
                target.unlink()
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                temp=target.with_name(target.name+f'.candidate-{os.getpid()}')
                try:
                    temp.write_bytes(new)
                    os.replace(temp,target)
                finally:temp.unlink(missing_ok=True)
        # Zero compilers invoked. Tests reuse already compiled external binaries.
        print('RECOMPDEV_DOCS_PROGRESS checking links, per-component changelogs and update tests',flush=True)
        command([sys.executable,'-B','-m','workspace.docs_governance','check'],source)
        command([sys.executable,'-B','-m','unittest','workspace.tests.test_docs_governance','-v'],source)
        validate_protected(source)
        print('RECOMPDEV_DOCS_PROGRESS running existing CTest regression suite (no C++ build)',flush=True)
        build=Path(os.environ.get('RECOMPDEV_PROJECTS_ROOT',str(source.parent))).resolve()/'RecompDev-Build'/'cmake'
        if not (build/'CTestTestfile.cmake').is_file():
            raise ValueError('Existing external CTest build missing; documentation update will not auto-rebuild C++')
        count=command(['ctest','--test-dir',build,'-N'],source).stdout
        if 'Total Tests: 38' not in count:
            raise ValueError('Expected 38 existing CTest gates; refuse incomplete regression run')
        command(['ctest','--test-dir',build,'-C','Release','--output-on-failure','--parallel','4'],source)
        lock_after,hashes_after=verify_runtime(source)
        if lock_after!=lock_before or hashes_after!=hashes_before:
            raise ValueError('Runtime component changed unexpectedly during documentation-only update')
        changed=[rel for rel,_,_,_ in changes]
        command(['git','add','-A','--']+changed,source)
        staged=command(['git','diff','--cached','--name-only','--no-renames'],source).stdout.splitlines()
        if set(staged)!=set(changed):
            raise ValueError('Unexpected staged source path; refuse commit: '+repr(sorted(set(staged)^set(changed))))
        command(['git','commit','-m','docs: structured knowledge base and release validation gates'],source)
        committed=True
    except Exception:
        if not committed:
            restore(changes,source)
            command(['git','reset','--quiet','--']+[rel for rel,_,_,_ in changes],source,required=False)
        (backup/'update-status.json').write_text(json.dumps({'status':'ROLLED_BACK' if not committed else 'COMMITTED_NOT_RELEASED'},indent=2)+'\n',encoding='utf8')
        raise
    # A release tag is a validated snapshot, separate from component identities.
    try:
        from workspace import manager
        result=manager.release('workspace/v0.4.5',source)
    except Exception as exc:
        result={'status':'COMMITTED_NOT_TAGGED','reason':str(exc)}
        (backup/'update-status.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
        raise RuntimeError('Source committed but release tag/backup failed; do not rerun blindly: '+str(exc)) from exc
    status={'status':'UPDATED','workspace_release':result['tag'],
            'git_commit':result['commit'], 'git_bundle':result['git_bundle'],
            'source':str(source),'backup':str(backup),
            'files_added_or_changed_or_moved':len(changes),
            'component_versions_changed':['workspace_governance (new 0.1.0)'],
            'existing_compiled_component_versions_unchanged':True,
            'compiled_binaries_rebuilt':0,'existing_ctest_suite':'PASSED',
            'new_governance_unit_tests':'PASSED',
            'protected_historical_files':642,
            'git_clean':command(['git','status','--porcelain','--untracked-files=all'],source).stdout.strip()==''}
    (backup/'update-status.json').write_text(json.dumps(status,indent=2)+'\n',encoding='utf8')
    return status


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--source',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        print(json.dumps(apply(args.package,args.source),indent=2,sort_keys=True),flush=True)
        return 0
    except Exception as exc:
        print(json.dumps({'status':'ERROR','reason':str(exc)},indent=2),file=sys.stderr,flush=True)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
