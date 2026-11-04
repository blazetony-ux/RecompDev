"""v0.4.0.27 acceptance: portable bounded batch backend and compiled null host.

Simulated batch backend is explicitly not an authentic Go executable or game parity test.
"""
import hashlib
import subprocess
import sys
from pathlib import Path
from tooling.gates_v0426 import run as previous
ROOT=Path(__file__).resolve().parents[1]
CHANGED=('tests/test_batch_campaign.py','nativepilot/CMakeLists.txt',
         'Run-Workbench.ps1','workbench.py','static/tooling.html')
def run(root=ROOT,run_tests=True):
 root=Path(root).resolve()
 prior=previous(root,False)
 summaries={}
 if run_tests:
  for case in ('test_batch_campaign.py','test_null_backends_v0425.py','test_release_v0427.py'):
   proc=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p',case,'-q'],
                       cwd=root,capture_output=True,text=True,timeout=300)
   if proc.returncode or 'OK' not in proc.stderr or 'skipped=' in proc.stderr:
    raise ValueError(f'{case} acceptance FAILED/was skipped:\n'+proc.stdout[-2000:]+proc.stderr[-12000:])
   summaries[case]=next((line for line in proc.stderr.splitlines() if line.startswith('Ran ')),'UNKNOWN')
 if prior['native_qualified'] or prior['gameplay']!='NOT_ESTABLISHED':
  raise ValueError('Native qualification requires independent genuine reference evidence')
 return {'schema':'recomp-portable-native-acceptance-v0427','release':'0.4.0.27',
  'status':'COMPILED_NULL_HOST_AND_PORTABLE_BATCH_FIXTURE_SYNTHETIC_PASS_AUTHENTIC_GATES_OPEN',
  'prior_gate':prior['status'],'test_status':'COMPILED_AND_BATCH_TESTS_PASS' if run_tests else 'NOT_RUN',
  'test_summaries':summaries,
  'source_sha256':{rel:hashlib.sha256((root/rel).read_bytes()).hexdigest() for rel in CHANGED},
  'milestones':{
   'WINDOWS_BATCH_BACKEND_TEST':'MOCKED_CROSS_PLATFORM_PROCESS_BOUNDARY_PASS' if run_tests else 'NOT_RUN',
   'WINDOWS_CLI_BACKEND_AVAILABILITY':'FAIL_CLOSED_WHEN_MISSING',
   'HEADLESS_AUTONOMOUS_COMPILED_RUN':'COMPILED_SYNTHETIC_PASS' if run_tests else 'NOT_RUN',
   'OWNER_WINDOWS_FULL_REGRESSION':'OWNER_MACHINE_PENDING',
   'REAL_GO_BACKEND':'EXTERNAL_OPTIONAL_NOT_BUNDLED',
   'REAL_MAME_ALIGNMENT':'NOT_ESTABLISHED',
   'Z80_INDEPENDENT_SEMANTIC_PARITY':'NOT_ESTABLISHED',
   'SHINOBI_PLAYABLE':'NOT_ESTABLISHED'},
  'native_qualified':False,'gameplay':'NOT_ESTABLISHED','game_specific_fixes':0}
