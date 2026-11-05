"""Read-only authenticated source-scoped view of historical discovery tasks.

Never schedules tasks, opens owner DB writable, or accepts title/name matching.
"""
from __future__ import annotations
from pathlib import Path
from contextlib import closing
import sqlite3
import sys

ID = 'legacy.catalogue.readonly.v1'


def inspect(source: Path, catalogue: Path, legacy_root: Path) -> dict:
    if str(legacy_root) not in sys.path:
        sys.path.insert(0, str(legacy_root))
    from discovery.engine import identity
    source_id, kind = identity(source)
    result = {'provider': ID, 'source_id': source_id, 'hash_kind': kind,
              'is_complete_source_hash': kind == 'SHA256_COMPLETE',
              'matching_source_record': False, 'task_status': {}, 'outstanding': [],
              'evidence_provenance': 'EXISTING_CATALOGUE_NOT_NEW_ANALYSIS'}
    path = Path(catalogue).resolve(strict=True)
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        table_names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {'discovery_sources','discovery_tasks','discovery_assets','discovery_disc_files'}
        if not required.issubset(table_names):
            result['catalogue_status'] = 'NO_DISCOVERY_SCHEMA'
            return result
        row = db.execute('SELECT source_id,bytes,source_hash_kind,system,detected_by FROM discovery_sources WHERE source_id=?', (source_id,)).fetchone()
        if row is None:
            result['catalogue_status'] = 'NO_MATCH_FOR_SOURCE_FINGERPRINT'
            return result
        if row['bytes'] != source.stat().st_size or row['source_hash_kind'] != kind:
            result['catalogue_status'] = 'SOURCE_RECORD_MISMATCH'
            return result
        result.update({'matching_source_record': True, 'catalogue_status': 'HASH_MATCHED',
                       'recorded_system': row['system'], 'recorded_detection': row['detected_by']})
        result['task_status'] = {status: count for status, count in db.execute(
            'SELECT status, COUNT(*) FROM discovery_tasks WHERE source_id=? GROUP BY status', (source_id,))}
        outstanding = db.execute('''SELECT kind,subject,priority,status,reason FROM discovery_tasks
             WHERE source_id=? AND status NOT IN ('DONE','SUPERSEDED')
             ORDER BY priority DESC,task_id LIMIT 40''', (source_id,)).fetchall()
        result['outstanding'] = [dict(r) for r in outstanding]
        result['outstanding_total'] = db.execute('''SELECT COUNT(*) FROM discovery_tasks
             WHERE source_id=? AND status NOT IN ('DONE','SUPERSEDED')''',(source_id,)).fetchone()[0]
        result['assets'] = {confidence: count for confidence, count in db.execute(
            'SELECT confidence,COUNT(*) FROM discovery_assets WHERE source_id=? GROUP BY confidence', (source_id,))}
        result['inventoried_disc_files'] = db.execute(
            'SELECT COUNT(*) FROM discovery_disc_files WHERE source_id=?', (source_id,)).fetchone()[0]
    return result


def run(context: dict) -> dict:
    return inspect(Path(context['source']), Path(context['catalogue']), Path(context['legacy_root']))
