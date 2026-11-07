#!/usr/bin/env python3
"""Portable, redacted, bounded diagnostic ZIP exporter for compiled controller jobs.

Executed only when the compiled controller requests --stage job-diagnostics.
Only files explicitly named by this module are allowed. It never packages ROMs,
SQLite, raw Ghidra dumps, compiled objects, native projects or arbitrary logs.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import zipfile

SCHEMA = 'recompdev.controller.diagnostics.v1'
MAX_SOURCE = 8 * 1024 * 1024
MAX_TOTAL = 48 * 1024 * 1024
MAX_SESSIONS = 16
MAX_FILES = 100
PATH = re.compile(r'(?i)(?:[a-z]:[\\/]|\\\\[^\\/]+[\\/]|/(?:home|users|mnt|tmp|var|private|root)/)')
SECRET = re.compile(r'(?i)(?:password|credential|secret|api[_-]?key|auth[_-]?token|access[_-]?token|bearer)')
JOB_ID = re.compile(r'^job-[A-Za-z0-9_-]{1,96}$')
SESSION = re.compile(r'^cycle-\d{2}$')
STOP_FILE = re.compile(r'^round-\d{2}-observed-stop\.json$')


def redact(value, key=''):
    """Fail closed: replace entire local path/string and sensitive-key values."""
    if SECRET.search(key):
        return '<redacted>'
    if isinstance(value, str):
        if SECRET.search(value):
            return '<sensitive-content-redacted>'
        return '<local-path-redacted>' if PATH.search(value) else value
    if isinstance(value, dict):
        return {k: redact(v, k) for k, v in value.items() if isinstance(k, str)}
    if isinstance(value, list):
        return [redact(x) for x in value]
    if value is None or isinstance(value, (int, float, bool)):
        return value
    raise ValueError('Unsupported diagnostic field')


def sanitized_json(path: Path, root: Path) -> bytes:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_SOURCE:
        raise ValueError('Unsafe/oversized diagnostic source')
    if not path.resolve(strict=True).is_relative_to(root):
        raise ValueError('Diagnostic source escapes job root')
    raw = path.read_bytes()
    if len(raw) > MAX_SOURCE:
        raise ValueError('Diagnostic source exceeds size limit')
    data = json.loads(raw.decode('utf-8'))
    return (json.dumps(redact(data), indent=2, sort_keys=True, ensure_ascii=False)+'\n').encode('utf-8')


def sanitized_events(path: Path, root: Path) -> bytes:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_SOURCE or not path.resolve().is_relative_to(root):
        raise ValueError('Unsafe/oversized event log')
    out=[]
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.strip():
            out.append(json.dumps(redact(json.loads(line)), sort_keys=True, ensure_ascii=False))
    return ('\n'.join(out)+'\n').encode('utf-8')


def archive_job(job_dir: Path, out_dir: Path) -> dict:
    if job_dir.is_symlink():
        raise ValueError('Symlink controller job directory is forbidden')
    root = job_dir.resolve(strict=True)
    if not root.is_dir() or not JOB_ID.fullmatch(root.name):
        raise ValueError('Invalid controller job directory')
    # Only the exact parent-root job registry layout is accepted.
    if root.parent.name != 'jobs' or root.is_symlink():
        raise ValueError('Not a controller-managed jobs directory')
    doc = json.loads((root/'job.json').read_text(encoding='utf-8'))
    if doc.get('schema') != 'recompdev.controller.job.v1' or doc.get('id') != root.name:
        raise ValueError('Job identity/schema mismatch')
    attempts = doc.get('attempts', [])
    if not isinstance(attempts, list) or len(attempts) > MAX_SESSIONS:
        raise ValueError('Invalid recovery attempts')
    destination = out_dir.resolve()
    if destination == root or destination.is_relative_to(root):
        raise ValueError('Archive destination may not be inside job')
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / (root.name+'-cycles-'+f'{len(attempts):02d}'+'-diagnostics.zip')
    if archive.exists():
        # Idempotent export is safe only when the existing archive exactly
        # matches the present job status and contains valid manifest hashes.
        with zipfile.ZipFile(archive) as z:
            manifest=json.loads(z.read('manifest.json'))
            if (z.testzip() is not None or manifest.get('schema')!=SCHEMA or
                manifest.get('job_id')!=root.name or manifest.get('status')!=doc.get('status') or
                manifest.get('source_sha256')!=doc.get('rom_sha256')):
                raise FileExistsError('Existing diagnostic snapshot does not match job; preserved')
            for entry in manifest['files']:
                payload=z.read(entry['path'])
                if (len(payload)!=entry['bytes'] or
                    hashlib.sha256(payload).hexdigest()!=entry['sha256']):
                    raise ValueError('Existing diagnostic snapshot integrity mismatch')
        digest=hashlib.sha256(archive.read_bytes()).hexdigest()
        return {'path':str(archive),'sha256':digest,'files':len(manifest['files'])+1,'bytes':archive.stat().st_size}

    entries = [('job.json', sanitized_json(root/'job.json', root))]
    events = root/'events.jsonl'
    if events.exists():
        entries.append(('events.jsonl', sanitized_events(events, root)))
    for index, attempt in enumerate(attempts, start=1):
        session = root/'sessions'/f'cycle-{index:02d}'
        if not session.is_dir() or session.is_symlink():
            raise ValueError('Missing or unsafe recorded session')
        if Path(attempt.get('output', '')).resolve() != session.resolve():
            raise ValueError('Recorded session path mismatch')
        report = session/'orchestration.json'
        entries.append((f'sessions/cycle-{index:02d}/orchestration.json', sanitized_json(report, root)))
        for stop in sorted(session.glob('round-*-observed-stop.json')):
            if STOP_FILE.fullmatch(stop.name):
                entries.append((f'sessions/cycle-{index:02d}/{stop.name}', sanitized_json(stop, root)))
    if len(entries) > MAX_FILES or sum(len(d) for _, d in entries) > MAX_TOTAL:
        raise ValueError('Diagnostic archive limits exceeded')

    max_frames = max((a.get('frames', 0) for a in attempts if isinstance(a.get('frames'), int)), default=0)
    summary = {'job_id':root.name, 'status':doc.get('status'), 'cycles':len(attempts),
               'best_frames':max_frames, 'target_frames':doc.get('target_frames'),
               'rom_sha256':doc.get('rom_sha256'), 'gameplay_parity_qualified':False,
               'notes':'Execution frame counts do not establish gameplay correctness.'}
    entries.append(('summary.json',(json.dumps(summary, sort_keys=True, indent=2)+'\n').encode()))
    entries.append(('README.txt',('RecompDev source-attested recovery diagnostics\n'
      'ROM and native binaries omitted. Absolute local paths and sensitive-key fields redacted.\n'
      'JSON files are sanitised copies, not byte-identical source evidence.\n'
      'Source originals remain in their immutable local session folders.\n'
      'Gameplay correctness, audio and VDP parity are not proven by this ZIP.\n').encode()))
    manifest = {'schema': SCHEMA, 'job_id':root.name, 'status':doc.get('status'),
                'source_sha256':doc.get('rom_sha256'), 'original_rom_included':False,
                'raw_analysis_and_binaries_included':False, 'redacted':True,
                'files':[{'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in entries]}
    entries.append(('manifest.json',(json.dumps(manifest, sort_keys=True, indent=2)+'\n').encode()))
    fd,tempfile_name=tempfile.mkstemp(prefix='.recompdev-diag-',suffix='.partial',dir=destination)
    os.close(fd)
    temp=Path(tempfile_name)
    created=False
    try:
        with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for name,data in entries:
                z.writestr(name,data)
        with zipfile.ZipFile(temp) as z:
            if z.testzip() is not None:
                raise ValueError('Diagnostic ZIP corrupt')
        with archive.open('xb') as out, temp.open('rb') as src:
            created=True
            shutil.copyfileobj(src,out,1024*1024)
        h=hashlib.sha256()
        with archive.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''):
                h.update(chunk)
        return {'path':str(archive), 'sha256':h.hexdigest(), 'files':len(entries), 'bytes':archive.stat().st_size}
    except Exception:
        if created:
            archive.unlink(missing_ok=True)
        raise
    finally:
        temp.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage',required=True,choices=['job-diagnostics'])
    parser.add_argument('--job-dir',type=Path,required=True)
    parser.add_argument('--out-dir',type=Path,required=True)
    opts=parser.parse_args(argv)
    try:
        result=archive_job(opts.job_dir,opts.out_dir)
        print('RECOMPDEV_DIAGNOSTICS_ZIP='+result['path'])
        print('RECOMPDEV_DIAGNOSTICS_SHA256='+result['sha256'])
        return 0
    except Exception as e:
        print('RECOMPDEV_DIAGNOSTICS_ERROR='+str(e))
        return 2

if __name__=='__main__':
    raise SystemExit(main())
