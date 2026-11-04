"""Bounded Master System/Z80 native pilot: compile verified Z80 P-code to C++ and trace.

Not a game emulator: missing code/unsupported semantics are explicit stop reasons.
Never uploads original game ROM bytes or writes to the ROM source.
"""
import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
from datetime import datetime,timezone
from pathlib import Path
from nativepilot.generator import generate_project,sha256,verify_export
from nativecore.adapters import provider_for
from nativecore.registry import capabilities
from nativecore.recovery import classify,RecoveryPlanner
from nativecore.dependencies import save_graph, frontier, reachable_branch_frontier
from nativecore.parity import compare as compare_parity
from nativecore.divergence import diagnose as diagnose_divergence
from nativecore.eventstream import manifest_for_native
from nativeprep.engine import SCHEMA as PREP_SCHEMA
from discovery.store import SCHEMA as DISCOVERY_SCHEMA

SCHEMA='''
CREATE TABLE IF NOT EXISTS native_bank_evidence_v0405 (
 source_id TEXT NOT NULL, slot INTEGER NOT NULL, bank INTEGER NOT NULL,
 entry_pc INTEGER NOT NULL, export_path TEXT NOT NULL, updated_utc TEXT NOT NULL,
 PRIMARY KEY(source_id,slot,bank,entry_pc)
);
CREATE TABLE IF NOT EXISTS native_pilots_v0404 (
 source_id TEXT PRIMARY KEY, target_id TEXT NOT NULL, status TEXT NOT NULL,
 translated_instructions INTEGER NOT NULL DEFAULT 0, native_steps INTEGER NOT NULL DEFAULT 0,
 blocker TEXT NOT NULL DEFAULT '', report_path TEXT NOT NULL DEFAULT '',
 updated_utc TEXT NOT NULL
);
'''

def in_roots(path,roots):
    p=Path(path).resolve()
    return bool(roots) and any(p==Path(r).resolve() or Path(r).resolve() in p.parents for r in roots)

def _build(project,timeout=180):
    build=project/'build'
    conf=subprocess.run(['cmake','-S',str(project),'-B',str(build),'-DCMAKE_BUILD_TYPE=Release'],
                        text=True,capture_output=True,timeout=60,errors='replace')
    if conf.returncode:raise RuntimeError('CMake configure failed: '+(conf.stdout+'\n'+conf.stderr)[-3000:])
    result=subprocess.run(['cmake','--build',str(build),'--config','Release','--parallel','2'],
                          text=True,capture_output=True,timeout=timeout,errors='replace')
    if result.returncode:raise RuntimeError('Native compilation failed: '+(result.stdout+'\n'+result.stderr)[-4000:])
    candidates=list(build.glob('**/RecompDevNativePilot.exe'))+list(build.glob('**/RecompDevNativePilot'))
    if not candidates:raise RuntimeError('Native executable missing after successful CMake build')
    return candidates[0],(conf.stdout+'\n'+result.stdout+'\n'+result.stderr)[-24000:]

def classify_native_process_exit(returncode, stdout='', stderr=''):
    """Classify *host process* failure separately from guest-code blockers.

    Windows NTSTATUS is printed unsigned even though subprocess returncode may
    be signed. Compilation success must never be relabelled as run success.
    """
    if returncode == 0:
        return None
    code=returncode & 0xffffffff
    cause='HOST_STACK_OVERFLOW' if code == 0xc00000fd else 'NATIVE_PROCESS_NONZERO_EXIT'
    evidence=(stdout+'\n'+stderr).strip()[-600:]
    return f'{cause}: exit_signed={returncode} exit_hex=0x{code:08X}' + (f'; output={evidence}' if evidence else '')


