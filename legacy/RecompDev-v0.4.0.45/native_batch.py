"""Source-authenticated cross-architecture batch coordinator.

The existing Go backend generates BOUNDED CODE UNITS at its own program entry,
not catalogue function translations. Records are deliberately independent.
No original binary bytes are stored in SQLite or reports.
"""
from __future__ import annotations
import hashlib
import json
import re
import sqlite3
import subprocess
import os
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

DDL='''
CREATE TABLE IF NOT EXISTS batch_campaigns(
 campaign_id TEXT PRIMARY KEY, created_utc TEXT NOT NULL, kind TEXT NOT NULL,
 source_manifest_sha256 TEXT NOT NULL, candidate_count INTEGER NOT NULL,
 target_count INTEGER NOT NULL, scope TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS batch_targets(
 campaign_id TEXT NOT NULL REFERENCES batch_campaigns(campaign_id),
 target_id TEXT NOT NULL REFERENCES targets(target_id),
 display_name TEXT NOT NULL, isa TEXT NOT NULL, input_status TEXT NOT NULL,
 native_status TEXT NOT NULL, native_units INTEGER NOT NULL DEFAULT 0,
 native_instructions INTEGER NOT NULL DEFAULT 0, native_blockers INTEGER NOT NULL DEFAULT 0,
 native_manifest_sha256 TEXT, notes TEXT NOT NULL,
 PRIMARY KEY(campaign_id,target_id)
);
CREATE TABLE IF NOT EXISTS batch_jobs(
 campaign_id TEXT NOT NULL REFERENCES batch_campaigns(campaign_id),
 target_id TEXT NOT NULL REFERENCES targets(target_id), entry INTEGER NOT NULL,
 run_id TEXT NOT NULL, instruction_count INTEGER NOT NULL,
 boundary_state TEXT NOT NULL, stage TEXT NOT NULL, blocker TEXT NOT NULL,
 PRIMARY KEY(campaign_id,target_id,entry)
);
CREATE TABLE IF NOT EXISTS backend_probes(
 backend TEXT NOT NULL, family TEXT NOT NULL, status TEXT NOT NULL,
 evidence TEXT NOT NULL, PRIMARY KEY(backend,family)
);
CREATE INDEX IF NOT EXISTS batch_jobs_status ON batch_jobs(campaign_id,stage);
'''
SUPPORTED_NATIVE_FORMATS={'megadrive','psx-exe'}
MAX_SCAN_FILE_BYTES=512*1024*1024  # Bound filesystem walks; no games copied.


def init(con):
    con.executescript(DDL)


