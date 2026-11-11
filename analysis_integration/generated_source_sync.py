#!/usr/bin/env python3
"""Hardware-independent Git preservation of verified, generated native source.

The existing game-specific Git commits remain authoritative.  `git subtree`
imports those *commits*, unsquashed, beneath generated/roms/<full SHA256> on
one shared main branch.  A provenance pointer makes restoration of the exact
original game-specific Git history possible, not merely a copy of C++ files.

No ROM bytes or native binary cache are uploaded. GitHub/network failure is
never a guest-execution failure: durable pending markers survive until retry.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import time
import threading

SCHEMA = 'recompdev.generated-source-sync.v1'
# v29: periodic automatic retry remains independent of guest execution timing.
RETRY_DELAYS = (10, 30, 60, 120, 300)
PROVENANCE = 'recompdev.generated-source-provenance.v1'
SHA256 = re.compile(r'^[a-f0-9]{64}$')
COMMIT = re.compile(r'^[a-f0-9]{40,64}$')
SOURCE_TOP = {'m', 'consolidated', 'exports', 'frontiers'}
SOURCE_ROOT = {'README.md', 'compatibility.json'}
MAX_TRACKED = 20000
MAX_SIZE = 16 * 1024 * 1024
GIT_TIMEOUT = 25


class SyncError(RuntimeError):
    pass


def run(repo: Path, *args: str, timeout: int = GIT_TIMEOUT, check: bool = True) -> str:
    command = ['git', '-C', str(repo), *args]
    # No password/UI prompts from a live game's background Git worker.
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never')
    try:
        proc = subprocess.run(command, env=env, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, encoding='utf-8', errors='replace', timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SyncError('GIT_PROCESS_UNAVAILABLE: ' + str(exc)[:150]) from exc
    if check and proc.returncode:
        raise SyncError('GIT_FAILED: ' + ' '.join(args[:4]) + ': ' + proc.stderr[-450:])
    return proc.stdout.strip() if not check or proc.returncode == 0 else ''


def code(repo: Path, *args: str) -> int:
    proc = subprocess.run(['git', '-C', str(repo), *args],
                          env=dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never'),
                          stdin=subprocess.DEVNULL,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          timeout=GIT_TIMEOUT, check=False)
    return proc.returncode


def home_default() -> Path:
    if os.environ.get('RECOMPDEV_HOME'):
        return Path(os.environ['RECOMPDEV_HOME']).expanduser().resolve()
    if os.name == 'nt':
        return (Path(os.environ['LOCALAPPDATA']) / 'RecompDev').resolve()
    return Path(os.getenv('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'recompdev'


def hash_file(file: Path) -> str:
    digest = hashlib.sha256()
    with file.open('rb') as fd:
        for chunk in iter(lambda: fd.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def config_path(home: Path) -> Path:
    return home / 'generated-source-sync.json'


def settings(home: Path) -> Path | None:
    p = config_path(home)
    if not p.is_file():
        return None
    if p.is_symlink() or p.stat().st_size > 8192:
        raise SyncError('SYNC_SETTINGS_UNSAFE')
    doc = json.loads(p.read_text(encoding='utf-8'))
    if doc.get('schema') != SCHEMA or doc.get('enabled') is not True or not isinstance(doc.get('repository'), str):
        raise SyncError('SYNC_SETTINGS_INVALID')
    repo = Path(doc['repository']).resolve(strict=True)
    if not (repo / '.git').is_dir():
        raise SyncError('SYNC_SHARED_REPOSITORY_MISSING')
    return repo


def setup(home: Path, repository: Path) -> Path:
    repository = repository.resolve(strict=True)
    if not (repository / '.git').is_dir():
        raise SyncError('SYNC_REPOSITORY_MUST_BE_CLONED')
    if run(repository, 'branch', '--show-current') != 'main':
        raise SyncError('SYNC_REPOSITORY_MUST_BE_ON_MAIN')
    if not run(repository, 'remote', 'get-url', 'origin'):
        raise SyncError('SYNC_REPOSITORY_ORIGIN_MISSING')
    if run(repository, 'status', '--porcelain', '--untracked-files=all'):
        raise SyncError('SYNC_SHARED_REPOSITORY_DIRTY')
    home.mkdir(parents=True, exist_ok=True)
    p = config_path(home)
    doc = {'schema': SCHEMA, 'enabled': True, 'repository': str(repository)}
    payload = (json.dumps(doc, indent=2, sort_keys=True) + '\n').encode('utf-8')
    if p.exists():
        if p.is_symlink() or settings(home) != repository:
            raise SyncError('SYNC_SETTINGS_CONFLICT')
        return p
    tmp = p.with_name(p.name + '.pending-' + str(os.getpid()))
    try:
        with tmp.open('xb') as fd:
            fd.write(payload)
            fd.flush()
            os.fsync(fd.fileno())
        os.replace(tmp, p)
    finally:
        tmp.unlink(missing_ok=True)
    return p


class CrossProcessLock:
    """Prevent concurrent publisher/installer modifications to shared Git."""
    def __init__(self, home: Path):
        self.path = home / 'gsync' / 'operations.lock'
        self.fd = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise SyncError('SYNC_LOCK_UNSAFE')
        self.fd = self.path.open('a+b')
        self.fd.seek(0, 2)
        if not self.fd.tell():
            self.fd.write(b'0')
            self.fd.flush()
        self.fd.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.fd.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError) as exc:
            self.fd.close()
            self.fd = None
            raise SyncError('SYNC_OPERATION_ALREADY_IN_PROGRESS') from exc
        return self

    def __exit__(self, *_):
        if self.fd is not None:
            self.fd.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.fd.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.fd.fileno(), fcntl.LOCK_UN)
            self.fd.close()


def safe_path(relative: str) -> bool:
    if not relative or '\\' in relative or any(c in relative for c in ('\n','\r','\x00')):
        return False
    pure = PurePosixPath(relative)
    parts = relative.split('/')
    if pure.is_absolute() or any(p in ('', '.', '..') or p.startswith('.') for p in parts):
        return False
    if len(parts) == 1:
        return parts[0] in SOURCE_ROOT
    if parts[0] not in SOURCE_TOP:
        return False
    if parts[0] in ('m', 'consolidated'):
        return len(parts) >= 3 and bool(SHA256.fullmatch(parts[1])) and (parts[-1].endswith(('.cpp','.json','.txt')) or
                                (parts[0] == 'consolidated' and parts[-1] == 'CMakeLists.txt'))
    return len(parts) == 2 and bool(re.fullmatch(r'[a-f0-9]{64}\.json', parts[1]))


def check_game_source(source: Path, sha: str) -> tuple[str, int]:
    if not SHA256.fullmatch(sha) or source.is_symlink() or not (source / '.git').exists():
        raise SyncError('SYNC_SOURCE_IDENTITY_INVALID')
    if run(source, 'status', '--porcelain', '--untracked-files=all'):
        raise SyncError('SYNC_GAME_SOURCE_UNCOMMITTED')
    names = run(source, 'ls-files', '-z').split('\x00')
    if names and not names[-1]:
        names.pop()
    if not names or len(names) > MAX_TRACKED:
        raise SyncError('SYNC_SOURCE_FILE_COUNT_INVALID')
    for rel in names:
        if not safe_path(rel):
            raise SyncError('SYNC_SOURCE_PATH_REJECTED: ' + rel[:100])
        item = source / rel
        if item.is_symlink() or not item.is_file() or item.stat().st_size > MAX_SIZE:
            raise SyncError('SYNC_SOURCE_FILE_UNSAFE: ' + rel[:100])
    compatibility = source / 'compatibility.json'
    if not compatibility.is_file() or json.loads(compatibility.read_text(encoding='utf-8')).get('rom_sha256') != sha:
        raise SyncError('SYNC_SOURCE_ROM_IDENTITY_MISMATCH')
    commit = run(source, 'rev-parse', 'HEAD')
    if not COMMIT.fullmatch(commit):
        raise SyncError('SYNC_SOURCE_COMMIT_INVALID')
    return commit, len(names)


def pending_path(home: Path, sha: str) -> Path:
    if not SHA256.fullmatch(sha):
        raise SyncError('SYNC_ROM_SHA_INVALID')
    return home / 'gsync' / 'pending' / (sha + '.json')


def mark_pending(home: Path, sha: str, commit: str) -> None:
    if not COMMIT.fullmatch(commit):
        raise SyncError('SYNC_COMMIT_INVALID')
    p = pending_path(home, sha)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps({'rom_sha256': sha, 'source_commit': commit}, sort_keys=True) + '\n')
    tmp = p.with_name(p.name + '.pending-' + str(os.getpid()) + '-' + str(threading.get_ident()))
    try:
        with tmp.open('x', encoding='utf-8') as fd:
            fd.write(data)
            fd.flush()
            os.fsync(fd.fileno())
        os.replace(tmp, p)
    finally:
        tmp.unlink(missing_ok=True)


def clear_pending(home: Path, sha: str, commit: str) -> None:
    p = pending_path(home, sha)
    if p.exists():
        doc = json.loads(p.read_text(encoding='utf-8'))
        if doc.get('source_commit') == commit:
            p.unlink()


def pending_items(home: Path) -> dict[str, str]:
    """Validate durable queue entries; never silently discard corrupted work."""
    folder = home / 'gsync' / 'pending'
    if folder.is_symlink():
        raise SyncError('SYNC_PENDING_DIRECTORY_UNSAFE')
    if not folder.exists():
        return {}
    if not folder.is_dir():
        raise SyncError('SYNC_PENDING_DIRECTORY_INVALID')
    result: dict[str, str] = {}
    for path in sorted(folder.iterdir()):
        if (path.is_symlink() or not path.is_file() or
                not path.name.endswith('.json') or path.stat().st_size > 4096):
            raise SyncError('SYNC_PENDING_ENTRY_UNSAFE')
        sha = path.name[:-5]
        if not SHA256.fullmatch(sha):
            raise SyncError('SYNC_PENDING_IDENTITY_INVALID')
        doc = json.loads(path.read_text(encoding='utf-8'))
        if (doc.get('rom_sha256') != sha or not isinstance(doc.get('source_commit'), str) or
                not COMMIT.fullmatch(doc['source_commit'])):
            raise SyncError('SYNC_PENDING_RECORD_INVALID')
        result[sha] = doc['source_commit']
    return result


def retry_pending(home: Path, *, repository: Path | None = None) -> dict:
    """Retry only when durable work exists. An outage is never reported as success."""
    items = pending_items(home)
    if not items:
        return {'status': 'UP_TO_DATE', 'pending': 0}
    # Reuse unsquashed subtree publication and all the original Git protections;
    # it coalesces multiple games into one shared main push.
    result = publish(home, repository=repository)
    remaining = pending_items(home)
    if remaining:
        raise SyncError('SYNC_RETRY_INCOMPLETE: ' + str(len(remaining)) + ' pending')
    return dict(result, pending=0, retried=len(items))


def _check_shared(repo: Path) -> None:
    if repo.is_symlink() or not (repo / '.git').is_dir():
        raise SyncError('SYNC_SHARED_REPO_UNSAFE')
    if run(repo, 'branch', '--show-current') != 'main':
        raise SyncError('SYNC_SHARED_NOT_ON_MAIN')
    if run(repo, 'status', '--porcelain', '--untracked-files=all'):
        raise SyncError('SYNC_SHARED_REPO_DIRTY')


def _integrate_remote(repo: Path, *, allow_offline: bool) -> bool:
    try:
        run(repo, 'fetch', '--no-tags', 'origin', 'main')
    except SyncError:
        if allow_offline:
            return False
        raise
    remote_head = run(repo, 'rev-parse', 'FETCH_HEAD')
    head = run(repo, 'rev-parse', 'HEAD')
    if head != remote_head:
        if code(repo, 'merge-base', '--is-ancestor', head, remote_head) == 0:
            run(repo, 'merge', '--ff-only', remote_head)
        elif code(repo, 'merge-base', '--is-ancestor', remote_head, head) == 0:
            pass  # Local queued commits have not yet reached remote.
        else:
            # No destructive reset/rebase: ordinary merge only for independent paths.
            try:
                run(repo, '-c', 'user.name=RecompDev Generated Source',
                    '-c', 'user.email=recompdev-generated@local.invalid',
                    'merge', '--no-edit', '-m', 'Integrate published generated source', remote_head)
            except SyncError:
                if (repo / '.git' / 'MERGE_HEAD').exists():
                    run(repo, 'merge', '--abort')
                raise SyncError('SYNC_REMOTE_DIVERGENCE_NEEDS_REVIEW')
    return True


def _commit(repo: Path, message: str) -> None:
    if code(repo, 'diff', '--cached', '--quiet') != 0:
        run(repo, '-c', 'user.name=RecompDev Generated Source',
            '-c', 'user.email=recompdev-generated@local.invalid', 'commit', '-m', message)


def _verify_source_tree(repo: Path, sha: str, commit: str) -> None:
    prefix = 'generated/roms/' + sha
    tree_from_shared = run(repo, 'rev-parse', 'HEAD:' + prefix)
    tree_from_game = run(repo, 'rev-parse', commit + '^{tree}')
    if tree_from_shared != tree_from_game:
        raise SyncError('SYNC_SUBTREE_SOURCE_TREE_MISMATCH')
    if code(repo, 'merge-base', '--is-ancestor', commit, 'HEAD'):
        raise SyncError('SYNC_SOURCE_COMMIT_NOT_IN_SHARED_HISTORY')


def _import_one(repo: Path, home: Path, sha: str) -> tuple[str, int]:
    game = home / 'gs' / sha
    commit, count = check_game_source(game, sha)
    prefix = 'generated/roms/' + sha
    # Compare the original game commits, not merely copied .cpp files. `subtree`
    # preserves the exact Git commit graph and its provenance for later reinstall.
    if code(repo, 'merge-base', '--is-ancestor', commit, 'HEAD') == 0:
        pass
    elif (repo / prefix).exists():
        run(repo, '-c', 'user.name=RecompDev Generated Source',
            '-c', 'user.email=recompdev-generated@local.invalid',
            'subtree', 'pull', '--prefix=' + prefix, str(game), 'HEAD',
            '-m', 'Update generated source history for ' + sha[:12], timeout=90)
    else:
        run(repo, '-c', 'user.name=RecompDev Generated Source',
            '-c', 'user.email=recompdev-generated@local.invalid',
            'subtree', 'add', '--prefix=' + prefix, str(game), 'HEAD',
            '-m', 'Import generated source history for ' + sha[:12], timeout=90)
    # Verify all imported bytes correspond exactly to the source commit tree.
    _verify_source_tree(repo, sha, commit)
    provenance = repo / 'generated' / 'provenance' / (sha + '.json')
    provenance.parent.mkdir(parents=True, exist_ok=True)
    doc = {'schema': PROVENANCE, 'rom_sha256': sha, 'source_commit': commit,
           'source_tree': run(repo, 'rev-parse', commit + '^{tree}'),
           'tracked_files': count}
    # The provenance lives OUTSIDE the git-subtree prefix to keep pulls clean.
    provenance.write_text(json.dumps(doc, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    run(repo, 'add', '--', 'generated/provenance/' + sha + '.json')
    _commit(repo, 'Record generated-source provenance ' + sha[:12])
    return commit, count


def publish(home: Path, rom_sha: str | None = None, *, repository: Path | None = None) -> dict:
    repo = repository or settings(home)
    if repo is None:
        return {'status': 'DISABLED_NO_REPOSITORY_CONFIGURED'}
    repo = repo.resolve(strict=True)
    if rom_sha is not None and not SHA256.fullmatch(rom_sha):
        raise SyncError('SYNC_ROM_SHA_INVALID')
    with CrossProcessLock(home):
        _check_shared(repo)
        remote_online = _integrate_remote(repo, allow_offline=True)
        games = ([rom_sha] if rom_sha else sorted(p.name for p in (home / 'gs').iterdir()
                 if p.is_dir() and SHA256.fullmatch(p.name))) if (home / 'gs').is_dir() else []
        imported = {}
        for sha in games:
            game = home / 'gs' / sha
            if not game.is_dir():
                raise SyncError('SYNC_GAME_SOURCE_MISSING: ' + sha[:12])
            imported[sha], _ = _import_one(repo, home, sha)
        _check_shared(repo)
        if not remote_online:
            raise SyncError('SYNC_REMOTE_UNAVAILABLE_LOCAL_COMMITS_PRESERVED')
        # Only normal fast-forward pushes. Never force-push, delete refs or create
        # one branch per game. A rejected push remains queued for next retry.
        run(repo, 'push', 'origin', 'HEAD:refs/heads/main', timeout=40)
        remote_line = run(repo, 'ls-remote', 'origin', 'refs/heads/main')
        if not remote_line or remote_line.split()[0] != run(repo, 'rev-parse', 'HEAD'):
            raise SyncError('SYNC_REMOTE_MAIN_VERIFICATION_FAILED')
        for sha, commit in imported.items():
            if run(home / 'gs' / sha, 'rev-parse', 'HEAD') == commit:
                clear_pending(home, sha, commit)
        return {'status': 'PUBLISHED', 'roms': len(imported), 'main_commit': run(repo, 'rev-parse', 'HEAD')}


def _reconcile_append_only_provenance(repo: Path, sha: str) -> bool:
    """Recover an append-only shared subtree checkpoint without destroying history.

    A live consolidation can commit generated C++ directly under the shared
    prefix without advancing the per-ROM provenance pointer.  Recreate the
    subtree's original-shaped history via `subtree split` and merge that commit
    as a *parent* of shared main.  A pointer update alone is forbidden because
    the source commit must remain reachable and its tree must equal the prefix.

    Only safe appended source files are accepted. Modifications, deletions,
    incompatible histories, or untrusted paths require manual review.
    """
    pointer = repo / 'generated' / 'provenance' / (sha + '.json')
    if pointer.is_symlink() or not pointer.is_file() or pointer.stat().st_size > 8192:
        raise SyncError('SYNC_PROVENANCE_MISSING_OR_UNSAFE')
    doc = json.loads(pointer.read_text(encoding='utf-8'))
    old = doc.get('source_commit')
    if (doc.get('schema') != PROVENANCE or doc.get('rom_sha256') != sha or
            not isinstance(old, str) or not COMMIT.fullmatch(old) or
            doc.get('source_tree') != run(repo, 'rev-parse', old + '^{tree}')):
        raise SyncError('SYNC_PROVENANCE_INVALID')
    prefix = 'generated/roms/' + sha
    current_tree = run(repo, 'rev-parse', 'HEAD:' + prefix)
    if current_tree == doc['source_tree']:
        return False
    if code(repo, 'merge-base', '--is-ancestor', old, 'HEAD') != 0:
        raise SyncError('SYNC_PROVENANCE_OLD_COMMIT_UNREACHABLE')
    # Fail closed on changed/deleted existing files or unsafe additions.
    changes = run(repo, 'diff-tree', '--no-commit-id', '--name-status', '-r',
                  doc['source_tree'], current_tree)
    added = []
    for line in changes.splitlines():
        columns = line.split('\t')
        if len(columns) != 2 or columns[0] != 'A' or not safe_path(columns[1]):
            raise SyncError('SYNC_RECONCILE_NON_APPEND_ONLY')
        added.append(columns[1])
    if not added:
        raise SyncError('SYNC_RECONCILE_EMPTY_DIFFERENCE')
    files = run(repo, 'ls-tree', '-r', '--name-only', 'HEAD:' + prefix).splitlines()
    if len(files) > MAX_TRACKED or not files or any(not safe_path(name) for name in files):
        raise SyncError('SYNC_RECONCILE_SOURCE_PATH_UNSAFE')
    for name in added:
        blob_bytes = int(run(repo, 'cat-file', '-s', 'HEAD:' + prefix + '/' + name))
        if blob_bytes > MAX_SIZE:
            raise SyncError('SYNC_RECONCILE_SOURCE_FILE_OVERSIZE')
    # Every source-history commit remains reachable; never rewrite either side.
    split = run(repo, 'subtree', 'split', '--prefix=' + prefix, 'HEAD', timeout=180).splitlines()[-1]
    if not COMMIT.fullmatch(split) or run(repo, 'rev-parse', split + '^{tree}') != current_tree:
        raise SyncError('SYNC_RECONCILE_SPLIT_TREE_INVALID')
    if code(repo, 'merge-base', '--is-ancestor', old, split) != 0:
        raise SyncError('SYNC_RECONCILE_ORIGINAL_HISTORY_NOT_PRESERVED')
    if code(repo, 'merge-base', '--is-ancestor', split, 'HEAD') != 0:
        run(repo, '-c', 'user.name=RecompDev Generated Source',
            '-c', 'user.email=recompdev-generated@local.invalid',
            'merge', '-s', 'ours', '--no-ff', '--no-edit', '-m',
            'Preserve incremental generated source ancestry ' + sha[:12], split)
    _verify_source_tree(repo, sha, split)
    updated = {'schema': PROVENANCE, 'rom_sha256': sha,
               'source_commit': split, 'source_tree': current_tree,
               'tracked_files': len(files)}
    pointer.write_text(json.dumps(updated, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    run(repo, 'add', '--', 'generated/provenance/' + sha + '.json')
    _commit(repo, 'Reconcile append-only generated-source provenance ' + sha[:12])
    return True


def _provenance(repo: Path, sha: str) -> str:
    if not SHA256.fullmatch(sha):
        raise SyncError('SYNC_ROM_SHA_INVALID')
    file = repo / 'generated' / 'provenance' / (sha + '.json')
    if file.is_symlink() or not file.is_file() or file.stat().st_size > 8192:
        raise SyncError('SYNC_PROVENANCE_MISSING_OR_UNSAFE')
    doc = json.loads(file.read_text(encoding='utf-8'))
    commit = doc.get('source_commit')
    if (doc.get('schema') != PROVENANCE or doc.get('rom_sha256') != sha or
            not isinstance(commit, str) or not COMMIT.fullmatch(commit) or
            doc.get('source_tree') != run(repo, 'rev-parse', commit + '^{tree}')):
        raise SyncError('SYNC_PROVENANCE_INVALID')
    _verify_source_tree(repo, sha, commit)
    return commit


def restore_all(home: Path, *, repository: Path | None = None) -> dict:
    repo = repository or settings(home)
    if repo is None:
        return {'status': 'DISABLED_NO_REPOSITORY_CONFIGURED', 'restored': 0}
    repo = repo.resolve(strict=True)
    with CrossProcessLock(home):
        _check_shared(repo)
        online = _integrate_remote(repo, allow_offline=True)
        folder = repo / 'generated' / 'provenance'
        subtree_root = repo / 'generated' / 'roms'
        # One-time migration from the owner's pre-v28 manually imported
        # UNSQUASHED subtrees.  `subtree split` recovers the original game HEAD
        # if its exact source commit is reachable in the shared history.
        # Reject synthetic/diverged trees rather than claiming exact restore.
        sources = set()
        if folder.is_dir():
            sources.update(p.stem for p in folder.glob('*.json'))
        if subtree_root.is_dir():
            sources.update(p.name for p in subtree_root.iterdir() if p.is_dir())
        restored = 0
        already = 0
        ahead = 0
        inferred = 0
        reconciled = 0
        for sha in sorted(sources):
            if not SHA256.fullmatch(sha):
                raise SyncError('SYNC_REMOTE_ROM_DIRECTORY_INVALID')
            pointer = folder / (sha + '.json')
            if pointer.exists():
                repaired = _reconcile_append_only_provenance(repo, sha)
                commit = _provenance(repo, sha)
                if repaired:
                    reconciled += 1
                    # Preserve a durable publication request for the newly linked
                    # source-history commit, including if the process exits now.
                    mark_pending(home, sha, commit)
            else:
                commit = run(repo, 'subtree', 'split', '--prefix=generated/roms/' + sha,
                             'HEAD', timeout=90).splitlines()[-1]
                if not COMMIT.fullmatch(commit):
                    raise SyncError('SYNC_LEGACY_SUBTREE_SPLIT_INVALID')
                _verify_source_tree(repo, sha, commit)
                inferred += 1
            destination = home / 'gs' / sha
            if destination.is_symlink():
                raise SyncError('SYNC_LOCAL_SOURCE_SYMLINK_UNSAFE')
            if destination.exists() and not (destination / '.git').is_dir():
                raise SyncError('SYNC_LOCAL_SOURCE_UNVERSIONED_CONFLICT')
            if destination.exists():
                if run(destination, 'status', '--porcelain', '--untracked-files=all'):
                    raise SyncError('SYNC_LOCAL_SOURCE_DIRTY: ' + sha[:12])
                current = run(destination, 'rev-parse', 'HEAD')
                if current == commit:
                    already += 1
                    continue
                # Check ancestry in the *per-game* repo, not shared main:
                # a newly discovered local commit may not have been uploaded
                # yet and therefore is unknown to the shared object database.
                run(destination, 'fetch', '--no-tags', str(repo), commit, timeout=90)
                if code(destination, 'merge-base', '--is-ancestor', commit, current) == 0:
                    ahead += 1
                    mark_pending(home, sha, current)
                    continue
                if code(destination, 'merge-base', '--is-ancestor', current, commit) != 0:
                    raise SyncError('SYNC_LOCAL_AND_REMOTE_HISTORY_DIVERGED: ' + sha[:12])
                run(destination, 'merge', '--ff-only', 'FETCH_HEAD')
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.mkdir(mode=0o700)
                try:
                    run(destination, 'init', '--quiet')
                    run(destination, 'fetch', '--no-tags', str(repo), commit, timeout=90)
                    run(destination, 'checkout', '-b', 'main', 'FETCH_HEAD')
                except Exception:
                    shutil.rmtree(destination)  # only our newly-created directory
                    raise
            if run(destination, 'rev-parse', 'HEAD') != commit:
                raise SyncError('SYNC_RESTORED_COMMIT_MISMATCH')
            check_game_source(destination, sha)
            restored += 1
        return {'status': 'RESTORED' if online else 'RESTORED_FROM_LOCAL_REMOTE_OFFLINE',
                'restored': restored, 'already': already, 'local_ahead': ahead,
                'legacy_subtrees_inferred': inferred, 'reconciled': reconciled,
                'remote_online': online}


class AutoPublisher:
    """Nonblocking guest-independent publisher with bounded offline retries.

    Source Git commits and queue markers are synchronous/durable.  The daemon
    coalesces multiple new modules and retries periodically while the game is
    open; an unfinished upload remains queued on process exit or shutdown.
    """
    def __init__(self, home: Path, retry_delays: tuple[int, ...] = RETRY_DELAYS):
        self.home = home
        self.retry_delays = retry_delays
        try:
            self.enabled = settings(home) is not None
        except (SyncError, OSError, ValueError) as error:
            self.enabled = False
            print('RECOMPDEV_GENERATED_SYNC_WARNING=' + str(error)[:180], flush=True)
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.thread = None
        if self.enabled:
            self.thread = threading.Thread(target=self._worker, name='RecompDevGeneratedSourceSync', daemon=True)
            self.thread.start()
            # v29: recover the last session's pending marker even when this
            # session never discovers another instruction.
            self.wake.set()

    def queued(self, sha: str, commit: str) -> None:
        if not self.enabled:
            return
        mark_pending(self.home, sha, commit)
        self.wake.set()
        print('RECOMPDEV_GENERATED_SYNC=QUEUED', flush=True)

    def _worker(self):
        failures = 0
        delay = None
        while not self.stop.is_set():
            self.wake.wait(timeout=delay)
            self.wake.clear()
            if self.stop.is_set():
                break
            try:
                result = retry_pending(self.home)
                if result['status'] != 'UP_TO_DATE':
                    print('RECOMPDEV_GENERATED_SYNC=' + result['status'], flush=True)
                failures = 0
                delay = None
            except (SyncError, OSError, ValueError, subprocess.TimeoutExpired) as error:
                failures += 1
                delay = self.retry_delays[min(failures - 1, len(self.retry_delays) - 1)]
                print('RECOMPDEV_GENERATED_SYNC=PENDING_RETRY ' + str(error)[:150], flush=True)

    def finish(self):
        if not self.thread:
            return
        # Do not allow a Git operation to hold gameplay shutdown indefinitely.
        self.thread.join(timeout=2)
        try:
            pending = len(pending_items(self.home))
            print('RECOMPDEV_GENERATED_SYNC_FINAL=' + ('PENDING:' + str(pending) if pending else 'UP_TO_DATE'), flush=True)
        except (SyncError, OSError, ValueError) as error:
            print('RECOMPDEV_GENERATED_SYNC_FINAL=CHECK_REQUIRED ' + str(error)[:120], flush=True)
        self.stop.set()
        self.wake.set()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('setup', 'publish', 'restore-all', 'retry-pending', 'status'))
    p.add_argument('--home', type=Path, default=home_default())
    p.add_argument('--repository', type=Path)
    p.add_argument('--rom-sha')
    args = p.parse_args(argv)
    try:
        if args.action == 'setup':
            if args.repository is None:
                raise SyncError('SYNC_REPOSITORY_REQUIRED_FOR_SETUP')
            target = setup(args.home, args.repository)
            result = {'status': 'CONFIGURED', 'settings': str(target)}
        elif args.action == 'publish':
            result = publish(args.home, args.rom_sha, repository=args.repository)
        elif args.action == 'restore-all':
            result = restore_all(args.home, repository=args.repository)
        elif args.action == 'retry-pending':
            result = retry_pending(args.home, repository=args.repository)
        else:
            repo = settings(args.home)
            pending = pending_items(args.home)
            result = {'status': 'CONFIGURED' if repo else 'DISABLED',
                      'repository': str(repo) if repo else None, 'pending': len(pending),
                      'pending_roms': sorted(sha[:12] for sha in pending)}
        print('RECOMPDEV_GENERATED_SOURCE_SYNC=' + json.dumps(result, sort_keys=True), flush=True)
        if result['status'] == 'DISABLED_NO_REPOSITORY_CONFIGURED':
            return 3
        if args.action == 'restore-all' and result.get('remote_online') is False:
            return 2  # local restore happened, but remote freshness is unverified
        return 0
    except (SyncError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print('RECOMPDEV_GENERATED_SOURCE_SYNC=PENDING_RETRY: ' + str(error)[:400], flush=True)
        return 2


if __name__ == '__main__':
    sys.exit(main())