def cache_evidence_roots(install_root):
    """Only this installation and a bounded set of prior verified owner installations.

    The older SQLite snapshot retains absolute export paths. Never trust such a
    path based on the database alone: only read from these fixed roots, then
    authenticate every instruction against the original ROM bytes.
    """
    install_root=Path(install_root).resolve()
    return tuple((base/'evidence'/f'native-pilot-v{tag}'/'jobs').resolve()
                 for base,tag in ((install_root,'0424'),(install_root.parent/'RecompDev-v0.4.0.23','0423'),(install_root.parent/'RecompDev-v0.4.0.22','0422'),(install_root.parent/'RecompDev-v0.4.0.21','0421'),(install_root,'0420'),(install_root,'0414'),(install_root.parent/'RecompDev-v0.4.0.14','0414'),(install_root.parent/'RecompDev-v0.4.0.13','0413'),(install_root.parent/'RecompDev-v0.4.0.12','0412'),(install_root.parent/'RecompDev-v0.4.0.11','0411'),(install_root.parent/'RecompDev-v0.4.0.10','0410'),(install_root.parent/'RecompDev-v0.4.0.9','0409'),(install_root.parent/'RecompDev-v0.4.0.8','0408'),(install_root.parent/'RecompDev-v0.4.0.7','0407'),(install_root.parent/'RecompDev-v0.4.0.6','0406'),(install_root.parent/'RecompDev-v0.4.0.5','0405')))


def cache_path_trusted(path,install_root):
    p=Path(path).resolve()
    return any(root in p.parents for root in cache_evidence_roots(install_root))


def summarize_trace(trace):
    """Observational loop / hardware telemetry, never an assertion of parity."""
    top=trace.get('hotspots',[])
    steps=trace.get('native_steps',0)
    if not isinstance(top,list):top=[]
    hottest=sorted((x for x in top if isinstance(x,dict) and type(x.get('count'))==int),
                   key=lambda x:x['count'],reverse=True)[:8]
    hotspot_share=sum(x['count'] for x in hottest[:2])/max(1,steps)
    checkpoints=trace.get('checkpoints',[])
    return {'hotspot_top_two_share':round(hotspot_share,4),
            'repetitive_execution_observed':bool(steps>=10000 and hotspot_share>=0.75),
            'loop_not_proven_infinite':True,
            'checkpoints_recorded':len(checkpoints) if isinstance(checkpoints,list) else 0,
            'first_vdp_port_step':trace.get('first_vdp_port_step',0),
            'first_vdp_data_step':trace.get('first_vdp_data_step',0),
            'vdp_control_writes':trace.get('vdp_control_writes',0),
            'vdp_data_writes':trace.get('vdp_data_writes',0),
            'first_psg_step':trace.get('first_psg_step',0),
            'reference_parity':'NOT_TESTED',
            'vblank_events':trace.get('vblank_events',0),
            'maskable_interrupts':trace.get('maskable_interrupts',0),
            'watched_memory':trace.get('watched_memory',[]),
            'c001_reads':trace.get('c001_reads',0),
            'c001_nonzero_writes':trace.get('c001_nonzero_writes',0),
            'vram_nonzero_bytes':trace.get('vram_nonzero_bytes',0),
            'cram_nonzero_bytes':trace.get('cram_nonzero_bytes',0)}


def observable_progress(trace):
    """Conservative *hint*, not an infinite-loop detector or reference proof.

    Ignore clock ticks alone. Require sampled processor-state change or
    nontrivial device / RAM effects. The run is always bounded by the owner cap.
    """
    cps=trace.get('checkpoints',[])
    if not isinstance(cps,list) or len(cps)<2:return False
    first=cps[-2];last=cps[-1]
    if not isinstance(first,dict) or not isinstance(last,dict):return False
    keys=('pc','af','bc','de','hl','sp','mapper','ram_writes','vram_writes','cram_writes','psg_writes','io_writes','irqs')
    return any(first.get(k)!=last.get(k) for k in keys)


def budget_plan(cap,adaptive):
    if type(cap)!=int or not 1<=cap<=2000000 or type(adaptive)!=bool:
        raise ValueError('Invalid bounded adaptive execution configuration')
    if not adaptive:return [cap]
    budget=min(cap,50000)
    plan=[budget]
    while budget<cap:
        budget=min(cap,budget*2)
        plan.append(budget)
    return plan