def sha_file(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def index_sources(con, paths=(), roots=()):
    """Only regular files in user-nominated locations; no auto trust of filename."""
    wanted={r['source_sha256'] for r in con.execute('SELECT source_sha256 FROM targets')}
    indexed={};errors=[]; seen=set()
    def inspect(p):
        p=Path(p).resolve()
        if p in seen:return
        seen.add(p)
        try:
            if not p.is_file() or p.stat().st_size>MAX_SCAN_FILE_BYTES:return
            digest=sha_file(p)
            if digest in wanted:indexed.setdefault(digest,str(p))
        except (OSError,PermissionError) as e:
            errors.append({'source':str(p),'error':type(e).__name__})
    for p in paths:
        if not Path(p).is_file():raise ValueError('explicit source file not found: '+str(p))
        inspect(p)
    for folder in roots:
        base=Path(folder)
        if not base.is_dir():raise ValueError('source directory not found: '+str(folder))
        # Do not follow directory symlinks, avoid unbounded recursion and evidence trees.
        remaining=20000
        for current, dirs, files in os.walk(base,followlinks=False):
            dirs[:]=[x for x in sorted(dirs) if not (Path(current)/x).is_symlink() and x not in ('.git','node_modules','build','.venv','__pycache__')]
            for name in sorted(files):
                if remaining<=0:raise ValueError('source scan exceeded 20,000 files; select a smaller folder')
                remaining-=1
                p=Path(current)/name
                if p.suffix.lower() in ('.md','.gen','.bin','.psx','.exe','.elf','.nes','.gba','.rom','.iso','.smd','.xex'):
                    inspect(p)
    return indexed,errors


def probe_go_sources(srcroot):
    if srcroot is None:return []
    root=Path(srcroot)/'tools/chqdev'
    if not root.is_dir():raise ValueError('Go source root not found')
    rules=[
      ('m68k-abs-long','recomp_m68k_abs_long_test.go',['recomp_ir.go','recomp_ir_codegen.go']),
      ('m68k-short-branch','recomp_m68k_branch_short_test.go',['recomp_convert.go','recomp_ir_codegen.go']),
      ('m68k-word-lea','recomp_m68k_word_lea_test.go',['recomp_ir.go','recomp_ir_codegen.go']),
      ('m68k-movem-btst','recomp_m68k_movem_btst_test.go',['recomp_ir.go','recomp_ir_codegen.go']),
    ]
    result=[]
    for family,test,sources in rules:
        files=[root/test,*[root/s for s in sources]]
        present=all(p.is_file() for p in files)
        result.append({'backend':'chqdev-go','family':family,'status':'TEST_SOURCE_PRESENT_NOT_EXECUTION_PARITY' if present else 'MISSING',
            'evidence':{'test':test,'test_sha256':sha_file(root/test) if present else None,'source_files':sources}})
    return result


def go_executable(root):
    root=Path(root).resolve()
    if os.name=='nt':
        exe=root/'tools/chqdev/bin/chqdev-windows-amd64.exe'
    else:exe=root/'tools/chqdev/bin/chqdev-linux-amd64'
    if not exe.is_file():raise ValueError('native CLI executable absent: '+str(exe))
    return root,exe


def attempt_go(root,source,expected_sha,timeout):
    """Invoke existing entry-based converter, not whole function recompilation."""
    root,exe=go_executable(root)
    if sha_file(source)!=expected_sha:raise ValueError('source changed immediately before native invocation')
    try:
        run=subprocess.run([str(exe),'--root',str(root),'recomp','convert',str(source)],
                           capture_output=True,text=True,timeout=timeout,check=False,errors='replace')
    except subprocess.TimeoutExpired:
        return {'status':'BACKEND_TIMEOUT','note':'bounded native converter timed out'}
    output=run.stdout+'\n'+run.stderr
    if run.returncode:
        return {'status':'BACKEND_FAILED','note':output[-1500:]}
    match=re.search(r'(?m)^Output:\s*(.+?)\s*$',output)
    if not match:return {'status':'BACKEND_RESULT_UNPARSEABLE','note':output[-1000:]}
    folder=Path(match.group(1).strip());manifest=folder/'manifest.json'
    if not manifest.is_file():return {'status':'BACKEND_MANIFEST_MISSING','note':'no native campaign manifest'}
    if manifest.stat().st_size>1024*1024:raise ValueError('oversized native manifest')
    obj=json.loads(manifest.read_text(encoding='utf-8-sig'))
    if obj.get('schema')!='recomp-native-campaign-v1' or obj.get('sourceSHA256')!=expected_sha:
        return {'status':'BACKEND_IDENTITY_MISMATCH','note':'native manifest SHA/schema mismatch'}
    return {'status':obj.get('compileStatus','UNKNOWN'), 'units':int(obj.get('generatedUnits',0)),
            'instructions':int(obj.get('generatedInstructions',0)), 'blockers':len(obj.get('blockers',[])),
            'manifest_sha256':sha_file(manifest), 'note':'BOUNDED_UNITS_ONLY;NOT_WHOLE_FUNCTION;NOT_PARITY_VERIFIED'}


def create_campaign(dbfile, sources=(), roots=(), go_root=None, attempt_bounded=False,
                    go_source_root=None, timeout=120, report_path=None):
    """Immutable batch job records; requires source hash before any executable invocation.

    Planning does not imply compilation, and backend campaign compilation never changes
    the per-function jobs to verified or compiled.
    """
    if attempt_bounded and not go_root:raise ValueError('--attempt-bounded requires --go-root')
    if timeout<1 or timeout>900:raise ValueError('timeout must be 1..900 seconds')
    from graph_store import connect
    con=connect(dbfile)
    try:
        init(con)
        lookup,errors=index_sources(con,sources,roots)
        targets=[dict(t) for t in con.execute('SELECT * FROM targets ORDER BY target_id')]
        # Stable latest run by SQLite insertion order; prior analyzers are retained.
        names={r['target_id']:r['display_name'] for r in con.execute('SELECT target_id,display_name FROM target_names')} if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='target_names'").fetchone() else {}
        manifest_digest=hashlib.sha256(json.dumps([{'target':x['target_id'],'sha256':x['source_sha256'],'matched':x['source_sha256'] in lookup} for x in targets],sort_keys=True).encode()).hexdigest()
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        batch_id='batch-'+stamp+'-'+manifest_digest[:10]
        jobs=[];summaries=[];go_results={}
        for t in targets:
            tid=t['target_id'];sha=t['source_sha256'];name=names.get(tid,tid)
            source=lookup.get(sha); input_status='SHA256_VERIFIED' if source else 'SOURCE_UNAVAILABLE'
            run=con.execute('SELECT * FROM graph_runs WHERE target_id=? ORDER BY rowid DESC LIMIT 1',(tid,)).fetchone()
            functions=con.execute('SELECT * FROM graph_functions WHERE run_id=? ORDER BY entry',(run['run_id'],)).fetchall() if run else []
            for fn in functions:
                boundary=fn['boundary_state']
                # External analyzer assertions are still only candidates, never verified boundaries.
                if not source:stage='SOURCE_UNAVAILABLE';blocker='No matching owner-local source hash supplied'
                elif boundary not in ('verified','verified_complete'):
                    stage='NEEDS_VERIFIED_BOUNDARY';blocker=boundary
                else:
                    stage='NEEDS_TYPED_IR_AND_SEMANTIC_TESTS';blocker='No qualified whole-function lowering or parity contract'
                jobs.append(dict(target_id=tid,entry=int(fn['entry']),run_id=fn['run_id'],instruction_count=fn['instruction_count'],boundary_state=boundary,stage=stage,blocker=blocker))
            go_status='NOT_ATTEMPTED';native={}
            if attempt_bounded:
                if not source:go_status='SOURCE_UNAVAILABLE'
                elif t['system_tag'] not in SUPPORTED_NATIVE_FORMATS:go_status='BACKEND_FORMAT_UNSUPPORTED'
                else:
                    native=attempt_go(go_root,source,sha,timeout)
                    go_status=native['status'];go_results[tid]=native
            summaries.append(dict(target_id=tid,display_name=name,isa=t['isa'],source_sha256=sha,
                                  input_status=input_status,source_matched=bool(source),candidate_functions=len(functions),
                                  native_status=go_status,native_units=native.get('units',0),
                                  native_instructions=native.get('instructions',0),native_blockers=native.get('blockers',0),
                                  native_manifest_sha256=native.get('manifest_sha256'),notes=native.get('note','')))
        probes=probe_go_sources(go_source_root or go_root)
        # Transactional publication after all probing and any backend calls.
        with con:
            con.execute('INSERT INTO batch_campaigns VALUES (?,?,?,?,?,?,?)',
                (batch_id,datetime.now(timezone.utc).isoformat(), 'bounded-experimental' if attempt_bounded else 'assessment',manifest_digest,len(jobs),len(targets),
                 'Source identity verified only; function boundaries unverified; native converter outputs bounded code units, not verified functions.'))
            for t in summaries:
                con.execute('INSERT INTO batch_targets VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    (batch_id,t['target_id'],t['display_name'],t['isa'],t['input_status'],t['native_status'],
                     t['native_units'],t['native_instructions'],t['native_blockers'],t['native_manifest_sha256'],t['notes']))
            for j in jobs:
                con.execute('INSERT INTO batch_jobs VALUES (?,?,?,?,?,?,?,?)',
                    (batch_id,j['target_id'],j['entry'],j['run_id'],j['instruction_count'],j['boundary_state'],j['stage'],j['blocker']))
            for probe in probes:
                con.execute('INSERT OR REPLACE INTO backend_probes VALUES (?,?,?,?)',
                    (probe['backend'],probe['family'],probe['status'],json.dumps(probe['evidence'],sort_keys=True)))
        counts=Counter(j['stage'] for j in jobs)
        # Source-observed forms are requirement counts, not verified semantics.
        gaps=[dict(r) for r in con.execute("""SELECT o.form_key, COUNT(*) occurrences, COUNT(DISTINCT o.target_id) targets
                FROM observations o WHERE o.evidence='static_reachable'
                GROUP BY o.form_key ORDER BY targets DESC,occurrences DESC,o.form_key LIMIT 60""")]
        small=Counter(j['target_id'] for j in jobs if 2 <= j['instruction_count'] <= 20
                      and j['boundary_state']=='boundary_not_verified')
        report={'schema':'recomp-batch-campaign-v0.3','campaign_id':batch_id,'scope':'Function candidate readiness and separate bounded Go experiments; no function C++ parity',
                'totals':{'targets':len(targets),'function_candidates':len(jobs),'stages':dict(counts),'sources_sha_verified':len(lookup)},
                'targets':summaries,'jobs':jobs,'backend_source_probes':probes,'source_scan_errors':errors,'cross_target_form_priorities':gaps,'small_boundary_candidates_by_target':dict(small),
                'disclaimer':'Native Go units are not verified whole functions. Not a multi-system emulator or gameplay conversion.'}
        if report_path:
            p=Path(report_path);p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        return report
    finally:con.close()
