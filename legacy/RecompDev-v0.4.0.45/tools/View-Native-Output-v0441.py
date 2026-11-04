#!/usr/bin/env python3
"""Show *actual generated native guest framebuffer* for an owner ROM.

The generic framebuffer/window pipeline lives in hardware/core.hpp and the
compiled RecompDevNativeApp. This launcher does not emulate a CPU, fabricate
pixels, compile synthetic code, or fetch any ROM. Only source-hash-matched
compiled projects produced by the owner campaign may be launched.
"""
import argparse
import datetime
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

SLUGS = ('shinobi', 'bank-panic', 'alex-kidd', 'fantasy-zone', 'r-type', 'sonic-sms', 'wonder-boy')
NAMES = {
 'shinobi': 'Shinobi (USA, Europe, Brazil) (En) (Rev 1).sms',
 'bank-panic': 'Bank Panic (Europe).sms',
 'alex-kidd': 'Alex Kidd in Miracle World (USA) (Rev-A).sms',
 'fantasy-zone': 'Fantasy Zone (USA) (Rev-A).sms',
 'r-type': 'R-Type (USA).sms',
 'sonic-sms': 'Sonic the Hedgehog (USA).sms',
 'wonder-boy': 'Wonder Boy (USA) (Rev-A).sms',
}
MAX_LOG = 1_000_000


def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as fh:
  for chunk in iter(lambda:fh.read(1048576),b''):h.update(chunk)
 return h.hexdigest()


def read_report(path):
 if not path.is_file() or path.stat().st_size>1048576:raise ValueError('Missing or oversized '+str(path))
 return json.loads(path.read_text(encoding='utf-8'))


def source_rom(rom_dir,slug):
 rom=rom_dir/NAMES[slug]
 if slug=='shinobi' and not rom.is_file():
  alternatives=list(rom_dir.glob('Shinobi*.sms'))
  if len(alternatives)==1:rom=alternatives[0]
  elif len(alternatives)>1:raise ValueError('Multiple Shinobi ROMs. Select the exact source revision.')
 if not rom.is_file():raise ValueError('ROM missing: '+str(rom))
 if rom.stat().st_size>64*1024*1024 or rom.stat().st_size==0:raise ValueError('Invalid ROM size')
 return rom.resolve()


def find_candidate(roots,slug,rom_sha):
 candidates=[]
 for root in roots:
  if not root.is_dir():continue
  for campaign in list(root.glob('evidence/sms-seven-v0441-*'))+list(root.glob('evidence/sms-seven-v0440-*'))+list(root.glob('evidence/sms-seven-v0439-*'))+list(root.glob('evidence/sms-seven-v0438-*')):
   recovery=campaign/slug/'recovery'
   project=recovery/'native-project'
   if not project.is_dir() or not (project/'generation.json').is_file():continue
   try:
    generated=read_report(project/'generation.json')
    report=read_report(recovery/'continuous-recovery-report.json')
   except (OSError,ValueError,UnicodeError,json.JSONDecodeError):continue
   if generated.get('original_source_sha256')!=rom_sha or report.get('source_sha256')!=rom_sha:continue
   bins=[project/'build'/'Release'/'RecompDevNativeApp.exe',project/'build'/'RecompDevNativeApp.exe',project/'build'/'RecompDevNativeApp']
   binary=next((b for b in bins if b.is_file()),None)
   if binary is None:continue
   # Fail closed on stale native builds or untracked compiler artifacts.
   attempts=[a for a in report.get('attempts',[]) if isinstance(a,dict) and isinstance(a.get('executable_sha256'),str)]
   if not attempts:continue
   pilots=[project/'build'/'Release'/'RecompDevNativePilot.exe',project/'build'/'RecompDevNativePilot.exe',project/'build'/'RecompDevNativePilot']
   pilot=next((b for b in pilots if b.is_file()),None)
   if pilot is None or digest(pilot)!=attempts[-1]['executable_sha256']:continue
   recorded_app_hash=attempts[-1].get('native_app_sha256')
   if recorded_app_hash is not None and digest(binary)!=recorded_app_hash:continue
   # Before v0441, reports attested only the pilot binary. Both binaries
   # were CMake-built from the same verified project, but the app binary
   # itself was not separately hashed. Reject obviously stale app builds.
   if not (project/'translated.cpp').is_file():continue
   if recorded_app_hash is None and binary.stat().st_mtime+3< (project/'translated.cpp').stat().st_mtime:continue
   candidates.append((campaign.stat().st_mtime,project,binary,report))
 if not candidates:raise ValueError('No verified compiled native project for this ROM. Run the v0.4.0.41 seven-game campaign first.')
 return max(candidates,key=lambda candidate:candidate[0])


def show_still(ppm,title):
 if not ppm.is_file():raise ValueError('Generated framebuffer not found: '+str(ppm))
 raw=ppm.open('rb').read(32)
 if not re.match(rb'P6\s+256\s+192\s+255\s',raw):
  raise ValueError('Expected generated 256x192 PPM framebuffer')
 import tkinter as tk
 root=tk.Tk();root.title(title+' — saved native framebuffer (not gameplay-verified)')
 original=tk.PhotoImage(file=str(ppm))
 enlarged=original.zoom(3,3)
 canvas=tk.Label(root,image=enlarged,bg='black');canvas.pack(padx=10,pady=10)
 canvas.image=enlarged
 tk.Label(root,text='Captured from translated guest execution. Not MAME-parity-verified. Close window to exit.').pack(pady=(0,10))
 root.mainloop()


