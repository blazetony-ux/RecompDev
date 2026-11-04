#!/usr/bin/env python3
"""No modifications to the existing RecompDev catalogue or binary sources."""
import argparse, json, csv
from pathlib import Path
from adapters.identity import identify
from adapters.registry import ADAPTERS
from planner import plan
from name_sync import scan_names

def main(argv=None):
    ap=argparse.ArgumentParser(description='RecompDev v0.3 identity adapters + read-only batch native readiness')
    p=ap.add_subparsers(dest='command',required=True)
    ident=p.add_parser('identify',help='Read game identity from file/container metadata')
    ident.add_argument('--input',required=True)
    ident.add_argument('--title-db',help='Optional owner-provided CSV with system,id,title to resolve serial/title ID')
    batch=p.add_parser('identify-folder',help='Identify all immediate input files (no code scanning)')
    batch.add_argument('--input',required=True)
    batch.add_argument('--title-db')
    sync=p.add_parser('sync-names',help='SHA-matched automated target naming from owner-local source tree; dry-run by default')
    sync.add_argument('--db',required=True);sync.add_argument('--sources-root',required=True);sync.add_argument('--apply',action='store_true');sync.add_argument('--include-discs',action='store_true')
    caps=p.add_parser('adapters',help='Show supported/partial/planned container adapters')
    readiness=p.add_parser('plan-cpp',help='Read current SQLite graph and produce C++ readiness queue')
    readiness.add_argument('--db',required=True)
    readiness.add_argument('--output',help='Output metadata-only JSON to this path')
    args=ap.parse_args(argv)
    try:
        if args.command=='adapters':o={'schema':'recomp-adapter-registry-v1','adapters':ADAPTERS}
        elif args.command=='plan-cpp':o=plan(args.db)
        elif args.command=='sync-names':o=scan_names(args.db,args.sources_root,apply=args.apply,include_discs=args.include_discs)
        else:
            def enrich(r):
                if not args.title_db or not r['identity'].get('game_id'):return r
                with open(args.title_db,newline='',encoding='utf-8-sig') as f:
                    rows=list(csv.DictReader(f))
                key=r['identity']['game_id'].upper().replace('_','-')
                matched=[x for x in rows if x.get('id','').upper().replace('_','-')==key and x.get('title') and x.get('system','').lower() in (r['identity']['system'].lower(),'ps1' if r['identity']['system']=='ps1' else r['identity']['system'].lower())]
                unique={x['title'].strip() for x in matched}
                if len(unique)==1:
                    r['identity'].update(display_name=unique.pop(),name_source='owner_supplied_title_db',confidence='external_catalogue_match')
                elif len(unique)>1:r['identity']['notes']+=('Serial matches multiple titles: identity ambiguous.',)
                return r
            if args.command=='identify':o=enrich(identify(args.input))
            else:
                folder=Path(args.input)
                if not folder.is_dir():raise ValueError('input directory not found')
                o={'schema':'recomp-identity-folder-v1','results':[],'errors':[]}
                for f in sorted(folder.iterdir()):
                    if f.is_file() and f.suffix.lower() in ('.md','.gen','.bin','.img','.iso','.psx','.exe','.elf','.xex','.con','.stfs','.live','.pirs','.sfo'):
                        try:o['results'].append(enrich(identify(f)))
                        except (OSError,ValueError) as e:o['errors'].append({'file':str(f),'error':str(e)})
        output=json.dumps(o,indent=2,ensure_ascii=False)
        if getattr(args,'output',None):
            out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(output+'\n',encoding='utf-8')
            print('REPORT='+str(out));print('STATUS=READ_ONLY_CATALOGUE_PLAN;NATIVE_PARITY=NOT_VERIFIED')
        else:print(output)
        return 0
    except (OSError,ValueError,KeyError,UnicodeError) as e:
        print('ERROR: '+str(e));return 1

if __name__=='__main__':raise SystemExit(main())
