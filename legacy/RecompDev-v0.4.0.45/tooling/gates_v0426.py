"""v0.4.0.26 Windows-robust host acceptance gate.

RecompDev verifies compiled generated instructions; this is NOT authentic game parity.
"""
import hashlib
import subprocess
import sys
from pathlib import Path
from tooling.gates_v0425 import run as prior
ROOT=Path(__file__).resolve().parents[1]
FIXED=(
    'nativepilot/interactive.cpp',
    'platform424/campaign.py',
    'tests/test_null_backends_v0425.py',
    'tests/test_continuous_native_v0423.py',
    'tests/test_startup_loop_diagnostics_v0406.py',
    'workbench.py',
    'Run-Workbench.ps1',
)
def run(root=ROOT,run_tests=True):
    root=Path(root).resolve()
    previous=prior(root,False)
    checks={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in FIXED}
    test_summaries={}
    if run_tests:
        for file in ('test_null_backends_v0425.py','test_release_v0426.py'):
            proc=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests',
                '-p',file,'-q'],cwd=root,text=True,capture_output=True,timeout=300)
            if proc.returncode or 'OK' not in proc.stderr or 'skipped=' in proc.stderr:
                raise ValueError(f'{file} compiled acceptance FAILED/was skipped:\n'+
                    proc.stdout[-2000:]+proc.stderr[-12000:])
            test_summaries[file]=next((line for line in proc.stderr.splitlines()
                if line.startswith('Ran ')),'UNKNOWN')
    if previous['native_qualified'] or previous['gameplay']!='NOT_ESTABLISHED':
        raise ValueError('Qualification status may not be promoted without independent parity')
    return {'schema':'recomp-windows-native-acceptance-v0426','release':'0.4.0.26',
        'status':'COMPILED_Z80_NULL_HOST_SYNTHETIC_PASS_WITH_WINDOWS_FIXES_AUTHENTIC_GATES_OPEN',
        'prior_gate':previous['status'],
        'test_status':'COMPILED_TESTS_PASS' if run_tests else 'NOT_RUN',
        'test_summaries':test_summaries,'source_sha256':checks,
        'milestones':{
            'WIN32_EXECUTABLE_SELECTION':'CMAKE_PRODUCT_PATH_VALIDATED',
            'HEADLESS_PHYSICAL_BACKEND_FAIL_CLOSED':'COMPILED_ARGUMENT_ORDER_PERMUTATIONS_PASS' if run_tests else 'NOT_RUN',
            'SQLITE_TEMP_DB_HANDLE_CLOSURE':'EXPLICIT_CONNECTION_LIFETIME_IMPLEMENTED_WINDOWS_CHECK_PENDING',
            'GENUINE_WINDOWS_MSVC_VERIFICATION':'OWNER_MACHINE_PENDING',
            'GENERIC_NULL_VIDEO_AUDIO_INPUT':'COMPILED_CROSS_SYSTEM_SYNTHETIC_PASS' if run_tests else 'NOT_RUN',
            'REAL_MAME_ALIGNMENT':'NOT_ESTABLISHED',
            'Z80_INDEPENDENT_SEMANTIC_PARITY':'NOT_ESTABLISHED',
            'SHINOBI_GAMEPLAY':'NOT_ESTABLISHED'},
        'native_qualified':False,'gameplay':'NOT_ESTABLISHED','game_specific_fixes':0}
