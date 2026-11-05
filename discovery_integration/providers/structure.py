"""Adapter to preserved structural probing and static executable mapping.

This module alone knows where the immutable historical implementation lives.
There is no controller knowledge of per-ISA formats or individual instructions.
"""
from __future__ import annotations
import sys
from pathlib import Path

ID = 'legacy.structure.v1'


def analyze(path: Path, legacy_root: Path, *, limit: int = 8 * 1024 * 1024) -> dict:
    if str(legacy_root) not in sys.path:
        sys.path.insert(0, str(legacy_root))
    from discovery.formats import probe
    fmt, method, name = probe(path)
    detail = {'provider': ID, 'format': fmt, 'detected_by': method,
              'title_header': name, 'native_translation': 'NOT_ATTEMPTED',
              'identity_from_filename': False}
    # Hardware/ISA selection is a format-adapter decision, never a game-name lookup.
    if fmt in ('mastersystem', 'gamegear', 'mastersystem-candidate', 'gamegear-candidate'):
        detail['isa_candidate'] = 'z80'
        detail['mapping_status'] = 'CPU_FAMILY_ONLY_NO_NATIVE_MAPPING'
    if fmt in ('megadrive', 'psx-exe'):
        from adapters.formats import open_image
        size = path.stat().st_size
        if size > limit:
            detail['mapping_status'] = 'BLOCKED_SIZE_LIMIT'
            detail['limit_bytes'] = limit
        else:
            try:
                img = open_image(path.read_bytes(), fmt=fmt)
                detail.update({'mapping_status': 'STATIC_ENTRY_VALIDATED', 'isa_candidate': img.isa,
                               'byte_order': img.endian, 'entry': img.entry,
                               'mapped_region': {'start': img.start, 'stop': img.stop},
                               'mapping_warnings': list(img.warnings)})
            except ValueError as exc:
                detail['mapping_status'] = 'BLOCKED_INVALID_EXECUTABLE_MAPPING'
                detail['mapping_reason'] = str(exc)[:250]
    return detail


def run(context: dict) -> dict:
    return analyze(Path(context['source']), Path(context['legacy_root']))
