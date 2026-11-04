"""Mandatory synthetic compiled multi-ISA and generic reference acceptance gate.

Authentic game parity and full-console qualification stay open.
"""
import hashlib,subprocess,sys
from pathlib import Path
from tooling.gates_v0431 import run as prior_run
ROOT=Path(__file__).resolve().parents[1]
FILES=('multisa/native.py','multisa/campaign.py','multisa/checkpoints.py','multisa/triage.py',
       'adapters/indirect.py','graph_store.py','recomp.py','discovery_benchmark.py',
       'tests/test_multisa_native_v0432.py','tests/test_generic_analysis_v0432.py',
       'tests/test_universal_campaign_v0432.py','Run-Workbench.ps1','workbench.py',
       'Verify-v0432.ps1','tooling/gates_v0432.py')
def run(root=ROOT,run_tests=True):
 root=Path(root).resolve();prior=prior_run(root,False)
 cases=('test_multisa_native_v0432.py','test_generic_analysis_v0432.py',
        'test_universal_campaign_v0432.py','test_release_v0432.py',
        'test_null_backends_v0425.py','test_unified_source_identity_v0431.py')
 summaries={}
 if run_tests:
  for case in cases:
   p=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p',case,'-q'],
     cwd=root,capture_output=True,text=True,timeout=300,errors='replace')
   if p.returncode or 'OK' not in p.stderr or 'FAILED (' in p.stderr or 'skipped=' in p.stderr:
    raise ValueError('Required compiled gate '+case+' failed or skipped: '+p.stdout[-1000:]+p.stderr[-5000:])
   summaries[case]=next((x for x in p.stderr.splitlines() if x.startswith('Ran ')),'UNKNOWN')
 return {'schema':'recomp-consolidated-multisa-engine-gate-v0432','release':'0.4.0.32',
   'status':'COMPILED_RESTRICTED_M68K_MIPS_AND_UNIVERSAL_TRIAGE_SYNTHETIC_PASS' if run_tests else 'NOT_RUN',
   'prior_gate':prior['status'],'test_status':'PASS' if run_tests else 'NOT_RUN',
   'test_summaries':summaries,
   'source_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in FILES},
   'milestones':{
    'M68K_NATIVE_SOURCE_TRANSLATION':'COMPILED_AUTHOR_CREATED_FIXTURES_PASS' if run_tests else 'NOT_RUN',
    'MIPS_NATIVE_SOURCE_TRANSLATION':'COMPILED_AUTHOR_CREATED_DELAY_SLOT_FIXTURES_PASS' if run_tests else 'NOT_RUN',
    'MIPS_MULTISTEP_REGISTER_RECOVERY':'SOURCE_ATTESTED_SYNTHETIC_PASS' if run_tests else 'NOT_RUN',
    'GENERIC_SOURCE_ATTESTED_CAMPAIGN':'CROSS_ISA_SYNTHETIC_PASS' if run_tests else 'NOT_RUN',
    'GENERIC_FIRST_DIVERGENCE':'SCHEMA_AND_ALIGNMENT_CONTRACT_PASS' if run_tests else 'NOT_RUN',
    'GENERIC_BARRIER_TRIAGE':'SOURCE_HASH_AND_CATEGORIES_PASS' if run_tests else 'NOT_RUN',
    'UNIFIED_SHINOBI_HISTORY':'PRIOR_WINDOWS_OWNER_CONFIRMED',
    'SONIC_M68K_DISCOVERY':'OWNER_REPORTED_1777_INSTRUCTIONS_77_CANDIDATES_STATIC_ONLY',
    'RIDGE_RACER_MIPS_DISCOVERY':'OWNER_REPORTED_14222_INSTRUCTIONS_213_CANDIDATES_NO_GAIN',
    'AUTHENTIC_NONZ80_NATIVE_COMPILATION':'NOT_ESTABLISHED',
    'REAL_MAME_ALIGNMENT':'NOT_ESTABLISHED',
    'Z80_INDEPENDENT_SEMANTIC_PARITY':'NOT_ESTABLISHED',
    'AUTONOMOUS_REPAIR':'NOT_ESTABLISHED',
    'SONIC_RIDGE_SHINOBI_PLAYABLE':'NOT_ESTABLISHED',
    'OWNER_WINDOWS_FULL_REGRESSION':'PENDING_OWNER_RUN'},
   'native_qualified':False,'gameplay':'NOT_ESTABLISHED','game_specific_fixes':0}
