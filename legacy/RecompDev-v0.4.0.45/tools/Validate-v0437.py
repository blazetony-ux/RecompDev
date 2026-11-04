#!/usr/bin/env python3
"""v0.4.0.37 compiled parity foundations gate; no assertion of authentic MAME equivalence."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tooling.gates_v0437 import run
if __name__=='__main__':
 try:print(json.dumps(run(),indent=2))
 except Exception as exc:
  print('v0437 VALIDATION FAILED:',repr(exc),file=sys.stderr)
  raise SystemExit(1)
