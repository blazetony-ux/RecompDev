"""Automatic diagnostic evidence ZIPs for RecompDev's existing workflow.

The run directory stays untouched. Only locally generated evidence types are
packaged. Original ROM/disc images and generated native-project build trees
are never included. ZIPs are upload-ready, with a per-file integrity manifest.

This is a packaging service, not an asset exporter or a parity validator.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

SCHEMA = 'recompdev-evidence-upload-v1'
# Keep high-value evidence: original Ghidra/P-code outputs, recovery reports,
# captured hardware outputs, log files and isolated SQLite snapshots.
ALLOWED_EXTENSIONS = frozenset({
    '.json', '.jsonl', '.log', '.txt', '.md', '.csv', '.tsv', '.ppm', '.png', '.wav',
    '.sqlite', '.sqlite3', '.db', '.xml', '.trace', '.vcd',
})
EXCLUDED_DIRS = frozenset({
    'native-project', 'build', 'build-win', 'build-linux', 'cmakefiles',
    '__pycache__', '.git', '.vs', 'node_modules', 'venv', '.venv',
})
EXCLUDED_NAMES = frozenset({'.env', 'credentials.json', 'secrets.json'})
MAX_FILE_SIZE = 128 * 1024 * 1024
MAX_TOTAL_SIZE = 512 * 1024 * 1024
MAX_FILES = 10000


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda:handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _is_allowed(path: Path) -> bool:
    if path.name.lower() in EXCLUDED_NAMES:
        return False
    if path.suffix.lower() in ALLOWED_EXTENSIONS:
        return True
    # Only explicit raw hardware state dumps. Never accept arbitrary .bin
    # files because those might be the original copyrighted source image.
    return path.suffix.lower() == '.bin' and path.name.lower().startswith(
        ('hardware-state-', 'vram-capture-', 'cram-capture-'))


def create_evidence_bundle(run_dir, *, source_sha256=None, status='UNKNOWN'):
    """Return a description of a non-destructive upload ZIP beside run_dir.

    Existing bundles are never overwritten. Failure raises a RuntimeError.
    Caller should keep the original workflow result even if packaging fails.
    """
    root = Path(run_dir).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Evidence path is not a directory: ' + str(root))
    archive = root.parent / (root.name + '-evidence.zip')
    if archive.exists():
        raise FileExistsError('Evidence archive already exists: ' + str(archive))

    included = []
    omitted = []
    eligible = []
    total = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        current = Path(directory)
        filtered = []
        for dirname in sorted(dirs):
            child = current / dirname
            rel = child.relative_to(root).as_posix()
            if dirname.lower() in EXCLUDED_DIRS or child.is_symlink():
                omitted.append({'path':rel+'/', 'reason':'excluded build directory or symbolic link'})
            else:
                filtered.append(dirname)
        dirs[:] = filtered
        for filename in sorted(files):
            path = current / filename
            rel = path.relative_to(root).as_posix()
            if path.is_symlink() or not path.is_file():
                omitted.append({'path':rel, 'reason':'not a regular file or symbolic link'})
                continue
            if not _is_allowed(path):
                omitted.append({'path':rel, 'reason':'excluded file type or sensitive name'})
                continue
            size = path.stat().st_size
            if size > MAX_FILE_SIZE or total + size > MAX_TOTAL_SIZE or len(eligible) >= MAX_FILES:
                omitted.append({'path':rel, 'reason':'diagnostic bundle size/file limit'})
                continue
            eligible.append((path,rel,size))
            total += size

    if not eligible:
        raise ValueError('No eligible evidence artifacts in ' + str(root))
    fd, tempname = tempfile.mkstemp(prefix='.recompdev-evidence-',suffix='.partial',dir=root.parent)
    os.close(fd)
    temp = Path(tempname)
    destination_created = False
    try:
        with zipfile.ZipFile(temp,mode='w',compression=zipfile.ZIP_DEFLATED,
                             compresslevel=6,allowZip64=True) as z:
            for path,rel,size in eligible:
                # Validate each source is still inside the run folder; avoid
                # packaging an unrelated path through a late path substitution.
                if not path.resolve(strict=True).is_relative_to(root):
                    raise ValueError('Evidence file escapes run directory: ' + rel)
                digest = _sha256_file(path)
                z.write(path,arcname='evidence/'+rel)
                included.append({'path':'evidence/'+rel,'size':size,'sha256':digest})
            manifest = {
                'schema': SCHEMA, 'run_id': root.name, 'workflow_status': str(status),
                'source_sha256': source_sha256, 'files':included,
                'omitted':omitted,
                'excluded_original_rom': True,
                'excluded_native_project_builds': True,
                'original_evidence_folder_preserved': True,
                'notes': [
                    'Review logs/SQLite content for local paths before uploading.',
                    'Source-byte authenticity and hardware activity do not prove gameplay parity.',
                    'No original ROM or disc image is intentionally included.',
                ],
            }
            z.writestr('bundle-manifest.json',json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        with zipfile.ZipFile(temp) as check:
            bad=check.testzip()
            if bad:
                raise RuntimeError('Corrupt evidence ZIP member: '+bad)
        # Fail rather than clobbering a previous upload package. Use an
        # exclusive destination copy for portability (NTFS and POSIX).
        with archive.open('xb') as dest:
            destination_created = True
            with temp.open('rb') as source:
                shutil.copyfileobj(source,dest,1024 * 1024)
        return {'status':'READY','path':str(archive),'bytes':archive.stat().st_size,
                'included_files':len(included),'omitted_paths':len(omitted),
                'sha256':_sha256_file(archive),'manifest':'bundle-manifest.json',
                'source_image_included':False,'original_evidence_preserved':True}
    except Exception:
        # On failed writes do not leave a misleading upload-ready ZIP.
        if destination_created and archive.exists():
            try: archive.unlink()
            except OSError: pass
        raise
    finally:
        temp.unlink(missing_ok=True)
