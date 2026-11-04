"""Persistent, architecture-namespaced *evidence* cache, never an executable-code cache.

Only original, SHA-attested recovery exports are retained; every load reattests
instruction bytes against the current owner-local ROM.  No dynamic CPU emulator,
ROM data or compiler binaries are written here. This SQLite database is separate
from the user's persistent central catalogue and requires no catalogue migration.
"""
from __future__ import annotations
import hashlib
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

MAX_DOCUMENT=32 * 1024 * 1024
MAX_DOCUMENTS=384
MAX_SCAN=3000
SCHEMA=1
LANG_Z80='z80:LE:16:default'

def coverage_path(release_root,explicit=None):
    if explicit:
        return Path(explicit).expanduser().resolve()
    from nativecore.shared_catalogue import shared_path
    return shared_path(Path(release_root)).parent/'verified-coverage-v0443.sqlite'

def _serialized(document):
    data=json.dumps(document,sort_keys=True,separators=(',',':'),ensure_ascii=True)
    if len(data.encode('utf-8'))>MAX_DOCUMENT:raise ValueError('Coverage export exceeds bounded record size')
    return data

def _attest(document,rom,source,target,language):
    if (document.get('source_sha256')!=source or document.get('target_id')!=target
        or document.get('language')!=language or not isinstance(document.get('bank_context'),dict)):
        raise ValueError('Coverage evidence identity, architecture or physical mapping mismatch')
    from nativepilot.generator import verify_export
    instructions,_,_=verify_export(document,rom)
    if not instructions:raise ValueError('Empty source-attested coverage export')
    return instructions