def pilot(db,source_id,output,allowed_roots,max_steps=50000,compile_native=True,max_recoveries=2,recovery_function=None,watch_addresses=(),batch_prefetch=0,reference=None,adaptive=False,input_events=None):
    db=Path(db).resolve();output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    result={'schema':'recomp-native-pilot-v0.4.0.24','source_id':source_id,'target_id':None,
            'status':'PENDING','blocker':'','translated_instructions':0,'native_steps':0,
            'native_project':str(output/'native-project'),'executable':None,'trace':None,
            'reference_parity':'NOT_TESTED','reference_check':None,'divergence_diagnosis':None,'dependency_graph':None,'dependency_frontier':[],'prefetch_attempts':[],'gameplay':'NOT_ESTABLISHED',
            'recovery_attempts':[],'bank_overlays':[],'execution_diagnostics':{},'watch_addresses':list(watch_addresses),'max_steps':max_steps,'max_recoveries':max_recoveries,'max_batch_prefetch':batch_prefetch,'reused_bank_exports':0,'adaptive_execution':adaptive,'budget_history':[],
            'runtime_scope':'Master System mapper + basic VDP/PSG port effects; experimental VBlank / IM0/IM1 IRQ with approximate frame timing; no full parity or verified frame rendering.'}
    if not isinstance(watch_addresses,(list,tuple)) or len(watch_addresses)>8 or any(type(a)!=int or not 0xc000<=a<=0xffff for a in watch_addresses):
        raise ValueError('Watchpoints must be at most eight 16-bit system RAM addresses')
    if type(batch_prefetch)!=int or not 0<=batch_prefetch<=2:
        raise ValueError('Batch prefetch budget must be 0..2')
    if type(max_steps)!=int or not 1<=max_steps<=2000000:
        raise ValueError('Step budget must be an integer from 1 to 2000000')
    plans=budget_plan(max_steps,adaptive)
    input_file=None;input_sha=None
    if input_events is not None:
        input_file=Path(input_events).resolve(strict=True)
        if not input_file.is_file() or input_file.is_symlink() or input_file.stat().st_size>1024*1024:
            raise ValueError('Invalid bounded input replay file')
        input_sha=sha256(input_file)
        result['input_replay']={'schema':'RECOMP_INPUT_CYCLES_V1','sha256':input_sha,
                               'source_path':str(input_file),'status':'OWNER_INPUT_UNVERIFIED_FOR_PARITY'}
    con=sqlite3.connect(str(db),timeout=30);con.row_factory=sqlite3.Row
    con.executescript(DISCOVERY_SCHEMA);con.executescript(PREP_SCHEMA);con.executescript(SCHEMA)
    try:
        row=con.execute('''SELECT s.path,s.bytes,s.source_hash_kind,s.system,p.target_id,p.source_sha256,p.export_path,p.candidate_count
         FROM discovery_sources s LEFT JOIN native_preparations_v0403 p ON p.source_id=s.source_id
         WHERE s.source_id=?''',(source_id,)).fetchone()
        if row is None:raise ValueError('ROM must first be imported with Autonomous Discovery')
        capability=capabilities(row['system']);result['capability']=capability
        if not capability['native_execution']:
            raise ValueError('Native execution adapter not integrated for '+row['system']+'; prepare/analyse are available separately')
        path=Path(row['path']).resolve()
        if not in_roots(path,allowed_roots):raise ValueError('ROM is outside configured local library')
        if not path.is_file() or path.stat().st_size!=row['bytes']:
            raise ValueError('Original ROM size changed or file is missing')
        if row['source_hash_kind']!='SHA256_COMPLETE' or sha256(path)!=source_id:
            raise ValueError('Original ROM SHA-256 changed, rediscover before generating code')
        result['target_id']=row['target_id']
        if not row['target_id'] or row['source_sha256']!=source_id:
            raise ValueError('Run Prepare for Native Recompilation on this game first')
        exported=Path(row['export_path']) if row['export_path'] else None
        if not exported or not exported.is_file():
            raise ValueError('Original Ghidra P-code export not available. Re-run native preparation in this installation.')
        if exported.stat().st_size>128*1024*1024:raise ValueError('Unbounded Ghidra evidence')
        # Exports from prior installations are permitted only after checking
        # their source hash and every instruction's original bytes.
        print('NATIVE_PILOT_STAGE=verify_original_rom_and_export',flush=True)
        doc=json.loads(exported.read_text(encoding='utf-8'))
        if doc.get('target_id')!=row['target_id']:
            raise ValueError('Ghidra target ID changed')
        if type(max_recoveries)!=int or not 0<=max_recoveries<=5:
            raise ValueError('Recovery budget must be an integer from 0 to 5')
        project=output/'native-project'
        bank_docs=[];planner=RecoveryPlanner(max_recoveries)
        # Reuse previous recovery evidence only from this version's owner-local
        # evidence root, reattesting ALL instructions against the current ROM.
        install_root=Path(__file__).resolve().parents[1]
        cached=con.execute('''SELECT slot,bank,entry_pc,export_path FROM native_bank_evidence_v0405
                               WHERE source_id=? ORDER BY updated_utc DESC LIMIT 50''',(source_id,)).fetchall()
        for record in cached:
            f=Path(record['export_path']).resolve()
            if not cache_path_trusted(f,install_root) or not f.is_file() or f.stat().st_size>64*1024*1024:continue
            try:
                bankdoc=json.loads(f.read_text(encoding='utf-8'))
                meta=bankdoc.get('bank_context',{})
                if meta.get('slot')!=record['slot'] or meta.get('bank')!=record['bank']:
                    continue
                if bankdoc.get('target_id')!=row['target_id']:continue
                verified,_,_=verify_export(bankdoc,path)
                if verified:
                    bank_docs.append(bankdoc)
                    result['reused_bank_exports']+=1
            except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError):continue
        if bank_docs:print(f'NATIVE_PILOT_STAGE=reuse_verified_banks count={len(bank_docs)}',flush=True)
        for attempt in range(max_recoveries+1):
            print(f'NATIVE_PILOT_STAGE=generate_static_cpp attempt={attempt}',flush=True)
            generated=generate_project(doc,path,project,bank_docs)
            result['dependency_graph']=save_graph(db,source_id,[doc]+bank_docs,path,row['system'])
            result['dependency_frontier']=frontier(db,source_id,12)
            (output/'dependency-graph-summary.json').write_text(json.dumps({'summary':result['dependency_graph'],'frontier':result['dependency_frontier']},indent=2)+'\n',encoding='utf-8')
            result['generation']=generated
            result['translated_instructions']=generated['translated_instructions']
            result['bank_overlays']=generated['recovered_bank_overlays']
            if not generated['translated_instructions']:
                result.update(status='NO_TRANSLATABLE_INSTRUCTIONS',blocker='No supported, source-attested P-code instructions');break
            if not compile_native:
                result.update(status='CPP_GENERATED_NOT_COMPILED',blocker='Compiled run disabled by caller');break
            if not shutil.which('cmake'):
                result.update(status='CMAKE_UNAVAILABLE',blocker='Install CMake on Windows PATH');break
            print(f'NATIVE_PILOT_STAGE=compile_native_cpp attempt={attempt}',flush=True)
            try:
                executable,log=_build(project)
                (output/'compiler.log').write_text(log,encoding='utf-8')
                result['executable']=str(executable)
                app_candidates=list((project/'build').glob('**/RecompDevNativeApp.exe'))+list((project/'build').glob('**/RecompDevNativeApp'))
                result['native_app']={'status':'EXPERIMENTAL_CONTINUOUS_HOST_NOT_REFERENCE_QUALIFIED',
                  'executable':str(app_candidates[0]) if app_candidates else None,
                  'run_command':'tools/Run-Continuous-Native.py',
                  'source_sha256':source_id}
                if sha256(path)!=source_id:raise RuntimeError('ROM changed during compilation; run refused')
                print(f'NATIVE_PILOT_STAGE=run_compiled_cpp attempt={attempt}',flush=True)
                preview=output/'diagnostic-background.ppm'
                observed=None
                for runtime_budget in plans:
                    # A retry replays from reset. Previous output files must never
                    # be mistaken for this attempt's verified event evidence.
                    stream_dir=output/'event-streams'/f'attempt-{attempt:02d}-budget-{runtime_budget}'
                    stream_dir.mkdir(parents=True,exist_ok=False)
                    stream_prefix=stream_dir/'hardware-events'
                    trace=subprocess.run([str(executable),str(path),str(runtime_budget),str(preview),str(output/'hardware-state'),','.join(hex(a) for a in watch_addresses),str(stream_prefix),str(stream_dir/'candidate-audio.wav'),str(input_file) if input_file else ''],
                                         capture_output=True,text=True,timeout=75,errors='replace')
                    trace_text=trace.stdout+'\n'+trace.stderr
                    (output/'execution.log').write_text(trace_text,encoding='utf-8')
                    (output/f'execution-attempt-{attempt:02}-budget-{runtime_budget}.log').write_text(trace_text,encoding='utf-8')
                    (output/f'execution-attempt-{attempt:02}.log').write_text(trace_text,encoding='utf-8')
                    match=re.search(r'^PILOT_RESULT=(\{.*\})$',trace.stdout,re.M)
                    exit_failure=classify_native_process_exit(trace.returncode,trace.stdout,trace.stderr)
                    if exit_failure:raise RuntimeError(exit_failure)
                    if not match:raise RuntimeError('NATIVE_RESULT_MISSING_AFTER_ZERO_EXIT; output='+trace_text[-600:])
                    if input_file and sha256(input_file)!=input_sha:raise RuntimeError('Input replay changed during native execution')
                    observed=json.loads(match.group(1))
                    audio_wav=stream_dir/'candidate-audio.wav'
                    if audio_wav.is_file():
                        observed['audio_capture']={'status':'CANDIDATE_PSG_PCM_APPROXIMATE_NOT_REFERENCE_VERIFIED',
                           'sha256':sha256(audio_wav),'bytes':audio_wav.stat().st_size,
                           'path':str(audio_wav.relative_to(output)).replace('\\','/')}
                    else:
                        observed['audio_capture']={'status':'NOT_AVAILABLE'}
                    if type(observed.get('pc'))!=int or type(observed.get('mapper'))!=list:
                        raise RuntimeError('Invalid native runtime trace format')
                    import hashlib
                    digests={}
                    for part in ('vram','cram','vdp-registers'):
                        dump=output/('hardware-state-'+part+'.bin')
                        if dump.is_file():digests[part]=hashlib.sha256(dump.read_bytes()).hexdigest()
                    observed['hardware_sha256']=digests
                    if observed.get('event_stream_complete') is True:
                        manifest=manifest_for_native(stream_dir,observed)
                        observed['event_stream_manifest']=manifest
                        observed['event_stream_directory']=str(stream_dir.relative_to(output)).replace('\\','/')
                        (stream_dir/'event-stream-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
                    else:
                        # Failure is never silently promoted as full event coverage.
                        observed['event_stream_manifest']={'schema':'recomp-event-stream-manifest-v1','status':'INCOMPLETE'}
                        observed['status']='EVENT_STREAM_INCOMPLETE' if not str(observed.get('status','')).startswith('EVENT_STREAM_') else observed['status']
                    progress=observable_progress(observed)
                    result['budget_history'].append({'recovery_attempt':attempt,'step_budget':runtime_budget,
                         'executed':observed.get('native_steps'),'status':observed['status'],
                         'observable_state_change':progress,'events_total':observed.get('events_total'),
                         'event_stream_complete':observed.get('event_stream_complete') is True})
                    print(f'NATIVE_BUDGET_RESULT={runtime_budget};STEPS={observed.get("native_steps")};PROGRESS={progress};STATUS={observed["status"]}',flush=True)
                    if observed['status']!='STEP_BUDGET_REACHED' or not progress or runtime_budget>=max_steps:
                        break
                    print(f'NATIVE_PILOT_STAGE=adaptive_replay next_budget={min(max_steps,runtime_budget*2)}',flush=True)
                if observed is None:raise RuntimeError('No native execution observation')
                result['trace']=observed;result['native_steps']=observed.get('native_steps',0)
                result['execution_diagnostics']=summarize_trace(observed)
                if reference is not None:
                    try:
                        ref_path=Path(reference).resolve()
                        if not ref_path.is_file() or ref_path.stat().st_size>1024*1024:
                            raise ValueError('Independent reference file missing or exceeds 1 MB')
                        independent=json.loads(ref_path.read_text(encoding='utf-8'))
                        parity=compare_parity(independent,result,event_root=stream_dir,reference_root=ref_path.parent)
                        result['reference_check']=parity
                        result['reference_parity']=parity['status']
                        (output/'parity-report.json').write_text(json.dumps(parity,indent=2)+'\n',encoding='utf-8')
                        if parity['status']=='DIVERGED':
                            result['status']='REFERENCE_DIVERGENCE'
                            result['blocker']='Independent reference differs from native effects; inspect parity-report.json'
                            if independent.get('schema') in ('recomp-independent-event-trace-v1', 'recomp-independent-stream-reference-v1'):
                                try:
                                    diagnosis=diagnose_divergence(independent,result,event_root=stream_dir,reference_root=ref_path.parent)
                                    result['divergence_diagnosis']={k:diagnosis[k] for k in ('status','classification','suggested_investigation','first_event_divergence')}
                                    (output/'divergence-diagnosis.json').write_text(json.dumps(diagnosis,indent=2)+'\n',encoding='utf-8')
                                except (ValueError,OSError,KeyError,TypeError) as diagnostic_error:
                                    result['divergence_diagnosis']={'status':'DIAGNOSIS_UNAVAILABLE','reason':str(diagnostic_error)[:240]}
                            break
                        if parity['status'] in ('INCOMPLETE_EVENT_COVERAGE','INCOMPLETE_REFERENCE_COVERAGE'):
                            result['status']='REFERENCE_INCOMPLETE'
                            result['blocker']='Reference exceeds the recorded native evidence; inspect parity-report.json'
                            break
                    except (ValueError,OSError,KeyError,TypeError,json.JSONDecodeError) as exc:
                        result['reference_parity']='REFERENCE_REJECTED'
                        result['reference_check']={'status':'REFERENCE_REJECTED','reason':str(exc)[:300]}
                        result['status']='REFERENCE_REJECTED'
                        result['blocker']=str(exc)[:300]
                        break
                record={'attempt':attempt,'status':observed['status'],'native_steps':observed['native_steps'],
                        'pc':observed['pc'],'physical_offset':observed.get('physical_offset'),
                        'mapper':observed['mapper'],'translated_instructions':generated['translated_instructions'],
                        'top_hotspots':observed.get('hotspots',[])[:3],
                        'first_vdp_port_step':observed.get('first_vdp_port_step',0)}
                result['recovery_attempts'].append(record)
                if preview.is_file():
                    from nativepilot.preview import convert_ppm
                    png=output/'diagnostic-background.png';convert_ppm(preview,png)
                    result['preview_path']=str(png)
                    pixels=preview.read_bytes()[len(b'P6\n256 192\n255\n'):]
                    nonblack=sum(pixels[k:k+3]!=b'\x00\x00\x00' for k in range(0,len(pixels),3))
                    result['preview_diagnostics']={'nonblack_pixels':nonblack,'pixels':256*192,'verified_against_reference':False}
                result['status']='NATIVE_TRACE_STOPPED' if observed['status']!='STEP_BUDGET_REACHED' else 'NATIVE_STEP_BUDGET_REACHED'
                result['blocker']=observed['status']
                print(f'NATIVE_TRACE_STEPS={observed.get("native_steps",0)};PC=0x{observed["pc"]:04x};PSG={observed.get("psg_writes",0)};VDP={observed.get("vdp_control_writes",0)+observed.get("vdp_data_writes",0)}',flush=True)
                target=classify(row['system'],path.stat().st_size,observed)
                if target is None:break
                choice=planner.claim(target)
                if choice!='RECOVERY_QUEUED':
                    record['recovery']=choice;break
                context={'slot':target.slot,'bank':target.bank,'entry_pc':target.entry_pc,'entry_physical':target.physical_offset}
                record['recovery_target']=target.record()
                bank_dir=output/'recovery'/f'attempt-{attempt+1:02}-{target.region}-slot{target.slot}-bank{target.bank:02x}'
                print(f'NATIVE_PILOT_STAGE=recover_missing_code region={target.region} slot={target.slot} bank={target.bank} pc=0x{observed["pc"]:04x}',flush=True)
                try:
                    analyzer=recovery_function or provider_for(row['system']).recover
                    bank_doc,recovered=analyzer(path,source_id,row['target_id'],observed['pc'],observed['mapper'],bank_dir)
                    # Authenticate before saving persistent evidence.
                    verified,_,_=verify_export(bank_doc,path)
                    if not verified:raise ValueError('Recovered bank has no attested instruction evidence')
                    bank_docs.append(bank_doc)
                    record['recovery']='BANK_SOURCE_VERIFIED' if target.region=='mapped-rom-bank' else 'CODE_SOURCE_VERIFIED';record['recovery_evidence']=recovered
                    with con:
                        con.execute('''INSERT INTO native_bank_evidence_v0405 VALUES(?,?,?,?,?,?)
                            ON CONFLICT(source_id,slot,bank,entry_pc)
                            DO UPDATE SET export_path=excluded.export_path,updated_utc=excluded.updated_utc''',
                            (source_id,context['slot'],context['bank'],context['entry_pc'],
                             str((bank_dir/'bank-functions.json').resolve()),datetime.now(timezone.utc).isoformat()))
                    # Recover a *bounded* set of direct branch dependencies before
                    # recompilation. Every candidate must be source mapped and every
                    # additional export must pass the same ROM byte authentication.
                    if batch_prefetch:
                        known=set()
                        for d in [doc]+bank_docs:
                            verified,_,_=verify_export(d,path)
                            known.update(verified)
                        candidates=reachable_branch_frontier([bank_doc],path,row['system'],target.physical_offset,known,batch_prefetch)
                        taken=set()
                        for e in candidates:
                            if len(taken)>=batch_prefetch:break
                            pc=e['to_pc'];phys=e['to_physical']
                            if phys in taken:continue
                            # Branch targets in a different bank must await actual
                            # mapper evidence. Never guess future mapper state.
                            from nativepilot.recovery import bank_context
                            if bank_context(path.stat().st_size,pc,observed['mapper'])['entry_physical']!=phys:continue
                            taken.add(phys)
                            prefetch_dir=bank_dir/('prefetch-%06x'%phys)
                            item={'from_physical':e['from_physical'],'logical_pc':pc,'physical_offset':phys}
                            try:
                                extra,extra_meta=analyzer(path,source_id,row['target_id'],pc,observed['mapper'],prefetch_dir)
                                extra_verified,_,_=verify_export(extra,path)
                                if phys not in extra_verified:raise ValueError('Prefetched branch entry not attested')
                                bank_docs.append(extra)
                                item.update(status='SOURCE_BYTES_VERIFIED',instructions=len(extra_verified))
                                with con:
                                    bc=extra.get('bank_context') or {}
                                    con.execute('''INSERT INTO native_bank_evidence_v0405 VALUES(?,?,?,?,?,?)
                                        ON CONFLICT(source_id,slot,bank,entry_pc)
                                        DO UPDATE SET export_path=excluded.export_path,updated_utc=excluded.updated_utc''',
                                        (source_id,bc['slot'],bc['bank'],pc,str((prefetch_dir/'bank-functions.json').resolve()),datetime.now(timezone.utc).isoformat()))
                            except (ValueError,OSError,RuntimeError,KeyError,TypeError,subprocess.TimeoutExpired) as exc:
                                item.update(status='PREFETCH_BLOCKED',reason=str(exc)[:200])
                            result['prefetch_attempts'].append(item)
                except (RuntimeError,ValueError,OSError,subprocess.TimeoutExpired) as exc:
                    record['recovery']='BLOCKED';record['recovery_blocker']=str(exc)[:400]
                    diagnostics=bank_dir/'entry-diagnostics.json'
                    if diagnostics.is_file():
                        try:record['recovery_diagnostic']=json.loads(diagnostics.read_text(encoding='utf-8'))
                        except (OSError,ValueError):pass
                    result['blocker']=observed['status']+'; '+str(exc)[:240]
                    print('NATIVE_PILOT_RECOVERY_BLOCKER='+str(exc)[:250],flush=True)
                    break
            except (OSError,RuntimeError,subprocess.TimeoutExpired) as exc:
                result.update(status='NATIVE_BUILD_OR_RUN_FAILED',blocker=str(exc)[-600:]);break
    except (ValueError,OSError,KeyError,json.JSONDecodeError) as exc:
        result.update(status='PILOT_BLOCKED',blocker=str(exc)[:600])
    finally:
        result['report_path']=str(output/'pilot-report.json')
        result['timestamp_utc']=datetime.now(timezone.utc).isoformat()
        (output/'pilot-report.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        if result['target_id']:
            with con:con.execute('''INSERT INTO native_pilots_v0404 VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(source_id) DO UPDATE SET target_id=excluded.target_id,
                status=excluded.status,translated_instructions=excluded.translated_instructions,
                native_steps=excluded.native_steps,blocker=excluded.blocker,
                report_path=excluded.report_path,updated_utc=excluded.updated_utc''',
                (source_id,result['target_id'],result['status'],result['translated_instructions'],
                 result['native_steps'],result['blocker'],result['report_path'],result['timestamp_utc']))
        con.close()
    print('NATIVE_PILOT_STATUS='+result['status'],flush=True)
    print('NATIVE_PILOT_REPORT='+result['report_path'],flush=True)
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--db',required=True);p.add_argument('--source-id',required=True)
    p.add_argument('--output',required=True);p.add_argument('--allowed-root',action='append',default=[])
    p.add_argument('--max-steps',type=int,default=50000);p.add_argument('--max-recoveries',type=int,default=2);p.add_argument('--generate-only',action='store_true')
    p.add_argument('--watch',action='append',type=lambda s:int(s,0),default=[])
    p.add_argument('--batch-prefetch',type=int,default=0,choices=(0,1,2))
    p.add_argument('--reference',help='Optional ROM-hash-bound external checkpoint or ordered event trace JSON')
    p.add_argument('--input-events',help='Optional bounded RECOMP_INPUT_CYCLES_V1 input replay CSV (owner-authored)')
    p.add_argument('--adaptive',action='store_true',help='Replay from reset using 50K, 100K ... steps up to --max-steps, only on observable progress')
    a=p.parse_args()
    if not 1<=a.max_steps<=2000000:p.error('max steps must be 1..2000000')
    if not 0<=a.max_recoveries<=5:p.error('max recoveries must be 0..5')
    result=pilot(a.db,a.source_id,a.output,a.allowed_root,a.max_steps,not a.generate_only,a.max_recoveries,watch_addresses=a.watch,batch_prefetch=a.batch_prefetch,reference=a.reference,adaptive=a.adaptive,input_events=a.input_events)
    if result['status'] in ('PILOT_BLOCKED','NATIVE_BUILD_OR_RUN_FAILED','NO_TRANSLATABLE_INSTRUCTIONS'):
        raise SystemExit(2)
if __name__=='__main__':main()
