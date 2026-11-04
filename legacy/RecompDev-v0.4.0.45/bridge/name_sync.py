"""SHA-matched automatic target naming from owner-local source files.

Dry run by default; verified SQLite backup before any explicit --apply action.
"""
from pathlib import Path
import sqlite3
from datetime import datetime, timezone
from adapters.identity import identify

ALLOWED={'.md','.gen','.bin','.psx','.exe','.elf','.xex','.con','.stfs','.live','.pirs','.sfo'}
EXTENDED={'.iso','.img'}

def scan_names(db_path:str, source_root:str, *, apply=False, include_discs=False):
    db=Path(db_path)
    root=Path(source_root)
    if not db.is_file():raise ValueError('catalogue not found')
    if not root.is_dir():raise ValueError('sources root not found')
    files=(f for f in root.rglob('*') if f.is_file() and f.suffix.lower() in (ALLOWED | EXTENDED if include_discs else ALLOWED))
    files=sorted(files)[:500]
    con=sqlite3.connect(db);con.row_factory=sqlite3.Row
    errors=[];findings=[];snapshot=None
    try:
        rows=con.execute('SELECT target_id,source_sha256 FROM targets').fetchall()
        by_sha={r['source_sha256']:r['target_id'] for r in rows}
        has_names=bool(con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='target_names'").fetchone())
        if not has_names:
            if apply: raise ValueError('target_names table missing: install Workbench naming update before applying')
            return {'status':'not_applicable','reason':'WorkBench target_names schema missing'}
        for f in files:
            try:
                evidence=identify(str(f));tid=by_sha.get(evidence['source_sha256'])
                if not tid:continue
                record=evidence['identity'];label=record.get('display_name')
                if not label:continue
                existing=con.execute('SELECT display_name,name_source FROM target_names WHERE target_id=?',(tid,)).fetchone()
                is_high=record.get('name_source')=='rom_header'
                proposed_source='megadrive_header' if is_high else 'evidence_folder'
                # Never overwrite a user alias, a header title, or a specific existing name.
                accepted= not existing or (existing['name_source'] in ('evidence_folder','local_filename') and (existing['display_name'].lower() in ('boot','game','unknown') or is_high))
                findings.append({'target_id':tid,'name':label,'evidence':record['name_source'],'proposed_db_source':proposed_source,
                                 'file':str(f),'sha256_match':True,'current_name':existing['display_name'] if existing else None,'eligible':accepted})
            except (OSError,ValueError,UnicodeError) as exc:
                errors.append({'file':str(f),'error':str(exc)})
        if apply:
            snapshot=db.with_name(db.name+'.pre-v03-names-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.bak')
            # SQLite online backup works even if a browser has a read-only connection open.
            dest=sqlite3.connect(snapshot)
            try:con.backup(dest)
            finally:dest.close()
            try:
                with con:
                    for item in findings:
                        if item['eligible']:
                            con.execute('''INSERT INTO target_names(target_id,display_name,name_source,evidence_sha256)
                              VALUES(?,?,?,?) ON CONFLICT(target_id) DO UPDATE SET
                              display_name=excluded.display_name,name_source=excluded.name_source,evidence_sha256=excluded.evidence_sha256''',
                              (item['target_id'],item['name'],item['proposed_db_source'], next(r['source_sha256'] for r in rows if r['target_id']==item['target_id'])))
            except Exception:
                con.rollback();raise
        return {'status':'applied' if apply else 'preview','scanned_files':len(files),'sha_matched_names':findings,'errors':errors,
                'backup':str(snapshot) if snapshot else None}
    finally:con.close()
