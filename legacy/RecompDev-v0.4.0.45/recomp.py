#!/usr/bin/env python3
"""RecompDev catalogue-first CLI. Workbench may start bounded local discovery."""
import argparse
import json
import sys
import subprocess
from pathlib import Path
from graph_store import connect,import_flow,import_analyzer
from workbench import serve
from scan_graph import run
from target_names import migrate,update,sync_evidence,sync_source
from native_batch import create_campaign,probe_go_sources

ROOT=Path(__file__).resolve().parent
from nativecore.shared_catalogue import ensure_shared_catalogue, shared_path

def main(argv=None):
    p=argparse.ArgumentParser(description='Catalogue-first RecompDev: analyse binaries, catalogue calls, browse evidence')
    p.add_argument('--db',default=str(shared_path(ROOT)),help='Persistent SQLite catalogue path')
    sub=p.add_subparsers(dest='command',required=True)
    boot=sub.add_parser('bootstrap',help='Import bundled Sonic and Ridge Racer historical graph evidence')
    imp=sub.add_parser('import-flow',help='Import compatible metadata-only flow evidence')
    imp.add_argument('file')
    ext=sub.add_parser('import-analyzer',help='Import Ghidra-like function/call evidence for an existing SHA-matched target')
    ext.add_argument('file')
    scan=sub.add_parser('scan',help='Scan owner-local source and catalogue reachable call/branch evidence')
    scan.add_argument('--input',required=True);scan.add_argument('--out',required=True)
    scan.add_argument('--format',choices=['auto','megadrive','psx-exe','raw'],default='auto')
    scan.add_argument('--isa',choices=['m68k','mips']);scan.add_argument('--endian',choices=['big','little'])
    scan.add_argument('--base',type=lambda s:int(s,0));scan.add_argument('--entry',type=lambda s:int(s,0))
    scan.add_argument('--seed',action='append',default=[],type=lambda s:int(s,0),help='additional owner-supplied entry seed')
    scan.add_argument('--max-instructions',type=int,default=100000)
    scan.add_argument('--seed-vectors',action='store_true',help='include valid Mega Drive exception-vector candidate entries')
    scan.add_argument('--recover-indirect',action='store_true',help='bounded source-supported local constant transfer recovery (experimental)')
    bench=sub.add_parser('benchmark-discovery',help='baseline versus bounded source-supported recovery, same source/seeds/budget')
    bench.add_argument('--input',required=True);bench.add_argument('--out',required=True)
    bench.add_argument('--format',choices=['auto','megadrive','psx-exe','raw'],default='auto')
    bench.add_argument('--isa',choices=['m68k','mips']);bench.add_argument('--endian',choices=['big','little'])
    bench.add_argument('--base',type=lambda s:int(s,0));bench.add_argument('--entry',type=lambda s:int(s,0))
    bench.add_argument('--seed',action='append',default=[],type=lambda s:int(s,0))
    bench.add_argument('--seed-vectors',action='store_true');bench.add_argument('--max-instructions',type=int,default=100000)
    bench.add_argument('--expected-sha256',help='fail closed unless the binary matches the expected original SHA-256')
    uc=sub.add_parser('universal-campaign',help='attested discovery + barrier triage + bounded native CPU subset')
    uc.add_argument('--input',required=True);uc.add_argument('--out',required=True)
    uc.add_argument('--format',choices=['auto','megadrive','psx-exe','raw'],default='auto')
    uc.add_argument('--isa',choices=['m68k','mips']);uc.add_argument('--endian',choices=['big','little'])
    uc.add_argument('--base',type=lambda s:int(s,0));uc.add_argument('--entry',type=lambda s:int(s,0))
    uc.add_argument('--seed-vectors',action='store_true');uc.add_argument('--max-instructions',type=int,default=100000)
    uc.add_argument('--expected-sha256');uc.add_argument('--compile',action='store_true');uc.add_argument('--run-steps',type=int)
    # Genuine bounded source-derived native compilation (no emulated fallback).
    ns=sub.add_parser('compile-native-slice',help='attested M68000/MIPS instructions -> C++17 compiled native subset')
    ns.add_argument('--input',required=True);ns.add_argument('--out',required=True)
    ns.add_argument('--format',choices=['auto','megadrive','psx-exe','raw'],default='auto')
    ns.add_argument('--isa',choices=['m68k','mips']);ns.add_argument('--endian',choices=['big','little'])
    ns.add_argument('--base',type=lambda s:int(s,0));ns.add_argument('--entry',type=lambda s:int(s,0))
    ns.add_argument('--max-instructions',type=int,default=160);ns.add_argument('--expected-sha256')
    ns.add_argument('--strict',action='store_true',help='require all mapped discovered instructions supported')
    ns.add_argument('--compile',action='store_true',help='compile using local CMake C++17 toolchain')
    ns.add_argument('--run-steps',type=int,help='execute compiled binary within bounded step budget')
    dc=sub.add_parser('compare-checkpoints',help='independent reference vs candidate first-difference checkpoint comparison')
    dc.add_argument('--reference',required=True);dc.add_argument('--candidate',required=True);dc.add_argument('--out',required=True)
    tr=sub.add_parser('triage-evidence',help='classify unresolved barriers from an authentic graph evidence file')
    tr.add_argument('--evidence',required=True);tr.add_argument('--out',required=True)
    batch=sub.add_parser('batch-cpp',help='SHA-match binaries, queue every candidate and optionally invoke bounded Go translator')
    batch.add_argument('--source',action='append',default=[],help='Owner-local binary path; repeatable')
    batch.add_argument('--source-root',action='append',default=[],help='Owner-local directory to inspect; repeatable')
    batch.add_argument('--attempt-bounded',action='store_true',help='Run existing bounded converter, not whole-function C++')
    batch.add_argument('--go-root',help='Path to existing RecompDev-v0.1.4 source/executable tree')
    batch.add_argument('--go-source-root',help='Go source tree for source/test inventory only')
    batch.add_argument('--timeout',type=int,default=120)
    batch.add_argument('--output',help='Optional metadata-only JSON report path')
    recover=sub.add_parser('recover-cpp',help='Verify SHA and Ghidra instruction bytes, compile safe recovered P-code function candidates')
    recover.add_argument('--source',action='append',default=[])
    recover.add_argument('--source-root',action='append',default=[])
    recover.add_argument('--ghidra-export',action='append',required=True)
    recover.add_argument('--output')
    recover.add_argument('--limit',type=int,default=50)
    recover.add_argument('--rizin-json',help='Optional Rizin aflj JSON evidence for boundary reconciliation')
    recover.add_argument('--require-dual',action='store_true')
    recover.add_argument('--compiler',help='MSVC cl.exe, g++ or clang++ executable')
    recover.add_argument('--no-compile',action='store_true')
    recover.add_argument('--pypcode-check',action='store_true')
    gh=sub.add_parser('ghidra-headless',help='Run authenticated headless Ghidra for one owned MD or PS-X EXE binary')
    gh.add_argument('--input',required=True);gh.add_argument('--target',required=True)
    gh.add_argument('--ghidra-exe',required=True);gh.add_argument('--output',required=True)
    bridge=sub.add_parser('adapters',help='List available metadata adapters (including PS2 and Xbox 360)')
    identity=sub.add_parser('identify',help='Identify an owner-local container without scanning code')
    identity.add_argument('--input',required=True);identity.add_argument('--title-db')
    folder=sub.add_parser('identify-folder',help='Identify local binary container formats')
    folder.add_argument('--input',required=True);folder.add_argument('--title-db')
    ready=sub.add_parser('plan-cpp',help='Report existing function-boundary readiness without running C++')
    ready.add_argument('--output')
    sub.add_parser('summary',help='Print current target/callgraph totals')
    label=sub.add_parser('name-target',help='Set a friendly owner alias without changing the immutable target ID')
    label.add_argument('--target',required=True);label.add_argument('--name',required=True)
    source=sub.add_parser('name-from-binary',help='Read trusted header/filename name from SHA-matched original input (no rescan)')
    source.add_argument('--input',required=True)
    sync=sub.add_parser('sync-names',help='Backfill target names from existing metadata-only scan evidence')
    sync.add_argument('--evidence-dir',default=str(ROOT/'evidence'))
    ui=sub.add_parser('serve',help='Run local Workbench with controlled discovery jobs')
    ui.add_argument('--port',type=int,default=8777)
    ui.add_argument('--rom-root',action='append',default=[],help='A trusted ROM folder visible to the local Workbench browser')
    ui.add_argument('--native-prepare-register-only',action='store_true',help='Register and authenticate sources without Ghidra (analysis enabled by default)')
    args=p.parse_args(argv)
    if Path(args.db).resolve()==shared_path(ROOT):
        ensure_shared_catalogue(ROOT)
    try:
        if args.command=='serve':
            serve(args.db,port=args.port,rom_roots=args.rom_root,
                  native_prepare_analysis=not args.native_prepare_register_only);return 0
        if args.command in ('identify','identify-folder','adapters','plan-cpp'):
            command=[sys.executable,str(ROOT/'bridge/recomp_bridge.py'),args.command]
            if args.command in ('identify','identify-folder'):
                command.extend(['--input',args.input])
                if args.title_db:command.extend(['--title-db',args.title_db])
            if args.command=='plan-cpp':
                command.extend(['--db',args.db])
                if args.output:command.extend(['--output',args.output])
            return subprocess.run(command,check=False).returncode
        if args.command=='ghidra-headless':
            from recovery.headless import export
            out=export(args.db,args.input,args.target,args.ghidra_exe,args.output)
            print(json.dumps(out,indent=2))
            return 0
        if args.command=='recover-cpp':
            from recovery.pipeline import run as recover_run
            out=recover_run(args.db,args.source,args.source_root,args.ghidra_export,args.output,
              args.limit,args.rizin_json,args.require_dual,args.compiler,not args.no_compile,args.pypcode_check)
            print('RECOVERY_REPORT='+str(Path(args.output or (Path(args.db).parent/'evidence'/'functions-v031'))/'campaign.json'))
            print('FUNCTIONS_SUBMITTED='+str(out['functions_submitted']))
            print('CPP_COMPILER_SMOKE='+str(out['cpp_compiled_runner_smoke']))
            print('ORIGINAL_CPU_PARITY='+str(out['original_vs_native_parity_passed']))
            print('STATUSES='+json.dumps(out['statuses'],sort_keys=True))
            return 0
        if args.command=='batch-cpp':
            o=create_campaign(args.db,args.source,args.source_root,args.go_root,args.attempt_bounded,
                              args.go_source_root,args.timeout,args.output)
            if args.output:
                print('REPORT='+str(Path(args.output).resolve()))
                print('BATCH='+o['campaign_id']+';TARGETS='+str(o['totals']['targets'])+';CANDIDATES='+str(o['totals']['function_candidates']))
                for t in o['targets']:
                    print('TARGET='+t['display_name']+';SOURCE='+t['input_status']+';NATIVE='+t['native_status']+';BOUNDED_UNITS='+str(t['native_units']))
            else:print(json.dumps(o,indent=2))
            print('STATUS=BATCH_CAMPAIGN_RECORDED;FUNCTION_PARITY=NOT_VERIFIED')
            return 0
        if args.command=='universal-campaign':
            from multisa.campaign import run as universal_run
            print(json.dumps(universal_run(args.input,args.out,args.format,args.isa,args.endian,args.base,args.entry,
                  args.seed_vectors,args.max_instructions,args.compile,args.run_steps,args.expected_sha256),indent=2))
            return 0
        if args.command=='compile-native-slice':
            from multisa.native import generate,compile_project
            report=generate(args.input,args.out,args.format,args.isa,args.endian,args.base,args.entry,
                            args.max_instructions,args.expected_sha256,args.strict)
            if args.run_steps is not None and not args.compile:raise ValueError('--run-steps requires --compile')
            if args.compile:
                exe=compile_project(args.out)
                report['compiled_native_executable_sha256']=__import__('hashlib').sha256(exe.read_bytes()).hexdigest()
                if args.run_steps is not None:
                    if not 1<=args.run_steps<=10000000:raise ValueError('step budget invalid')
                    proc=subprocess.run([str(exe),str(args.run_steps)],capture_output=True,text=True,timeout=90)
                    report['native_run']=json.loads(proc.stdout.strip()) if proc.stdout.strip().startswith('{') else {'error':proc.stderr[-1000:]}
                    report['native_returncode']=proc.returncode
            print(json.dumps(report,indent=2))
            return 0 if not args.compile or args.run_steps is None or report['native_returncode']==0 else 3
        if args.command=='compare-checkpoints':
            from multisa.checkpoints import compare
            result=compare(args.reference,args.candidate)
            out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
            out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
            print(json.dumps(result,indent=2));return 0
        if args.command=='triage-evidence':
            from multisa.triage import triage
            print(json.dumps(triage(args.evidence,args.out),indent=2));return 0
        if args.command=='benchmark-discovery':
            from discovery_benchmark import benchmark
            result=benchmark(args.input,args.out,args.format,args.isa,args.endian,args.base,args.entry,
                             args.max_instructions,args.seed,args.seed_vectors,args.expected_sha256)
            print(json.dumps(result,indent=2))
            print('STATUS=SOURCE_SUPPORTED_STATIC_CANDIDATES_ONLY; NATIVE_PARITY=NOT_VERIFIED')
            return 0
        if args.command=='scan':
            if args.max_instructions<=0:raise ValueError('max-instructions must be positive')
            result=run(args.input,args.db,args.out,args.format,args.isa,args.endian,args.base,args.entry,args.max_instructions,args.seed,args.seed_vectors,args.recover_indirect)
            print(json.dumps(result,indent=2));print('STATUS=STATIC_DISCOVERY_ONLY; NATIVE_PARITY=NOT_VERIFIED')
            return 0
        con=connect(args.db)
        try:
            if args.command in ('name-target','sync-names','name-from-binary'):
                migrate(con)
                if args.command=='name-target':
                    update(con,args.target,args.name,'owner_alias')
                    print('TARGET_LABEL='+json.dumps({'target_id':args.target,'name':args.name,'source':'owner_alias'}))
                elif args.command=='name-from-binary':
                    print('TARGET_LABELS='+json.dumps(sync_source(con,args.input),sort_keys=True))
                else:
                    print('LABEL_SYNC='+json.dumps(sync_evidence(con,args.evidence_dir),sort_keys=True))
            if args.command=='bootstrap':
                for name in ['sonic-flow-evidence.json','ridge-racer-flow-evidence.json']:
                    f=ROOT/'seed'/name
                    print(f'IMPORTED_RUN={import_flow(con,f)}')
                print('STATUS=HISTORICAL_METADATA_IMPORTED; FUNCTION_BOUNDARIES=UNVERIFIED')
            if args.command=='import-flow':print('IMPORTED_RUN='+import_flow(con,args.file))
            if args.command=='import-analyzer':print('IMPORTED_RUN='+import_analyzer(con,args.file))
            if args.command=='summary':
                for row in con.execute('''SELECT r.target_id,r.analyzer,r.instruction_count,
                     (SELECT COUNT(*) FROM graph_functions WHERE run_id=r.run_id) AS function_candidates,
                     (SELECT COUNT(*) FROM graph_transfers WHERE run_id=r.run_id AND kind IN ('direct_call','indirect_call')) AS call_sites,
                     (SELECT COUNT(*) FROM graph_barriers WHERE run_id=r.run_id) AS barriers
                     FROM graph_runs r WHERE r.rowid IN (SELECT MAX(rowid) FROM graph_runs GROUP BY target_id)'''):
                    print(json.dumps(dict(row)))
        finally:con.close()
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr);return 1
    return 0
if __name__=='__main__':sys.exit(main())
