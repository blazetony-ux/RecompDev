"""Prepare an owner-local source for the shared native catalogue.

Master System Z80 initial mapping uses Ghidra; banked code is recovered later
by Native Execution. Mega Drive and PS-X EXE are registered with honest stage
blockers; registration is not integrated native execution or CPU parity.
"""
import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime,timezone

from discovery.formats import probe
from discovery.store import SCHEMA as DISCOVERY_SCHEMA
from discovery import store
from recovery.pipeline import read_export

SCHEMA='''
CREATE TABLE IF NOT EXISTS native_preparations_v0403 (
 source_id TEXT PRIMARY KEY, target_id TEXT, source_sha256 TEXT,
 cpu TEXT NOT NULL, system TEXT NOT NULL, status TEXT NOT NULL,
 candidate_count INTEGER NOT NULL DEFAULT 0, banked_bytes INTEGER NOT NULL DEFAULT 0,
 blocker TEXT NOT NULL DEFAULT '', export_path TEXT NOT NULL DEFAULT '',
 updated_utc TEXT NOT NULL, FOREIGN KEY(source_id) REFERENCES discovery_sources(source_id)
);
CREATE TABLE IF NOT EXISTS native_function_candidates_v0403 (
 target_id TEXT NOT NULL, entry INTEGER NOT NULL, name TEXT NOT NULL,
 instruction_count INTEGER NOT NULL, boundary_state TEXT NOT NULL,
 evidence_export_sha256 TEXT NOT NULL, PRIMARY KEY(target_id,entry)
);
CREATE INDEX IF NOT EXISTS native_preparations_target_v0403 ON native_preparations_v0403(target_id);
'''
CPU={'mastersystem':'z80','megadrive':'m68k','psx-exe':'mips', 'gamegear':'z80'}
LANG={'z80':'z80:LE:16:default','m68k':'68000:BE:32:default','mips':'MIPS:LE:32:default'}
MAX_ROM=64*1024*1024
Z80_ROM_WINDOW=0xC000  # SMS 0xC000-0xFFFF is RAM, never ROM code
MAX_FUNCTIONS=1000
MAX_INSTRUCTIONS=200000

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def locate_ghidra(explicit=''):
    options=[explicit,os.environ.get('RECOMPDEV_GHIDRA','')]
    for home in (os.environ.get('GHIDRA_HOME',''),):
        if home:options.append(str(Path(home)/'support'/'analyzeHeadless.bat'))
    if os.name=='nt':
        base=Path('C:/Projects/_Old/Tools')
        if base.is_dir():options.extend(str(p) for p in sorted(base.glob('Ghidra*/support/analyzeHeadless.bat'),reverse=True))
        base=Path('C:/Projects/Tools')
        if base.is_dir():options.extend(str(p) for p in sorted(base.glob('Ghidra*/support/analyzeHeadless.bat'),reverse=True))
    which=shutil.which('analyzeHeadless.bat') or shutil.which('analyzeHeadless')
    if which:options.append(which)
    return next((str(Path(x)) for x in options if x and Path(x).is_file()),'')

def _inside(path,roots):
    p=Path(path).resolve()
    allowed=[Path(r).resolve() for r in roots]
    return not allowed or any(p==r or r in p.parents for r in allowed)

def _candidate_rows(doc, source, cpu):
    """Reject spoofed/incorrect exports: verify each instruction against source bytes."""
    if doc.get('language')!=LANG[cpu]:raise ValueError('Ghidra ISA/language disagrees with selected CPU')
    if len(doc['functions'])>10000:raise ValueError('Too many unbounded function records')
    out=[];ins_total=0
    with open(source,'rb') as f:
        for func in doc['functions']:
            entry=func.get('entry');ins=func.get('instructions')
            if type(entry)!=int or not isinstance(ins,list) or not ins:continue
            if len(ins)>10000:raise ValueError('Oversized Ghidra function')
            # For Z80, the first 64 KB contains switchable banks. We only attest
            # exact source bytes in the initial fixed view; no bank interpretations.
            for i in ins:
                a=i.get('address');n=i.get('length');digest=i.get('bytes_sha256')
                if type(a)!=int or type(n)!=int or n<1 or n>16:raise ValueError('Invalid instruction extent')
                off=a if cpu!='mips' else a # PS-X EXE checked by its existing dedicated pipeline, not here
                if off<0 or off+n>min(source.stat().st_size,Z80_ROM_WINDOW if cpu=='z80' else MAX_ROM):
                    raise ValueError('Instruction leaves authenticated raw image / mapped Z80 bank')
                f.seek(off)
                if hashlib.sha256(f.read(n)).hexdigest()!=digest:
                    raise ValueError('Ghidra instruction bytes differ from original ROM')
                ins_total+=1
                if ins_total>MAX_INSTRUCTIONS:raise ValueError('Excessive instruction metadata')
            out.append((entry,str(func.get('name',''))[:120],len(ins)))
    return out

