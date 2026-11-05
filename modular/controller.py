"""v0.4.1 generic controller: restore genuine RecompDev workflows without a rewrite.

Every run has a fresh catalogue snapshot and evidence folder. The preserved
v0.4.0.45 source and original data catalogues remain immutable.
"""
from __future__ import annotations
import hashlib
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from migration import controller as preservation
from modular.plugins import legacy
from modular import recovery_manager, hardware_review, cpu_production

LEGACY = preservation.LEGACY
DEFAULT_DB = LEGACY / 'catalogue.sqlite'

def default_catalogue():
    # Reuse richer owner-local history WITHOUT EVER writing to it. If absent,
    # use the preserved packaged catalogue as an explicit fallback.
    owner = ROOT.parent / 'RecompDev-Data' / 'catalogue.sqlite'
    return owner if owner.is_file() else DEFAULT_DB


def authentic_rom(path, native_required=True):
    rom = Path(path).resolve(strict=True)
    if not rom.is_file() or rom.stat().st_size <= 0:
        raise ValueError('A nonempty ROM file is required')
    # Original discovery supports larger sampled-disc inputs; native preparation
    # requires a full hash and enforces a separate 64-MiB native limit.
    if native_required and rom.stat().st_size > 64 * 1024 * 1024:
        raise ValueError('Source exceeds original v0.4.0.45 native-preparation limit (64 MiB); use --stage discover')
    return rom


def prepare_workspace(out, db_source):
    out = Path(out).resolve()
    if out.exists():
        raise ValueError('Evidence destination already exists; refusing overwrite: '+str(out))
    if out == LEGACY.resolve() or LEGACY.resolve() in out.parents:
        raise ValueError('Evidence cannot be written into preserved v0.4.0.45 source')
    if out == Path(db_source).resolve() or out in Path(db_source).resolve().parents:
        raise ValueError('Evidence output overlaps source database')
    out.mkdir(parents=True,exist_ok=False)
    working = out / 'working-catalogue.sqlite'
    preservation.catalogue_snapshot(db_source,working)
    return out,working


