"""Prove compiled controller launches the rights-cleared native-export demo."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
import tempfile

exe=Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix='recompdev-v34-controller-demo-') as root:
    root=Path(root);out=root/'standalone'
    p=subprocess.run([str(exe),'export','demo','--out',str(out)],
                     cwd=root,capture_output=True,text=True,timeout=220)
    assert p.returncode==0,(p.stdout[-2000:],p.stderr[-3000:])
    assert out.is_dir() and (out/'export-manifest.json').is_file()
    m=json.loads((out/'export-manifest.json').read_text())
    assert m['isolated_native_launch']['status']=='PASS'
    assert m['source_data_storage']=='embedded_in_native_executable'
    assert m['coverage_qualification']=='NOT_ESTABLISHED'
    assert sorted(q.name for q in out.iterdir())==sorted(['README.txt','export-manifest.json',m['native_executable']])
    v=subprocess.run([str(exe),'export','verify','--bundle',str(out)],
                     cwd=root,capture_output=True,text=True,timeout=30)
    assert v.returncode==0,(v.stdout,v.stderr)
    assert '"status": "VERIFIED"' in v.stdout
    print('RECOMPDEV_V34_CONTROLLER_DEMO_PASS native independent executable produced and verified')
