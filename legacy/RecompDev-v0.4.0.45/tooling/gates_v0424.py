"""v0.4.0.24 integration gate: real native code, cross-system safety, evidence.

This gate does not qualify authentic Shinobi gameplay, Z80 parity or hardware.
"""
import hashlib
import subprocess
import sys
from pathlib import Path
from tooling.gates_v0423 import run as previous
ROOT=Path(__file__).resolve().parents[1]
SHARED=('platform424/evidence.py','platform424/campaign.py','nativecore/host_registry.py',
        'workbench.py','tools/Run-Integrated-Native.py','static/tooling.js')

def run(root=ROOT,run_tests=True):
    root=Path(root).resolve()
    prior=previous(root,False)
    for rel in SHARED:
        if not (root/rel).is_file():raise ValueError('Missing unified integration component: '+rel)
    for rel in ('platform424/evidence.py','platform424/campaign.py'):
        value=(root/rel).read_text(encoding='utf-8')
        if any(name in value for name in ('Shinobi','Sonic The Hedgehog','Ridge Racer','dac4f1dcb411')):
            raise ValueError('Forbidden game title or ROM hash in shared coordinator')
    test_status='NOT_RUN';test_summary='NOT_RUN'
    if run_tests:
        cmd=[sys.executable,'-m','unittest','discover','-s','tests','-p','test_integrated_native_v0424.py','-q']
        p=subprocess.run(cmd,cwd=root,capture_output=True,text=True,timeout=180)
        if p.returncode or 'OK' not in p.stderr or 'skipped=' in p.stderr:
            raise ValueError('Integrated native gate failed or compiled tests skipped: '+p.stderr[-3500:])
        test_status='COMPILED_NATIVE_Z80_CAMPAIGN_HOST_AND_VERIFIED_REPLAY_PASS'
        test_summary=next((line for line in p.stderr.splitlines() if line.startswith('Ran ')),'UNKNOWN')
    return {'schema':'recomp-integrated-native-gate-v0424','release':'0.4.0.24',
            'status':'SOURCE_ATTESTED_NATIVE_TO_HOST_INTEGRATION_SYNTHETIC_PASS_AUTHENTIC_GATES_OPEN',
            'prior_gate':prior['status'],'test_status':test_status,'test_summary':test_summary,
            'source_sha256':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in SHARED},
            'milestones':{
                'OWNER_SOURCE_BOUND_NATIVE_CAMPAIGN':'COMPILED_SYNTHETIC_END_TO_END_PASS',
                'CROSS_SYSTEM_HOST_REGISTRY':'UNSUPPORTED_SYSTEM_BLOCKS_NO_FALLBACK',
                'COMPLETE_EVENT_STREAM_REVALIDATION':'TESTED_WITH_SHA256_TAMPER_REJECTION',
                'CONTINUOUS_NATIVE_HOST':'COMPILED_TWO_INDEPENDENT_Z80_FIXTURES_AND_HOST_PASS',
                'DETERMINISTIC_HEADLESS_REPLAY':'FRAME_AND_AUDIO_HASH_REPRODUCIBILITY_PASS',
                'UNIFIED_CROSS_RELEASE_PILOT_HISTORY':'SOURCE_LINKED_READ_ONLY_BOUNDED_VERIFICATION_PASS',
                'WINDOWS_MSVC_INTERACTIVE':'OWNER_WINDOWS_TEST_REQUIRED',
                'AUTHENTIC_SHINOBI_INTEGRATED_CAMPAIGN':'OWNER_TEST_REQUIRED',
                'Genuine_Z80_MAME_ALIGNED_PARITY':'NOT_ESTABLISHED',
                'Z80_CPU_SEMANTIC_PARITY':'NOT_ESTABLISHED',
                'AUTO_RECOVERY_FROM_NEW_BANKED_CODE':'EXISTING_BOUNDED_GHIDRA_PATH_ONLY',
                'MASTER_SYSTEM_VDP_PSG_REFERENCE_PARITY':'NOT_ESTABLISHED',
                'SHINOBI_PLAYABLE':'NOT_ESTABLISHED',
                'M68000_BACKEND':'RESTRICTED_SYNTHETIC_ONLY'},
            'native_qualified':False,'gameplay':'NOT_ESTABLISHED','game_specific_fixes':0}
