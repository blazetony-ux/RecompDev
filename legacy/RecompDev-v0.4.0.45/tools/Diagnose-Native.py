"""No-ROM diagnostic: report whether native backends initialise in isolated workers."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from recovery.native_workers import run_isolated

def diagnose():
    return {
      'schema':'recomp-native-worker-diagnostic-v0322',
      'python_executable':sys.executable,
      'python_version':sys.version.split()[0],
      'pypcode':run_isolated('pypcode',{'language':'68000:BE:32:default',
                                      'address':0x200,'hex':'7005'},timeout=20),
      'unicorn':run_isolated('unicorn-smoke',{},timeout=20),
      'statement':'Library initialization probes, NOT actual ROM conversion or CPU parity.'
    }

if __name__=='__main__':
    print(json.dumps(diagnose(),indent=2))
