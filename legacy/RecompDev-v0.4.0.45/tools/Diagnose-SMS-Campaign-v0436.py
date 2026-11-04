#!/usr/bin/env python3
"""Produce cross-game Z80 and SMS symptom correlation from source-identified owner sessions."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nativecore.session_triage_v0436 import analyze_campaign
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--campaign',required=True);p.add_argument('--output',required=True)
a=p.parse_args()
src=Path(a.campaign).resolve(strict=True);dst=Path(a.output).resolve()
if dst.exists():p.error('Refusing to overwrite immutable evidence')
result=analyze_campaign(json.loads(src.read_text(encoding='utf-8')),src.parent)
dst.parent.mkdir(parents=True,exist_ok=True)
dst.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
