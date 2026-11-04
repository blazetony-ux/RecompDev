#!/usr/bin/env python3
"""Read-only platform suitability assessment; writes JSON only to --output."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from platform_profiles import PROFILES,inspect_source

def main():
    p=argparse.ArgumentParser(description='Inspect CPU-vs-hardware compatibility without running foreign code')
    p.add_argument('--source',required=True)
    p.add_argument('--platform',choices=sorted(PROFILES),help='Explicit owner assertion, not a verified autodetection')
    p.add_argument('--output',help='Optional assessment JSON file')
    args=p.parse_args()
    report=inspect_source(args.source,args.platform)
    blob=json.dumps(report,indent=2,sort_keys=True)+'\n'
    if args.output:
        output=Path(args.output).resolve()
        if output==Path(args.source).resolve():p.error('refusing to overwrite source')
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(blob,encoding='utf-8')
    print(blob,end='')
    return 0 if report['native_status']=='EXPERIMENTAL_SMS_NATIVE_PILOT' else 2
if __name__=='__main__':sys.exit(main())
