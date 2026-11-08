"""Bounded, strict extraction of the one native terminal result from stdout.

Diagnostic stdout may exceed the old 512 KiB *diagnostic* cap without making
its terminal report invalid. Never accept a log beyond the 16 MiB safety cap,
ambiguous/malformed framing, duplicate keys, or an incomplete native process.
This is a locally validated stdout record, NOT an authenticated game-state save.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

DIAGNOSTIC_LOG_BUDGET = 512 * 1024
HARD_LOG_BUDGET = 16 * 1024 * 1024
MAX_TERMINAL_LINE = 2 * 1024 * 1024
PREFIX = b'NATIVE_APP_RESULT='

class NativeResultError(ValueError):
    pass

def _unique_pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise NativeResultError('PREVIEW_NATIVE_RESULT_DUPLICATE_KEY')
        result[key]=value
    return result

def _nonnegative(value):
    return type(value) is int and 0 <= value <= 1_000_000_000_000

def extract_terminal_result(path: Path, *, process_returncode: int | None):
    """Return (record, provenance). Failure is explicit and fail-closed.

    Reading is one bounded streaming pass. Other log lines are not parsed or
    truncated, nor are oversized logs silently accepted without counters.
    """
    path=Path(path)
    if path.is_symlink() or not path.is_file(): raise NativeResultError('PREVIEW_NATIVE_LOG_MISSING')
    size=path.stat().st_size
    if size > HARD_LOG_BUDGET:raise NativeResultError('PREVIEW_NATIVE_LOG_HARD_LIMIT')
    count=0
    found=None
    with path.open('rb') as stream:
        for line in stream:
            if not line.startswith(PREFIX): continue
            count+=1
            if count>1:raise NativeResultError('PREVIEW_NATIVE_RESULT_AMBIGUOUS')
            if len(line)>MAX_TERMINAL_LINE:raise NativeResultError('PREVIEW_NATIVE_RESULT_LINE_OVERSIZED')
            try:
                payload=line[len(PREFIX):].decode('utf-8','strict')
                found=json.loads(payload,object_pairs_hook=_unique_pairs)
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise NativeResultError('PREVIEW_NATIVE_RESULT_INVALID_JSON') from exc
    if count!=1:raise NativeResultError('PREVIEW_NATIVE_RESULT_MISSING')
    if not isinstance(found,dict) or found.get('schema')!='recomp-continuous-native-v2':
        raise NativeResultError('PREVIEW_NATIVE_RESULT_SCHEMA_INVALID')
    if not isinstance(found.get('status'),str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{2,79}',found['status']):
        raise NativeResultError('PREVIEW_NATIVE_RESULT_STATUS_INVALID')
    if any(not _nonnegative(found.get(key)) for key in ('frames','guest_frames','native_steps','pc','physical_offset')):
        raise NativeResultError('PREVIEW_NATIVE_RESULT_FIELDS_INVALID')
    if process_returncode!=0:raise NativeResultError('PREVIEW_NATIVE_PROCESS_NOT_SUCCESSFUL')
    return found,{'native_stdout_bytes':size,
                  'native_stdout_over_diagnostic_budget':size>DIAGNOSTIC_LOG_BUDGET,
                  'terminal_result_validation':'UNIQUE_BOUNDED_JSON_ON_SUCCESSFUL_PROCESS_NOT_STATE_ATTESTATION'}