class VerifiedCoverageCache:
    def __init__(self,path,source,target,architecture=LANG_Z80):
        supplied=Path(path).expanduser()
        if supplied.is_symlink():raise ValueError('Coverage cache must not be a symlink')
        self.path=supplied.resolve()
        if (not isinstance(source,str) or len(source)!=64 or not all(c in '0123456789abcdef' for c in source.lower())
            or not isinstance(target,str) or not 0<len(target)<=256 or not architecture):
            raise ValueError('Invalid bounded coverage cache identity')
        self.source=source.lower();self.target=target;self.architecture=architecture
        if self.path.is_symlink() or (self.path.exists() and (not self.path.is_file() or self.path.stat().st_size>1024*1024*1024)):
            raise ValueError('Unsafe or unbounded coverage cache')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(self.path,timeout=20)) as con:
            con.execute('PRAGMA busy_timeout=20000')
            current=con.execute('PRAGMA user_version').fetchone()[0]
            if current not in (0,SCHEMA):raise ValueError('Unsupported coverage cache schema (no automatic migration)')
            con.execute('''CREATE TABLE IF NOT EXISTS verified_overlays (
                source_sha256 TEXT NOT NULL, target_id TEXT NOT NULL, architecture TEXT NOT NULL,
                content_sha256 TEXT NOT NULL, slot INTEGER NOT NULL, bank INTEGER NOT NULL,
                physical_entry INTEGER NOT NULL, document_json TEXT NOT NULL,
                PRIMARY KEY(source_sha256,target_id,architecture,content_sha256))''')
            con.execute('PRAGMA user_version=1')
            con.commit()

    def put(self,document,rom,physical_entry=None):
        physical=_attest(document,rom,self.source,self.target,self.architecture)
        if physical_entry is not None and physical_entry not in physical:
            raise ValueError('Coverage export does not attest its observed entry')
        payload=_serialized(document)
        digest=hashlib.sha256(payload.encode('utf-8')).hexdigest()
        context=document['bank_context']
        entry=physical_entry if physical_entry is not None else min(physical)
        with closing(sqlite3.connect(self.path,timeout=20)) as con:
            con.execute('PRAGMA busy_timeout=20000')
            existing=con.execute('''SELECT count(*),coalesce(sum(length(document_json)),0) FROM verified_overlays
                WHERE source_sha256=? AND target_id=? AND architecture=?''',
                (self.source,self.target,self.architecture)).fetchone()
            if existing[0]>=MAX_DOCUMENTS and not con.execute('''SELECT 1 FROM verified_overlays
                WHERE source_sha256=? AND target_id=? AND architecture=? AND content_sha256=?''',
                (self.source,self.target,self.architecture,digest)).fetchone():
                raise ValueError('Coverage cache per-ROM document limit reached')
            if existing[1]+len(payload)>256*1024*1024 and not con.execute('''SELECT 1 FROM verified_overlays
                WHERE source_sha256=? AND target_id=? AND architecture=? AND content_sha256=?''',
                (self.source,self.target,self.architecture,digest)).fetchone():
                raise ValueError('Coverage cache per-ROM byte limit reached')
            cur=con.execute('''INSERT OR IGNORE INTO verified_overlays
                (source_sha256,target_id,architecture,content_sha256,slot,bank,physical_entry,document_json)
                VALUES (?,?,?,?,?,?,?,?)''',
                (self.source,self.target,self.architecture,digest,context['slot'],context['bank'],entry,payload))
            con.commit()
            return bool(cur.rowcount)

    def load(self,rom,initial=None):
        """All-or-nothing reattestation; corrupted evidence never silently reused."""
        from nativepilot.generator import verify_export
        occupied={}
        if initial is not None:occupied.update(verify_export(initial,rom)[0])
        with closing(sqlite3.connect(self.path,timeout=20)) as con:
            rows=con.execute('''SELECT content_sha256,document_json FROM verified_overlays
                WHERE source_sha256=? AND target_id=? AND architecture=? ORDER BY rowid LIMIT ?''',
                (self.source,self.target,self.architecture,MAX_DOCUMENTS+1)).fetchall()
        if len(rows)>MAX_DOCUMENTS:raise ValueError('Excessive cached coverage entries')
        documents=[];fresh=set()
        for digest,raw in rows:
            if len(raw)>MAX_DOCUMENT:raise ValueError('Oversized cached coverage evidence')
            if hashlib.sha256(raw.encode('utf-8')).hexdigest()!=digest:
                raise ValueError('Cached coverage document digest mismatch')
            doc=json.loads(raw)
            instructions=_attest(doc,rom,self.source,self.target,self.architecture)
            novel=False
            for address,ins in instructions.items():
                prior=occupied.get(address)
                if prior is not None and (prior['bytes_sha256']!=ins['bytes_sha256'] or prior['pcode']!=ins['pcode'] or prior['length']!=ins['length']):
                    raise ValueError('Conflicting cached instruction evidence at physical '+hex(address))
                if prior is None:
                    novel=True;fresh.add(address)
            if novel:
                documents.append(doc)
                occupied.update(instructions)
        return documents,fresh,len(rows)

    def import_history(self,rom,roots,*,max_scan=MAX_SCAN):
        """Ingest original recovery exports from owner evidence, never session reports.

        Hash and target must match. Bounds prevent an unbounded filesystem scan.
        Sources are left intact; no guessing of bank mapping from filenames.
        """
        scan=0;imported=0;rejected=0
        for root in roots:
            root=Path(root).expanduser().resolve()
            if not root.is_dir():continue
            for file in root.rglob('bank-functions.json'):
                scan+=1
                if scan>max_scan:raise ValueError('Historical coverage scan budget exceeded')
                if file.is_symlink() or not file.is_file() or file.stat().st_size>MAX_DOCUMENT:
                    rejected+=1;continue
                try:doc=json.loads(file.read_text(encoding='utf-8'))
                except (ValueError,UnicodeError,OSError):
                    rejected+=1;continue
                # Other ROMs in the campaign are not stale evidence for this ROM.
                if doc.get('source_sha256')!=self.source or doc.get('target_id')!=self.target:continue
                # A mismatched file claiming this ROM's identity is a blocker, not an ignored row.
                if self.put(doc,rom):imported+=1
        return {'files_examined':scan,'matching_exports_imported':imported,'unreadable_files_skipped':rejected}
