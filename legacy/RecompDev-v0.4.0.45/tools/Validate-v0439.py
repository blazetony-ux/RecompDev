#!/usr/bin/env python3
"""Standalone v0.4.0.39 focused acceptance (does not represent full repo suite)."""
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TASKS=[
 [sys.executable,str(ROOT/'tools'/'Validate-Native-Outputs-v0437.py')],
 *[[sys.executable,'-m','unittest','discover','-s','tests','-p',name,'-q'] for name in
   ('test_conditional_control_dev.py','test_sms_th_feedback_dev.py','test_right_shift_v0439.py','test_native_screen_v0439.py','test_release_v0438.py','test_release_v0437.py')],
 [sys.executable,'-m','unittest','discover','-s','bridge/tests','-p','test_*.py','-q'],
]
def main():
 for task in TASKS:
  print('FOCUSED_GATE: '+' '.join(task),flush=True)
  try:p=subprocess.run(task,cwd=ROOT,timeout=180)
  except subprocess.TimeoutExpired:
   print('TIMEOUT: '+str(task),file=sys.stderr);return 2
  if p.returncode:return p.returncode
 print('FOCUSED_GATES_PASS (not full-suite, not ROM parity)',flush=True)
 return 0
if __name__=='__main__':sys.exit(main())
