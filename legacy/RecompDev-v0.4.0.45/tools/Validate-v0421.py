#!/usr/bin/env python3
import sys,argparse,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tooling.gates_v0421 import run
p=argparse.ArgumentParser();p.add_argument('--skip-tests',action='store_true')
a=p.parse_args();print(json.dumps(run(run_tests=not a.skip_tests),indent=2))
