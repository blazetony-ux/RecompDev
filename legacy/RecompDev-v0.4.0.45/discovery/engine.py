"""Bounded, resumable game-image discovery. Never writes to source images.

Runs independently of native code conversion, against the same catalogue database.
A task is retried only when a source fingerprint changes (new ID) or explicitly requested.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from discovery import formats,store
from discovery.image import png_rgba,render_tim,render_md_tiles

EXCLUDE={'.git','node_modules','__pycache__','.venv','evidence','build'}
INPUT_SUFFIXES={'.md','.gen','.bin','.smd','.rom','.psx','.exe','.iso','.img','.cue','.ccd','.sub',
                '.nes','.sfc','.smc','.n64','.z64','.v64','.j64','.chd','.pce','.adf','.wad',
                '.gdi','.cdi','.zip','.xex','.xiso','.elf','.tim','.sms','.gg'}
MAX_FILES=1000
MAX_SAMPLE=1024*1024
HASH_COMPLETE_CEILING=128*1024*1024
MAX_TILES_PER_SOURCE=8
MAX_TIMS_PER_SOURCE=24


def identity(path):
    """True SHA-256 for bounded sources; otherwise explicitly provisional sample digest."""
    path=Path(path);size=path.stat().st_size
    h=hashlib.sha256()
    with open(path,'rb') as f:
        if size<=HASH_COMPLETE_CEILING:
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
            return h.hexdigest(),'SHA256_COMPLETE'
        h.update(b'RECOMPDEV_SAMPLED_NOT_FULL_SHA256\x00')
        h.update(size.to_bytes(8,'big'))
        h.update(f.read(MAX_SAMPLE))
        f.seek(max(0,size-MAX_SAMPLE));h.update(f.read(MAX_SAMPLE))
    return 'sample-'+h.hexdigest(),'PROVISIONAL_SIZE_HEAD_TAIL'


def walk_sources(roots,files,max_files=MAX_FILES):
    found=set()
    for value in files:
        p=Path(value).resolve()
        if not p.is_file():raise ValueError('Explicit source file missing: '+str(p))
        found.add(p)
    for folder in roots:
        base=Path(folder)
        if not base.is_dir():raise ValueError('Source directory missing: '+str(base))
        for here,dirs,filenames in os.walk(base,followlinks=False):
            dirs[:]=[d for d in sorted(dirs) if d not in EXCLUDE and not (Path(here)/d).is_symlink()]
            for filename in sorted(filenames):
                p=Path(here)/filename
                if p.suffix.lower() in INPUT_SUFFIXES and not p.is_symlink():found.add(p.resolve())
                if len(found)>max_files:raise ValueError(f'Source scan exceeded {max_files} files; select a smaller root')
    return sorted(found)


def add_tasks(con,src,system):
    prefix=store.task(con,src,'probe_structure',priority=100)
    store.task(con,src,'scan_tim',priority=80,dependencies=[prefix])
    if system=='megadrive':store.task(con,src,'scan_md_tiles',priority=65,dependencies=[prefix])
    if system=='iso9660':store.task(con,src,'inventory_iso',priority=85,dependencies=[prefix])
    store.task(con,src,'link_code_to_assets',priority=30,dependencies=[prefix])
    store.task(con,src,'investigate_unknown',priority=10,dependencies=[prefix])
    return prefix


def _sega8_header_at(path,offset):
    with open(path,'rb') as stream:
        stream.seek(offset)
        return stream.read(8)==b'TMR SEGA'


def _mark_structure(con,row):
    src=row['source_id'];n=row['bytes'];system=row['system']
    if system=='megadrive':
        if n>=0x200:store.region(con,src,0,0x100,'STRUCTURE','VALIDATED_STRUCTURE',{'type':'m68k_vector_region'})
        if n>=0x200:store.region(con,src,0x100,0x100,'STRUCTURE','VALIDATED_STRUCTURE',{'type':'genesis_header'})
    elif system=='psx-exe':
        header_len=min(0x800,n)
        store.region(con,src,0,header_len,'STRUCTURE','VALIDATED_STRUCTURE',{'type':'psx_exe_header'})
        if n>header_len:
            store.region(con,src,header_len,n-header_len,'CODE_CANDIDATE','UNVERIFIED_MIXED_PAYLOAD',
                         {'type':'executable_payload_may_contain_data','note':'not proven all code'})
    elif system=='iso9660':
        iso=formats.IsoReader(row['path'])
        if iso.valid():
            physical=iso.sector_physical(16)
            if physical+2048<=n:store.region(con,src,physical,2048,'STRUCTURE','VALIDATED_STRUCTURE',
                  {'type':'iso9660_primary_volume_descriptor','sector_size':iso.sector_size})
    elif system in ('mastersystem','gamegear'):
        offset=next((o for o in (0x7FF0,0x3FF0,0x1FF0) if n>=o+16 and _sega8_header_at(row['path'],o)),None)
        if offset is not None:store.region(con,src,offset,16,'STRUCTURE','VALIDATED_STRUCTURE',{'type':'sega_8bit_header','offset':offset})
    elif system=='nes' and n>=16:
        store.region(con,src,0,16,'STRUCTURE','VALIDATED_STRUCTURE',{'type':'iNES_header'})


def _save_asset(con,row,output,offset,raw,kind,fmt,confidence,rgba=None,width=0,height=0,evidence=None):
    src=row['source_id'];name=store.stable_id(src,offset,len(raw),fmt)
    dest=output/'assets'/src[:16]
    dest.mkdir(parents=True,exist_ok=True)
    raw_path=dest/(name+'.bin');png_path=dest/(name+'.png')
    raw_path.write_bytes(raw)
    if rgba is not None:
        png_path.write_bytes(png_rgba(width,height,rgba))
    else:png_path=Path('')
    # Only save file paths to generated exports; original sources stay read-only.
    aid=store.asset(con,src,offset,len(raw),kind,fmt,confidence,hashlib.sha256(raw).hexdigest(),
                    raw_path,str(png_path) if rgba is not None else '',evidence or {})
    store.region(con,src,offset,len(raw),'ASSET' if confidence=='STRUCTURALLY_VALIDATED' else 'ASSET_CANDIDATE',
                 confidence,{'asset_id':aid,'format':fmt})
    return aid


def _scan_tim(con,row,output):
    # Only bounded direct stream scans; raw CD images require sector decoding, not raw byte scanning.
    src=row['source_id'];n=row['bytes'];path=row['path']
    iso=formats.IsoReader(path) if row['system']=='iso9660' else None
    if iso and iso.sector_size==2352:
        return {'status':'BLOCKED','reason':'RAW_SECTOR_DISC: TIM scan requires sector-aware file extraction; ISO file inventory remains available'}
    hits=formats.find_tims(path,max_count=MAX_TIMS_PER_SOURCE)
    ids=[]
    for offset,raw,fmt,w,h,rgba in hits:
        ids.append(_save_asset(con,row,output,offset,raw,'image',fmt,'STRUCTURALLY_VALIDATED',rgba,w,h,
                 {'method':'TIM structure validation','clut_alpha':'preview approximation, original CLUT retained'}))
    return {'status':'DONE','result':{'valid_tim_images':len(ids),'assets':ids,
             'scan_limit_bytes':min(n,formats.SCAN_BYTES_LIMIT),'whole_file_scanned':n<=formats.SCAN_BYTES_LIMIT}}


def _scan_md_tiles(con,row,output):
    """Heuristic tile previews, NEVER proof of graphics or compression format."""
    n=row['bytes'];ids=[]
    if n<=0x400:return {'status':'DONE','result':{'tile_candidates':0}}
    with open(row['path'],'rb') as f:
        stop=min(n,formats.SCAN_BYTES_LIMIT)
        for offset in range(0x200,stop-512+1,0x2000):
            if len(ids)>=MAX_TILES_PER_SOURCE:break
            f.seek(offset);raw=f.read(512)
            if len(raw)!=512:break
            zeros=raw.count(0)/len(raw)
            if zeros>0.65 or zeros<0.005:continue
            used=set(v for b in raw for v in (b>>4,b&15))
            if not (5<=len(used)<=16):continue
            count=Counter(raw)
            ent=-sum((c/len(raw))*math.log2(c/len(raw)) for c in count.values())
            if ent<2.8 or ent>7.8:continue
            w,h,rgba=render_md_tiles(raw)
            ids.append(_save_asset(con,row,output,offset,raw,'image_candidate',
                       'MD_4BPP_TILE_INTERPRETATION','HEURISTIC_UNVERIFIED',rgba,w,h,
                       {'method':'alignment+entropy candidate','entropy':round(ent,2),
                        'grayscale':'synthetic; actual CRAM palette unknown',
                        'warning':'May be code, compressed data or arbitrary bytes'}))
    return {'status':'DONE','result':{'tile_candidates':len(ids),'assets':ids,
            'note':'Candidates are NOT recovered artwork until palette/pointer evidence confirms them.'}}


def _inventory_iso(con,row,output):
    reader=formats.IsoReader(row['path'])
    if not reader.valid():return {'status':'BLOCKED','reason':'ISO9660 descriptor not readable'}
    try:
        listing=reader.files()
    except (OSError,ValueError) as exc:return {'status':'BLOCKED','reason':f'ISO directory unavailable: {exc}'}
    assets=[];errors=[]
    for item in listing:
        store.disc_file(con,row['source_id'],item['path'],item['extent'],item['size'],item['physical_offset'])
        # TIM files can exist in a raw 2352-byte/sector image. Decode through the ISO sector reader.
        if item['path'].upper().endswith('.TIM') and 20<=item['size']<=formats.MAX_ASSET_BYTES:
            try:
                raw=reader.read(item['extent'],0,item['size'])
                fmt,w,h,rgba,consumed=render_tim(raw)
                if consumed!=len(raw):raise ValueError('TIM file contains trailing bytes')
                # Logical file offset maps to its first physical sector; if 2352, bytes are not contiguous.
                if reader.sector_size==2048:
                    assets.append(_save_asset(con,row,output,item['physical_offset'],raw,'image',fmt,
                        'STRUCTURALLY_VALIDATED',rgba,w,h,{'disc_path':item['path'],'filesystem':'ISO9660'}))
                else:
                    # Save raw and PNG, but don't assert that non-contiguous sectors form a physical range.
                    asset_id=store.stable_id(row['source_id'],item['physical_offset'],len(raw),fmt)
                    dest=output/'assets'/row['source_id'][:16];dest.mkdir(parents=True,exist_ok=True)
                    raw_path=dest/(asset_id+'.tim');png_path=dest/(asset_id+'.png')
                    raw_path.write_bytes(raw);png_path.write_bytes(png_rgba(w,h,rgba))
                    store.asset(con,row['source_id'],item['physical_offset'],len(raw),'image',fmt,
                                'STRUCTURALLY_VALIDATED',hashlib.sha256(raw).hexdigest(),raw_path,png_path,
                                {'disc_path':item['path'],'filesystem':'ISO9660','raw_sector_interleaving':True})
                    assets.append(asset_id)
            except (OSError,ValueError) as exc:errors.append({'path':item['path'],'reason':str(exc)[:160]})
    return {'status':'DONE','result':{'iso_files':len(listing),'tim_assets_extracted':len(assets),
              'tim_failures':errors[:15],'sector_size':reader.sector_size,
              'truncated_listing':len(listing)>=5000}}


def _handle(con,row,job,output):
    kind=job['kind'];system=row['system']
    if kind=='probe_structure':
        _mark_structure(con,row)
        return {'status':'DONE','result':{'system':system,'detected_by':row['detected_by']}}
    if kind=='scan_tim':return _scan_tim(con,row,output)
    if kind=='scan_md_tiles':return _scan_md_tiles(con,row,output)
    if kind=='inventory_iso':return _inventory_iso(con,row,output)
    if kind=='link_code_to_assets':
        # Do not invent code/asset links from offsets or heuristics.
        n=con.execute('SELECT COUNT(*) FROM discovery_assets WHERE source_id=?',(row['source_id'],)).fetchone()[0]
        return {'status':'NEEDS_EVIDENCE','reason':
            f'{n} asset records; linking needs validated pointer refs, decompressor crossrefs or reference execution traces'}
    if kind=='investigate_unknown':
        return {'status':'NEEDS_ADAPTER','reason':
            'Unknown ranges retained; next work requires structural parser or execution evidence, not automatic relabeling'}
    return {'status':'NEEDS_ADAPTER','reason':'Unknown discovery worker: '+kind}


def schedule(con,output,budget=150,retry_failed=False):
    processed=[]
    for i in range(budget):
        candidates=list(con.execute('''SELECT * FROM discovery_tasks WHERE status='READY'
                   OR (? AND status='FAILED') ORDER BY priority DESC,updated_utc,task_id LIMIT 300''',(int(retry_failed),)))
        ready=None
        for job in candidates:
            deps=json.loads(job['dependencies'])
            if deps and any(not (x:=con.execute('SELECT status FROM discovery_tasks WHERE task_id=?',(dep,)).fetchone())
                            or x['status']!='DONE' for dep in deps):continue
            ready=job;break
        if ready is None:break
        row=con.execute('SELECT * FROM discovery_sources WHERE source_id=?',(ready['source_id'],)).fetchone()
        try:
            result=_handle(con,row,ready,output)
            status=result['status'];reason=result.get('reason','')
            store.state(con,ready['task_id'],status,reason,result.get('result'))
        except (OSError,ValueError,sqlite3.Error,IndexError,OverflowError) as error:
            status='FAILED';reason=type(error).__name__+': '+str(error)[:240]
            store.state(con,ready['task_id'],status,reason)
        processed.append({'task':ready['kind'],'source':row['display_name'] or Path(row['path']).name,
                          'status':status,'reason':reason})
    return processed


def ingest_function_campaign(con,campaign):
    """Import prior native-recovery evidence as *blocked follow-up tasks*, not new successes.

    This makes existing function failures discoverable and deduplicated in the
    autonomous backlog. It does not synthesize a call graph or execute code.
    """
    if not campaign:return {'imported':0,'unmatched':0,'reason':'No previous campaign provided'}
    data=json.loads(Path(campaign).read_text(encoding='utf-8'))
    if not str(data.get('schema','')).startswith('recomp-function-campaign-'):
        raise ValueError('Not a RecompDev function campaign')
    by_target={r['target_id']:r['source_sha256'] for r in con.execute('SELECT target_id,source_sha256 FROM targets')}
    known={r['source_id'] for r in con.execute('SELECT source_id FROM discovery_sources')}
    imported=0;unmatched=0;groups=Counter()
    for job in data.get('jobs',[]):
        src=by_target.get(job.get('target_id'))
        if not src or src not in known:
            unmatched+=1;continue
        entry=job.get('entry')
        if type(entry) is not int or entry<0:continue
        status=str(job.get('compile_status',''))
        block=str(job.get('blocker','')).strip().replace('\n',' ')[:350]
        if status.startswith('COMPILED_'):
            task_kind='verify_native_function';priority=75;state='NEEDS_EVIDENCE'
            reason=f'Native compilation evidence {status}; comparison requires realistic CPU/memory fixtures; {job.get("verification_status", "NOT_VERIFIED")}'
        elif 'delay_slot' in block:
            task_kind='implement_mips_delay_semantics';priority=82;state='NEEDS_CAPABILITY';reason='MIPS delay-slot semantics required; no unsafe fallback'
        elif 'external_call' in block:
            task_kind='resolve_function_dispatch';priority=78;state='NEEDS_CAPABILITY';reason='Missing safe cross-function dispatch and call target evidence'
        elif 'outside_function' in block:
            task_kind='corroborate_function_boundary';priority=79;state='NEEDS_EVIDENCE';reason='Resolve function ownership with Ghidra/Rizin independent evidence'
        else:
            task_kind='extend_semantic_lifter';priority=70;state='NEEDS_CAPABILITY';reason=block or status
        subject=f'{job["target_id"]}@0x{entry:08X}'
        # New evidence must retire stale classifications, not leave the same
        # function permanently blocked under an obsolete reason.
        with con:
            con.execute('''UPDATE discovery_tasks SET status='SUPERSEDED',
              reason='Superseded by later function-campaign classification', updated_utc=?
              WHERE source_id=? AND subject=? AND kind<>? AND status<>'SUPERSEDED' ''',
              (store.now(),src,subject,task_kind))
        ident=store.task(con,src,task_kind,subject,priority)
        # Unchanged report evidence doesn't reset an already-resolved task.
        row=con.execute('SELECT attempts,status FROM discovery_tasks WHERE task_id=?',(ident,)).fetchone()
        if row['attempts']==0 and row['status']=='READY':
            store.state(con,ident,state,reason,{'original_status':status,'entry':entry,
                        'verification_status':job.get('verification_status',''),
                        'reconciliation':job.get('reconciliation','')},increment=False)
        groups[task_kind]+=1;imported+=1
    # Prioritise capabilities with broader cross-function leverage. Deterministic
    # (never accumulates on repeat runs), based on actual imported blocker counts.
    base_priority={'verify_native_function':75,'implement_mips_delay_semantics':82,
        'resolve_function_dispatch':78,'corroborate_function_boundary':79,'extend_semantic_lifter':70}
    with con:
        for kind,count in groups.items():
            score=min(99,base_priority[kind]+int(4*math.log2(count+1)))
            con.execute('''UPDATE discovery_tasks SET priority=?
                   WHERE kind=? AND status NOT IN ('SUPERSEDED','DONE')''',(score,kind))
    return {'imported':imported,'unmatched':unmatched,'grouped_backlog':dict(groups),
            'note':'Function jobs are evidence-backed tasks, not new decompilation or parity passes.'}


def run(db,roots,files,output,budget=150,max_files=300,retry_failed=False,campaign=None):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    con=store.connect(db)
    warnings=[]
    try:
        paths=walk_sources(roots,files,max_files)
        print(f"DISCOVERY_INPUT_FILES={len(paths)}",flush=True)
        for path in paths:
            try:
                src,kind=identity(path)
                system,method,title=formats.probe(path)
                store.store_source(con,src,path,path.stat().st_size,kind,system,title or path.name,method)
                add_tasks(con,src,system)
            except (OSError,ValueError) as error:
                warnings.append({'source':str(path),'error':type(error).__name__+': '+str(error)[:180]})
        print(f"DISCOVERY_FINGERPRINTED={len(paths)};WARNINGS={len(warnings)}",flush=True)
        previous=ingest_function_campaign(con,campaign)
        print("DISCOVERY_TASK_SCHEDULER=RUNNING",flush=True)
        processed=schedule(con,output,budget,retry_failed)
        result=store.summary(con)
        result['run']={'sources_seen':len(paths),'tasks_executed':len(processed),'budget':budget,
                      'source_warnings':warnings,'previous_function_campaign':previous,'recent_jobs':processed[-150:]}
        report=output/'discovery-report.json'
        report.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print('DISCOVERY_REPORT='+str(report),flush=True)
        print('DISCOVERY_SOURCES='+str(len(result['sources'])),flush=True)
        print('DISCOVERY_ASSETS='+str(len(result['assets'])),flush=True)
        print('DISCOVERY_STATUS='+json.dumps(result['task_status_counts'],sort_keys=True),flush=True)
        return result
    finally:con.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',required=True)
    p.add_argument('--source-root',action='append',default=[])
    p.add_argument('--source',action='append',default=[])
    p.add_argument('--output',required=True)
    p.add_argument('--budget',type=int,default=150)
    p.add_argument('--max-files',type=int,default=300)
    p.add_argument('--retry-failed',action='store_true')
    p.add_argument('--campaign',help='Optional prior function campaign JSON to import as discovery tasks')
    args=p.parse_args()
    if not args.source and not args.source_root:p.error('provide --source or --source-root')
    if not 1<=args.budget<=5000 or not 1<=args.max_files<=1000:p.error('invalid bounds')
    run(args.db,args.source_root,args.source,args.output,args.budget,args.max_files,args.retry_failed,args.campaign)

if __name__=='__main__':main()
