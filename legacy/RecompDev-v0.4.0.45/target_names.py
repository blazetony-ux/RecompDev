"""Stable target display names with SHA-verified provenance.

The target ID remains immutable. Game titles are only read from known format
metadata, explicitly owner-provided aliases, or labelled file/evidence hints.
"""
import json
import hashlib
import sqlite3
from pathlib import Path

DDL = '''CREATE TABLE IF NOT EXISTS target_names (
 target_id TEXT PRIMARY KEY REFERENCES targets(target_id),
 display_name TEXT NOT NULL,
 name_source TEXT NOT NULL CHECK(name_source IN ('owner_alias','megadrive_header','local_filename','evidence_folder')),
 evidence_sha256 TEXT NOT NULL
)'''
EXTENSIONS = {'.md','.bin','.gen','.smd','.rom','.32x','.psx','.exe','.elf','.iso','.img','.gba','.nes','.z64','.n64','.v64','.cue'}
PRIORITY = {'owner_alias':4,'megadrive_header':3,'local_filename':2,'evidence_folder':1}

def normalize(value, *, filename=False):
    if not isinstance(value,str):raise ValueError('display name must be text')
    if filename:
        value=Path(value).name
        if Path(value).suffix.lower() in EXTENSIONS:value=Path(value).stem
    value=' '.join(value.replace('\x00',' ').split()).strip()
    if not value or len(value)>120:raise ValueError('display name must contain 1-120 characters')
    return value

def megadrive_title(data):
    """Read the documented cartridge header title fields (no identity guesswork)."""
    if len(data)<0x200 or b'SEGA' not in data[0x100:0x110]:return None
    for start,stop in ((0x150,0x180),(0x120,0x150)):
        block=data[start:stop].rstrip(b'\x00 ')
        if not block or any(c<32 or c>126 for c in block):continue
        title=' '.join(block.decode('ascii').split())
        if len(title)>=3 and sum(c.isalpha() for c in title)>=3:
            return title
    return None

def migrate(con):
    con.execute(DDL)
    con.commit()

def update(con,target_id,label,source,*,expected_sha=None):
    if source not in PRIORITY:raise ValueError('unknown display name source')
    record=con.execute('SELECT source_sha256 FROM targets WHERE target_id=?',(target_id,)).fetchone()
    if record is None:raise ValueError(f'unknown target {target_id}')
    sha=record[0]
    if expected_sha is not None and expected_sha.lower()!=sha:raise ValueError('target/source SHA-256 mismatch')
    label=normalize(label,filename=(source in ('local_filename','evidence_folder')))
    old=con.execute('SELECT display_name,name_source FROM target_names WHERE target_id=?',(target_id,)).fetchone()
    if old and PRIORITY.get(old['name_source'],0)>PRIORITY[source]:return False
    if old and old['display_name']==label and old['name_source']==source:return False
    with con:con.execute('INSERT INTO target_names(target_id,display_name,name_source,evidence_sha256) VALUES(?,?,?,?) ON CONFLICT(target_id) DO UPDATE SET display_name=excluded.display_name,name_source=excluded.name_source,evidence_sha256=excluded.evidence_sha256', (target_id,label,source,sha))
    return True

def sync_evidence(con, evidence_root):
    """Recover display labels from existing SHA-matched metadata-only scan reports."""
    root=Path(evidence_root)
    stats={'matched':0,'updated':0,'mismatched':0,'errors':0}
    if not root.is_dir():return stats
    for path in sorted(root.glob('*/flow-evidence.json')):
        try:
            doc=json.loads(path.read_text(encoding='utf-8'))
            if doc.get('schema')!='recomp-flow-evidence-v1':continue
            tid=doc.get('target_id');sha=doc.get('source_sha256')
            row=con.execute('SELECT source_sha256 FROM targets WHERE target_id=?',(tid,)).fetchone()
            if row is None or sha!=row[0]:
                stats['mismatched']+=1;continue
            stats['matched']+=1
            hint=doc.get('source_file_name') or path.parent.name
            if update(con,tid,hint,'evidence_folder',expected_sha=sha):stats['updated']+=1
        except (OSError,UnicodeError,ValueError,KeyError,TypeError,sqlite3.Error,json.JSONDecodeError):
            stats['errors']+=1
    return stats


def sync_source(con,source_path):
    """Read local input for *name metadata only*, matched to an existing SHA.

    No graph changes, no code scans; reject unregistered or modified binaries.
    """
    source=Path(source_path)
    if not source.is_file():raise ValueError(f'input file not found: {source}')
    digest=hashlib.sha256()
    with source.open('rb') as f:
        header=f.read(0x200)
        digest.update(header)
        for block in iter(lambda:f.read(1024*1024), b''):
            digest.update(block)
    sha=digest.hexdigest()
    matches=con.execute('SELECT target_id,system_tag FROM targets WHERE source_sha256=?',(sha,)).fetchall()
    if not matches:raise ValueError('file SHA-256 is not registered in this catalogue')
    results=[]
    for row in matches:
        title=megadrive_title(header) if row['system_tag']=='megadrive' else None
        source_name='megadrive_header' if title else 'local_filename'
        label=title or source.name
        updated=update(con,row['target_id'],label,source_name,expected_sha=sha)
        results.append({'target_id':row['target_id'],'display_name':normalize(label,filename=(source_name=='local_filename')),'name_source':source_name,'updated':updated})
    return results
