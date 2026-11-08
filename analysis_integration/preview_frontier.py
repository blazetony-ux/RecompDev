"""Guarded handoff of a compiled native preview's observed translation stop.

A preview is separate from a recovery job. Only a complete, SHA-verified
small archive with native final CPU state, ROM identity, original generated
translation-source identity, and an actual untranslated-code stop can enter
recovery. The target native discovery/translator provider checks bytes again.
The archive is evidence, not a runtime checkpoint or an authenticated signature.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import zipfile
import argparse
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from analysis_integration.recovery_history import _check_seed, RecoveryHistoryError

GAPS=frozenset({'UNTRANSLATED_INITIAL_CODE','BANKED_CODE_NOT_TRANSLATED','UNTRANSLATED_PHYSICAL_ROM_OFFSET'})
EXPECTED={'manifest.json','preview.json','monitor-events.jsonl','recovery-seed.json'}
JOB_ID=re.compile(r'job-[A-Za-z0-9_-]{1,96}\Z')
CYCLE=re.compile(r'cycle-(?:0[1-9]|[1-9][0-9]|1[01][0-9]|12[0-8])\Z')
ROUND=re.compile(r'round-0[1-8]\Z')

class PreviewFrontierError(ValueError):pass

def _sha(raw):return hashlib.sha256(raw).hexdigest()

def _json(blob, max_bytes):
    if not 0<len(blob)<=max_bytes:raise PreviewFrontierError('PREVIEW_DOCUMENT_SIZE_INVALID')
    try:doc=json.loads(blob)
    except (UnicodeError,ValueError) as e:raise PreviewFrontierError('PREVIEW_INVALID_JSON') from e
    if not isinstance(doc,dict):raise PreviewFrontierError('PREVIEW_DOCUMENT_NOT_OBJECT')
    return doc


def verify_and_stage_preview(archive:Path, previous:Path, rom:Path, job_id:str, destination:Path|None)->Path|dict:
    """Inspect a controller-created ZIP and copy only the admitted stop to a
    fresh evidence path. Never modifies a previous job/session or archive.
    """
    if Path(archive).is_symlink():raise PreviewFrontierError('PREVIEW_ARCHIVE_UNSAFE')
    archive=Path(archive).resolve(strict=True)
    previous=Path(previous).resolve(strict=True)
    rom=Path(rom).resolve(strict=True)
    destination=Path(destination) if destination is not None else None
    if not JOB_ID.fullmatch(job_id or '') or not CYCLE.fullmatch(previous.name):
        raise PreviewFrontierError('PREVIEW_SESSION_OR_JOB_INVALID')
    if previous.parent.name!='sessions' or previous.parent.parent.name!=job_id:
        raise PreviewFrontierError('PREVIEW_JOB_PATH_MISMATCH')
    if not archive.is_file() or archive.stat().st_size>4*1024*1024 or archive.is_symlink():
        raise PreviewFrontierError('PREVIEW_ARCHIVE_UNSAFE')
    if destination is not None and (destination.exists() or destination.is_symlink()):raise PreviewFrontierError('PREVIEW_DESTINATION_ALREADY_EXISTS')
    rom_bytes=rom.read_bytes()
    if not (0<len(rom_bytes)<=32*1024*1024) or len(rom_bytes)%0x4000:
        raise PreviewFrontierError('PREVIEW_ROM_LAYOUT_INVALID')
    digest=_sha(rom_bytes)
    try:
        with zipfile.ZipFile(archive) as z:
            if set(z.namelist())!=EXPECTED or len(z.infolist())!=len(EXPECTED):
                raise PreviewFrontierError('PREVIEW_SEED_MISSING_OR_EXTRA_FILES')
            if any(x.is_dir() or x.file_size>2*1024*1024 or x.compress_size>2*1024*1024 for x in z.infolist()):
                raise PreviewFrontierError('PREVIEW_ZIP_MEMBER_TOO_LARGE')
            content={name:z.read(name) for name in EXPECTED}
    except (zipfile.BadZipFile,RuntimeError,OSError) as exc:
        raise PreviewFrontierError('PREVIEW_ZIP_UNREADABLE') from exc
    manifest=_json(content['manifest.json'],16384)
    if manifest.get('schema')!='recompdev.preview.diagnostics.v1' or not isinstance(manifest.get('files'),dict) or set(manifest['files'])!=EXPECTED-{'manifest.json'}:
        raise PreviewFrontierError('PREVIEW_MANIFEST_INVALID')
    if manifest.get('rom_included') is not False or manifest.get('native_binary_included') is not False:
        raise PreviewFrontierError('PREVIEW_CONTENT_POLICY_INVALID')
    for name,meta in manifest['files'].items():
        if not isinstance(meta,dict) or meta.get('sha256')!=_sha(content[name]) or meta.get('bytes')!=len(content[name]):
            raise PreviewFrontierError('PREVIEW_MANIFEST_HASH_MISMATCH')
    summary=_json(content['preview.json'],256*1024)
    seed=_json(content['recovery-seed.json'],16384)
    if (summary.get('schema')!='recompdev.preview.session.v1' or
        summary.get('status')!='GUEST_BLOCKED_UNTRANSLATED' or
        summary.get('process_exit_code')!=0 or
        summary.get('recovery_state_modified') is not False or
        summary.get('recovery_seed_available') is not True or
        summary.get('source_sha256')!=digest or summary.get('job_id')!=job_id or
        summary.get('cycle')!=previous.name):
        raise PreviewFrontierError('PREVIEW_SESSION_ATTESTATION_MISMATCH')
    round_name=summary.get('round')
    if not isinstance(round_name,str) or not ROUND.fullmatch(round_name):
        raise PreviewFrontierError('PREVIEW_ROUND_INVALID')
    project=previous/round_name
    expected_project=project/'translated.cpp'
    if expected_project.is_symlink() or not expected_project.is_file() or not expected_project.resolve().is_relative_to(previous):
        raise PreviewFrontierError('PREVIEW_TRANSLATION_SOURCE_MISSING')
    if summary.get('translated_cpp_sha256') != _sha(expected_project.read_bytes()):
        raise PreviewFrontierError('PREVIEW_TRANSLATION_SOURCE_MISMATCH')
    report=_json((previous/'orchestration.json').read_bytes(),8*1024*1024)
    if report.get('schema')!='recompdev.native.orchestrator.v1' or report.get('source_sha256')!=digest:
        raise PreviewFrontierError('PREVIEW_ORCHESTRATION_IDENTITY_MISMATCH')
    stop=summary.get('native_stop')
    if not isinstance(stop,dict) or stop.get('status') not in GAPS:
        raise PreviewFrontierError('PREVIEW_STOP_NOT_TRANSLATION_GAP')
    published=stop.get('published_stop')
    if (not isinstance(published,dict) or published.get('type')!='stop' or
        published.get('status')!='untranslated_code' or published.get('pc')!=seed.get('pc') or
        published.get('physical_offset')!=seed.get('physical_offset') or
        stop.get('pc')!=seed.get('pc') or stop.get('physical_offset')!=seed.get('physical_offset') or
        stop.get('status')!=seed.get('status')):
        raise PreviewFrontierError('PREVIEW_GUEST_STOP_MISMATCH')
    if (seed.get('observed_run')!='CONTROLLER_NATIVE_PREVIEW' or
        seed.get('qualification')!='UNTRANSLATED_CODE_STOP_ONLY' or
        seed.get('source_sha256')!=digest):
        raise PreviewFrontierError('PREVIEW_SEED_PROVENANCE_MISMATCH')
    try:_check_seed(seed,rom_bytes,digest)
    except RecoveryHistoryError as exc:
        raise PreviewFrontierError('PREVIEW_SEED_'+str(exc)) from exc
    # The native provider will independently validate source bytes and mapping.
    if destination is None:return seed
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_bytes(content['recovery-seed.json'])
    return destination


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage',choices=['preview-verify'],required=True)
    p.add_argument('--preview-stop',required=True)
    p.add_argument('--resume-from',required=True)
    p.add_argument('--rom',required=True)
    p.add_argument('--job-id',required=True)
    args=p.parse_args(argv)
    try:
        seed=verify_and_stage_preview(args.preview_stop,args.resume_from,args.rom,args.job_id,None)
    except (PreviewFrontierError,OSError,ValueError,KeyError) as exc:
        print('RECOMPDEV_PREVIEW_VERIFICATION=REJECTED_'+type(exc).__name__,flush=True)
        return 2
    print('RECOMPDEV_PREVIEW_VERIFICATION=SOURCE_AND_SESSION_RECHECKED',flush=True)
    print('RECOMPDEV_PREVIEW_PC='+str(seed['pc']),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
