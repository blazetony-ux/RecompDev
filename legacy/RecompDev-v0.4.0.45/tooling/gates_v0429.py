"""v0.4.0.29: Windows browser-worker deterministic lifecycle gate.

Compiled Z80 acceptance is mandatory, real Ghidra is not run by synthetic
Workbench tests, and authentic-game parity remains open.
"""
import hashlib,subprocess,sys
from pathlib import Path
from tooling.gates_v0428 import run as previous
ROOT=Path(__file__).resolve().parents[1]
CHANGED=(
 'discovery/workbench_jobs.py','workbench.py','recomp.py',
 'tests/test_native_preparation_v0403.py','tests/test_release_v0428.py',
 'tests/test_integrated_native_v0424.py','tests/test_release_v0426.py',
 'tests/test_release_v0427.py','nativepilot/CMakeLists.txt',
 'Run-Workbench.ps1','static/tooling.html','Verify-v0429.ps1')

def run(root=ROOT,run_tests=True):
 root=Path(root).resolve()
 prior=previous(root,False)
 summaries={}
 if run_tests:
  for case in ('test_null_backends_v0425.py','test_native_preparation_v0403.py',
               'test_release_v0428.py','test_release_v0429.py'):
   p=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests',
     '-p',case,'-q'],cwd=root,capture_output=True,text=True,timeout=300,errors='replace')
   if p.returncode or 'OK' not in p.stderr or 'FAILED (' in p.stderr or ('skipped=' in p.stderr and case!='test_release_v0428.py'):
    raise ValueError(f'{case} acceptance failed: '+p.stdout[-2000:]+p.stderr[-8000:])
   summaries[case]=next((x for x in p.stderr.splitlines() if x.startswith('Ran ')),'UNKNOWN')
 return {
  'schema':'recomp-native-browser-worker-gate-v0429','release':'0.4.0.29',
  'status':'COMPILED_Z80_NULL_HOST_AND_BOUNDED_BROWSER_REGISTRATION_PASS_AUTHENTIC_GATES_OPEN',
  'test_status':'COMPILED_AND_BROWSER_TESTS_PASS' if run_tests else 'NOT_RUN',
  'prior_gate':prior['status'],'test_summaries':summaries,
  'source_sha256':{x:hashlib.sha256((root/x).read_bytes()).hexdigest() for x in CHANGED},
  'milestones':{
   'SYNTHETIC_WORKBENCH_PREP':'REGISTER_ONLY_SOURCE_VERIFIED_PASS' if run_tests else 'NOT_RUN',
   'PRODUCTION_GHIDRA_PREPARATION':'ENABLED_BY_DEFAULT_NOT_INTEGRATION_TESTED_HERE',
   'WORKER_LOG_LIFECYCLE':'BOUNDED_POLL_CANCEL_AND_REAP',
   'WINDOWS_COMPILED_NULL_HOST':'COMPILED_SYNTHETIC_PASS' if run_tests else 'NOT_RUN',
   'OWNER_WINDOWS_FULL_REGRESSION':'OWNER_MACHINE_PENDING',
   'REAL_MAME_ALIGNMENT':'NOT_ESTABLISHED',
   'Z80_INDEPENDENT_SEMANTIC_PARITY':'NOT_ESTABLISHED',
   'SHINOBI_GAMEPLAY':'NOT_ESTABLISHED'},
  'native_qualified':False,'gameplay':'NOT_ESTABLISHED','game_specific_fixes':0}
