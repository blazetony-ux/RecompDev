#!/usr/bin/env python3
"""Release v0.4.0.36 compiled acceptance; does not run commercial ROMs."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tooling.gates_v0436 import run
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--skip-tests',action='store_true')
 a=p.parse_args();print(json.dumps(run(run_tests=not a.skip_tests),indent=2))
