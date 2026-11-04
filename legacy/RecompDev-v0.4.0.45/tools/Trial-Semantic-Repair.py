#!/usr/bin/env python3
"""Run approved synthetic semantic recipe search with separate holdout tests."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from campaign.repair import trial
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--discovery',required=True);p.add_argument('--holdout',required=True)
p.add_argument('--output',required=True)
p.add_argument('--broken-recipe',choices=('bitwise-or','xor','identity','wrapping-add'),default='bitwise-or')
a=p.parse_args()
r=trial(a.discovery,a.holdout,a.output,a.broken_recipe)
print(json.dumps(r,indent=2))
raise SystemExit(0 if r['status']=='SYNTHETIC_RECIPE_VALIDATED' else 2)
