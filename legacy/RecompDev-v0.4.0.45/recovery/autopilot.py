"""Batch three-game function export + conversion, with per-target error isolation.

This may run Ghidra for multiple minutes per target on the owner's Windows PC.
Everything is synchronous, source-bound, persisted and restartable.
"""
from __future__ import annotations
import sys
from pathlib import Path as _Path
sys.path.insert(0,str(_Path(__file__).resolve().parents[1]))
import argparse
import json
import sqlite3
import subprocess
from pathlib import Path
import shutil
from collections import Counter
from native_batch import index_sources
from recovery.headless import export
from recovery.pipeline import run, read_export
from recovery.native_workers import run_isolated


def autopilot(db,sources,roots,ghidra_exe,out,limit=50,compiler=None,pypcode_check=True,
              previous_ghidra_dir=None,refresh_ghidra=False,compare_samples=True):
    db=Path(db).resolve();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    checkpoint=out/'last-stage.json'
    def progress(stage,**details):
        # Atomically replace a small, durable checkpoint BEFORE native work.
        # Even if a non-Python fail-fast kills the process, this remains.
        payload={'schema':'recomp-crash-checkpoint-v0323','stage':stage,**details}
        temp=out/'last-stage.writing.json'
        temp.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
        temp.replace(checkpoint)
        print('AUTOPILOT_STAGE='+stage+';TARGET='+str(details.get('target_id',''))+
              ';ENTRY='+str(details.get('entry','')),flush=True)
    progress('startup')
    con=sqlite3.connect(str(db));con.row_factory=sqlite3.Row
    try:
        progress('source_indexing')
        inputs,scan_errors=index_sources(con,sources,roots)
        progress('catalogue_query')
        targets=[dict(x) for x in con.execute('SELECT * FROM targets ORDER BY target_id')]
    finally:con.close()
    successes=[];problems=[]
    for t in targets:
        progress('target_analysis',target_id=t['target_id'])
        if t['system_tag'] not in ('megadrive','psx-exe'):
            problems.append({'target_id':t['target_id'],'status':'BINARY_EXTRACTION_ADAPTER_MISSING'});continue
        binary=inputs.get(t['source_sha256'])
        if not binary:
            problems.append({'target_id':t['target_id'],'status':'AUTHENTICATED_SOURCE_NOT_FOUND',
                             'reason':'Expected SHA256 '+t['source_sha256'][:16]+'... not found in supplied source files or roots',
                             'explicit_source_count':len(sources),'source_root_count':len(roots)});continue
        file=out/'ghidra'/f'{t["target_id"]}.json'
        try:
            reused=False
            cache_reason=''
            if previous_ghidra_dir and not refresh_ghidra:
                cached=Path(previous_ghidra_dir)/f'{t["target_id"]}.json'
                if cached.is_file():
                    try:
                        candidate=read_export(cached)
                        if candidate.get('target_id')!=t['target_id']:
                            cache_reason='cached target_id differs from current catalogue'
                        elif candidate.get('source_sha256')!=t['source_sha256']:
                            cache_reason='cached source SHA256 differs from current catalogue'
                        else:
                            # Full byte matching happens again in pipeline.run.
                            if cached.resolve()!=file.resolve():
                                file.parent.mkdir(parents=True,exist_ok=True)
                                shutil.copyfile(cached,file)
                            else:
                                file=cached
                            reused=True
                            x={'function_candidates':len(candidate['functions'])}
                    except (ValueError,OSError,KeyError,TypeError) as error:
                        cache_reason='cached Ghidra export rejected: '+type(error).__name__+': '+str(error)[:200]
                else:
                    cache_reason='cached Ghidra export missing: '+str(cached)
            if not reused:
                if not ghidra_exe:
                    raise ValueError((cache_reason+'; ' if cache_reason else '')+
                                     'No Ghidra executable available for fresh analysis. '
                                     'Supply -GhidraExe or -PreviousExports with valid exports.')
                x=export(db,binary,t['target_id'],ghidra_exe,file)
            successes.append({'target_id':t['target_id'],'source':binary,'export':str(file),
                              'ghidra_candidates':x['function_candidates'],
                              'analysis_source':'SHA_MATCHED_REUSED_EXPORT' if reused else 'NEW_HEADLESS_GHIDRA'})
        except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as ex:
            problems.append({'target_id':t['target_id'],'status':'GHIDRA_EXPORT_FAILED','reason':str(ex)[:500]})
    if successes:
        progress('pipeline_begin',sources_found=len(successes))
        result=run(db,[x['source'] for x in successes],(),[x['export'] for x in successes],out/'compiled',limit,
                   compiler=compiler,pypcode_check=pypcode_check,progress=progress)
    else:result={'functions_submitted':0,'cpp_compiled_runner_smoke':0,
                 'original_vs_native_parity_passed':0,'statuses':{},'jobs':[]}
    # A completely unsuccessful discovery must still emit a reliable report.
    (out/'compiled').mkdir(parents=True, exist_ok=True)
    comparison_results=[]
    original_reference_workers=0
    if compare_samples:
        source_by_id={x['target_id']:x['source'] for x in successes}
        export_hash={x['target']:x['export_sha256'] for x in result.get('exports',[])}
        for job in result.get('jobs',[]):
            if job['compile_status'] not in ('COMPILED_SEEDED_SMOKE_ONLY','COMPILED_RUNNER_SMOKE_ONLY','COMPILED_HARDWARE_TRACE_SMOKE_ONLY'):
                continue
            tid=job['target_id'];sha=export_hash.get(tid)
            if not sha:continue
            folder=out/'compiled'/f'{tid}-{job["entry"]:08x}-{sha[:10]}'
            manifest=folder/'manifest.json'
            if not manifest.is_file():continue
            progress('unicorn_worker',target_id=tid,entry=job['entry'])
            if job['compile_status']=='COMPILED_HARDWARE_TRACE_SMOKE_ONLY':
                evidence={'status':'HARDWARE_EVENT_TRACE_ONLY_NOT_CPU_PARITY',
                          'reason':'Hardware writes were captured as events, not emulated. '
                                   'Device effects and bus timing are not independently compared.'}
            else:
                original_reference_workers+=1
                evidence=run_isolated('unicorn',{'db':str(db),'source':source_by_id[tid],
                                                   'manifest':str(manifest)},timeout=40)
            (folder/'comparison.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
            recorded=json.loads(manifest.read_text(encoding='utf-8'))
            recorded['verification_status']=evidence['status']
            recorded['reference_comparison_evidence']='comparison.json'
            manifest.write_text(json.dumps(recorded,indent=2)+'\n',encoding='utf-8')
            con=sqlite3.connect(db)
            try:
                with con:con.execute('''UPDATE conversion_v031 SET verification_status=?
                  WHERE target_id=? AND source_sha256=? AND entry=? AND export_sha256=?''',(
                    evidence['status'],tid,recorded['source_sha256'],job['entry'],sha))
            finally:con.close()
            job['verification_status']=evidence['status']
            comparison_results.append({'target_id':tid,'entry':job['entry'],'status':evidence['status']})
    progress('writing_reports')
    result['sample_comparison_statuses']=dict(Counter(x['status'] for x in comparison_results))
    result['sample_comparisons_attempted']=original_reference_workers
    result['hardware_trace_reference_not_attempted']=len(comparison_results)-original_reference_workers
    # No finite subset of synthetic-state comparison is whole-function parity.
    result['original_vs_native_parity_passed']=0
    (out/'compiled'/'campaign.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    summary={'schema':'recomp-autopilot-v0.3.2.3','successes':successes,'issues':problems,
             'source_scan_errors':scan_errors,
             'diagnostics':{'catalogue_path':str(db),'targets_in_catalogue':len(targets),
                            'matched_source_hashes':len(inputs),'source_roots':list(map(str,roots)),
                            'explicit_sources':list(map(str,sources)),
                            'previous_ghidra_dir':str(previous_ghidra_dir or ''),
                            'ghidra_exe_present':bool(ghidra_exe)},
             'function_pipeline':result,
             'statement':'Automated job preparation and bounded compiling, not verified full native-game recompilation.'}
    (out/'autopilot-report.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    progress('complete',sources_found=len(successes),functions_submitted=result['functions_submitted'])
    return summary


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--db',required=True);p.add_argument('--source',action='append',default=[])
    p.add_argument('--source-root',action='append',default=[])
    p.add_argument('--ghidra-exe',default='');p.add_argument('--output',required=True)
    p.add_argument('--previous-ghidra-dir')
    p.add_argument('--refresh-ghidra',action='store_true')
    p.add_argument('--compiler');p.add_argument('--limit',type=int,default=50)
    p.add_argument('--no-pypcode-check',action='store_true')
    p.add_argument('--no-sample-compare',action='store_true')
    a=p.parse_args()
    result=autopilot(a.db,a.source,a.source_root,a.ghidra_exe,a.output,a.limit,a.compiler,not a.no_pypcode_check,a.previous_ghidra_dir,a.refresh_ghidra,not a.no_sample_compare)
    for x in result['successes']:
        print('SOURCE='+x['target_id']+';GHIDRA_FUNCTIONS='+str(x['ghidra_candidates']))
    for x in result['issues']:
        print('ISSUE='+x['target_id']+';STATUS='+x['status']+';REASON='+x.get('reason',''))
    d=result['diagnostics']; print('CATALOGUE_TARGETS='+str(d['targets_in_catalogue'])+
      ';SOURCE_SHA_MATCHES='+str(d['matched_source_hashes']))
    q=result['function_pipeline'];print('FUNCTIONS_SUBMITTED='+str(q['functions_submitted']))
    print('CPP_COMPILED_TOTAL='+str(q.get('cpp_compiled_total',0)))
    print('SEEDED_RUNTIME_SMOKE='+str(q.get('cpp_seeded_smoke_only',0)))
    print('HARDWARE_TRACE_SMOKE='+str(q.get('cpp_hardware_trace_smoke_only',0)))
    print('REFERENCE_SAMPLES_ATTEMPTED='+str(q.get('sample_comparisons_attempted',0)))
    print('ORIGINAL_CPU_PARITY=NOT_ESTABLISHED')
    print('REPORT='+str(Path(a.output)/'autopilot-report.json'))
    return 0 if result['successes'] else 1

if __name__=='__main__':
    import subprocess
    raise SystemExit(main())
