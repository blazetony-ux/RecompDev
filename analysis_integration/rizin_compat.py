"""Strict, architecture-neutral Rizin ``aflj`` console normalization.

The active direct provider owns the process and this independent parser owns
structured output. Function records remain untrusted *hypotheses*, never
verified native instructions. Historic tests may still call legacy-status mode.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

MAX_FUNCTIONS = 20_000  # matches the established reconciliation ceiling

MAX_LOG_BYTES = 32 * 1024 * 1024
MAX_DIAGNOSTIC_BYTES = 8192
MAX_WARNINGS = 64
# Rizin 0.9.1 can emit a *standalone* erase-line command before warnings.
# Only this formatting code and restricted SGR formatting are admitted; not
# terminal cursor movement, alternate screen, arbitrary ANSI or OSC data.
_SGR = re.compile(r'\x1b\[[0-9;]{0,24}m')
_ERASE_LINE = '\x1b[2K'
_WARNING = re.compile(r'WARNING: invalid address from 0x[0-9a-fA-F]{1,16}')
# An array must begin at a line boundary, with its first element an object,
# or be an empty array. An unrelated bracket in a warning cannot count.
_ARRAY_START = re.compile(r'(?m)^[ \t]*(?=\[\s*(?:\{|\]))')


class RizinCompatibilityError(ValueError):
    """Fail-closed malformed, ambiguous, or unsupported analyzer evidence."""


def _no_nonfinite(token: str):
    raise RizinCompatibilityError('RIZIN_JSON_NONFINITE_VALUE: ' + token)


def _unique_fields(pairs):
    obj = {}
    for name, value in pairs:
        if name in obj:
            raise RizinCompatibilityError('RIZIN_JSON_DUPLICATE_FIELD')
        obj[name] = value
    return obj


def normalize_rizin_log(raw_log: Path, export_file: Path, audit_file: Path,
                        *, expected_log_hash: str, legacy_status: str | None = None) -> dict:
    """Validate exactly one aflj JSON array and approved diagnostic prefix.

    Called only after a successful *direct* process exit, or by historical
    compatibility regression tests with the explicit legacy_status argument.
    No modifications to raw process logs and no silent unknown diagnostics.
    """
    if legacy_status is not None and legacy_status != 'UNPARSABLE_JSON':
        raise RizinCompatibilityError('RIZIN_COMPAT_LEGACY_STATUS_NOT_APPLICABLE')
    raw_log = Path(raw_log)
    if not raw_log.is_file() or not 0 < raw_log.stat().st_size <= MAX_LOG_BYTES:
        raise RizinCompatibilityError('RIZIN_LOG_MISSING_EMPTY_OR_OVERSIZED')
    raw = raw_log.read_bytes()
    raw_sha = hashlib.sha256(raw).hexdigest()
    if raw_sha != expected_log_hash:
        raise RizinCompatibilityError('RIZIN_LOG_HASH_MISMATCH')
    try:
        text = raw.decode('utf-8', errors='strict')
    except UnicodeDecodeError as exc:
        raise RizinCompatibilityError('RIZIN_LOG_INVALID_UTF8') from exc
    start = _ARRAY_START.search(text)
    if start is None:
        raise RizinCompatibilityError('RIZIN_ARRAY_NOT_FOUND')
    prefix = text[:start.end()]
    if len(prefix.encode('utf-8')) > MAX_DIAGNOSTIC_BYTES:
        raise RizinCompatibilityError('RIZIN_DIAGNOSTIC_PREFIX_TOO_LARGE')
    # Strip formatting *only* on recognized lines, before interpretation.
    # Preserve every raw byte in the authoritative log and record counts in
    # the separate audit. Rizin 0.9.1 on Windows emits ESC[2K by itself.
    warnings = []
    erase_line_count = 0
    sgr_count = 0
    for line in prefix.splitlines():
        item = line.strip(' \t\r')
        if item == _ERASE_LINE:
            erase_line_count += 1
            continue
        sgr_count += len(_SGR.findall(item))
        item = _SGR.sub('', item).strip(' \t\r')
        if not item:
            continue
        if not _WARNING.fullmatch(item):
            raise RizinCompatibilityError('RIZIN_UNKNOWN_CONSOLE_DIAGNOSTIC')
        warnings.append(item)
    if len(warnings) > MAX_WARNINGS or erase_line_count > MAX_WARNINGS:
        raise RizinCompatibilityError('RIZIN_DIAGNOSTIC_COUNT_INVALID')
    if legacy_status is not None and not warnings:
        raise RizinCompatibilityError('RIZIN_WARNING_COUNT_INVALID')
    # Repeated warnings are retained verbatim: multiplicity may be an
    # important analyst-quality signal rather than a parser failure.
    decoder = json.JSONDecoder(parse_constant=_no_nonfinite,
                               object_pairs_hook=_unique_fields)
    try:
        records, end = decoder.raw_decode(text, start.end())
    except (ValueError, RecursionError) as exc:
        raise RizinCompatibilityError('RIZIN_JSON_INVALID') from exc
    if text[end:].strip():
        raise RizinCompatibilityError('RIZIN_JSON_TRAILING_MATERIAL')
    if not isinstance(records, list) or len(records) > MAX_FUNCTIONS:
        raise RizinCompatibilityError('RIZIN_AFLJ_LIST_INVALID')
    for obj in records:
        if not isinstance(obj, dict):
            raise RizinCompatibilityError('RIZIN_FUNCTION_OBJECT_INVALID')
        for field in ('offset', 'size'):
            value = obj.get(field)
            if type(value) is not int or not 0 <= value < (1 << 64):
                raise RizinCompatibilityError('RIZIN_FUNCTION_' + field.upper() + '_INVALID')
        if obj['size'] == 0:
            raise RizinCompatibilityError('RIZIN_FUNCTION_SIZE_ZERO')
    if export_file.exists() or audit_file.exists():
        raise RizinCompatibilityError('RIZIN_NORMALIZED_OUTPUT_ALREADY_EXISTS')
    try:
        payload = (json.dumps(records, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')
    except (ValueError, RecursionError) as exc:
        raise RizinCompatibilityError('RIZIN_JSON_NONFINITE_OR_TOO_DEEP') from exc
    metadata = {
        'schema': 'recompdev.analysis.rizin-provider-audit.v1' if legacy_status is None else 'recompdev.analysis.rizin-compatibility.v1',
        'normalization': 'strict-rizin-aflj-ansi-v2',
        'historical_parser_status': legacy_status,
        'original_log': raw_log.name,
        'original_log_sha256': raw_sha,
        'original_log_bytes': len(raw),
        'diagnostic_prefix_bytes': len(prefix.encode('utf-8')),
        'warnings': warnings,
        'warning_count': len(warnings),
        'erase_line_count': erase_line_count,
        'sgr_sequence_count': sgr_count,
        'function_count': len(records),
        'normalized_file': export_file.name,
        'normalized_sha256': hashlib.sha256(payload).hexdigest(),
        'function_claim': 'RIZIN_FUNCTION_BOUNDARY_HYPOTHESIS_ONLY',
    }
    with export_file.open('xb') as fp:
        fp.write(payload)
    try:
        with audit_file.open('xb') as fp:
            fp.write((json.dumps(metadata, sort_keys=True, indent=2) + '\n').encode('utf-8'))
    except BaseException:
        export_file.unlink(missing_ok=True)
        raise
    return metadata
