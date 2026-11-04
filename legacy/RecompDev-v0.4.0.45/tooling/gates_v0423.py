"""v0.4.0.23 compile-and-run gate for the generated continuous native app.
Does not qualify real game, independent CPU parity or owner Windows graphics.
"""
import hashlib
import subprocess
import sys
from pathlib import Path
from tooling.gates_v0422 import run as previous
ROOT=Path(__file__).resolve().parents[1]
SHARED=('hardware/core.hpp','hardware/runtime.hpp','hardware/continuous.hpp',
        'hardware/win32_window.hpp','hardware/win32_audio.hpp','hardware/wav.hpp')
GENERATED=('nativepilot/live_sms.hpp','nativepilot/interactive.cpp','nativepilot/generator.py',
           'nativepilot/CMakeLists.txt','tools/Run-Continuous-Native.py')
def run(root=ROOT,run_tests=True):
 root=Path(root).resolve()
 prior=previous(root,False)
 for file in SHARED+GENERATED:
  if not (root/file).is_file():raise ValueError('Continuous native source missing: '+file)
 for file in SHARED:
  txt=(root/file).read_text(encoding='utf-8')
  if any(term in txt for term in ('Shinobi','Sonic The Hedgehog','Chase H.Q.','dac4f1dcb411','z80:LE:16:default')):
   raise ValueError('Game/ISA-specific assumption in universal host: '+file)
  if file in ('hardware/runtime.hpp','hardware/continuous.hpp') and any(term in txt for term in ('3579545','256x192','0x7f')):
   raise ValueError('Master System clock/port leaked into generic coordinator')
 tests='NOT_RUN';summary='NOT_RUN'
 if run_tests:
  command=[sys.executable,'-m','unittest','discover','-s','tests','-p','test_continuous_native_v0423.py','-q']
  proc=subprocess.run(command,cwd=root,capture_output=True,text=True,timeout=150)
  if proc.returncode or 'OK' not in proc.stderr:raise ValueError('Continuous native test failed: '+proc.stderr[-3500:])
  tests='COMPILED_TWO_Z80_TARGETS_AND_GENERIC_SECOND_SYSTEM_PASS'
  summary=next((line for line in proc.stderr.splitlines() if line.startswith('Ran ')),'UNKNOWN')
 return {'schema':'recomp-continuous-native-gate-v0423','release':'0.4.0.23',
         'status':'EXPERIMENTAL_CONTINUOUS_NATIVE_HOST_SYNTHETIC_PASS_AUTHENTIC_GATES_OPEN',
         'prior_gate':prior['status'],'test_status':tests,'test_summary':summary,
         'source_sha256':{f:hashlib.sha256((root/f).read_bytes()).hexdigest() for f in SHARED+GENERATED},
         'milestones':{
          'GENERIC_CONTINUOUS_SCHEDULER':'COMPILED_CROSS_SYSTEM_SYNTHETIC_PASS',
          'Z80_NATIVE_INTERACTIVE_GUEST':'COMPILED_HEADLESS_TWO_SOURCE_ATTESTED_SYNTHETIC_TARGETS_PASS',
          'GENUINE_HOST_FRAME_AND_SOUND':'COMPILED_HEADLESS_PPM_PCM_WAV_PASS',
          'DETERMINISTIC_INPUT_REPLAY':'COMPILED_TWO_Z80_FIXTURE_PASS',
          'WINDOWED_GUI_AND_LIVE_SPEAKER':'WIN32_BACKEND_SOURCE_PRESENT_OWNER_MSVC_RUN_UNVERIFIED',
          'REAL_MAME_NATIVE_ALIGNMENT':'NOT_ESTABLISHED',
          'Z80_INDEPENDENT_SEMANTIC_PARITY':'NOT_ESTABLISHED',
          'AUTOMATIC_RECOVERY_FROM_MISSING_CODE':'EXISTING_BOUNDARY_ONLY',
          'SMS_VDP_PSG_CYCLE_AND_FRAME_PARITY':'NOT_ESTABLISHED',
          'SHINOBI_PLAYABLE':'NOT_ESTABLISHED',
          'M68000_NATIVE_BACKEND':'RESTRICTED_SYNTHETIC_ONLY'},
         'native_qualified':False,'gameplay':'NOT_ESTABLISHED','game_specific_fixes':0}
