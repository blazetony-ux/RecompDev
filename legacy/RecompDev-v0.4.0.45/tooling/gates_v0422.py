"""RecompDev v0.4.0.22 hardware-runtime architecture gate.
Synthetic tests are deliberately not authentic game parity qualification.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from tooling.gates_v0421 import run as previous
ROOT=Path(__file__).resolve().parents[1]
SHARED=('hardware/core.hpp','hardware/runtime.hpp','hardware/wav.hpp','hardware/input_replay.hpp')
ADAPTERS=('hardware/adapters/sms.hpp','hardware/adapters/sms_machine.hpp','hardware/adapters/alternate.hpp')
OTHERS=('nativepilot/generator.py','systems/mastersystem/runtime.cpp','host/UniversalHost.cpp')

def run(root=ROOT,run_tests=True):
 root=Path(root).resolve()
 prior=previous(root,False)
 for file in SHARED+ADAPTERS+OTHERS:
  if not (root/file).is_file():raise ValueError('Hardware release source missing: '+file)
 forbidden=('Shinobi','Sonic The Hedgehog','Chase H.Q.','0x9e0c','dac4f1dcb411')
 for file in SHARED:
  text=(root/file).read_text(encoding='utf-8')
  if any(name in text for name in forbidden):raise ValueError('Game-specific dependence in common hardware: '+file)
  if '256x192' in text or '3579545' in text or '0x7f' in text:
   raise ValueError('Master System size/port/timing leaked into generic contract: '+file)
 status='NOT_RUN';summary='NOT_RUN'
 if run_tests:
  proc=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests',
      '-p','test_hardware_runtime_v0422.py','-q'],cwd=root,text=True,capture_output=True,timeout=180)
  if proc.returncode or 'OK' not in proc.stderr:
   raise ValueError('Hardware acceptance failed: '+proc.stderr[-3500:])
  status='PASS_COMPILED_SYNTHETIC_TWO_DEVICES_AND_Z80_PORT_EVIDENCE'
  summary=next((line for line in proc.stderr.splitlines() if line.startswith('Ran ')),'UNKNOWN')
 return {'schema':'recomp-hardware-gate-v0422','release':'0.4.0.22',
         'status':'SYNTHETIC_CROSS_DEVICE_AND_Z80_IO_PATH_PASS_WITH_AUTHENTIC_GATES_OPEN',
         'prior_gate':prior['status'],'cross_system':status,'test_summary':summary,
         'code_sha256':{f:hashlib.sha256((root/f).read_bytes()).hexdigest() for f in SHARED+ADAPTERS+OTHERS},
         'milestones':{'GENERIC_VIDEO_AUDIO_INPUT_CONTRACTS':'COMPILED_SYNTHETIC_PASS',
                       'GENERIC_BUS_CLOCK_AND_REPLAY':'COMPILED_SYNTHETIC_PASS',
                       'SECOND_DEVICE_PLATFORM':'FICTIONAL_NON_SMS_FIXTURE_PASS',
                       'Z80_NATIVE_IO_VIDEO_AUDIO':'SOURCE_ATTESTED_SYNTHETIC_CPP_EXECUTION_PASS',
                       'REAL_SMS_VDP_PSG_PARITY':'NOT_ESTABLISHED',
                       'CONTINUOUS_GENERATED_GAME_HOST':'NOT_IMPLEMENTED',
                       'INDEPENDENT_GAME_VIDEO_AUDIO':'NOT_TESTED',
                       'SHINOBI_PLAYABLE':'NOT_ESTABLISHED',
                       'CROSS_PLATFORM_GUI':'WIN32_DEMO_ONLY',
                       'WINDOWS_MSVC_RUN':'NOT_TESTED_ON_OWNER_MACHINE'},
         'native_qualified':False,'gameplay':'NOT_ESTABLISHED','game_specific_fixes':0}
