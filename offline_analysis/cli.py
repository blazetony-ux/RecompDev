#!/usr/bin/env python3
"""One owner command for every supported ROM or executable format."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from offline_analysis.engine import AnalysisFailure,interrogate,registry

def main(argv=None):
    parser=argparse.ArgumentParser(description='Universal plugin-dispatched, non-executing ROM interrogation')
    parser.add_argument('--rom',type=Path)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--budget',type=int,default=40000)
    parser.add_argument('--profile',default=None,help='Select a registered format plugin; no forced reinterpretation')
    parser.add_argument('--profiles',action='store_true',help='List registered profiles without running a game')
    a=parser.parse_args(argv)
    if a.profiles:
        print('RECOMPDEV_OFFLINE_PROFILES='+json.dumps({'schema':'recompdev.offline.profiles.v1','profiles':registry()},sort_keys=True))
        return 0
    if a.rom is None or a.out is None:parser.error('--rom and --out are both required')
    try:
        result=interrogate(a.rom,a.out,budget=a.budget,profile=a.profile)
        print('RECOMPDEV_OFFLINE_ANALYSIS='+json.dumps({'status':result['status'],
              'source_sha256':result['source_sha256'],'profile':result.get('profile'),
              'static_candidates':result.get('decoded_candidates',0),
              'unresolved':result.get('unresolved',0),'output':str(a.out)},sort_keys=True))
        return 2 if result['status']=='UNSUPPORTED_FORMAT' else 0
    except (AnalysisFailure,ValueError,OSError) as e:
        print('RECOMPDEV_OFFLINE_ANALYSIS_ERROR='+str(e),file=sys.stderr)
        return 3

if __name__=='__main__':raise SystemExit(main())
