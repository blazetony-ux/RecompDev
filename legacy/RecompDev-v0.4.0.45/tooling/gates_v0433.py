"""Compiled Z80 counter/timing acceptance and guarded authentic reference assessment.

A passing synthetic test does not qualify authentic ROM parity or playable gameplay.
"""
import hashlib,subprocess,sys
from pathlib import Path
from tooling.gates_v0432 import run as prior_run
ROOT=Path(__file__).resolve().parents[1]
FILES=(
 'nativepilot/z80_cycles.hpp','nativepilot/generator.py','nativepilot/main.cpp',
 'nativepilot/interactive.cpp','nativepilot/CMakeLists.txt',
 'systems/mastersystem/counters.hpp','systems/mastersystem/runtime.cpp',
 'systems/mastersystem/runtime.hpp','nativecore/sms_startup_v0433.py',
 'tools/Assess-SMS-Startup-v0433.py','tools/Run-Continuous-Native.py',
 'platform424/campaign.py','tests/test_z80_timing_v0433.py',
 'tests/test_sms_counters_v0433.py','tests/test_z80_polling_v0433.py',
 'tests/test_sms_startup_v0433.py','tests/test_release_v0433.py',
 'workbench.py','Verify-v0433.ps1','Run-Workbench.ps1','tooling/gates_v0433.py')
CASES=('test_z80_timing_v0433.py','test_sms_counters_v0433.py',
       'test_z80_polling_v0433.py','test_sms_startup_v0433.py',
       'test_release_v0433.py','test_null_backends_v0425.py',
       'test_integrated_native_v0424.py','test_unified_source_identity_v0431.py',
       'test_multisa_native_v0432.py')
def run(root=ROOT,run_tests=True):
 root=Path(root).resolve();prior=prior_run(root,False)
 summaries={}
 if run_tests:
  for case in CASES:
   p=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p',case,'-q'],
                    cwd=root,capture_output=True,text=True,timeout=300,errors='replace')
   if p.returncode or 'OK' not in p.stderr or 'FAILED (' in p.stderr or 'skipped=' in p.stderr:
    raise ValueError('Required Z80/Windows gate '+case+' failed or skipped: '+p.stdout[-1000:]+p.stderr[-5000:])
   summaries[case]=next((x for x in p.stderr.splitlines() if x.startswith('Ran ')),'UNKNOWN')
 return {'schema':'recomp-z80-hardware-correctness-gate-v0433','release':'0.4.0.33',
    'status':'COMPILED_Z80_OPCODE_TIMING_AND_SMS_COUNTER_POLLING_PASS_AUTHENTIC_GATES_OPEN' if run_tests else 'NOT_RUN',
    'prior_gate':prior['status'],'test_status':'PASS' if run_tests else 'NOT_RUN',
    'test_summaries':summaries,
    'source_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in FILES},
    'milestones':{
      'SOURCE_OPCODE_Z80_TIMING':'COMPILED_BRANCH_BLOCK_PREFIX_FIXTURES_PASS' if run_tests else 'NOT_RUN',
      'TIMING_COVERAGE_ACCOUNTING':'GENERATED_NATIVE_RUNTIME_PRESENT',
      'NTSC_SMS_VCOUNTER':'COMPILED_192_LINE_DEVICE_TEST_PASS' if run_tests else 'NOT_RUN',
      'LATCHED_HCOUNTER':'EXPERIMENTAL_NO_PIXEL_PHASE_PARITY',
      'TRANSLATED_Z80_SCANLINE_POLL':'COMPILED_SOURCE_AUTHORED_FIXTURE_EXITED_WAIT_LOOP' if run_tests else 'NOT_RUN',
      'MAME_STARTUP_ASSESSMENT':'PREVIOUS_OWNER_MAME_AND_NATIVE_CAPTURE_CONFIRMS_UNALIGNED_FIRST_SELECTED_IO',
      'MAME_BOOT_STATE_ALIGNMENT':'NOT_ESTABLISHED',
      'Z80_INDEPENDENT_INSTRUCTION_PARITY':'NOT_ESTABLISHED',
      'SMS_SPRITES_SCANLINE_IRQ_PSG_PARITY':'NOT_ESTABLISHED',
      'AUTONOMOUS_CORRECTNESS_REPAIR':'NOT_ESTABLISHED',
      'SHINOBI_PLAYABLE':'NOT_ESTABLISHED',
      'NONZ80_COMPILERS':'INHERITED_RESTRICTED_SYNTHETIC_REGRESSIONS',
      'WINDOWS_OWNER_COMPILED_GATE':'OWNER_TEST_PENDING'},
    'native_qualified':False,'gameplay':'NOT_ESTABLISHED','game_specific_fixes':0}
