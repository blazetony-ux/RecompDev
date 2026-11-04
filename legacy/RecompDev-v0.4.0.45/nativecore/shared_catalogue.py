"""Persistent RecompDev SQLite catalogue location and one-time bootstrap.

Software releases live beside RecompDev-Data, NOT inside it.  Never rename,
delete, or automatically overwrite existing working catalogues.  The initial
snapshot uses the SQLite online backup API and leaves its source untouched.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from tools.import_previous_catalogue import _check_database, import_best

def shared_path(root: Path, explicit=None) -> Path:
    """Resolve one catalogue across versioned software releases.

    Explicit --db/--Database overrides environment overrides.  The data-dir
    override is useful for installations outside the default C:\\Projects.
    """
    root=Path(root).resolve()
    if explicit:
        return Path(explicit).expanduser().resolve()
    path=os.environ.get('RECOMPDEV_CATALOGUE')
    if path:
        return Path(path).expanduser().resolve()
    folder=os.environ.get('RECOMPDEV_DATA_DIR')
    return ((Path(folder).expanduser() if folder else root.parent/'RecompDev-Data')/'catalogue.sqlite').resolve()

def validate(path: Path) -> None:
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True, timeout=10)) as con:
        _check_database(con)

def _version(path: Path):
    match=re.search(r'RecompDev-v(\d+(?:\.\d+)*)',str(path))
    return tuple(map(int,match.group(1).split('.'))) if match else (0,)

def legacy_sources(root: Path, destination: Path) -> list[Path]:
    root=Path(root).resolve();destination=Path(destination).resolve()
    # Highest version first for tie breaks; importer still prioritizes the
    # richest independently verified evidence.  The bundled seed is LAST.
    versions=sorted(root.parent.glob('RecompDev-v*'),key=_version,reverse=True)
    candidates=[]
    for release in versions:
        if not release.is_dir(): continue
        candidates+=sorted(release.glob('catalogue.v*-working.sqlite'),reverse=True)
    candidates.append(root/'catalogue.sqlite')
    return [p for p in dict.fromkeys(p.resolve() for p in candidates) if p!=destination and p.is_file()]

def ensure_shared_catalogue(root: Path, explicit=None) -> dict:
    """Validate existing central DB, or snapshot a valid legacy DB ONCE.

    Protect concurrent first boots with an exclusive lock file.  On failure
    legacy catalogues and incomplete destinations are never removed.
    """
    root=Path(root).resolve();destination=shared_path(root,explicit)
    if destination.is_file() and not (destination.parent/'.catalogue-bootstrap.lock').exists():
        validate(destination)
        return {'status':'REUSED_SHARED_CATALOGUE','destination':str(destination)}
    destination.parent.mkdir(parents=True,exist_ok=True)
    lock=destination.parent/'.catalogue-bootstrap.lock'
    acquired=False
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        try:
            fd=os.open(str(lock),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,'w',encoding='utf-8') as file:
                file.write(str(os.getpid())+'\n')
            acquired=True
            break
        except FileExistsError:
            # Don't read a half-written destination while the first bootstrap
            # still holds the lock. Wait for a complete SQLite backup.
            time.sleep(0.1)
    if not acquired:
        raise RuntimeError('Shared catalogue bootstrap is locked: '+str(lock)+'. Close other initializers; inspect the lock before removing it.')
    try:
        if destination.is_file():
            validate(destination)
            return {'status':'REUSED_SHARED_CATALOGUE','destination':str(destination)}
        sources=legacy_sources(root,destination)
        if not sources:
            raise RuntimeError('No valid local seed or legacy catalogue found; never create an empty replacement.')
        stamp=destination.parent/'catalogue-bootstrap.json'
        result=import_best(sources,destination,stamp)
        validate(destination)
        result['catalogue_mode']='ONE_SHARED_PERSISTENT_DATABASE'
        result['legacy_sources_preserved']=True
        result['candidate_count']=len(sources)
        # Non-authoritative diagnostic metadata only; does not mutate DB.
        history=destination.parent/'catalogue-sources-reviewed.json'
        history.write_text(json.dumps({'selected':result.get('source'),'candidates':[str(p) for p in sources]},indent=2)+'\n',encoding='utf-8')
        return result
    finally:
        lock.unlink(missing_ok=True)
