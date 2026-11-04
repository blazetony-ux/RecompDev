#!/usr/bin/env python3
"""Owner-local, optional Shinobi MAME observation and native comparison.

Requires an independently installed MAME; never substitutes emulation for the
compiled guest CPU. Frame comparisons are diagnostic and NOT instruction parity.
"""
import argparse,datetime as dt,hashlib,importlib.util,json,re,shutil,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nativecore.frame_oracle import sha256
from nativecore.reference_parity_v0437 import compare_frame_observations

SHINOBI='Shinobi (USA, Europe, Brazil) (En) (Rev 1).sms'

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--mame',type=Path,help='Explicit owner-installed MAME executable; defaults to mame on PATH')
 p.add_argument('--rom',type=Path,default=Path(r'C:\Roms\MASTERSYSTEM')/SHINOBI)
 p.add_argument('--native-session',type=Path,help='Existing compiled native continuous-session.json; auto-select latest v0436 Shinobi')
 p.add_argument('--output-dir',type=Path)
 p.add_argument('--frames',type=int,default=120)
 p.add_argument('--timeout',type=int,default=180)
 p.add_argument('--rom-root',type=Path,action='append',default=[],help='Additional owner-approved MAME BIOS directory')
 a=p.parse_args()
 mame=a.mame or (Path(shutil.which('mame') or shutil.which('mame.exe')) if (shutil.which('mame') or shutil.which('mame.exe')) else None)
 if mame is None or not mame.is_file():p.error('MAME is not available on PATH. Supply --mame <your installed mame.exe>; no parity claim possible.')
 native=a.native_session
 if native is None:
  base=Path(r'C:\Projects\RecompDev-v0.4.0.36')/'evidence'
  choices=list(base.glob('sms-seven-v0436-*/shinobi/recovery/sessions/attempt-*/continuous-session.json'))
  if not choices:p.error('No v0.4.0.36 Shinobi session found; use --native-session <existing report path>')
  native=max(choices,key=lambda x:(x.parent.parent.parent.parent.parent.stat().st_mtime,x.parent.name))
 if not native.is_file():p.error('Native session missing: '+str(native))
 if not a.rom.is_file():p.error('Owner Shinobi ROM missing: '+str(a.rom))
 session=json.loads(native.read_text(encoding='utf-8'))
 source=sha256(a.rom)
 if source!=session.get('source_sha256'):p.error('Native ROM SHA-256 and owner source do not match')
 if type(a.frames)!=int or not 1<=a.frames<=1200:p.error('Invalid frame bound')
 if len(session.get('frame_hardware',[]))<a.frames:p.error('Native execution has fewer captured frames than requested')
 stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M%S')
 out=(a.output_dir or ROOT/'evidence'/('shinobi-mame-reference-v0437-'+stamp)).resolve()
 if out.exists():p.error('Refusing to overwrite a previous reference capture')
 spec=importlib.util.spec_from_file_location('mame_capture',ROOT/'tools/Capture-MAME-SMS.py')
 mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 print('MAME_REFERENCE_SOURCE='+source,flush=True)
 print('MAME_REFERENCE_TOOL='+str(mame.resolve()),flush=True)
 try:
  mod.capture(mame,mame.resolve().parent,a.rom,source,out,'sms',a.frames,a.timeout,a.rom_root)
  report=compare_frame_observations(out,native,a.rom)
  (out/'mame-native-sampled-comparison.json').write_text(json.dumps(report,indent=2)+'\n')
  print('MAME_SAMPLED_COMPARISON='+report['status'],flush=True)
  print('CPU_PARITY='+report['cpu_parity'],flush=True)
 except Exception as error:
  out.mkdir(parents=True,exist_ok=True)
  (out/'reference-capture-status.json').write_text(json.dumps({
   'status':'REFERENCE_CAPTURE_FAILED','error':str(error),'cpu_parity':'NOT_ESTABLISHED'},indent=2)+'\n')
  print('REFERENCE_CAPTURE_FAILED='+str(error),flush=True)
 finally:
  zpath=out.with_suffix('.zip')
  with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED) as archive:
   for name in ('frame-observations.json','mame-frames.jsonl','selected-bus-reference.json','mame-bus.jsonl',
                'mame-native-sampled-comparison.json','reference-capture-status.json','mame-stderr.log','mame-stdout.log'):
    path=out/name
    if path.is_file() and path.stat().st_size<=8*1024*1024:archive.write(path,name)
  print('EVIDENCE_ZIP='+str(zpath),flush=True)
 return 0 if (out/'mame-native-sampled-comparison.json').is_file() else 2
if __name__=='__main__':raise SystemExit(main())
