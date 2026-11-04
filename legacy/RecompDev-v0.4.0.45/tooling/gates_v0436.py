"""v0.4.0.36: compiled transition provenance, recovery classification, seven-ROM campaign contracts.

Retain every earlier compiled gate. Real-ROM parity is not inferred from synthetic tests.
"""
import hashlib,subprocess,sys
from pathlib import Path
from tooling.gates_v0435 import run as previous
from tooling.release_contract import assert_entrypoints
ROOT=Path(__file__).resolve().parents[1]
REQUIRED=('test_correctness_v0436.py','test_release_v0436.py')
PATHS=('nativecore/continuous_recovery_v0436.py','nativecore/session_triage_v0436.py',
       'tools/Run-Continuous-Recovery-v0436.py','tools/Run-SMS-Campaign-v0436.py',
       'nativepilot/live_sms.hpp','nativepilot/interactive.cpp','nativepilot/generator.py',
       'Verify-v0436.ps1','Run-Workbench.ps1')

def run(root=ROOT,run_tests=True):
 root=Path(root).resolve();release=assert_entrypoints(root)
 prior=previous(root,run_tests=run_tests)
 details={}
 if run_tests:
  for case in REQUIRED:
   p=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests',
                     '-p',case,'-q'],cwd=root,capture_output=True,text=True,
                    timeout=360,errors='replace')
   if p.returncode or 'OK' not in p.stderr or 'FAILED (' in p.stderr or 'skipped=' in p.stderr:
    raise ValueError('v0436 mandatory test failed or skipped '+case+': '+p.stderr[-5000:])
   details[case]=next((line for line in p.stderr.splitlines() if line.startswith('Ran ')),'UNKNOWN')
 return {'schema':'recomp-release-qualification-v0436','release':release,
         'status':'SYNTHETIC_COMPILED_CORRECTNESS_GATES_PASS_AUTHENTIC_GAMES_PENDING' if run_tests else 'NOT_RUN',
         'prior_gate_status':prior['status'],'new_tests':details,
         'source_sha256':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in PATHS},
         'milestones':{'COMPILED_LAST_256_PC_SP_IRQ_MAPPER_TRANSITIONS':'GATED' if run_tests else 'NOT_RUN',
                       'SOURCE_VERIFIED_VS_EMITTED_DISPATCH_DIAGNOSIS':'GATED' if run_tests else 'NOT_RUN',
                       'BUILD_TIMEOUT_STRUCTURED_FAILURE':'GATED' if run_tests else 'NOT_RUN',
                       'SEVEN_GAME_CAMPAIGN':'TOOL_DELIVERED_OWNER_RUN_PENDING',
                       'SHINOBI_MAME_CPU_ALIGNMENT':'NOT_ESTABLISHED',
                       'SHINOBI_PLAYABLE':'NOT_ESTABLISHED',
                       'ALEX_KIDD_RAM_CAUSALITY':'NOT_ESTABLISHED',
                       'WINDOWS_OWNER_ACCEPTANCE':'PENDING'},
         'native_qualified':False,'gameplay':'NOT_ESTABLISHED','game_specific_fixes':0}
