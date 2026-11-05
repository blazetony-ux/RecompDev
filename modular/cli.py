#!/usr/bin/env python3
"""RecompDev v0.4.4 real workflow controller (legacy-backed, modular adapters)."""
import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from modular import controller, evidence_bundle, hardware_review
from workspace.provenance import record_provenance
from workspace.manager import read_state, manifest, git_head
from modular.plugins import legacy
from migration import controller as preservation


def fresh_evidence():
    release = manifest(ROOT)['workspace_release']
    return Path(__import__('os').environ.get('RECOMPDEV_EVIDENCE_ROOT') or (ROOT.parent/'RecompDev-Evidence')) / release / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('plugins')
    sub.add_parser('verify')
    sub.add_parser('status')
    run=sub.add_parser('run-rom',help='Real original discovery/preparation/recovery with isolated evidence')
    run.add_argument('--rom',required=True)
    run.add_argument('--out')
    run.add_argument('--catalogue')
    run.add_argument('--stage',choices=('discover','prepare','recover'),default='prepare')
    run.add_argument('--budget',type=int,default=150)
    run.add_argument('--steps',type=int,default=200000)
    run.add_argument('--frames',type=int,default=120)
    run.add_argument('--max-recoveries',type=int,default=2)
    run.add_argument('--auto-continue',action=argparse.BooleanOptionalAction,default=True,
                     help='Continue recovery in bounded source-verified batches (default: on)')
    run.add_argument('--max-rounds',type=int,default=3,
                     help='Maximum recovery batches (1..12, default: 3)')
    run.add_argument('--timeout',type=int,default=720)
    run.add_argument('--ghidra',default='')
    run.add_argument('--export',default='')
    run.add_argument('--capture-hardware',action='store_true')
    run.add_argument('--cpu-plugin',choices=('auto','required','legacy'),default='auto',
                     help='Z80 production instruction gate: auto selects installed DLL, required fails if missing, legacy explicitly bypasses')
    run.add_argument('--reference-image',default='',help='Opt-in aligned PNG/PPM reference screenshot')
    run.add_argument('--reference-session',default='',help='Opt-in independent reference frame-hardware JSON')
    run.add_argument('--input-events',default='')
    run.add_argument('--history-root',action='append',default=[])
    review=sub.add_parser('review-evidence',help='Analyse existing native capture without rerunning any ROM')
    review.add_argument('--evidence-dir',required=True)
    review.add_argument('--out')
    review.add_argument('--reference-image',default='')
    review.add_argument('--reference-session',default='')
    campaign=sub.add_parser('run-campaign',help='Original seven-game owner campaign in isolated legacy sandbox')
    campaign.add_argument('--rom-dir',required=True)
    campaign.add_argument('--out')
    campaign.add_argument('--catalogue')
    campaign.add_argument('--frames',type=int,default=120)
    campaign.add_argument('--steps',type=int,default=200000)
    campaign.add_argument('--max-recoveries',type=int,default=2)
    campaign.add_argument('--compile-timeout',type=int,default=600)
    campaign.add_argument('--timeout',type=int,default=3600)
    campaign.add_argument('--capture-hardware',action='store_true')
    comp=sub.add_parser('compare-discovery',help='Execute original and modular discovery on same source and compare canonical evidence rows')
    comp.add_argument('--rom',required=True)
    comp.add_argument('--out')
    comp.add_argument('--catalogue')
    comp.add_argument('--budget',type=int,default=150)
    comp.add_argument('--timeout',type=int,default=720)
    args=p.parse_args(argv)
    auto_out = None
    if args.command in ('run-rom', 'run-campaign', 'compare-discovery'):
        auto_out = args.out or fresh_evidence()
        selected = Path(auto_out).resolve()
        if selected == ROOT.resolve() or ROOT.resolve() in selected.parents:
            p.error('Run evidence must be outside the Git-managed source checkout')
    try:
        if args.command=='plugins':
            report={'schema':'recompdev-plugins-v0.4.4', 'plugins':list(legacy.registry().values()),
                    'component_versions':manifest(ROOT)['components'],
                    'runtime_active':read_state(ROOT)['active'],
                    'native_recovery_still_uses_legacy_services':True,
                    'production_cpu_admission_plugin_enabled':True}
        elif args.command=='verify':
            report={'source_integrity':preservation.verify(),
                    'loadable_adapters':list(legacy.registry()),'status':'PASS'}
        elif args.command=='status':
            report=preservation.status()
            report['release']='0.4.1-capability-restoration'
            report['legacy_workflows']=['discovery','native-preparation','continuous-recovery','sms-seven-game-campaign']
            report['route']='original_v0445_executables_via_modular_plugin_adapters'
            report['component_versions']=manifest(ROOT)['components']
            report['runtime_active']=read_state(ROOT)['active']
        elif args.command=='run-rom':
            report=controller.run_rom(args.rom,auto_out,stage=args.stage,
                    database=args.catalogue,budget=args.budget,steps=args.steps,
                    frames=args.frames,recoveries=args.max_recoveries,ghidra=args.ghidra,
                    export=args.export,capture=args.capture_hardware,timeout=args.timeout,
                    input_events=args.input_events,history_roots=args.history_root,
                    auto_continue=args.auto_continue,max_rounds=args.max_rounds,
                    reference_image=args.reference_image or None,reference_session=args.reference_session or None,
                    cpu_plugin_mode=args.cpu_plugin)
        elif args.command=='review-evidence':
            source=Path(args.evidence_dir).resolve(strict=True)
            destination=Path(args.out).resolve() if args.out else source.parent/(source.name+'-hardware-v043')
            review_report=hardware_review.analyze_evidence(source,destination,
                        reference_image=args.reference_image or None,
                        reference_session=args.reference_session or None)
            report={'schema':'recompdev-review-command-v0.4.3','status':'HARDWARE_REVIEW_COMPLETE',
                    'hardware_review':review_report,'review_output':str(destination)}
        elif args.command=='run-campaign':
            report=controller.run_campaign(args.rom_dir,auto_out,
                        args.catalogue,args.frames,args.steps,args.max_recoveries,
                        args.compile_timeout,args.capture_hardware,args.timeout)
        else:
            report=controller.compare_discovery(args.rom,auto_out,
                                                 args.catalogue,args.budget,args.timeout)
        if args.command in ('run-rom', 'run-campaign', 'compare-discovery') and Path(auto_out).is_dir():
            record_provenance(Path(auto_out), ROOT, report)
        # Every normal run, including blocked/failed recovery, gets an
        # upload-ready archive. The original evidence is never modified.
        if args.command in ('run-rom', 'run-campaign', 'compare-discovery','review-evidence'):
            destination = (Path(args.out).resolve() if args.out else Path(report['review_output'])) if args.command=='review-evidence' else (getattr(args, 'out', None) or auto_out)
            try:
                report['evidence_bundle'] = evidence_bundle.create_evidence_bundle(
                    destination, source_sha256=report.get('source_sha256'),
                    status=report.get('status', 'UNKNOWN'))
                print('RECOMPDEV_EVIDENCE_ZIP='+report['evidence_bundle']['path'],
                      file=sys.stderr, flush=True)
            except Exception as bundle_error:
                # Evidence-packaging issues must not obscure the actual
                # recovery result or corrupt the production catalogue.
                report['evidence_bundle'] = {
                    'status':'FAILED',
                    'reason':f'{type(bundle_error).__name__}: {bundle_error}'}
                print('RECOMPDEV_EVIDENCE_ZIP_FAILED='+report['evidence_bundle']['reason'],
                      file=sys.stderr, flush=True)
        print(json.dumps(report,indent=2,sort_keys=True))
        return 0 if report.get('status') in ('PASS','CAMPAIGN_REPORTED','DISCOVERY_COMPLETE','PREPARATION_COMPLETE','RECOVERY_REPORTED','HARDWARE_REVIEW_COMPLETE') else 2 if args.command in ('run-rom','run-campaign','compare-discovery') else 0
    except (ValueError,RuntimeError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({'status':'FAIL','error':f'{type(exc).__name__}: {exc}'},indent=2),file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
