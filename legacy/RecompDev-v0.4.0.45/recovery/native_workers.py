"""Parent-side worker supervisor. Never imports Unicorn or pypcode.

A 0xC0000409 Windows fail-fast kills only the worker subprocess. Exit codes
are evidence of failure, never evidence of correct CPU semantics.
"""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def run_isolated(kind,payload,timeout=25,argv=None):
    if kind not in ('pypcode','unicorn','unicorn-smoke'):
        raise ValueError('unknown isolated worker kind')
    cmd=list(argv) if argv is not None else [sys.executable,'-u','-X','faulthandler','-m','recovery.isolated_native',kind]
    try:
        done=subprocess.run(cmd,input=json.dumps(payload),text=True,capture_output=True,
                            timeout=timeout,check=False,errors='replace',cwd=str(ROOT))
    except subprocess.TimeoutExpired:
        return {'status':'NATIVE_WORKER_TIMEOUT','reason':kind+' timed out; subprocess terminated'}
    except OSError as exc:
        return {'status':'NATIVE_WORKER_LAUNCH_FAILED','reason':type(exc).__name__+': '+str(exc)[:300]}
    if done.returncode:
        unsigned=done.returncode & 0xffffffff
        return {'status':'NATIVE_WORKER_CRASH_OR_ERROR','worker':kind,
                'exit_code':done.returncode,'exit_hex':f'0x{unsigned:08X}',
                'reason':('Windows fail-fast exception; see crash telemetry' if unsigned==0xC0000409 else
                          'worker exited without successful result'),
                'stderr_tail':done.stderr[-1200:]}
    try:
        data=json.loads(done.stdout)
        if not isinstance(data,dict) or not isinstance(data.get('status'),str):
            raise ValueError('worker returned malformed JSON')
        return data
    except (json.JSONDecodeError,ValueError) as exc:
        return {'status':'NATIVE_WORKER_INVALID_OUTPUT','worker':kind,
                'reason':type(exc).__name__,'stdout_tail':done.stdout[-600:]}
