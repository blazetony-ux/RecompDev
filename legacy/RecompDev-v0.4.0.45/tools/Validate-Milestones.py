from pathlib import Path
import sys,json,argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tooling.gates_v0420 import verify
p=argparse.ArgumentParser();p.add_argument('--skip-tests',action='store_true');p.add_argument('--output')
a=p.parse_args();r=verify(run_tests=not a.skip_tests)
if a.output:
 f=Path(a.output)
 if f.exists():raise SystemExit('Refusing to overwrite prior verification evidence')
 f.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
print(json.dumps(r,indent=2))
