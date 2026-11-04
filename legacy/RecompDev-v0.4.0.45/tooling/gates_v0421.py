"""Release 0.4.0.21: executed architecture gates, explicit production blockers."""
import hashlib,json,subprocess,sys
from pathlib import Path
from tooling.gates_v0420 import verify
ROOT=Path(__file__).resolve().parents[1]

def run(root=ROOT,run_tests=True):
    root=Path(root).resolve();old=verify(root,False)
    charter=json.loads((root/'PLATFORM_CHARTER.json').read_text(encoding='utf-8'))
    for k in ('architecture_first','no_invisible_semantic_repair','source_provenance_required',
              'independent_testing_required_before_native_promotion','third_party_tools_opt_in_only'):
        if charter.get('release_policy',{}).get(k) is not True:raise ValueError('Architecture charter violation')
    fixture_status='NOT_RUN';summary='NOT_RUN'
    if run_tests:
        proc=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests',
            '-p','test_durable_campaign_v0421.py','-q'],capture_output=True,text=True,cwd=root,timeout=160)
        if proc.returncode or 'OK' not in proc.stderr:
            raise ValueError('New cross-target test failure: '+proc.stderr[-3000:])
        fixture_status='PASS_COMPILED_SYNTHETIC_MULTITARGET'
        summary=next((x for x in proc.stderr.splitlines() if x.startswith('Ran ')),'UNKNOWN')
    new_source=('campaign/handoff.py','campaign/resume.py','campaign/compiled_repair.py','campaign/reference_triage.py',
                'host/GuestBridge.hpp','host/SyntheticGuest.cpp')
    forbidden=('Shinobi','Sonic The Hedgehog','Chase H.Q.')
    for f in new_source:
        if any(name in (root/f).read_text(encoding='utf-8') for name in forbidden):
            raise ValueError('Game-specific rule introduced into shared core: '+f)
    return {'schema':'recomp-integration-gate-v0421','release':'0.4.0.21',
        'status':'PASS_REUSABLE_SYNTHETIC_INTEGRATION_WITH_REAL_WORLD_GATES_OPEN',
        'previous_release_gate':old['status'],'cross_target_tests':fixture_status,
        'test_summary':summary,'source_provenance':'ENFORCED',
        'new_core_file_sha256':{f:hashlib.sha256((root/f).read_bytes()).hexdigest() for f in new_source},
        'milestones':{
          'DURABLE_CAMPAIGN':'IMPLEMENTED_REUSABLE_ATTEMPTS_AND_SHA_VERIFICATION',
          'Z80_TWO_TARGET_NATIVE':'COMPILED_EXECUTED_SYNTHETIC_WITH_EXPLICIT_BANK_BLOCKERS',
          'M68K_SECOND_ISA':'RESTRICTED_COMPILED_SYNTHETIC_ONLY',
          'ANALYZER_TO_RECOVERY':'AUTHENTICATED_RECOVERY_QUEUE_NOT_EXECUTABLE_IR',
          'AUTONOMOUS_REPAIR':'SYNTHETIC_COMPILED_HOLDOUT_ONLY_NO_PRODUCTION_PATCH',
          'NATIVE_HOST':'SYNTHETIC_GUEST_FRAME_AND_INPUT_BRIDGE_NO_GAME',
          'REAL_MAME_ALIGNMENT':'BLOCKED_NO_AUTHENTICATED_COMMON_BOOT_AND_BANK_STATE',
          'MASTER_SYSTEM_HARDWARE_PARITY':'NOT_ESTABLISHED',
          'SHINOBI_PLAYABLE':'NOT_ESTABLISHED',
          'OWNER_WINDOWS_GHIDRA_RIZIN':'NOT_TESTED',
          'GENERAL_M68000_BACKEND':'NOT_ESTABLISHED',
          'SAFE_PRODUCTION_REPAIR':'NOT_IMPLEMENTED'},
        'game_specific_exception_count_added':0,'native_qualified':False,
        'original_game_parity':'NOT_TESTED'}
