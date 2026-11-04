#!/usr/bin/env python3
"""RecompDev modular migration gate controller (NO production catalogue mutation).

G0/G1 preservation and side-by-side integration. This is not a complete rewrite.
No invocation downloads tools, installs software, touches owner-local databases or ROMs.
"""
import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
LEGACY = PROJECT / 'legacy' / 'RecompDev-v0.4.0.45'
BASE = PROJECT / 'baselines' / 'ModularHarness-PoC-v0.3'
MANIFEST = PROJECT / 'migration' / 'source-integrity-manifest.json'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def verify():
    baseline = json.loads(MANIFEST.read_text(encoding='utf8'))['sources']
    results = []
    # Baseline keys can be read from the immutable inventory, not guessed.
    for k, spec in baseline.items():
        root = LEGACY if spec['file_count'] == 581 else BASE if spec['file_count'] == 61 else None
        if root is None:
            raise ValueError('Unexpected source baseline: ' + k)
        archive = PROJECT / 'original-archives' / spec['archive_filename']
        if not archive.exists():
            archive = PROJECT.parent / 'RecompDev-Archive' / 'original-archives' / spec['archive_filename']
        if not archive.exists() or sha(archive) != spec['archive_sha256']:
            raise ValueError('Original immutable source ZIP missing or altered: ' + spec['archive_filename'])
        entries = spec['entries']
        # Python may create transient __pycache__ files while importing the frozen
        # source. They are excluded from archive member identity, not promoted as source.
        actual = {p.relative_to(root).as_posix() for p in root.rglob('*')
                  if p.is_file() and '__pycache__' not in p.parts}
        expected = {'/'.join(Path(e['path']).parts[1:]) for e in entries}
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            raise ValueError(f'{k}: member mismatch missing={missing[:4]} extra={extra[:4]}')
        for entry in entries:
            rel = '/'.join(Path(entry['path']).parts[1:])
            p = root / rel
            if p.stat().st_size != entry['bytes'] or sha(p) != entry['sha256']:
                raise ValueError(f'Integrity failure in {k}/{rel}')
        results.append({'baseline': k, 'files': len(entries), 'status': 'identical', 'root': str(root.relative_to(PROJECT))})
    # Verify bundled catalogue is valid, never open with write access.
    with closing(sqlite3.connect(LEGACY.joinpath('catalogue.sqlite').as_uri() + '?mode=ro', uri=True)) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Legacy catalogue failed SQLite integrity check')
        tables = db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    return {'status': 'PASS', 'unchanged_original_files': sum(r['files'] for r in results),
            'baselines': results, 'legacy_catalogue_tables': tables,
            'note': 'Integrity, not behavioural migration parity; owner-local external databases not included'}


def status():
    reg = json.loads((PROJECT / 'migration' / 'capability-registry.json').read_text(encoding='utf8'))
    return {'release': '0.4-consolidation', 'gates': reg['gates'],
            'capabilities': reg['capabilities'], 'external_evidence': reg['external_evidence']}


