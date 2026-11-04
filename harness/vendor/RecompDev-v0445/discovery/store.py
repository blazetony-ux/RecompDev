"""Persistent, replayable discovery knowledge base. Does not mutate source binaries."""
import hashlib
import json
import sqlite3
from datetime import datetime, timezone

SCHEMA = '''
CREATE TABLE IF NOT EXISTS discovery_sources (
 source_id TEXT PRIMARY KEY, path TEXT NOT NULL, bytes INTEGER NOT NULL,
 source_hash_kind TEXT NOT NULL, system TEXT NOT NULL, display_name TEXT,
 detected_by TEXT NOT NULL, scanned_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS discovery_regions (
 claim_id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES discovery_sources(source_id),
 start INTEGER NOT NULL, length INTEGER NOT NULL CHECK(length>0),
 category TEXT NOT NULL, status TEXT NOT NULL, evidence TEXT NOT NULL,
 CHECK(start>=0)
);
CREATE INDEX IF NOT EXISTS discovery_regions_src ON discovery_regions(source_id,start);
CREATE TABLE IF NOT EXISTS discovery_assets (
 asset_id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES discovery_sources(source_id),
 offset INTEGER NOT NULL, length INTEGER NOT NULL, kind TEXT NOT NULL,
 format TEXT NOT NULL, confidence TEXT NOT NULL, original_sha256 TEXT NOT NULL,
 raw_path TEXT NOT NULL, preview_path TEXT NOT NULL, evidence TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS discovery_assets_src ON discovery_assets(source_id,offset);
CREATE TABLE IF NOT EXISTS discovery_disc_files (
 file_id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES discovery_sources(source_id),
 disc_path TEXT NOT NULL, extent INTEGER NOT NULL, bytes INTEGER NOT NULL, physical_offset INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS discovery_tasks (
 task_id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES discovery_sources(source_id),
 kind TEXT NOT NULL, subject TEXT NOT NULL, priority INTEGER NOT NULL,
 status TEXT NOT NULL, dependencies TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
 reason TEXT NOT NULL DEFAULT '', result TEXT NOT NULL DEFAULT '',
 worker_version TEXT NOT NULL, updated_utc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS discovery_tasks_queue ON discovery_tasks(status,priority);
CREATE TABLE IF NOT EXISTS discovery_links (
 link_id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES discovery_sources(source_id),
 left_kind TEXT NOT NULL, left_id TEXT NOT NULL, relation TEXT NOT NULL,
 right_kind TEXT NOT NULL, right_id TEXT NOT NULL, status TEXT NOT NULL, evidence TEXT NOT NULL
);
'''


def now():
    return datetime.now(timezone.utc).isoformat()


def stable_id(*parts):
    return hashlib.sha256(json.dumps(parts, sort_keys=True, separators=(',',':')).encode()).hexdigest()[:32]


def connect(path):
    con=sqlite3.connect(str(path),timeout=30)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    con.execute('PRAGMA busy_timeout=30000')
    con.executescript(SCHEMA)
    return con


def store_source(con, source_id, path, n, hash_kind, system, name, detected_by):
    with con:
        con.execute('''INSERT INTO discovery_sources VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(source_id) DO UPDATE SET path=excluded.path, system=excluded.system,
         display_name=excluded.display_name,scanned_utc=excluded.scanned_utc''',
        (source_id,str(path),n,hash_kind,system,name,detected_by,now()))


def region(con,src,start,length,category,status,evidence):
    total=con.execute('SELECT bytes FROM discovery_sources WHERE source_id=?',(src,)).fetchone()
    if total is None or start<0 or length<=0 or start+length>total[0]:
        raise ValueError('Region outside authenticated source')
    claim=stable_id(src,start,length,category,status,evidence)
    with con:
        con.execute('INSERT OR IGNORE INTO discovery_regions VALUES(?,?,?,?,?,?,?)',
            (claim,src,start,length,category,status,json.dumps(evidence,sort_keys=True)))
    return claim