def _ghidra_z80(path, target, digest, output, binary, timeout=360):
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='recompdev-z80-nativeprep-') as td:
        td=Path(td);image=td/'rom-initial-window.bin'
        with open(path,'rb') as inp:image.write_bytes(inp.read(Z80_ROM_WINDOW))
        cmd=[str(binary),str(td),'RecompDevZ80Preparation','-import',str(image),
             '-loader','BinaryLoader','-loader-baseAddr','0x0',
             '-processor',LANG['z80'],'-scriptPath',str(Path(__file__).resolve().parents[1]/'ghidra'),
             '-preScript','SeedRecompEntry.java','0x0',
             '-postScript','ExportFunctionBodies.java',str(output),target,digest,str(MAX_FUNCTIONS),
             '-readOnly','-analysisTimeoutPerFile','180']
        try:run=subprocess.run(cmd,text=True,capture_output=True,timeout=timeout,errors='replace')
        except subprocess.TimeoutExpired as exc:raise ValueError('Ghidra Z80 analysis timed out') from exc
        output.with_suffix('.ghidra.log').write_text((run.stdout+'\n'+run.stderr)[-150000:],encoding='utf-8')
        if run.returncode or not output.is_file():
            raise ValueError('Ghidra Z80 analysis failed; inspect '+str(output.with_suffix('.ghidra.log')))

def _cached_md(source,target,digest,output):
    """Reuse an existing Ghidra export only when its source and byte hashes match."""
    root=Path(__file__).resolve().parents[1].parent
    for version in ('v0.4.0.2','v0.4.0.1','v0.4.0','v0.3.2.3','v0.3.2.2','v0.3.1'):
        for dirname in ('autopilot-v0323','autopilot-v0322','autopilot-v031'):
            p=root/('RecompDev-'+version)/'evidence'/dirname/'ghidra'/(target+'.json')
            if p.is_file() and p.stat().st_size<128*1024*1024:
                d=read_export(p)
                if d.get('source_sha256')==digest and d.get('target_id')==target:
                    try:rows=_candidate_rows(d,source,'m68k')
                    except ValueError:continue
                    shutil.copyfile(p,output)
                    return rows
    return None