def main(argv=None):
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--game',choices=SLUGS,default='shinobi')
 ap.add_argument('--rom-dir',type=Path,default=Path(r'C:\Roms\MASTERSYSTEM'))
 ap.add_argument('--install-parent',type=Path,default=Path(r'C:\Projects'))
 ap.add_argument('--frames',type=int,default=120)
 ap.add_argument('--steps',type=int,default=6000000)
 ap.add_argument('--still',action='store_true',help='View the saved framebuffer without executing the guest again')
 ap.add_argument('--no-hold',action='store_true',help='Close window at the end of the native run')
 a=ap.parse_args(argv)
 if not (1<=a.frames<=1800 and 1<=a.steps<=20_000_000):ap.error('Frame or step limit out of bounds')
 root=Path(__file__).resolve().parents[1]
 rom=source_rom(a.rom_dir,a.game)
 rom_sha=digest(rom)
 _,project,binary,report=find_candidate([root,a.install_parent/'RecompDev-v0.4.0.40',a.install_parent/'RecompDev-v0.4.0.39',a.install_parent/'RecompDev-v0.4.0.38'],a.game,rom_sha)
 print('GAME='+a.game,flush=True)
 print('SOURCE_SHA256='+rom_sha,flush=True)
 print('GENERATED_PROJECT='+str(project),flush=True)
 print('NATIVE_EXECUTABLE='+str(binary),flush=True)
 print('GUEST_CPU=Z80; GRAPHICS_SOURCE=TRANSLATED_GUEST_VDP; REFERENCE_PARITY=NOT_ESTABLISHED',flush=True)
 if a.still:
  frames=sorted(project.parent.glob('sessions/attempt-*/native-frame.ppm'),key=lambda x:x.stat().st_mtime)
  frames+=sorted((root/'evidence'/'native-screen-v0441'/a.game).glob('*/native-frame.ppm'),key=lambda x:x.stat().st_mtime) if (root/'evidence'/'native-screen-v0441'/a.game).is_dir() else []
  if not frames:raise ValueError('No saved native framebuffer exists. Run without --still first.')
  show_still(max(frames,key=lambda x:x.stat().st_mtime),a.game)
  return 0
 if sys.platform!='win32':raise ValueError('Live native window requires Windows; use --still for saved frames')
 # v0438 binaries support --video window but not the v0441 hold flag.
 is_v0441=any(v in project.parts for v in ('RecompDev-v0.4.0.41','RecompDev-v0.4.0.40','RecompDev-v0.4.0.39'))
 stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
 out=root/'evidence'/'native-screen-v0441'/a.game/stamp
 out.mkdir(parents=True,exist_ok=False)
 prefix=out/'native-frame'
 cmd=[str(binary),str(rom),str(prefix),str(a.frames),str(a.steps),'-',
      '--video','window','--audio','capture','--input','neutral']
 if is_v0441 and not a.no_hold:cmd.append('--hold-window')
 print('SCREEN=OPENING_NATIVE_WINDOW',flush=True)
 if not is_v0441:print('NOTE=v0438 compiled executable: closes at session end; run v0441 campaign for held-window support',flush=True)
 print('CAPTURE_DIRECTORY='+str(out),flush=True)
 print('Press Esc or close the window when finished inspecting the native graphics.',flush=True)
 try:
  completed=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,errors='replace',timeout=410)
 except subprocess.TimeoutExpired as ex:
  (out/'screen-launch-report.json').write_text(json.dumps({'status':'TIMEOUT','source_sha256':rom_sha},indent=2)+'\n')
  raise ValueError('Native display exceeded bounded timeout') from ex
 (out/'native-stdout.log').write_text(completed.stdout[-MAX_LOG:],encoding='utf-8')
 (out/'native-stderr.log').write_text(completed.stderr[-MAX_LOG:],encoding='utf-8')
 match=re.search(r'^NATIVE_APP_RESULT=(\{.*\})$',completed.stdout,re.M)
 observation=json.loads(match.group(1)) if match else None
 artifacts={x:(prefix.with_suffix('.'+x).is_file()) for x in ('ppm','wav')}
 result={'schema':'recomp-native-screen-v0441','status':'CAPTURE_RETURNED' if completed.returncode==0 and observation else 'NATIVE_EXIT_OR_REPORT_FAILURE',
         'exit_code':completed.returncode,'source_sha256':rom_sha,'executable_sha256':digest(binary),
         'frames_requested':a.frames,'steps_requested':a.steps,'source_project':str(project),
         'observation':{'status':observation.get('status'),'frames':observation.get('frames'),'native_steps':observation.get('native_steps'),'cram_nonzero_bytes':observation.get('cram_nonzero_bytes')} if observation else None,
         'outputs':artifacts,'independent_reference_parity':'NOT_TESTED','playable_game':'NOT_ESTABLISHED'}
 (out/'screen-launch-report.json').write_text(json.dumps(result,indent=2)+'\n')
 print('SCREEN_RESULT='+result['status'],flush=True)
 print('FRAMEBUFFER='+str(prefix.with_suffix('.ppm')) if artifacts['ppm'] else 'NONE',flush=True)
 print('REPORT='+str(out/'screen-launch-report.json'),flush=True)
 if completed.returncode:
  print('NATIVE_ERROR='+completed.stderr[-1500:],file=sys.stderr)
  return 2
 # Existing v0438 apps cannot hold their own window open. Display their
 # actual saved PPM in a CPU-neutral viewer after native execution finishes.
 if not is_v0441 and artifacts['ppm'] and not a.no_hold:
  print('SAVED_FRAME_VIEWER=OPENING (close viewer window to finish)',flush=True)
  show_still(prefix.with_suffix('.ppm'),a.game)
 return 0

if __name__=='__main__':
 try:sys.exit(main())
 except (ValueError,OSError,UnicodeError,json.JSONDecodeError,RuntimeError) as e:
  print('SCREEN_LAUNCH_BLOCKED='+str(e),file=sys.stderr)
  sys.exit(2)
