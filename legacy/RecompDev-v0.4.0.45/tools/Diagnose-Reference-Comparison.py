#!/usr/bin/env python3
import sys,argparse,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from campaign.reference_triage import triage
p=argparse.ArgumentParser(description='Non-mutating external reference comparison triage')
p.add_argument('--input',required=True);p.add_argument('--comparison',required=True);p.add_argument('--output',required=True)
a=p.parse_args();print(json.dumps(triage(a.input,a.comparison,a.output),indent=2))
