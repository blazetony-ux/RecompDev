"""Assess MAME/native startup from existing authenticated captures (no rerun required)."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nativecore.sms_startup_v0433 import inspect

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--reference-dir',required=True)
 p.add_argument('--pilot-report',required=True)
 p.add_argument('--out',required=True)
 a=p.parse_args();out=Path(a.out).resolve()
 if out.exists():p.error('Output already exists; immutable evidence')
 try:result=inspect(a.reference_dir,a.pilot_report)
 except (OSError,ValueError,KeyError,TypeError) as err:p.error(str(err))
 out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:v for k,v in result.items() if k!='first_selected_io_difference'},indent=2))
if __name__=='__main__':main()
