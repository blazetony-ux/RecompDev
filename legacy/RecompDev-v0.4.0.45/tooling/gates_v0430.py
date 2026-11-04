"""v0.4.0.30: cross-ISA source-supported recovery and owner-evidence acceptance.

Only authenticated synthetic code is executed in this gate. External real-game
improvements must be measured on the owner's original binary separately.
"""
import hashlib
import subprocess
import sys
from pathlib import Path
from tooling.gates_v0429 import run as previous
ROOT=Path(__file__).resolve().parents[1]
CHANGED=('adapters/indirect.py','adapters/flow.py','scan_graph.py','graph_store.py',
         'discovery_benchmark.py','recomp.py','platform424/evidence.py',
         'workbench.py','static/app.js','static/index.html',
         'tests/test_cross_isa_recovery_v0430.py',
         'tests/test_unified_current_history_v0430.py',
         'Run-Workbench.ps1','Verify-v0430.ps1')

def run(root=ROOT,run_tests=True):
 root=Path(root).resolve()
 prior=previous(root,False)
 summaries={}
 if run_tests:
  cases=('test_cross_isa_recovery_v0430.py','test_unified_current_history_v0430.py',
         'test_null_backends_v0425.py','test_release_v0430.py')
  for case in cases:
   p=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests',
                     '-p',case,'-q'],cwd=root,capture_output=True,text=True,
                     timeout=300,errors='replace')
   if p.returncode or 'OK' not in p.stderr or 'FAILED (' in p.stderr or 'skipped=' in p.stderr:
    raise ValueError(case+' failed or skipped: '+p.stdout[-1000:]+p.stderr[-4000:])
   summaries[case]=next((x for x in p.stderr.splitlines() if x.startswith('Ran ')),'UNKNOWN')
 return {'schema':'recomp-cross-isa-recovery-gate-v0430','release':'0.4.0.30',
         'status':'SYNTHETIC_SOURCE_SUPPORTED_M68K_MIPS_RECOVERY_PASS_AUTHENTIC_IMPROVEMENT_PENDING',
         'prior_gate':prior['status'],'test_status':'PASS' if run_tests else 'NOT_RUN',
         'test_summaries':summaries,
         'source_sha256':{x:hashlib.sha256((root/x).read_bytes()).hexdigest() for x in CHANGED},
         'milestones':{'M68K_LOCAL_CONSTANT_RECOVERY':'SYNTHETIC_SOURCE_DECODED_PASS' if run_tests else 'NOT_RUN',
           'MIPS_LOCAL_CONSTANT_RECOVERY':'SYNTHETIC_SOURCE_DECODED_PASS' if run_tests else 'NOT_RUN',
           'MIPS_AMBIGUOUS_JOIN_REJECTION':'SYNTHETIC_PASS' if run_tests else 'NOT_RUN',
           'FRESH_SQLITE_SCAN':'SYNTHETIC_PASS' if run_tests else 'NOT_RUN',
           'SONIC_AUTHENTIC_BEFORE_AFTER':'OWNER_ROM_BENCHMARK_PENDING',
           'RIDGE_RACER_AUTHENTIC_BEFORE_AFTER':'OWNER_EXE_BENCHMARK_PENDING',
           'UNIFIED_SHINOBI_CAMPAIGN_HISTORY':'AUTHENTIC_UPLOADED_JOB_REVALIDATED_DEVELOPMENT_MACHINE',
           'NONZ80_NATIVE_GAME_COMPILATION':'NOT_ESTABLISHED',
           'INDEPENDENT_MAME_PARITY':'NOT_ESTABLISHED',
           'SHINOBI_PLAYABLE':'NOT_ESTABLISHED'},
         'native_qualified':False,'gameplay':'NOT_ESTABLISHED','game_specific_fixes':0}
