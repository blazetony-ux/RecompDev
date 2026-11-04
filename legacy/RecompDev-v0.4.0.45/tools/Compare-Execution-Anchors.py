#!/usr/bin/env python3
"""Check two explicitly recorded binary-source execution anchors; never guess."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nativecore.alignment import compare_anchors
from campaign.engine import atomic_json
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',required=True);p.add_argument('--anchors',required=True);p.add_argument('--output',required=True)
a=p.parse_args()
f=Path(a.anchors)
if not f.is_file() or f.stat().st_size>1024*1024:raise ValueError('Missing/oversized anchors')
x=json.loads(f.read_text(encoding='utf-8'))
if x.get('schema')!='recomp-explicit-anchor-pair-v1':raise ValueError('Unknown anchor bundle schema')
r=compare_anchors(x['reference'],x['native'],a.source)
atomic_json(a.output,r)
print(json.dumps(r,indent=2))
raise SystemExit(0 if r['status']=='MATCHED_CODE_IDENTITY_WITH_SELECTED_REGISTERS' else 2)
