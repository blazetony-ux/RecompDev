"""Release label must agree in compiled controller and live session source."""
import json
from pathlib import Path
import subprocess
import sys

exe=Path(sys.argv[1]);source=Path(sys.argv[2]);
expected='workspace/'+json.loads((source/'workspace/components.json').read_text())['workspace_release']
p=subprocess.run([str(exe),'--version'],capture_output=True,text=True,timeout=20)
assert p.returncode==0,(p.stdout,p.stderr)
assert p.stdout.strip()=='RecompDev '+expected.removeprefix('workspace/v'),(p.stdout,expected)
live=(source/'analysis_integration/live_session.py').read_text(encoding='utf8')
assert 'evidence_version(source)' in live and "'release':current_release(source)" in live
assert "evidence_root(source,config)/'v0.4.9.29'" not in live
print('RECOMPDEV_RELEASE_IDENTITY_PASS '+expected)
