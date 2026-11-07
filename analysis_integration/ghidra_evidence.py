"""Maintained, source-bound Ghidra raw P-code evidence checks.

Export format is a tool-evidence contract, not executable permission. Byte hashes
are independently compared with the authenticated ROM before the C++ translator
receives the export. No imports from archived services.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

LANG = {'z80': 'z80:LE:16:default', 'm68k': '68000:BE:32:default',
        'mips': 'MIPS:LE:32:default'}
MAX_EXPORT = 128 * 1024 * 1024
MAX_FUNCTIONS = 20_000
MAX_INSTRUCTIONS = 200_000


def read_export(filename: Path, max_bytes: int = MAX_EXPORT) -> dict:
    path = Path(filename)
    if not path.is_file() or not 0 < path.stat().st_size <= min(max_bytes, MAX_EXPORT):
        raise ValueError('GHIDRA_EXPORT_MISSING_OR_OVERSIZED')
    doc = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(doc, dict) or doc.get('schema') != 'recomp-function-pcode-v1' or doc.get('analyzer') != 'ghidra-raw-pcode':
        raise ValueError('GHIDRA_EXPORT_SCHEMA_INVALID')
    functions = doc.get('functions')
    if not isinstance(functions, list) or len(functions) > MAX_FUNCTIONS:
        raise ValueError('GHIDRA_EXPORT_FUNCTIONS_INVALID')
    return doc


def candidate_rows(doc: dict, source: Path, cpu: str) -> list[tuple[int, str, int]]:
    if cpu not in LANG or doc.get('language') != LANG[cpu]:
        raise ValueError('GHIDRA_CPU_LANGUAGE_MISMATCH')
    functions = doc.get('functions')
    if not isinstance(functions, list) or len(functions) > 10000:
        raise ValueError('GHIDRA_FUNCTION_LIMIT')
    source = Path(source)
    size = source.stat().st_size
    max_image = min(size, 0xc000 if cpu == 'z80' else 64 * 1024 * 1024)
    rows = []
    instruction_count = 0
    with source.open('rb') as handle:
        for function in functions:
            if not isinstance(function, dict):
                raise ValueError('GHIDRA_FUNCTION_NOT_OBJECT')
            entry, instructions = function.get('entry'), function.get('instructions')
            if type(entry) is not int or not isinstance(instructions, list) or not instructions:
                continue
            if len(instructions) > 10000:
                raise ValueError('GHIDRA_OVERSIZED_FUNCTION')
            for item in instructions:
                if not isinstance(item, dict):
                    raise ValueError('GHIDRA_INVALID_INSTRUCTION')
                offset, length, expected = item.get('address'), item.get('length'), item.get('bytes_sha256')
                if type(offset) is not int or type(length) is not int or not 1 <= length <= 16:
                    raise ValueError('GHIDRA_INVALID_INSTRUCTION_EXTENT')
                if offset < 0 or offset + length > max_image:
                    raise ValueError('GHIDRA_INSTRUCTION_OUTSIDE_MAPPED_SOURCE')
                handle.seek(offset)
                if type(expected) is not str or hashlib.sha256(handle.read(length)).hexdigest() != expected:
                    raise ValueError('GHIDRA_BYTES_DIFFER_FROM_AUTHENTICATED_SOURCE')
                instruction_count += 1
                if instruction_count > MAX_INSTRUCTIONS:
                    raise ValueError('GHIDRA_INSTRUCTION_LIMIT')
            rows.append((entry, str(function.get('name', ''))[:120], len(instructions)))
    return rows