def run_rom(rom, out, stage='prepare', database=None, budget=150, steps=200000,
            frames=120, recoveries=2, ghidra='', export='', capture=False,
            timeout=720, input_events='', history_roots=(),auto_continue=True,max_rounds=3,
            reference_image=None,reference_session=None,cpu_plugin_mode="auto"): 
    """Drive real legacy discovery -> Ghidra/native prep -> optional native recovery.

    All services run in standalone subprocesses; no unverified fallback rewrite.
    Missing Ghidra/export is an honest BLOCKED status with evidence and exit code.
    """
    if stage not in ('discover','prepare','recover'):
        raise ValueError('Unknown stage')
    if not (1 <= budget <= 5000 and 1 <= steps <= 20000000 and 1 <= frames <= 36000
            and 0 <= recoveries <= 24 and 30 <= timeout <= 7200
            and 1 <= max_rounds <= 12):
        raise ValueError('Invalid execution/campaign limits')
    if stage == 'recover' and not export and not ghidra:
        # Ghidra may still be discoverable through original nativeprep.locate_ghidra.
        pass
    rom = authentic_rom(rom,native_required=stage!='discover')
    source_db = Path(database or default_catalogue()).resolve(strict=True)
    src_sha = preservation.sha(rom)
    src_sha_db_before = preservation.sha(source_db)
    output, working = prepare_workspace(out,source_db)
    report = {'schema':'recompdev-modular-pipeline-v0.4.2','source':str(rom),
              'source_sha256':src_sha,'requested_stage':stage,'source_catalogue':str(source_db),
              'source_catalogue_sha256_before':src_sha_db_before,
              'working_catalogue':str(working),'services':[],
              'status':'PENDING','native_gameplay_parity':'NOT_ESTABLISHED',
              'source_rom_copied':False,'production_catalogue_mutated':False}
    def step(pid,args,dirname,t):
        folder = output/dirname
        folder.mkdir(exist_ok=False)
        result=legacy.invoke(pid,args,folder,timeout=t)
        report['services'].append(result)
        return result
    try:
        discovery_dir=output/'discovery'
        result=step('legacy.discovery', ['--db',working,'--source',rom,'--output',discovery_dir,
                                         '--budget',str(budget),'--max-files','1'], 'discovery-stage',timeout)
        if result['return_code'] != 0:
            report['status']='DISCOVERY_FAILED'
        elif not (discovery_dir/'discovery-report.json').is_file():
            report['status']='DISCOVERY_REPORT_MISSING'
        elif stage=='discover':
            report['status']='DISCOVERY_COMPLETE'
        else:
            # The genuine preparation service uses Ghidra if available, not a stub.
            prep_dir=output/'preparation'
            prep_args=['--db',working,'--source-id',src_sha,'--output',prep_dir,
                       '--allowed-root',rom.parent]
            if ghidra: prep_args += ['--ghidra-exe',str(Path(ghidra).resolve())]
            if export: prep_args += ['--no-analysis']
            prep=step('legacy.preparation',prep_args,'preparation-stage',timeout)
            prep_report=prep_dir/'preparation-report.json'
            if prep['return_code'] != 0 or not prep_report.is_file():
                report['status']='PREPARATION_FAILED'
            else:
                doc=json.loads(prep_report.read_text(encoding='utf8'))
                report['preparation_status']=doc.get('status')
                report['cpu']=doc.get('cpu')
                report['system']=doc.get('system')
                report['ghidra_candidates']=doc.get('candidates')
                if stage=='prepare':
                    report['status']='PREPARATION_COMPLETE' if doc.get('status') in ('CANDIDATES_RECOVERED_TRANSLATOR_NEEDED','PREVIOUS_CANDIDATES_RETAINED') else 'PREPARATION_BLOCKED'
                else:
                    source_export = Path(export).resolve(strict=True) if export else Path(doc.get('ghidra_export') or '')
                    if not source_export.is_file():
                        report['status']='RECOVERY_BLOCKED_NO_AUTHENTICATED_EXPORT'
                    else:
                        # Identity/byte preflight uses the original v0.4.0.45 verifier.
                        evidence = preservation.pcode_verify(rom,source_export,[])
                        report['authenticated_export'] = evidence
                        # A selected active DLL participates in the REAL production
                        # hand-off: every source-attested instruction must be admitted
                        # before any legacy native compilation is launched.
                        try:
                            if report['cpu'] != 'z80':
                                if cpu_plugin_mode == 'required':
                                    raise cpu_production.GateError('NO_CPU_SOURCE_GATE_REGISTERED_FOR_'+str(report['cpu']))
                                report['production_cpu_gate'] = {
                                    'status':'LEGACY_FALLBACK_OTHER_CPU', 'cpu':report['cpu'],
                                    'selected_plugin':None}
                                (output/'production-cpu-gate.json').write_text(
                                    json.dumps(report['production_cpu_gate'],indent=2,sort_keys=True)+'\n',encoding='utf8')
                            else:
                                report['production_cpu_gate'] = cpu_production.admit(
                                    rom, source_export, root=ROOT, mode=cpu_plugin_mode,
                                    output=output/'production-cpu-gate.json')
                        except cpu_production.GateError as gate_error:
                            report['production_cpu_gate'] = {
                                'status':'BLOCKED', 'reason':str(gate_error),
                                'selected_mode':cpu_plugin_mode}
                            report['status']='RECOVERY_BLOCKED_CPU_PLUGIN'
                            (output/'production-cpu-gate.json').write_text(
                                json.dumps(report['production_cpu_gate'],indent=2,sort_keys=True)+'\n',encoding='utf8')
                        if report['status']!='RECOVERY_BLOCKED_CPU_PLUGIN':
                            rec_dir=output/'recovery'
                            rec_args=['--rom',rom,'--export',source_export,
                                      '--frames',str(frames),'--steps',str(steps),
                                      '--max-recoveries',str(recoveries),'--compile-timeout',str(max(30,min(timeout,1800))),
                                      '--no-history-import','--coverage-cache',output/'coverage-working.sqlite']
                            if capture: rec_args.append('--capture-hardware')
                            if input_events: rec_args += ['--input-events',str(Path(input_events).resolve(strict=True))]
                            for history in history_roots: rec_args += ['--history-root',str(Path(history).resolve(strict=True))]
                            summary,services=recovery_manager.run_bounded(
                                legacy.invoke,rec_args,rec_dir,output/'recovery-stage',
                                auto_continue=auto_continue,max_rounds=max_rounds,
                                timeout=timeout,capture=capture)
                            report['services'].extend(services)
                            report['production_translation']=summary.get('production_translation',{'status':'NOT_RUN'})
                            report['legacy_recovery_status']=summary['last_legacy_status']
                            report['legacy_native_steps']=summary['maximum_steps_observed']
                            report['maximum_frames_observed']=summary['maximum_frames_observed']
                            report['recovered_entries']=summary['recovered_entries']
                            report['recovery_rounds']=summary['rounds_completed']
                            report['recovery_stop_reason']=summary['stop_reason']
                            report['hardware_diagnostics']=summary['hardware']
                            report['recovery_report']=str(rec_dir/'continuous-recovery-report.json')
                            report['status']='RECOVERY_REPORTED' if summary['status']=='CONTINUOUS_SESSION_COMPLETE' else 'RECOVERY_LIMITED_OR_BLOCKED'
        report['source_image_unchanged']=preservation.sha(rom)==src_sha
        report['production_catalogue_mutated']=preservation.sha(source_db)!=src_sha_db_before
        if not report['source_image_unchanged'] or report['production_catalogue_mutated']:
            report['status']='INTEGRITY_VIOLATION'
    except Exception as exc:
        report['status']='ERROR'
        report['error']=f'{type(exc).__name__}: {exc}'
    finally:
        if stage=='recover' and capture and (output/'recovery').is_dir():
            try:
                report['hardware_review']=hardware_review.analyze_evidence(
                    output,output/'hardware-review',
                    reference_image=reference_image, reference_session=reference_session)
                report['hardware_review_report']=str(output/'hardware-review'/'hardware-review.json')
            except Exception as review_error:
                report['hardware_review']={'status':'REVIEW_FAILED','error':f'{type(review_error).__name__}: {review_error}'}
        report['working_catalogue_sha256']=preservation.sha(working) if working.is_file() else None
        (output/'controller-report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf8')
    return report


