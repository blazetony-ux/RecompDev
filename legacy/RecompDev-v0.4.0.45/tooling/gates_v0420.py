"""Consolidated v0.4.0.20 gates: real implemented scope versus outstanding gaps."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tooling.gates import validate as legacy_validate
ROOT=Path(__file__).resolve().parents[1]

def verify(root=ROOT,run_tests=True):
    root=Path(root).resolve()
    legacy=legacy_validate(root,run_tests)
    if legacy['status']!='PASS_ARCHITECTURE_FOUNDATION_SYNTHETIC':
        raise ValueError('Previous architecture gate not passed')
    charter=json.loads((root/'PLATFORM_CHARTER.json').read_text())
    required=charter.get('consolidated_milestone_roadmap',[])
    if [x.get('id') for x in required]!=['V15','V16','V17','V18','V19','V20']:
        raise ValueError('Consolidated milestone roadmap was removed or changed')
    test_report={'status':'NOT_RUN'}
    if run_tests:
        cmd=[sys.executable,'-m','unittest','discover','-s','tests',
             '-p','test_unified_campaign_v0420.py','-q']
        proc=subprocess.run(cmd,cwd=root,capture_output=True,text=True,timeout=150)
        if proc.returncode or 'OK' not in proc.stderr:
            raise ValueError('Consolidated milestone tests failed: '+proc.stderr[-1200:])
        test_report={'status':'PASSED','log_sha256':hashlib.sha256((proc.stdout+proc.stderr).encode()).hexdigest(),
             'summary':next((x for x in proc.stderr.splitlines() if x.startswith('Ran ')),'UNKNOWN')}
    return {'schema':'recomp-consolidated-milestone-gate-v1','release':'0.4.0.20',
       'status':'PASS_SYNTHETIC_FOUNDATIONS_WITH_OPEN_REAL_WORLD_GATES',
       'previous_architecture_gate':legacy['status'],
       'consolidated_tests':test_report,'milestones':{
           'V15_UNIFIED_CAMPAIGN':'IMPLEMENTED_BOUNDED_TWO_ISA_INTERFACE',
           'V16_REFERENCE_ALIGNMENT':'PARTIAL_EXPLICIT_ANCHORS_REQUIRES_REAL_MAME_BANK_MAPPING',
           'V17_SEMANTIC_REPAIR':'SYNTHETIC_ALLOWLIST_RECIPE_TESTED_NO_LIVE_PATCH',
           'V18_HARDWARE_VERIFICATION':'CONTRACT_IMPLEMENTED_NO_ALIGNED_EXTERNAL_DEVICE_EVIDENCE',
           'V19_NATIVE_HOST':'WINDOWS_HOST_SOURCE_PRESENT_UNVERIFIED_ON_WINDOWS_NOT_GAME_CONNECTED',
           'V20_SECOND_ISA':'RESTRICTED_M68K_COMPILED_SYNTHETIC_FIXTURE_NOT_GENERAL_BACKEND',
           'EXTERNAL_STATIC_ENGINES':'NOT_RUN_ON_OWNER_WINDOWS',
           'NATIVE_GAMEPLAY':'NOT_ESTABLISHED'},
       'owner_windows_integration':'NOT_TESTED',
       'authentic_mame_native_parity':'NOT_TESTED',
       'runtime_native_promotion':'NOT_QUALIFIED',
       'game_specific_exception_count_added':0}
