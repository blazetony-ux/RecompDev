"""v0.4.0.28 test portability and SQLite lifecycle gate.

The compiled native Z80 acceptance stays mandatory via the inherited gate.
Cache/export testing never substitutes for real compiler acceptance.
"""
import hashlib
import subprocess
import sys
from pathlib import Path
from tooling.gates_v0427 import run as previous
ROOT=Path(__file__).resolve().parents[1]
CHANGED=('tests/test_blockers_v032.py','tests/test_dependencies_and_parity_v0410.py',
         'tests/test_workbench_pages_v0401.py','tests/test_durable_campaign_v0421.py',
         'tests/test_memory_bus_v0323.py','tests/test_integrated_native_v0424.py','tests/test_release_v0426.py','tests/test_release_v0427.py',
         'campaign/resume.py','nativepilot/CMakeLists.txt','Run-Workbench.ps1',
         'workbench.py','static/tooling.html')

def run(root=ROOT,run_tests=True):
    root=Path(root).resolve()
    previous_result=previous(root,False)
    summaries={}
    if run_tests:
        # Requires real compiled Z80 native host, plus test that previously failed
        # under Windows; do not permit a skipped acceptance suite.
        for case in ('test_null_backends_v0425.py','test_blockers_v032.py',
                     'test_release_v0428.py'):
            p=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests',
                              '-p',case,'-q'],cwd=root,capture_output=True,text=True,
                              timeout=300,errors='replace')
            if p.returncode or 'OK' not in p.stderr or (case!='test_blockers_v032.py' and 'skipped=' in p.stderr):
                raise ValueError(f'{case} acceptance failed: '+p.stdout[-2000:]+p.stderr[-12000:])
            summaries[case]=next((x for x in p.stderr.splitlines() if x.startswith('Ran ')),'UNKNOWN')
    if previous_result['native_qualified'] or previous_result['gameplay']!='NOT_ESTABLISHED':
        raise ValueError('Native qualification requires independent reference evidence')
    return {
       'schema':'recomp-windows-portability-gate-v0428','release':'0.4.0.28',
       'status':'COMPILED_NULL_HOST_AND_SQLITE_PATH_CACHE_FIXTURE_PASS_AUTHENTIC_GATES_OPEN',
       'test_status':'COMPILED_AND_PORTABILITY_TESTS_PASS' if run_tests else 'NOT_RUN',
       'prior_gate':previous_result['status'],'test_summaries':summaries,
       'source_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in CHANGED},
       'milestones':{
          'WINDOWS_SQLITE_TEST_HANDLE_LIFETIMES':'EXPLICIT_CLOSE_WITH_CLOSING',
          'WINDOWS_ROM_PATH_TEST':'HOST_PATH_SEPARATOR_AWARE',
          'GHIDRA_CACHE_SMOKE_TEST':'COMPILER_INDEPENDENT_SOURCE_AUTHENTICATION',
          'WINDOWS_COMPILED_NULL_HOST':'COMPILED_SYNTHETIC_PASS' if run_tests else 'NOT_RUN',
          'OWNER_WINDOWS_FULL_REGRESSION':'OWNER_MACHINE_PENDING',
          'REAL_MAME_ALIGNMENT':'NOT_ESTABLISHED',
          'Z80_INDEPENDENT_SEMANTIC_PARITY':'NOT_ESTABLISHED',
          'SHINOBI_GAMEPLAY':'NOT_ESTABLISHED'},
       'native_qualified':False,'gameplay':'NOT_ESTABLISHED','game_specific_fixes':0}
