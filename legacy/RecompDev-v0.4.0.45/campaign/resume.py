"""Append-only, source-attested conversion campaign controller.

Prior complete attempts are re-used *only* after confirming source, settings,
compiler, relevant evidence, engine code and their output reports. Changed inputs
cause a fresh immutable attempt, not mutation of an earlier diagnosis.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from campaign.engine import run, digest
from campaign.handoff import convert
from campaign.reference_triage import triage

SCHEMA='recomp-durable-campaign-v0421'
CORE=('campaign/engine.py','campaign/handoff.py','campaign/resume.py','campaign/reference_triage.py',
      'nativecore/m68k_fixture.py','campaign/m68k_oracle.py','nativepilot/engine.py',
      'nativepilot/generator.py','nativepilot/runtime.cpp','systems/mastersystem/runtime.cpp',
      'systems/mastersystem/runtime.hpp','hardware/core.hpp','hardware/runtime.hpp',
      'hardware/wav.hpp','hardware/input_replay.hpp','hardware/adapters/sms.hpp','hardware/adapters/sms_machine.hpp',
      'tooling/analysis.py')

def hash_object(data):return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def record(path,doc):
    path=Path(path)
    if path.exists():raise ValueError('Immutable campaign record already exists')
    tmp=path.with_name(path.name+'.writing')
    if tmp.exists():raise ValueError('Interrupted publication must be inspected')
    try:
        with tmp.open('x',encoding='utf-8') as out:
            json.dump(doc,out,sort_keys=True,indent=2);out.write('\n')
        tmp.replace(path)
    finally:
        if tmp.exists():tmp.unlink()

def _arg_path(value):return str(Path(value).resolve(strict=True)) if value else None

def _prepared_input(db,source_sha):
    """Fingerprint stable prepared source rows, not mutable pilot-status SQLite pages."""
    if not db:return None
    database=Path(db).resolve(strict=True)
    with closing(sqlite3.connect(str(database))) as conn:
        # Only data that the native generator consumes; an ever-changing job
        # history must not destroy cache reuse on every successful run.
        discovery=conn.execute('SELECT path,bytes,source_hash_kind,system FROM discovery_sources WHERE source_id=?',(source_sha,)).fetchone()
        prepared=conn.execute('SELECT target_id,source_sha256,export_path,candidate_count FROM native_preparations_v0403 WHERE source_id=?',(source_sha,)).fetchone()
    export=Path(prepared[2]).resolve(strict=True) if prepared and prepared[2] else None
    return {'path':str(database),'discovery':discovery,'preparation':prepared,
            'export_sha256':digest(export) if export and export.is_file() else None}

def _fingerprint(source,isa,base,entry,db,rom_roots,steps,rizin,ghidra,approved_tool_roots,
                 reference_anchors,reference_hardware,synthetic,compiler,bus_comparison=None):
    root=Path(__file__).resolve().parents[1]
    code={p:digest(root/p) for p in CORE}
    file_args={key:({'path':_arg_path(val),'sha256':digest(val)} if val else None)
        for key,val in [('rizin',rizin),('ghidra',ghidra),
                        ('anchors',reference_anchors),('hardware',reference_hardware),('compiler',compiler),('bus_comparison',bus_comparison)]}
    args={'schema':SCHEMA,'source':str(Path(source).resolve(strict=True)),
          'source_sha256':digest(source),'isa':isa,'base':base,'entry':entry,
          'steps':steps,'rom_roots':[str(Path(p).resolve(strict=True)) for p in rom_roots],
          'approved_tool_roots':[str(Path(p).resolve(strict=True)) for p in approved_tool_roots],
          'synthetic':synthetic,'prepared_input':_prepared_input(db,digest(source)) if db else None,'file_arguments':file_args,'engine_code_sha256':hash_object(code)}
    return args,hash_object(args)

def verify_attempt(folder,expected_key):
    folder=Path(folder);manifest=folder/'attempt-manifest.json'
    if not manifest.is_file() or manifest.is_symlink():return None
    try:
        data=json.loads(manifest.read_text(encoding='utf-8'))
        if data.get('schema')!=SCHEMA:raise ValueError('Unknown attempt manifest schema')
        current=data.get('fingerprint')
        report=folder/'campaign-report.json'
        if not report.is_file() or digest(report)!=data.get('report_sha256'):raise ValueError('Tampered campaign report')
        if json.loads(report.read_text()).get('source_sha256')!=data['inputs']['source_sha256']:
            raise ValueError('Report source mismatched')
        for name,sha in data.get('evidence',{}).items():
            path=folder/name
            if not path.is_file() or path.is_symlink() or digest(path)!=sha:raise ValueError('Tampered evidence: '+name)
        return data if current==expected_key else None
    except (OSError,ValueError,KeyError) as exc:
        raise ValueError('Previous attempt integrity failure: '+str(exc)) from exc

def durable(source,output,isa,base=0,entry=None,db=None,rom_roots=(),steps=50000,
        rizin=None,ghidra=None,approved_tool_roots=(),reference_anchors=None,
        reference_hardware=None,synthetic=False,compiler=None,retry_blocked=False,bus_comparison=None):
    source=Path(source).resolve(strict=True)
    if not source.is_file() or source.is_symlink() or not 0<source.stat().st_size<=32*1024*1024:
        raise ValueError('Invalid owner source file')
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    inputs,key=_fingerprint(source,isa,base,entry,db,rom_roots,steps,rizin,ghidra,approved_tool_roots,
                    reference_anchors,reference_hardware,synthetic,compiler,bus_comparison)
    lock=output/'.campaign-running'
    # Atomic exclusive create; an interrupted job requires explicit owner cleanup.
    with lock.open('x',encoding='utf-8') as guard:
        guard.write(key+'\n')
    try:
        attempts=sorted(p for p in output.iterdir() if p.is_dir() and p.name.startswith('attempt-'))
        for folder in attempts:
            previous=verify_attempt(folder,key)
            if previous and (previous.get('status')!='BLOCKED' or not retry_blocked):
                return {'schema':SCHEMA,'status':'REUSED_VERIFIED_ATTEMPT',
                        'attempt':str(folder),'fingerprint':key,'report':str(folder/'campaign-report.json'),
                        'original_status':previous['status']}
        ordinal=max([int(p.name[8:]) for p in attempts if p.name[8:].isdigit()] or [-1])+1
        if ordinal>=100:raise ValueError('Maximum campaign attempts reached')
        target=output/f'attempt-{ordinal:04d}'
        result=run(source,target,isa,base,entry,db,rom_roots,steps,rizin,ghidra,
                   approved_tool_roots,reference_anchors,reference_hardware,synthetic,compiler)
        extra={}
        if bus_comparison:
            investigation=triage(source,bus_comparison,target/'reference-investigation.json')
            extra['reference-investigation.json']=digest(target/'reference-investigation.json')
        recon=target/'static-analysis'/'reconciliation.json'
        if recon.is_file() and result.get('source_unchanged'):
            handoff=convert(source,recon,target/'recovery-queue.json')
            extra['recovery-queue.json']=digest(target/'recovery-queue.json')
        # Digest main independent evidence files; compiled products stay in the
        # original attempt but are not trusted as proof by this manifest.
        for rel in ('alignment.json','hardware-comparison.json','native-oracle-comparison.json',
                    'static-analysis/reconciliation.json','static-analysis/analysis-job.json'):
            f=target/rel
            if f.is_file():extra[rel]=digest(f)
        manifest={'schema':SCHEMA,'fingerprint':key,'inputs':inputs,'status':result['status'],
                  'report_sha256':digest(target/'campaign-report.json'),'evidence':extra,
                  'native_qualified':False,'gameplay':'NOT_ESTABLISHED','replay_policy':'IMMUTABLE_REUSE_OR_NEW_ATTESTED_ATTEMPT'}
        record(target/'attempt-manifest.json',manifest)
        return {'schema':SCHEMA,'status':'RECORDED_NEW_ATTEMPT','attempt':str(target),
                'fingerprint':key,'report':str(target/'campaign-report.json'),
                'original_status':result['status'],'recovery_tasks':len(handoff['recovery_tasks']) if recon.is_file() and result.get('source_unchanged') else 0}
    finally:
        lock.unlink(missing_ok=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True);p.add_argument('--output',required=True)
    p.add_argument('--isa',required=True,choices=['z80','m68k']);p.add_argument('--base',type=lambda x:int(x,0),default=0)
    p.add_argument('--entry',type=lambda x:int(x,0));p.add_argument('--db');p.add_argument('--rom-root',action='append',default=[])
    p.add_argument('--steps',type=int,default=50000);p.add_argument('--rizin');p.add_argument('--ghidra')
    p.add_argument('--allow-tool-root',action='append',default=[]);p.add_argument('--reference-anchors')
    p.add_argument('--reference-hardware');p.add_argument('--synthetic-fixture',action='store_true');p.add_argument('--compiler')
    p.add_argument('--retry-blocked',action='store_true')
    p.add_argument('--bus-comparison',help='Existing source-matched external bus comparison to triage')
    a=p.parse_args()
    result=durable(a.input,a.output,a.isa,a.base,a.entry,a.db,a.rom_root,a.steps,a.rizin,a.ghidra,
                   a.allow_tool_root,a.reference_anchors,a.reference_hardware,a.synthetic_fixture,a.compiler,a.retry_blocked,a.bus_comparison)
    print(json.dumps(result,indent=2));return 0 if result['original_status']=='FINISHED_WITH_EXPLICIT_GATES' else 2
if __name__=='__main__':raise SystemExit(main())
