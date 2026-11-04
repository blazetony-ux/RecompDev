#!/usr/bin/env python3
"""Automatically recompile and reset/replay on source-attested missing Z80 ROM code."""
from contextlib import closing
import argparse,json,sys,sqlite3
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nativecore.continuous_recovery_v0436 import run
from nativecore.verified_coverage_v0443 import coverage_path

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--rom',required=True);p.add_argument('--export')
 p.add_argument('--db',help='Read prepared source-attested export location from working catalogue')
 p.add_argument('--output-dir',required=True);p.add_argument('--frames',type=int,default=120)
 p.add_argument('--steps',type=int,default=2000000);p.add_argument('--max-recoveries',type=int,default=3)
 p.add_argument('--compile-timeout',type=int,default=480)
 p.add_argument('--capture-hardware',action='store_true',help='Capture frame hashes and last PPM/WAV without physical devices')
 p.add_argument('--input-events',help='Owner-local bounded deterministic input replay')
 p.add_argument('--coverage-cache',help='Override the central source-verified SQLite coverage cache path')
 p.add_argument('--no-coverage-cache',action='store_true',help='Explicitly disable persisted coverage reuse')
 p.add_argument('--no-history-import',action='store_true',help='Do not seed empty cache from earlier evidence directories')
 p.add_argument('--history-root',action='append',default=[],help='Additional owner-local evidence tree (repeatable)')
 a=p.parse_args()
 try:
  export=a.export
  if not export:
   if not a.db:raise ValueError('Supply --export or --db with prepared source evidence')
   from nativepilot.generator import sha256
   db=Path(a.db).resolve(strict=True)
   if not db.is_file():raise ValueError('Catalogue missing')
   with closing(sqlite3.connect(str(db))) as con:
    record=con.execute('SELECT p.export_path,p.source_sha256,p.system FROM native_preparations_v0403 p WHERE p.source_id=?',(sha256(a.rom),)).fetchone()
   if not record or record[1]!=sha256(a.rom) or record[2]!='mastersystem' or not record[0]:
    raise ValueError('Matching prepared Master System source/export is not registered in the catalogue')
   export=record[0]
  root=Path(__file__).resolve().parents[1]
  cache=None if a.no_coverage_cache else coverage_path(root,a.coverage_cache)
  history=[] if a.no_history_import or a.no_coverage_cache else [
    root.parent/'RecompDev-v0.4.0.42'/'evidence',
    root.parent/'RecompDev-v0.4.0.40'/'evidence',
    root/'evidence']+list(map(Path,a.history_root))
  result=run(a.rom,export,a.output_dir,frames=a.frames,steps=a.steps,
             max_recoveries=a.max_recoveries,input_events=a.input_events,
             compile_timeout=a.compile_timeout,capture_hardware=a.capture_hardware,
             coverage_cache=cache,history_roots=history)
 except (ValueError,OSError,TypeError,sqlite3.Error) as e:p.error(str(e))
 print(json.dumps(result,indent=2))
 if result['status'] in ('RECOVERY_BLOCKED','STOPPED_WITHOUT_RECOVERABLE_CODE','BUILD_FAILED','BUILD_TIMEOUT'):raise SystemExit(2)
if __name__=='__main__':main()