def task(con,src,kind,subject='',priority=50,dependencies=(),version='0.4.0'):
    tid=stable_id(src,kind,subject,version)
    with con:
        con.execute('''INSERT OR IGNORE INTO discovery_tasks
          (task_id,source_id,kind,subject,priority,status,dependencies,worker_version,updated_utc)
          VALUES (?,?,?,?,?,?,?,?,?)''',
          (tid,src,kind,str(subject),priority,'READY',json.dumps(list(dependencies)),version,now()))
    return tid


def state(con,tid,status,reason='',result=None,increment=True):
    with con:
        con.execute('''UPDATE discovery_tasks SET status=?,reason=?,result=?,updated_utc=?,
                  attempts=attempts+? WHERE task_id=?''',
                  (status,reason,json.dumps(result or {},sort_keys=True),now(),int(increment),tid))


def asset(con,src,offset,length,kind,fmt,confidence,original_sha,raw,preview,evidence):
    aid=stable_id(src,offset,length,fmt)
    with con:
        con.execute('''INSERT OR REPLACE INTO discovery_assets
          VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
          (aid,src,offset,length,kind,fmt,confidence,original_sha,str(raw),str(preview),
           json.dumps(evidence,sort_keys=True)))
    return aid


def disc_file(con,src,path,extent,size,physical):
    fid=stable_id(src,path,extent,size)
    with con:
        con.execute('INSERT OR REPLACE INTO discovery_disc_files VALUES(?,?,?,?,?,?)',
                    (fid,src,path,extent,size,physical))
    return fid


def summary(con,source_id=None,limit=500):
    filt=' WHERE source_id=?' if source_id else ''
    params=(source_id,) if source_id else ()
    srcs=[dict(x) for x in con.execute('SELECT * FROM discovery_sources'+
                                       (' WHERE source_id=?' if source_id else '')+' ORDER BY display_name,path',params)]
    tasks=[dict(x) for x in con.execute('SELECT * FROM discovery_tasks'+filt+' ORDER BY priority DESC,task_id LIMIT ?',(*params,limit))]
    assets=[dict(x) for x in con.execute('SELECT * FROM discovery_assets'+filt+' ORDER BY source_id,offset LIMIT ?',(*params,limit))]
    disc_count=con.execute('SELECT COUNT(*) FROM discovery_disc_files'+filt,params).fetchone()[0]
    for row in tasks:row['dependencies']=json.loads(row['dependencies'])
    claims_by_source={}
    for src in srcs:
        claims=list(con.execute('SELECT start,length,category,status FROM discovery_regions WHERE source_id=?',
                                (src['source_id'],)))
        # Exclusive coverage is over byte intervals, NEVER a sum of overlapping claims.
        boundaries={0,src['bytes']}
        for claim in claims:
            boundaries.add(claim['start']);boundaries.add(claim['start']+claim['length'])
        bounds=sorted(boundaries);counts={'STRUCTURE':0,'ASSET':0,'CODE_CANDIDATE':0,'ASSET_CANDIDATE':0,'UNKNOWN':0}
        for a,b in zip(bounds,bounds[1:]):
            overlapping=[r for r in claims if r['start']<b and r['start']+r['length']>a]
            if any(r['category']=='STRUCTURE' for r in overlapping):category='STRUCTURE'
            elif any(r['category']=='ASSET' for r in overlapping):category='ASSET'
            elif any(r['category']=='CODE_CANDIDATE' for r in overlapping):category='CODE_CANDIDATE'
            elif any(r['category']=='ASSET_CANDIDATE' for r in overlapping):category='ASSET_CANDIDATE'
            else:category='UNKNOWN'
            counts[category]+=b-a
        assert sum(counts.values())==src['bytes']
        src['coverage_bytes']=counts
        src['unknown_percent']=round(100*counts['UNKNOWN']/src['bytes'],2) if src['bytes'] else 0
        src['region_claims']=len(claims)
    by_status={}
    for t in tasks:by_status[t['status']]=by_status.get(t['status'],0)+1
    return {'schema':'recomp-autonomous-discovery-v0.4.0','sources':srcs,'tasks':tasks,
            'assets':assets,'disc_files':disc_count,'task_status_counts':by_status,
            'disclaimer':'Byte ranges are hypothesis/evidence categories, not decompiled-game completeness. '\
            'Asset candidates are unverified. No native-function parity implied.'}
