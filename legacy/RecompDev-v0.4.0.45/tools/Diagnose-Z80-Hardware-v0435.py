#!/usr/bin/env python3
"""Produce CPU/IRQ/mapper/VDP provenance triage without claiming MAME parity."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nativecore.hardware_triage_v0435 import diagnose

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--pilot-report',required=True)
 p.add_argument('--alignment-report');p.add_argument('--output',required=True)
 a=p.parse_args()
 dest=Path(a.output).resolve()
 if dest.exists():p.error('Output exists; do not overwrite an evidence snapshot')
 try:result=diagnose(a.pilot_report,a.alignment_report)
 except (ValueError,OSError,KeyError,TypeError) as e:p.error(str(e))
 dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
