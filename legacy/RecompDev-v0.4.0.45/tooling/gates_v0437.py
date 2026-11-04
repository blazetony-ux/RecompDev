"""Proof-over-coverage acceptance: compiled expected output plus guarded reference evidence.

Inherits every v0436 gate. Commercial ROM and MAME results remain owner-pending.
"""
import hashlib,subprocess,sys
from pathlib import Path
from tooling.gates_v0436 import run as prior
from tooling.release_contract import assert_entrypoints
ROOT=Path(__file__).resolve().parents[1]
NEW=('test_parity_v0437.py','test_release_v0437.py')
PATHS=('hardware/image_io.hpp','hardware/adapters/sms.hpp',
       'hardware/tests/output_probe_v0437/main.cpp','hardware/tests/output_probe_v0437/CMakeLists.txt',
       'nativecore/output_qualification_v0437.py','nativecore/reference_parity_v0437.py',
       'tools/Validate-Native-Outputs-v0437.py','tools/Compare-MAME-Native-v0437.py',
       'tools/Run-Shinobi-Reference-v0437.py','nativepilot/interactive.cpp',
       'Verify-v0437.ps1','Run-Workbench.ps1')

def run(root=ROOT,run_tests=True):
 root=Path(root).resolve()
 release=assert_entrypoints(root)
 upstream=prior(root,run_tests=run_tests)
 checks={}
 if run_tests:
  for test in NEW:
   p=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p',test,'-q'],
                    cwd=root,capture_output=True,text=True,timeout=240,errors='replace')
   if p.returncode or 'OK' not in p.stderr or 'FAILED (' in p.stderr or 'skipped=' in p.stderr:
    raise ValueError('Mandatory v0437 test failed/skipped '+test+': '+(p.stdout+p.stderr)[-5000:])
   checks[test]=next((line for line in p.stderr.splitlines() if line.startswith('Ran ')),'UNKNOWN')
 return {'schema':'recomp-release-qualification-v0437','release':release,
         'status':'COMPILED_CONTROLLED_OUTPUT_PASS_MAME_PARITY_PENDING' if run_tests else 'NOT_RUN',
         'inherited_gates':upstream['status'],'new_tests':checks,
         'source_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in PATHS},
         'milestones':{
             'COMPILED_SMS_VIDEO_OUTPUT':'EXPECTED_NONBLACK_2_COLOR_PPM_MATCH' if run_tests else 'NOT_RUN',
             'COMPILED_SMS_PSG_OUTPUT':'EXPECTED_NONZERO_PCM_WAV_MATCH' if run_tests else 'NOT_RUN',
             'MAME_ROM_IDENTICAL_FRAME_OBSERVATION':'PROVENANCE_GUARDED_TOOL_DELIVERED_OWNER_CAPTURE_PENDING',
             'DETERMINISTIC_STEP_ALIGNMENT':'NOT_ESTABLISHED',
             'SHINOBI_MAME_NATIVE_PARITY':'NOT_ESTABLISHED',
             'PLAYABLE_NATIVE_GAME':'NOT_ESTABLISHED',
             'AUTONOMOUS_ROOT_CAUSE_REPAIR':'NOT_ESTABLISHED',
             'WINDOWS_OWNER_VERIFICATION':'PENDING'},
         'native_qualified':False,'gameplay':'NOT_ESTABLISHED','game_specific_fixes':0}
