"""Create an independent, restartable SQLite working catalogue.

Never rename, overwrite, unlink or mutate a packaged/Workbench catalogue.
Uses SQLite's backup API to safely snapshot databases currently open for reading.
Source choice prefers existing discovery evidence, then conversion history.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import json
import sqlite3
from pathlib import Path

NEEDED = {'targets', 'graph_runs', 'graph_functions'}


def _open_read_only(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True, timeout=10)


def _check_database(con):
    if con.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
        raise ValueError('SQLite integrity_check failed')
    names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not NEEDED <= names:
        raise ValueError('not a RecompDev catalogue')
    return names


def _evidence_score(source):
    with closing(_open_read_only(source)) as con:
        tables = _check_database(con)
        conversions = (con.execute('SELECT COUNT(*) FROM conversion_v031').fetchone()[0]
                       if 'conversion_v031' in tables else 0)
        batches = (con.execute('SELECT COUNT(*) FROM batch_campaigns').fetchone()[0]
                   if 'batch_campaigns' in tables else 0)
        native_prepared = (con.execute('SELECT COUNT(*) FROM native_preparations_v0403').fetchone()[0]
                           if 'native_preparations_v0403' in tables else 0)
        discovered = (con.execute('SELECT COUNT(*) FROM discovery_sources').fetchone()[0]
                      if 'discovery_sources' in tables else 0)
        tasks = (con.execute('SELECT COUNT(*) FROM discovery_tasks').fetchone()[0]
                 if 'discovery_tasks' in tables else 0)
        return (bool(native_prepared), native_prepared, discovered, tasks, conversions, batches)


def import_previous(source, dest, stamp):
    """Backup SOURCE to a *new* DEST, refusing to clobber any existing database."""
    source = Path(source).resolve()
    dest = Path(dest).resolve()
    stamp = Path(stamp).resolve()
    if not source.is_file() or source == dest:
        raise ValueError('source must exist and differ from destination')
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        with closing(_open_read_only(dest)) as existing:
            _check_database(existing)
        return {'status': 'EXISTING_WORKING_DB_REUSED', 'destination': str(dest)}
    # Connect directly to a uniquely named destination. There is deliberately
    # NO os.replace() of a database used by the Workbench or another process.
    try:
        with closing(_open_read_only(source)) as old:
            _check_database(old)
            # SQLite will create a fresh destination. Never pass an existing file.
            with closing(sqlite3.connect(str(dest), timeout=10)) as new:
                old.backup(new, pages=256, sleep=0.05)
                _check_database(new)
                new.execute('PRAGMA journal_mode=WAL')
        stamp.write_text(json.dumps({'status':'SQLITE_BACKUP_NEW_WORKING_DB',
                                      'source':str(source),'destination':str(dest)},indent=2)+'\n',encoding='utf-8')
    except Exception:
        # Leave any incomplete database for forensic inspection rather than
        # deleting files that another process might have opened meanwhile.
        raise
    return {'status': 'SQLITE_BACKUP_NEW_WORKING_DB', 'source': str(source), 'destination': str(dest)}


def import_best(sources, dest, stamp):
    dest = Path(dest).resolve()
    if dest.exists():
        with closing(_open_read_only(dest)) as con:
            _check_database(con)
        return {'status':'EXISTING_WORKING_DB_REUSED','destination':str(dest)}
    available = []
    rejected = []
    for position, source in enumerate(sources):
        p = Path(source).resolve()
        if not p.is_file():
            continue
        try:
            score = _evidence_score(p)
            available.append((score, -position, p))
        except (sqlite3.Error, ValueError, OSError) as exc:
            rejected.append({'source':str(p),'error':type(exc).__name__+': '+str(exc)[:200]})
    # Ties prefer earlier candidates; recovery evidence takes precedence over version age.
    for _, _, candidate in sorted(available, reverse=True):
        try:
            result = import_previous(candidate, dest, stamp)
            result['rejected_previous_sources'] = rejected
            return result
        except (sqlite3.Error, ValueError, OSError) as exc:
            rejected.append({'source':str(candidate),'error':type(exc).__name__+': '+str(exc)[:200]})
    raise ValueError('No accessible, valid catalogue. Inspected: '+json.dumps(rejected))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', action='append', required=True)
    p.add_argument('--destination', required=True)
    p.add_argument('--stamp', required=True)
    a = p.parse_args()
    print(json.dumps(import_best(a.source, a.destination, a.stamp)))
