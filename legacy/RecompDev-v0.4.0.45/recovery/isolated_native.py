"""Native-extension crash containment for pypcode and Unicorn.

The caller process MUST NOT import the native extension. This module is invoked
as `python -u -X faulthandler -m recovery.isolated_native KIND` in a child.
Genuine crashes/timeouts are reported to the caller, never marked as parity.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

def dispatch(kind, payload):
    if kind == 'pypcode':
        try:
            import pypcode
        except ImportError:
            return {'status':'PYPCODE_NOT_INSTALLED'}
        language = payload['language']
        raw = bytes.fromhex(payload['hex'])
        if not (1 <= len(raw) <= 16):
            raise ValueError('pypcode input must be one bounded instruction')
        result = pypcode.Context(language).translate(raw, int(payload['address']), max_instructions=1)
        return {'status':'PYPCODE_FIRST_INSTRUCTION_LIFTED_NOT_PARITY' if result.ops else 'PYPCODE_DECODE_EMPTY'}
    if kind == 'unicorn-smoke':
        try:
            from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN
        except ImportError:
            return {'status':'UNICORN_DEPENDENCY_NOT_INSTALLED'}
        uc=Uc(UC_ARCH_M68K,UC_MODE_BIG_ENDIAN)
        uc.mem_map(0,4096)
        return {'status':'UNICORN_INITIALIZED_NOT_CPU_PARITY'}
    if kind == 'unicorn':
        from recovery.verify import verify
        return verify(payload['db'], payload['source'], payload['manifest'])
    raise ValueError('unknown native worker: '+kind)

def main():
    if len(sys.argv) != 2:
        raise SystemExit('usage: python -m recovery.isolated_native {pypcode|unicorn}')
    payload=json.loads(sys.stdin.read())
    result=dispatch(sys.argv[1],payload)
    print(json.dumps(result,ensure_ascii=True),flush=True)

if __name__ == '__main__':
    main()
