#!/usr/bin/env python3
"""Compare owner-captured MAME frame samples against one authentic compiled session.

Unaligned frame observations are never promoted to native CPU equivalence.
"""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nativecore.reference_parity_v0437 import compare_frame_observations

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('reference-dir','native-session','rom','output'):
  p.add_argument('--'+name,required=True)
 a=p.parse_args();out=Path(a.output)
 if out.exists():p.error('Refusing to overwrite immutable comparison evidence')
 report=compare_frame_observations(a.reference_dir,a.native_session,a.rom)
 out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(report,indent=2))
 # An unaligned comparison is an honest diagnostic, not a verified parity gate.
 return 0
if __name__=='__main__':sys.exit(main())
