"""Release-specific compiled continuous recovery and guarded hardware triage gate.

Prior Z80/Windows acceptance remains a hard dependency. A synthetic native
rebuild/replay proves the mechanism, NOT Bank Panic, Alex Kidd or Shinobi parity.
"""
import hashlib,subprocess,sys
from pathlib import Path
from tooling.gates_v0433 import run as prior_run
from tooling.release_contract import assert_entrypoints
ROOT=Path(__file__).resolve().parents[1]
REQUIRED=('test_continuous_recovery_v0435.py','test_hardware_triage_v0435.py',
          'test_platform_profiles_v0434.py','test_release_v0435.py')

def run(root=ROOT,run_tests=True):
 root=Path(root).resolve()
 release=assert_entrypoints(root)
 old=prior_run(root,run_tests=run_tests)
 results={}
 if run_tests:
  for case in REQUIRED:
   p=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests',
                     '-p',case,'-q'],cwd=root,capture_output=True,text=True,
                    timeout=300,errors='replace')
   if p.returncode or 'OK' not in p.stderr or 'FAILED (' in p.stderr or 'skipped=' in p.stderr:
    raise ValueError('v0435 compiled or integration gate '+case+' failed or skipped: '+p.stdout[-1200:]+p.stderr[-5000:])
   results[case]=next((x for x in p.stderr.splitlines() if x.startswith('Ran ')),'UNKNOWN')
 paths=('nativecore/continuous_recovery_v0435.py','nativecore/hardware_triage_v0435.py',
        'tools/Run-Continuous-Recovery-v0435.py','tools/Diagnose-Z80-Hardware-v0435.py',
        'nativepilot/interactive.cpp','nativepilot/live_sms.hpp','tools/Run-Continuous-Native.py',
        'Verify-v0435.ps1','Run-Workbench.ps1')
 return {'schema':'recomp-release-qualification-v0435','release':release,
     'status':'SYNTHETIC_COMPILED_RECOVERY_ACCEPTANCE_PASS_AUTHENTIC_ROM_GATES_OPEN' if run_tests else 'NOT_RUN',
     'test_status':'PASS' if run_tests else 'NOT_RUN',
     'prior_compiled_z80_gate':old['status'],'test_summaries':results,
     'source_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths},
     'milestones':{
       'CONTINUOUS_COMPILED_REBUILD_AND_RESET_REPLAY':'SYNTHETIC_SOURCE_ATTESTED_GATE_PASS' if run_tests else 'NOT_RUN',
       'GUEST_STOP_PC_AND_MAPPER':'COMPILED_NATIVE_HOST_GATED' if run_tests else 'NOT_RUN',
       'BANK_PANIC_AFTER_FRAME_99':'OWNER_ROM_ACCEPTANCE_PENDING',
       'ALEX_KIDD_AFTER_FRAME_66':'OWNER_ROM_ACCEPTANCE_PENDING',
       'SHINOBI_MAME_INITIAL_STATE_ALIGNMENT':'NOT_ESTABLISHED',
       'SHINOBI_EARLIEST_CAUSAL_DIVERGENCE':'NOT_ESTABLISHED',
       'SHINOBI_HARDWARE_TRIAGE':'PROVENANCE_GUARDED_REPORT_GATED' if run_tests else 'NOT_RUN',
       'SHINOBI_PLAYABLE':'NOT_ESTABLISHED',
       'WINDOWS_OWNER_VERIFICATION':'OWNER_TEST_PENDING'},
     'native_qualified':False,'gameplay':'NOT_ESTABLISHED','game_specific_fixes':0}