def discovery_fingerprint(db, source_id):
    """Canonical rows only: ignore timestamps, file locations and run IDs."""
    with closing(sqlite3.connect(Path(db).resolve().as_uri()+'?mode=ro',uri=True)) as con:
        def rows(sql): return [tuple(x) for x in con.execute(sql,(source_id,)).fetchall()]
        return {
          'sources':rows('SELECT source_id,bytes,source_hash_kind,system,detected_by FROM discovery_sources WHERE source_id=? ORDER BY source_id'),
          'regions':rows('SELECT claim_id,start,length,category,status,evidence FROM discovery_regions WHERE source_id=? ORDER BY claim_id'),
          'tasks':rows('SELECT task_id,kind,subject,priority,status,dependencies,attempts,reason,result,worker_version FROM discovery_tasks WHERE source_id=? ORDER BY task_id'),
          'assets':rows('SELECT asset_id,offset,length,kind,format,confidence,original_sha256,evidence FROM discovery_assets WHERE source_id=? ORDER BY asset_id'),
          'disc_files':rows('SELECT file_id,disc_path,extent,bytes,physical_offset FROM discovery_disc_files WHERE source_id=? ORDER BY file_id'),
        }


def run_campaign(rom_dir, out, database=None, frames=120, steps=200000,
                 recoveries=2, compile_timeout=600, capture=False, timeout=3600):
    """Actual seven-game v0445 orchestration in an isolated clone of the original.

    Never run the campaign in the preserved source: the original is designed to
    create evidence under its --root and bootstraps shared data relative to root.
    """
    import shutil
    rom_dir=Path(rom_dir).resolve(strict=True)
    if not rom_dir.is_dir(): raise ValueError('ROM directory required')
    if not 1<=frames<=36000 or not 1<=steps<=20000000 or not 0<=recoveries<=24:
        raise ValueError('Invalid campaign limits')
    if not 30<=compile_timeout<=1800 or not 60<=timeout<=7200:
        raise ValueError('Invalid campaign timeout')
    source_db=Path(database or default_catalogue()).resolve(strict=True)
    dbhash=preservation.sha(source_db)
    out,working=prepare_workspace(out,source_db)
    clone=out/'legacy-campaign-sandbox'
    shutil.copytree(LEGACY,clone,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    run_dir=out/'campaign-stage'
    run_dir.mkdir()
    args=['--root',clone,'--rom-dir',rom_dir,'--frames',frames,
          '--steps',steps,'--max-recoveries',recoveries,
          '--compile-timeout',compile_timeout,'--no-history-import']
    if not capture: args.append('--no-capture')
    invocation=legacy.invoke('legacy.sms-campaign',args,run_dir,timeout,
                             extra_env={'RECOMPDEV_CATALOGUE':str(working)})
    summary_paths=sorted((clone/'evidence').glob('sms-seven-v0445-*/campaign-summary.json'))
    summary=summary_paths[-1] if summary_paths else None
    report={'schema':'recompdev-modular-campaign-v0.4.1',
            'status':'CAMPAIGN_REPORTED' if invocation['return_code']==0 and summary else 'BLOCKED_OR_FAILED',
            'rom_dir':str(rom_dir), 'source_catalogue':str(source_db),
            'working_catalogue':str(working), 'stage':invocation,
            'campaign_summary':str(summary) if summary else None,
            'production_catalogue_mutated':preservation.sha(source_db)!=dbhash,
            'source_of_truth':'Original v0.4.0.45 seven-game orchestration (unmodified script)',
            'gameplay_parity':'NOT_ESTABLISHED'}
    if summary:
        details=json.loads(summary.read_text(encoding='utf8'))
        report['game_statuses']={r['slug']:r.get('status') for r in details.get('games',[])}
        if report['status']=='CAMPAIGN_REPORTED' and all(s=='ROM_NOT_FOUND' for s in report['game_statuses'].values()):
            report['status']='NO_MATCHING_ROMS'
    if report['production_catalogue_mutated']: report['status']='INTEGRITY_VIOLATION'
    (out/'controller-report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf8')
    return report


def compare_discovery(rom, out, database=None, budget=150, timeout=720):
    """Execute original CLI directly and plugin-wrapped CLI on identical snapshots.

    This tests adapter transparency, *not independent emulator state parity*.
    """
    import subprocess, os
    rom=authentic_rom(rom,native_required=False)
    db=Path(database or default_catalogue()).resolve(strict=True)
    out=Path(out).resolve()
    if out.exists(): raise ValueError('Comparison destination already exists')
    out.mkdir(parents=True)
    # The original discovery engine uses sampled identity above 128 MiB.
    # Compare its actual identifier, not an invented full SHA value.
    sys.path.insert(0,str(LEGACY))
    from discovery.engine import identity
    source_hash,identity_kind=identity(rom)
    dbhash=preservation.sha(db)
    old_db=out/'original.sqlite'
    preservation.catalogue_snapshot(db,old_db)
    original_out=out/'original-discovery'
    original_out.mkdir()
    log=out/'original.log'
    env=dict(os.environ);env['PYTHONDONTWRITEBYTECODE']='1'
    args=[sys.executable,'-u','-m','discovery.engine','--db',str(old_db),
          '--source',str(rom),'--output',str(original_out),'--budget',str(budget),'--max-files','1']
    with log.open('wb') as fp:
        try:
            proc=subprocess.run(args,cwd=LEGACY,env=env,stdin=subprocess.DEVNULL,
                                stdout=fp,stderr=subprocess.STDOUT,timeout=timeout,check=False)
            rc=proc.returncode
        except subprocess.TimeoutExpired:
            rc=None
    if rc!=0:
        result={'status':'ORIGINAL_WORKFLOW_FAILED','original_exit_code':rc,'log':str(log)}
    else:
        modular=run_rom(rom,out/'modular',stage='discover',database=db,budget=budget,timeout=timeout)
        if modular['status']!='DISCOVERY_COMPLETE':
            result={'status':'MODULAR_WORKFLOW_FAILED','modular':modular['status']}
        else:
            old=discovery_fingerprint(old_db,source_hash)
            new=discovery_fingerprint(modular['working_catalogue'],source_hash)
            sections={k:old[k]==new[k] for k in old}
            result={'status':'PASS' if all(sections.values()) else 'DIFFERENT',
                    'row_level_equivalence':sections,'original_exit_code':rc,
                    'comparison_kind':'Original v0.4.0.45 discovery CLI versus modular adapter, same original implementation',
                    'not_independent_gameplay_parity':True}
    result.update(schema='recompdev-discovery-parity-v0.4.1',
                  source_id=source_hash, source_hash_kind=identity_kind,
                  original_rom_unchanged=identity(rom)[0]==source_hash,
                  source_catalogue_unchanged=preservation.sha(db)==dbhash)
    (out/'equivalence-report.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf8')
    return result
