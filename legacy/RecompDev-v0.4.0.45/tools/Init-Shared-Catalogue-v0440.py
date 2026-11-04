#!/usr/bin/env python3
"""Ensure RecompDev's persistent catalogue exists, once for all releases."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nativecore.shared_catalogue import ensure_shared_catalogue

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--db',type=Path,help='Optional central catalogue override')
    a=p.parse_args(argv)
    try:
        result=ensure_shared_catalogue(a.root,a.db)
    except Exception as exc:
        print('SHARED_CATALOGUE_ERROR='+type(exc).__name__+': '+str(exc),file=sys.stderr)
        return 2
    print('SHARED_CATALOGUE_STATUS='+result['status'])
    print('DATABASE='+result['destination'])
    if result.get('source'):print('ONE_TIME_SOURCE='+result['source'])
    return 0
if __name__=='__main__':raise SystemExit(main())
