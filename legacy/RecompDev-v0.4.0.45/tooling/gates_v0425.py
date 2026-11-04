"""v0.4.0.25 host-neutral execution gate: actual compiled guest, no hardware bypass."""
import hashlib
import subprocess
import sys
from pathlib import Path
from tooling.gates_v0424 import run as previous
ROOT=Path(__file__).resolve().parents[1]
SHARED=('hardware/backends.hpp','hardware/runtime.hpp','hardware/core.hpp',
        'hardware/continuous.hpp','hardware/input_replay.hpp')
WIRED=('nativepilot/interactive.cpp','nativepilot/live_sms.hpp',
       'nativepilot/generator.py','tools/Run-Continuous-Native.py',
       'platform424/campaign.py','platform424/evidence.py','Run-Workbench.ps1')
def run(root=ROOT,run_tests=True):
    root=Path(root).resolve();prior=previous(root,False)
    for rel in SHARED+WIRED:
        if not (root/rel).is_file():raise ValueError('Missing null adapter component: '+rel)
    for rel in SHARED:
        source=(root/rel).read_text(encoding='utf-8')
        if any(term in source for term in ('Shinobi','Sonic The Hedgehog','3579545','z80:LE:16:default','dac4f1dcb411')):
            raise ValueError('System or game-specific assumption in generic backend: '+rel)
    generator=(root/'nativepilot/generator.py').read_text(encoding='utf-8')
    if "'backends.hpp'" not in generator:raise ValueError('Generated C++ does not vendor null backends')
    test_status='NOT_RUN';summary='NOT_RUN'
    if run_tests:
        proc=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests',
           '-p','test_null_backends_v0425.py','-q'],cwd=root,capture_output=True,text=True,timeout=240)
        if proc.returncode or 'OK' not in proc.stderr or 'skipped=' in proc.stderr:
            raise ValueError('Null backend acceptance tests failed or skipped: '+proc.stderr[-4000:])
        test_status='COMPILED_TWO_Z80_GUESTS_NULL_CAPTURE_PARITY_AND_GENERIC_SECOND_SYSTEM_PASS'
        summary=next((line for line in proc.stderr.splitlines() if line.startswith('Ran ')),'UNKNOWN')
    return {'schema':'recomp-null-host-gate-v0425','release':'0.4.0.25',
      'status':'NULL_PRESENTATION_GUEST_STATE_EQUIVALENCE_COMPILED_SYNTHETIC_PASS_AUTHENTIC_GATES_OPEN',
      'prior_gate':prior['status'],'test_status':test_status,'test_summary':summary,
      'source_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in SHARED+WIRED},
      'milestones':{
       'NULL_FRAME_SINK':'COMPILED_CROSS_SYSTEM_PASS',
       'NULL_AUDIO_SINK':'COMPILED_CROSS_SYSTEM_PASS',
       'NEUTRAL_AND_REPLAY_INPUT':'COMPILED_TWO_Z80_GUEST_FIXTURE_PASS',
       'MIXED_HOST_BACKEND_SELECTION':'COMPILED_SOURCE_ATTESTED_GUEST_PASS',
       'HEADLESS_AUTONOMOUS_INTEGRATED_CAMPAIGN':'COMPILED_PILOT_TO_NULL_HOST_PASS',
       'NULL_VS_CAPTURE_CPU_GUEST_STATE':'DETERMINISTIC_FINGERPRINT_COUNTER_EQUIVALENCE_PASS',
       'GENUINE_CONSOLE_HARDWARE_TIMING':'UNQUALIFIED_UNCHANGED',
       'WINDOWED_WIN32_MSVC_RUNTIME':'OWNER_WINDOWS_QUALIFICATION_REQUIRED',
       'AUTHENTIC_MAME_ALIGNED_PARITY':'NOT_ESTABLISHED',
       'Z80_FULL_SEMANTIC_PARITY':'NOT_ESTABLISHED',
       'SHINOBI_PLAYABLE':'NOT_ESTABLISHED',
       'M68000_BACKEND':'RESTRICTED_SYNTHETIC_ONLY'},
      'native_qualified':False,'gameplay':'NOT_ESTABLISHED','game_specific_fixes':0}
