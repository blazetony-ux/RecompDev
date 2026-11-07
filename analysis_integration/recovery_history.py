"""Immutable, source-attested import of previous native recovery evidence.

This is *evidence replay*, not process/checkpoint restoration. It imports no
executables and never trusts prior translator results in place of new checks.
The active native discovery/translation DLLs recheck all submitted evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from analysis_integration.ghidra_evidence import read_export

MAX_DOC = 64 * 1024 * 1024
MAX_IMPORTS = 64

class RecoveryHistoryError(ValueError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(path: Path, limit: int = MAX_DOC) -> tuple[dict, bytes]:
    if not path.is_file() or path.is_symlink() or not 0 < path.stat().st_size <= limit:
        raise RecoveryHistoryError('HISTORY_MISSING_OR_OVERSIZED_EVIDENCE')
    blob = path.read_bytes()
    try:
        data = json.loads(blob.decode('utf-8-sig'))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RecoveryHistoryError('HISTORY_INVALID_JSON') from exc
    if not isinstance(data, dict):
        raise RecoveryHistoryError('HISTORY_DOCUMENT_NOT_OBJECT')
    return data, blob


def _inside(root: Path, value: str) -> Path:
    if not isinstance(value, str) or not value:
        raise RecoveryHistoryError('HISTORY_PATH_INVALID')
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise RecoveryHistoryError('HISTORY_MISSING_OR_OVERSIZED_EVIDENCE') from exc
    if root not in resolved.parents:
        raise RecoveryHistoryError('HISTORY_PATH_ESCAPES_ROOT')
    if path.is_symlink() or not resolved.is_file():
        raise RecoveryHistoryError('HISTORY_FILE_INVALID')
    return resolved


def _check_seed(seed: dict, source_bytes: bytes, digest: str) -> tuple:
    if seed.get('schema') != 'recompdev.native.app.stop.v1' or seed.get('source_sha256') != digest or seed.get('rom_bytes') != len(source_bytes):
        raise RecoveryHistoryError('HISTORY_STOP_SOURCE_IDENTITY_MISMATCH')
    if seed.get('status') not in ('UNTRANSLATED_INITIAL_CODE','BANKED_CODE_NOT_TRANSLATED','UNTRANSLATED_PHYSICAL_ROM_OFFSET'):
        raise RecoveryHistoryError('HISTORY_STOP_NOT_TRANSLATION_GAP')
    if len(source_bytes) % 0x4000 or not 0 < len(source_bytes) <= 32 * 1024 * 1024:
        raise RecoveryHistoryError('HISTORY_ROM_BANK_LAYOUT_UNSUPPORTED')
    pc, physical, mapper, sp, steps = (seed.get(x) for x in ('pc','physical_offset','mapper','sp','native_steps'))
    if (type(pc) is not int or not 0 <= pc < 0xc000 or
        type(sp) is not int or not 0 <= sp <= 0xffff or
        type(steps) is not int or steps < 0 or
        not isinstance(mapper, list) or len(mapper) != 4 or
        any(type(bank) is not int or not 0 <= bank <= 255 for bank in mapper) or
        type(physical) is not int or not 0 <= physical < len(source_bytes)):
        raise RecoveryHistoryError('HISTORY_STOP_INVALID_OBSERVED_STATE')
    if pc >= 0x8000 and mapper[0] & 8:
        raise RecoveryHistoryError('HISTORY_STOP_MAPPED_TO_RAM')
    bank_count = len(source_bytes)//0x4000
    slot = pc // 0x4000
    effective_bank = mapper[slot + 1] % bank_count
    expected = pc if pc < 0x400 else effective_bank * 0x4000 + (pc & 0x3fff)
    if physical != expected:
        raise RecoveryHistoryError('HISTORY_STOP_PHYSICAL_MISMATCH')
    return pc, physical, tuple(mapper)


def _check_bank_export(doc: dict, seed: dict, source_bytes: bytes, digest: str, base: dict) -> int:
    if doc.get('source_sha256') != digest or doc.get('target_id') != base.get('target_id') or doc.get('language') != base.get('language'):
        raise RecoveryHistoryError('HISTORY_GHIDRA_BASE_IDENTITY_MISMATCH')
    context = doc.get('bank_context')
    if not isinstance(context, dict):
        raise RecoveryHistoryError('HISTORY_GHIDRA_BANK_CONTEXT_MISSING')
    slot = seed['pc']//0x4000
    bank_count = len(source_bytes)//0x4000
    bank = seed['mapper'][slot+1] % bank_count
    if (type(context.get('slot')) is not int or context['slot'] != slot or
        type(context.get('bank')) is not int or context['bank'] != bank or
        context.get('base') != slot*0x4000 or context.get('physical_start') != bank*0x4000):
        raise RecoveryHistoryError('HISTORY_GHIDRA_BANK_CONTEXT_MISMATCH')
    hits = 0
    seen = set()
    total = 0
    for function in doc['functions']:
        if not isinstance(function, dict) or not isinstance(function.get('instructions'), list):
            raise RecoveryHistoryError('HISTORY_GHIDRA_BAD_FUNCTION')
        for ins in function['instructions']:
            if not isinstance(ins, dict):
                raise RecoveryHistoryError('HISTORY_GHIDRA_BAD_INSTRUCTION')
            addr, length, expected = (ins.get(k) for k in ('address','length','bytes_sha256'))
            if type(addr) is not int or type(length) is not int or type(expected) is not str or not 1 <= length <= 8:
                raise RecoveryHistoryError('HISTORY_GHIDRA_BAD_EXTENT')
            if not slot*0x4000 <= addr < addr+length <= (slot+1)*0x4000 or addr in seen:
                raise RecoveryHistoryError('HISTORY_GHIDRA_OUTSIDE_VERIFIED_SLOT')
            off = addr if slot == 0 and addr < 0x400 else bank*0x4000+(addr&0x3fff)
            if off + length > len(source_bytes) or _sha(source_bytes[off:off+length]) != expected:
                raise RecoveryHistoryError('HISTORY_GHIDRA_INSTRUCTION_BYTES_MISMATCH')
            seen.add(addr)
            total += 1
            if total > 200000:
                raise RecoveryHistoryError('HISTORY_GHIDRA_INSTRUCTION_LIMIT')
            if addr == seed['pc']:
                hits += 1
    if hits != 1:
        raise RecoveryHistoryError('HISTORY_GHIDRA_OBSERVED_STOP_NOT_VERIFIED')
    return total


def import_previous(previous: Path, destination: Path, rom: Path, base_export: Path, preview_seed: Path | None = None) -> tuple[list[Path], list[Path], dict]:
    """Read, verify and independently copy prior gap seeds and bank P-code overlays.

    No writes occur under `previous`. A fresh destination is mandatory. All
    imported evidence remains read-only input to the separately compiled native
    translator and its own source verification gates.
    """
    previous = Path(previous).resolve(strict=True)
    destination = Path(destination)
    if not previous.is_dir() or destination.exists():
        raise RecoveryHistoryError('HISTORY_ROOT_OR_DESTINATION_INVALID')
    if destination.resolve() == previous or previous in destination.resolve().parents:
        raise RecoveryHistoryError('HISTORY_OUTPUT_OVERLAPS_INPUT')
    data = Path(rom).read_bytes()
    digest = _sha(data)
    report, _ = _json(previous/'orchestration.json', 8 * 1024 * 1024)
    if report.get('schema') != 'recompdev.native.orchestrator.v1' or report.get('source_sha256') != digest:
        raise RecoveryHistoryError('HISTORY_ORCHESTRATION_IDENTITY_MISMATCH')
    rounds = report.get('rounds')
    if not isinstance(rounds, list) or not 1 <= len(rounds) <= 8:
        raise RecoveryHistoryError('HISTORY_ROUNDS_INVALID')
    base = read_export(base_export)
    if base.get('source_sha256') != digest:
        raise RecoveryHistoryError('HISTORY_BASE_GHIDRA_SOURCE_MISMATCH')
    # A session's imported-history folder contains the *attested copies*
    # brought forward from older sessions. Revalidate those local copies against
    # the original ROM and current Ghidra identity before adding this session's
    # fresh stops. Never chase previous_root (an unauthorised external path).
    entries = []
    seen = set()
    inherited = previous / 'imported-history'
    if inherited.exists() or inherited.is_symlink():
        if inherited.is_symlink() or not inherited.is_dir():
            raise RecoveryHistoryError('HISTORY_INHERITED_DIRECTORY_INVALID')
        imported, _ = _json(_inside(previous, 'imported-history/history-import.json'), 1024 * 1024)
        if (imported.get('schema') != 'recompdev.recovery.history-import.v1' or
            imported.get('source_sha256') != digest or
            imported.get('verified') != 'RECHECKED_SOURCE_MAPPER_INSTRUCTION_HASHES'):
            raise RecoveryHistoryError('HISTORY_INHERITED_AUDIT_INVALID')
        records = imported.get('entries')
        if (not isinstance(records, list) or not 1 <= len(records) <= MAX_IMPORTS or
            imported.get('imported_stops') != len(records)):
            raise RecoveryHistoryError('HISTORY_INHERITED_COUNT_INVALID')
        bank_count = 0
        for n, entry in enumerate(records, start=1):
            if not isinstance(entry, dict):
                raise RecoveryHistoryError('HISTORY_INHERITED_ENTRY_INVALID')
            seed_blob = _json(_inside(previous, f'imported-history/stop-{n:02d}.json'), 2 * 1024 * 1024)[1]
            if _sha(seed_blob) != entry.get('stop_sha256'):
                raise RecoveryHistoryError('HISTORY_INHERITED_STOP_HASH_MISMATCH')
            seed = json.loads(seed_blob.decode('utf-8-sig'))
            key = _check_seed(seed, data, digest)
            if (entry.get('pc') != key[0] or entry.get('physical_offset') != key[1] or
                entry.get('mapper') != list(key[2]) or key in seen):
                raise RecoveryHistoryError('HISTORY_INHERITED_STOP_STATE_MISMATCH')
            bank_blob = None
            if 'bank_export_sha256' in entry:
                path = _inside(previous, f'imported-history/bank-{n:02d}.json')
                bank_doc, bank_blob = _json(path)
                if _sha(bank_blob) != entry['bank_export_sha256']:
                    raise RecoveryHistoryError('HISTORY_INHERITED_BANK_HASH_MISMATCH')
                _check_bank_export(read_export(path), seed, data, digest, base)
                bank_count += 1
            seen.add(key)
            entries.append((seed_blob, bank_blob, key, entry.get('previous_round', n)))
        if imported.get('imported_bank_exports') != bank_count:
            raise RecoveryHistoryError('HISTORY_INHERITED_BANK_COUNT_MISMATCH')
    inherited_count = len(entries)
    for index, record in enumerate(rounds, start=1):
        if not isinstance(record, dict) or record.get('round') != index:
            raise RecoveryHistoryError('HISTORY_ROUND_ORDER_INVALID')
        if 'recovery_seed' not in record:
            continue
        path = _inside(previous, record['recovery_seed'])
        seed, seed_blob = _json(path, 2 * 1024 * 1024)
        key = _check_seed(seed, data, digest)
        if key in seen:
            raise RecoveryHistoryError('HISTORY_REPEATED_OBSERVED_STOP')
        seen.add(key)
        bank_blob = None
        if 'ghidra_focused_region' in record:
            overlay = _inside(previous, 'round-%02d-ghidra-recovery/source-verified-bank-functions.json' % index)
            bank_doc, bank_blob = _json(overlay)
            bank_doc = read_export(overlay)
            _check_bank_export(bank_doc, seed, data, digest, base)
            audit, _ = _json(_inside(previous, 'round-%02d-ghidra-recovery/recovery-audit.json' % index), 1024*1024)
            for field in ('observed_pc','observed_physical','observed_mapper','source_sha256'):
                expected = {'observed_pc': seed['pc'], 'observed_physical': seed['physical_offset'],
                            'observed_mapper': seed['mapper'], 'source_sha256': digest}[field]
                if audit.get(field) != expected:
                    raise RecoveryHistoryError('HISTORY_GHIDRA_AUDIT_MISMATCH')
        entries.append((seed_blob, bank_blob, key, index))
    preview_added = False
    if preview_seed is not None:
        seed, blob = _json(Path(preview_seed), 2 * 1024 * 1024)
        key = _check_seed(seed, data, digest)
        if seed.get('observed_run') != 'CONTROLLER_NATIVE_PREVIEW':
            raise RecoveryHistoryError('HISTORY_PREVIEW_PROVENANCE_INVALID')
        if key not in seen:
            entries.append((blob, None, key, 'preview'))
            seen.add(key)
            preview_added = True
    if not entries:
        raise RecoveryHistoryError('HISTORY_NO_REUSABLE_OBSERVATIONS')
    if len(entries) > MAX_IMPORTS:
        raise RecoveryHistoryError('HISTORY_IMPORT_LIMIT_REACHED')
    destination.mkdir(parents=True, exist_ok=False)
    imported_seeds = []
    imported_banks = []
    provenance = []
    for n, (seed_blob, bank_blob, key, old_round) in enumerate(entries, start=1):
        dest_seed = destination/('stop-%02d.json' % n)
        dest_seed.write_bytes(seed_blob)
        imported_seeds.append(dest_seed)
        entry = {'previous_round': old_round, 'stop_sha256': _sha(seed_blob), 'pc': key[0],
                 'physical_offset': key[1], 'mapper': list(key[2])}
        if bank_blob is not None:
            dest_bank = destination/('bank-%02d.json' % n)
            dest_bank.write_bytes(bank_blob)
            imported_banks.append(dest_bank)
            entry['bank_export_sha256'] = _sha(bank_blob)
        provenance.append(entry)
    audit = {'schema': 'recompdev.recovery.history-import.v1',
             'source_sha256': digest, 'previous_orchestration_sha256': _sha((previous/'orchestration.json').read_bytes()),
             'imported_stops': len(imported_seeds), 'imported_bank_exports': len(imported_banks),
             'inherited_stops': inherited_count, 'new_stops': len(entries) - inherited_count,
             'preview_stops': int(preview_added),
             'verified': 'RECHECKED_SOURCE_MAPPER_INSTRUCTION_HASHES', 'entries': provenance,
             'previous_root': str(previous), 'native_semantics_qualified': False}
    (destination/'history-import.json').write_text(json.dumps(audit, sort_keys=True, indent=2)+'\n', encoding='utf8')
    return imported_seeds, imported_banks, audit