def schema_counts(db):
    """Read-only table counts for exact equality checks (no user data output)."""
    tables = [x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    # Internal table names are from sqlite_master, safely quoted for SQL identifiers.
    return {table: db.execute('SELECT COUNT(*) FROM "' + table.replace('"', '""') + '"').fetchone()[0]
            for table in tables}


def catalogue_inspect(source):
    source = Path(source).resolve(strict=True)
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as db:
        integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
        if integrity != 'ok':
            raise ValueError('Catalogue integrity check failed: ' + integrity)
        return {'status': 'PASS', 'source_sha256': sha(source), 'size': source.stat().st_size,
                'tables': schema_counts(db), 'mutated': False}


def catalogue_snapshot(source, dest):
    """Backup from read-only source to NEW destination; no overwrite, identical schema/rows."""
    source, dest = Path(source).resolve(strict=True), Path(dest).resolve()
    if source == dest or dest.exists():
        raise ValueError('Refusing overwrite or in-place catalogue migration')
    if LEGACY.resolve() == dest or LEGACY.resolve() in dest.parents:
        raise ValueError('Refusing to write into preserved legacy source tree')
    dest.parent.mkdir(parents=True, exist_ok=True)
    source_hash = sha(source)
    before = catalogue_inspect(source)['tables']
    try:
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as src:
            with closing(sqlite3.connect(dest)) as dst:
                src.backup(dst)
                dst.commit()
        after = catalogue_inspect(dest)['tables']
        if before != after or sha(source) != source_hash:
            raise ValueError('Catalogue snapshot changed source or table row counts')
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return {'status': 'PASS', 'source_sha256': source_hash, 'snapshot_sha256': sha(dest),
            'tables': len(after), 'rows': sum(after.values()), 'original_mutated': False,
            'destination': str(dest)}


def pcode_verify(rom, export, banks):
    # Calls unchanged production generator via import from the preservation baseline.
    sys.path.insert(0, str(LEGACY))
    from nativepilot.generator import verify_export
    rom = Path(rom).resolve(strict=True)
    docs = [Path(export).resolve(strict=True)] + [Path(x).resolve(strict=True) for x in banks]
    accepted = {}
    info = []
    target = None
    for idx, path in enumerate(docs):
        document = json.loads(path.read_text(encoding='utf8'))
        if document.get('schema') != 'recomp-function-pcode-v1':
            raise ValueError('Not an authenticated RecompDev function export')
        if idx == 0 and document.get('bank_context') is not None:
            raise ValueError('First export must be a base window')
        if idx > 0 and document.get('bank_context') is None:
            raise ValueError('Additional exports require explicit bank context')
        if target is not None and target != document.get('target_id'):
            raise ValueError('Target identity differs across exports')
        target = document.get('target_id')
        blocks, stats, _ = verify_export(document, rom)
        for p, block in blocks.items():
            if p in accepted and accepted[p] != block:
                raise ValueError(f'Conflicting P-code at physical {p:#x}')
            accepted[p] = block
        info.append({'file': path.name, 'verified_instructions': len(blocks), 'analysis': stats})
    return {'status': 'PASS', 'source_sha256': sha(rom), 'target_id': target,
            'physically_attested_instructions': len(accepted), 'documents': info,
            'native_gameplay_qualification': False}


def run_legacy_tests(patterns):
    """Run existing tests from a disposable clone, preserving the frozen legacy tree."""
    if not patterns:
        patterns = ['test_z80_timing_v0433.py', 'test_cross_isa_recovery_v0430.py']
    available = {p.name for p in (LEGACY / 'tests').glob('test_*.py')}
    for pattern in patterns:
        if pattern not in available:
            raise ValueError('Unknown legacy test module ' + pattern)
    results = []
    with tempfile.TemporaryDirectory(prefix='recompdev-legacy-tests-') as td:
        work = Path(td) / 'legacy'
        shutil.copytree(LEGACY, work)
        for pattern in patterns:
            proc = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
                                   '-p', pattern, '-q'], cwd=work, capture_output=True, text=True)
            results.append({'test': pattern, 'passed': proc.returncode == 0,
                            'details': (proc.stdout + proc.stderr)[-1200:]})
            if proc.returncode:
                raise ValueError('Original legacy regression failure: ' + pattern + ' ' + (proc.stderr or '')[-500:])
    return {'status': 'PASS', 'tests': results, 'original_tree_modified': False}


def inventory_external(root, output):
    root = Path(root).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('External evidence inventory already exists; refusing overwrite')
    paths = sorted(p for p in root.rglob('*') if p.is_file())
    if output == root or root in output.parents:
        raise ValueError('Inventory must be written outside the source tree')
    documents = [{'path': p.relative_to(root).as_posix(), 'bytes': p.stat().st_size,
                  'sha256': sha(p)} for p in paths]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'schema': 'recompdev-external-evidence-v1',
                  'files': documents, 'source_mutated': False}, indent=2), encoding='utf8')
    return {'status': 'PASS', 'files': len(documents), 'output': str(output),
            'note': 'Inventory only. No external data copied or imported.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('verify')
    commands.add_parser('status')
    inspect = commands.add_parser('catalogue-inspect')
    inspect.add_argument('--source', default=str(LEGACY / 'catalogue.sqlite'))
    snapshot = commands.add_parser('catalogue-snapshot')
    snapshot.add_argument('--source', required=True)
    snapshot.add_argument('--out', required=True)
    pcode = commands.add_parser('pcode-verify')
    pcode.add_argument('--rom', required=True)
    pcode.add_argument('--export', required=True)
    pcode.add_argument('--bank-export', action='append', default=[])
    tests = commands.add_parser('legacy-tests')
    tests.add_argument('--pattern', action='append', default=[])
    inv = commands.add_parser('inventory-external')
    inv.add_argument('--root', required=True)
    inv.add_argument('--out', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'verify': report = verify()
        elif args.command == 'status': report = status()
        elif args.command == 'catalogue-inspect': report = catalogue_inspect(args.source)
        elif args.command == 'catalogue-snapshot': report = catalogue_snapshot(args.source, args.out)
        elif args.command == 'pcode-verify': report = pcode_verify(args.rom, args.export, args.bank_export)
        elif args.command == 'legacy-tests': report = run_legacy_tests(args.pattern)
        elif args.command == 'inventory-external': report = inventory_external(args.root, args.out)
        else: raise ValueError('Unknown operation')
        print(json.dumps(report, indent=2, sort_keys=True))
    except (ValueError, OSError, sqlite3.DatabaseError, KeyError) as exc:
        print(json.dumps({'status': 'FAIL', 'error': str(exc)}), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
