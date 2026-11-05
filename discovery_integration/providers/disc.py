"""ISO9660 disc reader bridge (2048 and raw 2352 sectors), no PS1 game assumptions.

Reads bounded logical files through the preserved sector-aware adapter. Exports are
opt-in and excluded by existing evidence bundling rules. Only structurally
confirmed executable/TIM files are eligible for extraction.
"""
from __future__ import annotations
import hashlib
import io
import sys
from pathlib import Path

ID = 'legacy.iso9660.sector.v1'
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_CHECKED_FILES = 512
MAX_EXPORTED_FILES = 16


def scan(path: Path, legacy_root: Path, *, export_dir: Path | None = None) -> dict:
    if str(legacy_root) not in sys.path:
        sys.path.insert(0, str(legacy_root))
    from discovery.formats import IsoReader, tim_span
    from discovery.image import render_tim
    from adapters.formats import open_image
    reader = IsoReader(path)
    if not reader.valid():
        raise ValueError('ISO9660 sector provider was selected for a non-ISO input')
    entries = reader.files(max_entries=MAX_CHECKED_FILES, max_depth=8)
    result = {'provider': ID, 'sector_size': reader.sector_size,
              'user_data_offset': reader.data_offset, 'inventory_count': len(entries),
              'inventory_may_be_truncated': len(entries) >= MAX_CHECKED_FILES,
              'candidates': [], 'blocked': [], 'native_translation': 'NOT_ATTEMPTED',
              'assets_gameplay_verified': False}
    exported = 0
    for entry in entries:
        size = entry['size']
        logical = entry['path']
        if size <= 0:
            continue
        if size > MAX_FILE_BYTES:
            if logical.upper().endswith(('.EXE','.TIM')):
                result['blocked'].append({'disc_path': logical, 'status': 'FILE_EXCEEDS_EXTRACTION_BOUND', 'bytes': size})
            continue
        # A format signature is always required: extension alone is not evidence.
        header = reader.read(entry['extent'],0,min(size,0x800))
        kind = 'psx-exe' if header.startswith(b'PS-X EXE') else 'ps1-tim' if header.startswith(b'\x10\0\0\0') else None
        if kind is None:
            continue
        raw = reader.read(entry['extent'],0,size)
        data = {'disc_path': logical, 'bytes': size, 'sha256': hashlib.sha256(raw).hexdigest(),
                'kind': kind, 'sector_aware': True}
        try:
            if kind == 'psx-exe':
                img = open_image(raw, fmt='psx-exe')
                data.update({'status': 'STATIC_ENTRY_VALIDATED', 'isa_candidate': img.isa,
                             'entry': img.entry, 'mapped_region': {'start':img.start, 'stop':img.stop},
                             'warnings': list(img.warnings)})
            else:
                length = tim_span(io.BytesIO(raw),0,len(raw))
                if length is None or length != len(raw):
                    raise ValueError('TIM is not a bounded complete image')
                fmt,w,h,_,consumed = render_tim(raw)
                if consumed != len(raw):
                    raise ValueError('TIM decoded length mismatch')
                data.update({'status': 'STRUCTURALLY_VALIDATED_ASSET', 'tim_format':fmt, 'width':w,'height':h})
            if export_dir is not None and exported < MAX_EXPORTED_FILES:
                dest = export_dir / (f'candidate-{exported:03d}.' + ('psx-exe' if kind == 'psx-exe' else 'tim'))
                dest.parent.mkdir(parents=True,exist_ok=True)
                with dest.open('xb') as f: f.write(raw)
                data['exported_path'] = str(dest)
                exported += 1
        except (ValueError, IndexError) as exc:
            data['status'] = 'BLOCKED_VALIDATION'
            data['reason'] = str(exc)[:240]
        result['candidates'].append(data)
    result['extracted_files'] = exported
    result['unrecognised_payloads_not_claimed_decoded'] = len(entries) - len(result['candidates'])
    return result


def run(context: dict) -> dict:
    export = Path(context['export_dir']) if context.get('export_dir') is not None else None
    return scan(Path(context['source']), Path(context['legacy_root']), export_dir=export)
