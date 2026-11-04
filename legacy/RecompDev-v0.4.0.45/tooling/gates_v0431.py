"""v0.4.0.31: authenticated Workbench history / source identity reliability gate."""
import hashlib
import subprocess
import sys
from pathlib import Path
from tooling.gates_v0430 import run as previous
ROOT=Path(__file__).resolve().parents[1]
CHANGED=('workbench.py','tests/test_unified_source_identity_v0431.py','Run-Workbench.ps1',
         'Verify-v0431.ps1','tooling/gates_v0431.py','static/tooling.html',
         'tests/test_release_v0431.py')

def run(root=ROOT,run_tests=True):
 root=Path(root).resolve()
 prior=previous(root,False)
 summaries={}
 if run_tests:
  cases=('test_unified_source_identity_v0431.py','test_unified_current_history_v0430.py',
         'test_null_backends_v0425.py','test_release_v0431.py')
  for case in cases:
   p=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p',case,'-q'],
     cwd=root,capture_output=True,text=True,timeout=300,errors='replace')
   if p.returncode or 'OK' not in p.stderr or 'FAILED (' in p.stderr or 'skipped=' in p.stderr:
    raise ValueError(case+' failed or skipped: '+p.stdout[-1000:]+p.stderr[-4000:])
   summaries[case]=next((x for x in p.stderr.splitlines() if x.startswith('Ran ')),'UNKNOWN')
 return {'schema':'recomp-history-source-identity-gate-v0431','release':'0.4.0.31',
    'status':'SOURCE_SHA256_HISTORY_JOIN_SYNTHETIC_PASS_WINDOWS_OWNER_CHECK_PENDING',
    'prior_gate':prior['status'],'test_status':'PASS' if run_tests else 'NOT_RUN',
    'test_summaries':summaries,
    'source_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in CHANGED},
    'milestones':{
      'GRAPH_SHA256_NATIVE_HISTORY':'SYNTHETIC_CROSS_CATALOGUE_PASS' if run_tests else 'NOT_RUN',
      'INVALID_LEGACY_SOURCE_ID':'PER_RECORD_REJECT_WITH_DIAGNOSTIC' if run_tests else 'NOT_RUN',
      'INTEGRATED_HISTORY_WITHOUT_DISCOVERY_ROW':'SYNTHETIC_PASS' if run_tests else 'NOT_RUN',
      'TAMPERED_NATIVE_HOST_REPORT':'FAIL_CLOSED' if run_tests else 'NOT_RUN',
      'OWNER_WINDOWS_API_RESPONSE':'PENDING_OWNER_CHECK',
      'SONIC_SOURCE_SUPPORTED_M68K_RECOVERY':'OWNER_REPORTED_1777_INSTRUCTIONS_77_FUNCTION_CANDIDATES_NOT_INDEPENDENTLY_VERIFIED',
      'RIDGE_RACER_MIPS_RECOVERY':'OWNER_REPORTED_NO_GAIN_81_BARRIERS',
      'NONZ80_NATIVE_GAME_COMPILATION':'NOT_ESTABLISHED',
      'INDEPENDENT_MAME_PARITY':'NOT_ESTABLISHED','SHINOBI_PLAYABLE':'NOT_ESTABLISHED'},
    'native_qualified':False,'gameplay':'NOT_ESTABLISHED','game_specific_fixes':0}
