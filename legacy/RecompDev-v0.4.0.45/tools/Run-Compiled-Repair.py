#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from campaign.compiled_repair import repair
p=argparse.ArgumentParser(description='Bounded synthetic C++ candidate repair, does not patch production')
p.add_argument('--discovery',required=True);p.add_argument('--holdout',required=True)
p.add_argument('--output',required=True);p.add_argument('--compiler',required=True)
a=p.parse_args();r=repair(a.discovery,a.holdout,a.output,a.compiler)
print(json.dumps(r,indent=2));raise SystemExit(0 if r['status']=='ISOLATED_COMPILED_HOLDOUT_PASS' else 2)