def prepare(db, source_id, output, ghidra_exe='',allowed_roots=(), analyze=True):
    db=Path(db).resolve();output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(str(db),timeout=30)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    con.executescript(DISCOVERY_SCHEMA)
    con.executescript(SCHEMA)
    print('NATIVE_PREP_STAGE=source_lookup',flush=True)
    row=con.execute('SELECT * FROM discovery_sources WHERE source_id=?',(source_id,)).fetchone()
    if row is None:con.close();raise ValueError('Source is not registered in Autonomous Discovery')
    path=Path(row['path']).resolve()
    if not _inside(path,allowed_roots):con.close();raise ValueError('Source is outside the configured ROM library')
    if not path.is_file() or path.stat().st_size!=row['bytes']:
        con.close();raise ValueError('Source missing or file size changed; rediscover the ROM first')
    system=row['system'];cpu=CPU.get(system,'')
    result={'schema':'recomp-native-preparation-v0.4.0.3','source_id':source_id,'source':str(path),
            'system':system,'cpu':cpu or 'UNSUPPORTED','target_id':None,'candidates':0,
            'status':'NEEDS_EXECUTABLE_EXTRACTOR','blocker':'No executable extractor/CPU adapter for this container',
            'banked_bytes':0,'verified_source_sha256':None,'ghidra_export':None,
            'native_cpp_functions_verified':0,
            'caveat':'Candidates need corroboration and runtime parity; the Z80 pilot is not a universal CPU backend.'}
    if cpu and system in ('mastersystem','megadrive','gamegear','psx-exe'):
        if row['bytes']>MAX_ROM or row['source_hash_kind']!='SHA256_COMPLETE':
            result.update(status='NEEDS_FULL_SOURCE_HASH',blocker='ROM must have a complete SHA-256 before native registration')
        else:
            print('NATIVE_PREP_STAGE=sha256_verify',flush=True)
            actual=sha256(path)
            if actual!=source_id or actual not in (row['source_id'],):
                con.close();raise ValueError('Source SHA-256 differs from discovery fingerprint; rediscover before preparation')
            # Recheck platform signature, not merely a filename.
            detected,reason,_=probe(path)
            if detected!=system:
                con.close();raise ValueError('CPU/platform identity changed since discovery; rediscover before preparation')
            target=f'{system}-{actual[:12]}'
            result.update(target_id=target,verified_source_sha256=actual,
                          status='REGISTERED_NEEDS_ANALYSIS',blocker='Function recovery not yet attempted')
            with con:
                old=con.execute('SELECT source_sha256,isa,system_tag FROM targets WHERE target_id=?',(target,)).fetchone()
                if old and (old['source_sha256'],old['isa'],old['system_tag'])!=(actual,cpu,system):
                    raise ValueError('Existing native target identity mismatch')
                if not old:
                    con.execute('INSERT INTO targets(target_id,isa,source_sha256,system_tag,analyzer) VALUES(?,?,?,?,?)',
                                (target,cpu,actual,system,'native-preparation-v0403'))
                # Friendly labels are *hints* inherited from discovery; preserve
                # any existing owner-chosen display names.
                has_names=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='target_names'").fetchone()
                if has_names:
                    label=(row['display_name'] or path.name).strip()[:180]
                    if label:
                        con.execute('''INSERT OR IGNORE INTO target_names
                            (target_id,display_name,name_source,evidence_sha256)
                            VALUES(?,?,?,?)''',
                            (target,label,'megadrive_header' if system=='megadrive' and 'header' in row['detected_by'].lower() else 'local_filename',actual))
            export_path=output/'functions.json'
            result['banked_bytes']=max(0,row['bytes']-Z80_ROM_WINDOW) if cpu=='z80' else 0
            candidate_rows=None
            if analyze:
                if cpu=='m68k':
                    candidate_rows=_cached_md(path,target,actual,export_path)
                    if candidate_rows is None:
                        # Existing specialized headless path is used by recompilation campaign.
                        gh=locate_ghidra(ghidra_exe)
                        if gh:
                            from recovery.headless import export
                            try:
                                export(db,path,target,gh,export_path)
                                d=read_export(export_path);candidate_rows=_candidate_rows(d,path,'m68k')
                            except (ValueError,OSError) as exc:
                                result.update(status='ANALYSIS_FAILED',blocker=str(exc)[:250])
                elif cpu=='z80':
                    print('NATIVE_PREP_STAGE=z80_headless_analysis',flush=True)
                    gh=locate_ghidra(ghidra_exe)
                    if gh:
                        try:
                            _ghidra_z80(path,target,actual,export_path,gh)
                            d=read_export(export_path)
                            if d.get('source_sha256')!=actual or d.get('target_id')!=target:raise ValueError('Ghidra identity mismatch')
                            candidate_rows=_candidate_rows(d,path,'z80')
                        except (ValueError,OSError) as exc:
                            result.update(status='ANALYSIS_FAILED',blocker=str(exc)[:250])
                if cpu=='mips' and candidate_rows is None and result['status']!='ANALYSIS_FAILED':
                    result.update(status='NEEDS_MIPS_ANALYSIS_ADAPTER',
                      blocker='PS-X EXE registered with source SHA-256; unified MIPS function extraction and native execution are not integrated')
                if candidate_rows is not None:
                    if sha256(path)!=actual:raise ValueError('Original ROM changed during native recovery')
                    print('NATIVE_PREP_STAGE=source_instruction_hashes_verified',flush=True)
                    evidence_sha=sha256(export_path)
                    with con:
                        for entry,name,n in candidate_rows:
                            con.execute('''INSERT INTO native_function_candidates_v0403 VALUES(?,?,?,?,?,?)
                                         ON CONFLICT(target_id,entry) DO UPDATE SET name=excluded.name,
                                         instruction_count=excluded.instruction_count,
                                         evidence_export_sha256=excluded.evidence_export_sha256''',
                                        (target,entry,name,n,'GHIDRA_CANDIDATE_UNCORROBORATED',evidence_sha))
                    result.update(candidates=len(candidate_rows),ghidra_export=str(export_path),
                        status=('CANDIDATES_RECOVERED_TRANSLATOR_NEEDED' if candidate_rows else 'ANALYSIS_NO_CANDIDATES'),
                        blocker=('Experimental Z80 C++ lowering exists in Native Execution; semantics, banking and parity remain incomplete' if cpu=='z80' else
                                 'Function boundaries and C++ parity remain unverified') if candidate_rows else 'Ghidra produced no function candidates; inspect log')
                elif result['status'] not in ('ANALYSIS_FAILED','NEEDS_MIPS_ANALYSIS_ADAPTER'):
                    result.update(status='NEEDS_GHIDRA',blocker='Headless Ghidra unavailable; set RECOMPDEV_GHIDRA or GHIDRA_HOME')
            else:result.update(status='REGISTERED_NEEDS_ANALYSIS',blocker='Headless analysis not requested')
            if candidate_rows is None:
                # Don't discard previously attested recovery evidence because a
                # later run lacks Ghidra or the user cancels an analysis request.
                previous=con.execute('''SELECT candidate_count,export_path
                    FROM native_preparations_v0403 WHERE source_id=?''',(source_id,)).fetchone()
                if previous and previous['candidate_count']>0:
                    existing=con.execute('SELECT COUNT(*) FROM native_function_candidates_v0403 WHERE target_id=?',(target,)).fetchone()[0]
                    if existing:
                        result['candidates']=existing
                        result['ghidra_export']=previous['export_path'] or None
                        result['status']='PREVIOUS_CANDIDATES_RETAINED'
                        result['blocker']='Previous verified-byte Ghidra metadata retained; newest analysis unavailable or incomplete'
    with con:
        con.execute('''INSERT INTO native_preparations_v0403
        (source_id,target_id,source_sha256,cpu,system,status,candidate_count,banked_bytes,blocker,export_path,updated_utc)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(source_id) DO UPDATE SET target_id=excluded.target_id,source_sha256=excluded.source_sha256,
        cpu=excluded.cpu,system=excluded.system,status=excluded.status,candidate_count=excluded.candidate_count,
        banked_bytes=excluded.banked_bytes,blocker=excluded.blocker,export_path=excluded.export_path,
        updated_utc=excluded.updated_utc''',
        (source_id,result['target_id'],result['verified_source_sha256'],result['cpu'],system,
         result['status'],result['candidates'],result['banked_bytes'],result['blocker'],
         result['ghidra_export'] or '',datetime.now(timezone.utc).isoformat()))
    # Aggregate, resumable *capability* tasks; avoid a new blocker task for every
    # candidate when one Z80 translator feature would unlock the entire group.
    plan=store.task(con,source_id,'prepare_native_target',priority=95,version='0.4.0.3')
    if result['target_id']:
        store.state(con,plan,'DONE','Registered as '+result['target_id'],result,increment=False)
        discover=store.task(con,source_id,'native_function_discovery',priority=90,
                            dependencies=(plan,),version='0.4.0.3')
        if result['candidates']:
            store.state(con,discover,'DONE',str(result['candidates'])+' byte-attested candidate bodies',
                        {'export':result['ghidra_export']},increment=False)
        else:
            stage='NEEDS_CAPABILITY' if result['status']=='NEEDS_GHIDRA' else 'NEEDS_EVIDENCE'
            store.state(con,discover,stage,result['blocker'],increment=False)
        if cpu=='z80':
            sem=store.task(con,source_id,'implement_z80_cpp_lowering',priority=96,
                           dependencies=(discover,),version='0.4.0.3')
            store.state(con,sem,'NEEDS_CAPABILITY',
                        'Implement validated Z80 instruction, flag, call and IO semantics before C++ generation',increment=False)
            banks=store.task(con,source_id,'recover_cartridge_bank_mapping',priority=91,
                             dependencies=(discover,),version='0.4.0.3')
            store.state(con,banks,'NEEDS_EVIDENCE',
                        'Only the initial 48 KB mapped view analysed; dynamic bank switching unresolved',increment=False)
            bounds=store.task(con,source_id,'corroborate_z80_function_boundaries',priority=89,
                              dependencies=(discover,),version='0.4.0.3')
            store.state(con,bounds,'NEEDS_EVIDENCE',
                        'Ghidra-only candidates require independent boundary and call-site evidence',increment=False)
    else:
        store.state(con,plan,'NEEDS_ADAPTER',result['blocker'],increment=False)
    con.close()
    (output/'preparation-report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--db',required=True);p.add_argument('--source-id',required=True)
    p.add_argument('--output',required=True);p.add_argument('--ghidra-exe',default='')
    p.add_argument('--allowed-root',action='append',default=[])
    p.add_argument('--no-analysis',action='store_true')
    a=p.parse_args(argv)
    result=prepare(a.db,a.source_id,a.output,a.ghidra_exe,a.allowed_root,not a.no_analysis)
    print('NATIVE_PREP_STATUS='+result['status'],flush=True)
    print('NATIVE_TARGET='+str(result['target_id']),flush=True)
    print('GHIDRA_FUNCTION_CANDIDATES='+str(result['candidates']),flush=True)
    print('NATIVE_PREP_REPORT='+str(Path(a.output)/'preparation-report.json'),flush=True)
    return 0
if __name__=='__main__':raise SystemExit(main())
