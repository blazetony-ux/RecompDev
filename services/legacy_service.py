#!/usr/bin/env python3
"""Stable JSON-line service boundary for original RecompDev Python analysis modules.

One request per line and one response per line; no shell command execution.
Original Ghidra, analysis and orchestration tools remain external services,
not pretend DLLs. This service deliberately exposes READ-ONLY methods only.
"""
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / 'legacy' / 'RecompDev-v0.4.0.45'
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(LEGACY))
from discovery import store  # genuine v0.4.0.45 production source, immutable
from migration import controller


CAPABILITIES = {
    'api': 'recompdev-service-jsonl-v1',
    'service': 'legacy-v0445',
    'operations': ['ping', 'discovery.schema', 'discovery.summary',
                   'catalogue.inspect', 'pcode.verify'],
    'mutations': 'none',
    'qualification': 'legacy services retained; native parity not implied',
}


def call(request):
    if not isinstance(request, dict) or request.get('api') != CAPABILITIES['api']:
        raise ValueError('Wrong service protocol version')
    op = request.get('operation')
    if op == 'ping':
        return CAPABILITIES
    if op == 'discovery.schema':
        # Introspect EXACT production schema from module, no edited copy.
        return {'schema_sha256': __import__('hashlib').sha256(store.SCHEMA.encode()).hexdigest(),
                'tables': sorted(__import__('re').findall(r'CREATE TABLE IF NOT EXISTS\s+(\w+)', store.SCHEMA)),
                'native_qualification': False}
    if op == 'catalogue.inspect':
        return controller.catalogue_inspect(request.get('source', str(LEGACY / 'catalogue.sqlite')))
    if op == 'discovery.summary':
        path = Path(request['source']).resolve(strict=True)
        # Read-only SQLite URI; store.connect() would run CREATE TABLE and is forbidden.
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
            db.row_factory = sqlite3.Row
            report = store.summary(db, source_id=request.get('source_id'), limit=100)
        return report
    if op == 'pcode.verify':
        if 'rom' not in request or 'export' not in request:
            raise ValueError('ROM and export are required to verify real P-code')
        return controller.pcode_verify(request['rom'], request['export'], request.get('bank_exports', []))
    raise ValueError('Unknown/forbidden service operation')


def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            result = {'ok': True, 'result': call(json.loads(line))}
        except Exception as exc:
            result = {'ok': False, 'error': str(exc)}
        print(json.dumps(result, separators=(',', ':'), sort_keys=True), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
