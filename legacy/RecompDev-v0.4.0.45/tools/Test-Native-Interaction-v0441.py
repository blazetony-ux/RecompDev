#!/usr/bin/env python3
"""Rebuild an SHA-attested generated SMS project with current generic input support.

Original ROM and generated C++ remain solely on the owner's computer. This
runner checks neutral vs controlled Pause/Start, and can run a live native window.
It never falls back to CPU emulation and does not claim gameplay/MAME parity.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
GUEST_CLOCK=3579545
REFRESH=60
MAX_LOG=1048576
BUTTON_MASKS={"start":128,"a":16,"b":32}

def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as file:
  for block in iter(lambda:file.read(1048576),b''):h.update(block)
 return h.hexdigest()

def load_screen():
 spec=importlib.util.spec_from_file_location('native_screen_v0440',HERE/'View-Native-Output-v0440.py')
 mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 return mod

def start_timeline(path,at_frame,duration,frames,button="start"):
 if not (1<=at_frame<frames and 1<=duration<=120 and at_frame+duration<frames):
  raise ValueError('Input press must begin and end within the requested session')
 if button not in BUTTON_MASKS:raise ValueError('Unknown SMS input action')
 # Schedule in guest Z80 cycles, not approximate wall-clock seconds.
 at=(at_frame*GUEST_CLOCK)//REFRESH
 release=((at_frame+duration)*GUEST_CLOCK)//REFRESH
 data=f'RECOMP_INPUT_CYCLES_V1\n0,0,0\n{at},0,{BUTTON_MASKS[button]}\n{release},0,0\n'
 path.write_text(data,encoding='ascii',newline='\n')
 return {'button':button,'button_mask':BUTTON_MASKS[button],'start_frame':at_frame,'release_frame':at_frame+duration,
         'start_cycle':at,'release_cycle':release,'input_sha256':digest(path)}

def native_sources():
 source=[('nativepilot',n) for n in ('main.cpp','interactive.cpp','live_sms.hpp','z80_cycles.hpp','CMakeLists.txt')]
 source += [('systems/mastersystem',n) for n in ('runtime.cpp','runtime.hpp','counters.hpp')]
 source += [('hardware',n) for n in ('core.hpp','runtime.hpp','continuous.hpp','input_replay.hpp','backends.hpp','image_io.hpp','wav.hpp','win32_window.hpp','win32_audio.hpp','adapters/sms.hpp')]
 return source

def prepare(earlier,project,rom_sha):
 generation=earlier/'generation.json'
 if not generation.is_file():raise ValueError('Generated source provenance missing')
 doc=json.loads(generation.read_text(encoding='utf-8'))
 if doc.get('original_source_sha256')!=rom_sha:raise ValueError('Generated source does not match original ROM')
 if doc.get('translated_instructions',0)<1:raise ValueError('No source-attested native instructions')
 project.mkdir(parents=True,exist_ok=False)
 generated=('translated.cpp','generation.json','emitted-offsets.json','unsupported-offsets.json')
 for name in generated:
  src=earlier/name
  if src.is_file():shutil.copy2(src,project/name)
 if not (project/'translated.cpp').is_file():raise ValueError('Missing authenticated translated C++')
 # Preserve *exactly* the recovered guest instructions. Only retarget the
 # architecture-specific native adapter and the CPU-neutral host runtime.
 before=digest(earlier/'translated.cpp')
 for folder,name in native_sources():
  src=ROOT/folder/name
  if not src.is_file():raise ValueError('Missing current native host source: '+str(src))
  target=project/('hardware/'+name if folder=='hardware' else name)
  target.parent.mkdir(parents=True,exist_ok=True)
  shutil.copy2(src,target)
 if digest(project/'translated.cpp')!=before:raise ValueError('Translated guest code modified')
 return {'source_sha256':rom_sha,'guest_translation_sha256':before,
         'native_adapter_sha256':digest(project/'runtime.cpp'),'native_host_sha256':digest(project/'interactive.cpp')}

def exe_path(project,name):
 for p in (project/'build'/'Release'/(name+'.exe'),project/'build'/(name+'.exe'),project/'build'/name):
  if p.is_file():return p
 raise ValueError('Compiled '+name+' not found')

def build(project):
 build_dir=project/'build'
 for args in (['cmake','-S',str(project),'-B',str(build_dir)],
              ['cmake','--build',str(build_dir),'--config','Release','--parallel','2']):
  try:
   p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,
                    errors='replace',timeout=900,check=False)
  except (OSError,subprocess.TimeoutExpired) as ex:raise ValueError('Native CMake build failed: '+str(ex)) from ex
  (project/('configure.log' if args[1]=='-S' else 'compile.log')).write_text(p.stdout[-MAX_LOG:],encoding='utf-8')
  if p.returncode:raise ValueError('Native build failed, inspect '+str(project/'compile.log'))
 return exe_path(project,'RecompDevNativeApp'),exe_path(project,'RecompDevNativePilot')

def run_native(exe,rom,folder,frames,steps,mode,replay=None):
 folder.mkdir(parents=True,exist_ok=False)
 prefix=folder/'native-frame'
 cmd=[str(exe),str(rom),str(prefix),str(frames),str(steps),'-',
      '--video','window' if mode=='live' else 'capture','--audio','capture',
      '--input','live' if mode=='live' else 'replay' if replay else 'neutral']
 if replay:cmd+=['--input-events',str(replay)]
 if mode=='live':print('LIVE_KEYS=Enter:Start/Pause NMI; Arrows:movement; Z/X:buttons; Esc:close',flush=True)
 try:p=subprocess.run(cmd,capture_output=True,text=True,errors='replace',timeout=240,check=False)
 except (OSError,subprocess.TimeoutExpired) as e:raise ValueError('Native execution failed to launch/finish: '+str(e)) from e
 (folder/'native-stdout.log').write_text(p.stdout[-MAX_LOG:],encoding='utf-8')
 (folder/'native-stderr.log').write_text(p.stderr[-MAX_LOG:],encoding='utf-8')
 m=re.search(r'^NATIVE_APP_RESULT=(\{.*\})$',p.stdout,re.M)
 result=json.loads(m.group(1)) if m else None
 if p.returncode or result is None:
  return {'status':'NATIVE_EXIT_OR_REPORT_FAILURE','exit_signed':p.returncode,'exit_hex':f'0x{p.returncode&0xffffffff:08X}',
          'stderr_tail':p.stderr[-1000:]}
 if result.get('hardware_parity')!='NOT_TESTED':raise ValueError('Unsupported parity assertion')
 return {'status':result.get('status'),'frames':result.get('frames'),'steps':result.get('native_steps'),
         'guest_cycles':result.get('guest_cycles'),'nmi_events':result.get('nmi_events'),
         'pc':result.get('pc'),'guest_state_fingerprint':result.get('guest_state_fingerprint'),
         'frame_hashes':result.get('frame_hashes'),
         'frame_ppm':(prefix.with_suffix('.ppm')).is_file(),
         'frame_ppm_sha256':digest(prefix.with_suffix('.ppm')) if prefix.with_suffix('.ppm').is_file() else None,
         'input_backend':result.get('input_backend'),'reference_parity':'NOT_TESTED'}

def first_frame_difference(before,after):
 x=before.get('frame_hashes') or [];y=after.get('frame_hashes') or []
 for i,(a,b) in enumerate(zip(x,y)):
  if a!=b:return i+1
 return None

def pack_report(folder):
 archive=folder.with_suffix('.zip')
 allowed={'interaction-report.json','native-stdout.log','native-stderr.log','compile.log','configure.log','RELEASE_NOTES.txt','start-input.csv'}
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
  for p in sorted(folder.rglob('*')):
   if p.is_file() and p.name in allowed and p.stat().st_size<=MAX_LOG:
    z.write(p,p.relative_to(folder))
 return archive

def main(argv=None):
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--game',choices=('shinobi','bank-panic','alex-kidd','fantasy-zone','r-type','sonic-sms','wonder-boy'),default='r-type')
 ap.add_argument('--mode',choices=('test','live'),default='test')
 ap.add_argument('--frames',type=int,default=600)
 ap.add_argument('--steps',type=int,default=12000000)
 ap.add_argument('--start-frame',type=int,default=300)
 ap.add_argument('--start-duration',type=int,default=4)
 ap.add_argument('--button',choices=tuple(BUTTON_MASKS),default='start',help='SMS console Start/Pause NMI, or controller button A/B')
 ap.add_argument('--show',action='store_true',help='Display guest-generated final framebuffer after the two-session test')
 ap.add_argument('--rom-dir',type=Path,default=Path(r'C:\Roms\MASTERSYSTEM'))
 ap.add_argument('--install-parent',type=Path,default=Path(r'C:\Projects'))
 a=ap.parse_args(argv)
 if not 30<=a.frames<=1800 or not 1000<=a.steps<=20000000:ap.error('Invalid bounded frame or step count')
 if a.mode=='test' and not (1<=a.start_frame<a.frames and 1<=a.start_duration<=120 and a.start_frame+a.start_duration<a.frames):ap.error('Start pulse outside session')
 if sys.platform!='win32':ap.error('Owner-local Windows native program required')
 screen=load_screen();rom=screen.source_rom(a.rom_dir,a.game);sha=digest(rom)
 _,source_project,source_binary,_=screen.find_candidate([a.install_parent/'RecompDev-v0.4.0.40',a.install_parent/'RecompDev-v0.4.0.39',a.install_parent/'RecompDev-v0.4.0.38'],a.game,sha)
 if (source_project/'translated.cpp').stat().st_mtime>source_binary.stat().st_mtime+3:
  raise ValueError('Source-attested translated C++ has changed after the verified native build')
 stamp=dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
 out=ROOT/'evidence'/'native-interaction-v0441'/a.game/stamp
 out.mkdir(parents=True,exist_ok=False)
 project=out/'native-project'
 print('GAME='+a.game,flush=True)
 print('SOURCE_SHA256='+sha,flush=True)
 print('SOURCE_TRANSLATED_PROJECT='+str(source_project),flush=True)
 try:
  attestation=prepare(source_project,project,sha)
  print('GUEST_TRANSLATION_SHA256='+attestation['guest_translation_sha256'],flush=True)
  print('NATIVE_BUILD=COMPILING_SOURCE_ATTESTED_GUEST_AND_V0441_HOST',flush=True)
  exe,pilot=build(project)
  attestation.update({'native_app_sha256':digest(exe),'native_pilot_sha256':digest(pilot)})
  print('NATIVE_EXECUTABLE='+str(exe),flush=True)
  report={'schema':'recomp-native-interaction-v0441','game':a.game,'mode':a.mode,
          'status':'OBSERVATION_ONLY','source':attestation,'prior_project':str(source_project),
          'frames_requested':a.frames,'steps_requested':a.steps,'reference_parity':'NOT_TESTED',
          'gameplay':'NOT_ESTABLISHED'}
  if a.mode=='live':
   report['live']=run_native(exe,rom,out/'live',a.frames,a.steps,'live')
   print('LIVE_STATUS='+str(report['live']['status']),flush=True)
  else:
   input_path=out/'start-input.csv'
   report['replay']=start_timeline(input_path,a.start_frame,a.start_duration,a.frames,a.button)
   report['neutral']=run_native(exe,rom,out/'neutral',a.frames,a.steps,'neutral')
   report['start']=run_native(exe,rom,out/'start',a.frames,a.steps,'start',input_path)
   report['first_different_frame']=first_frame_difference(report['neutral'],report['start'])
   report['nmi_events_neutral']=report['neutral'].get('nmi_events')
   report['nmi_events_start']=report['start'].get('nmi_events')
   print('NEUTRAL_FRAMES='+str(report['neutral'].get('frames')),flush=True)
   print('START_FRAMES='+str(report['start'].get('frames')),flush=True)
   print('NEUTRAL_NMI='+str(report['nmi_events_neutral']),flush=True)
   print('START_NMI='+str(report['nmi_events_start']),flush=True)
   print('FIRST_DIFFERENT_FRAME='+str(report['first_different_frame']),flush=True)
  (out/'interaction-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
  print('REPORT='+str(out/'interaction-report.json'),flush=True)
  print('EVIDENCE_ZIP='+str(pack_report(out)),flush=True)
  if a.show and a.mode=='test' and (out/'start'/'native-frame.ppm').is_file():
   print('SAVED_NATIVE_FRAME_VIEWER=OPENING',flush=True)
   screen.show_still(out/'start'/'native-frame.ppm',a.game+' — controlled Start replay')
  return 0 if ((a.mode=='live' and report['live'].get('frames',0)>0) or
               (a.mode=='test' and report['neutral'].get('frames',0)>0 and report['start'].get('frames',0)>0)) else 2
 except (OSError,ValueError,RuntimeError,KeyError,TypeError,json.JSONDecodeError,subprocess.SubprocessError) as exc:
  error={'schema':'recomp-native-interaction-v0441','game':a.game,'mode':a.mode,
         'source_sha256':sha,'status':'OWNER_DIAGNOSTIC_FAILED','error_type':type(exc).__name__,
         'error':str(exc)[:1200],'reference_parity':'NOT_TESTED','gameplay':'NOT_ESTABLISHED'}
  (out/'interaction-report.json').write_text(json.dumps(error,indent=2)+'\n',encoding='utf-8')
  print('EVIDENCE_ZIP='+str(pack_report(out)),flush=True)
  raise

if __name__=='__main__':
 try:sys.exit(main())
 except (OSError,ValueError,RuntimeError,KeyError,TypeError,json.JSONDecodeError) as e:
  print('INTERACTION_BLOCKED='+str(e),file=sys.stderr)
  sys.exit(2)
