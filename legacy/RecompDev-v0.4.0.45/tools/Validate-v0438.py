#!/usr/bin/env python3
"""v0.4.0.38 compiled conditional CALL/RET and SMS TH release acceptance.

Runs prior v0437 native output qualification and independent game-agnostic compiled fixes.
"""
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    calls=[
      [sys.executable,str(ROOT/'tools/Validate-v0437.py')],
      [sys.executable,'-m','unittest','discover','-s','tests','-p','test_conditional_control_dev.py','-v'],
      [sys.executable,'-m','unittest','discover','-s','tests','-p','test_sms_th_feedback_dev.py','-v'],
    ]
    for call in calls:
      print('RELEASE_0438_GATE:', ' '.join(call),flush=True)
      try:result=subprocess.run(call,cwd=ROOT,timeout=450)
      except subprocess.TimeoutExpired:
        print('FAIL: compiled acceptance timeout',file=sys.stderr);return 2
      if result.returncode:
        print('FAIL: compiled gate returned',result.returncode,file=sys.stderr);return result.returncode
    print('PASS: v0.4.0.38 compiled gates; authentic cross-game parity remains unproven')
    return 0
if __name__=='__main__':raise SystemExit(main())
