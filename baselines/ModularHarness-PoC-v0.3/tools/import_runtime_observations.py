#!/usr/bin/env python3
"""Import source-checked *runtime observations* into a NEW v0445 schema sidecar.

Observations are NOT Ghidra exports, native parity, proven instruction lengths,
or evidence of code coverage of unexecuted paths. Never edits main catalogue.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'vendor' / 'RecompDev-v0445'))
from discovery import store  # noqa: E402

EVENTS = {'FALLBACK_DISCOVERED', 'NATIVE_EXECUTED', 'BANK_SWITCH', 'EXECUTION_BLOCKED'}
MAX_EVENTS = 100000
MAX_ROM_BYTES = 64 * 1024 * 1024


def _integer(row, key, bottom, top):
    val = row.get(key)
    if type(val) is not int or not bottom <= val <= top:
        raise ValueError(f'invalid {key}: {val!r}')
    return val


def convert(rom_path: Path, event_path: Path, out: Path, report_path=None):
    rom_path = Path(rom_path).resolve(strict=True)
    event_path = Path(event_path).resolve(strict=True)
    out = Path(out).resolve()
    if out.exists():
        raise ValueError('Refusing to replace existing database: ' + str(out))
    if not (0x4000 <= rom_path.stat().st_size <= MAX_ROM_BYTES):
        raise ValueError('ROM size outside supported bounds')
    if event_path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('Event file exceeds safety limit')
    raw = rom_path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if report_path is not None:
        report = json.loads(Path(report_path).read_text(encoding='utf-8'))
        if report.get('source_sha256') != sha or report.get('case') != 'rom':
            raise ValueError('Execution report / ROM identity mismatch')
    observations = []
    last_step = 0
    with event_path.open('r', encoding='utf-8') as stream:
        for n, line in enumerate(stream, 1):
            if n > MAX_EVENTS:
                raise ValueError('Event count exceeds safety limit')
            row = json.loads(line)
            kind = row.get('event')
            if kind not in EVENTS:
                raise ValueError('Unsupported event type')
            pc = _integer(row, 'pc', 0, 0xffff)
            physical = _integer(row, 'physical', 0, 0xffffffff)
            opcode = _integer(row, 'opcode', 0, 255)
            step = _integer(row, 'step', 1, MAX_EVENTS + 1)
            cycles = _integer(row, 'cycles', 0, 1000)
            bank = _integer(row, 'bank', 0, 255)
            if step < last_step:
                raise ValueError('Out-of-order event sequence')
            last_step = step
            if kind == 'EXECUTION_BLOCKED' and cycles != 0:
                raise ValueError('Blocked instruction cannot accrue cycles')
            if kind in {'FALLBACK_DISCOVERED', 'NATIVE_EXECUTED', 'BANK_SWITCH'} and cycles == 0:
                raise ValueError('Executed instruction must have cycles')
            if physical == 0xffffffff:
                if pc < 0x8000:
                    raise ValueError('Invalid dynamic-memory execution address')
                source_backed = False
            else:
                if physical >= len(raw):
                    raise ValueError('Physical address outside source image')
                if physical % 0x4000 != pc % 0x4000 or (pc < 0x400 and physical != pc):
                    raise ValueError('PC / physical banking identity mismatch')
                if raw[physical] != opcode:
                    raise ValueError('Opcode / ROM byte mismatch')
                source_backed = True
            observations.append((kind, pc, physical, opcode, step, cycles, bank, source_backed))
    if not observations:
        raise ValueError('No execution events')
    out.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive reservation: never silently overwrite a production or prior sidecar.
    with out.open('xb'):
        pass
    con = None
    try:
        con = store.connect(out)
        store.store_source(con, sha, str(rom_path), len(raw), 'SHA256_COMPLETE',
                           'mastersystem', rom_path.name, 'harness-v0.3-unverified-runtime')
        regions = set()
        tasks = set()
        dynamic = set()
        for kind, pc, physical, opcode, step, cycles, bank, source_backed in observations:
            if kind == 'BANK_SWITCH':
                # Mapping changes cannot be reconstructed without full mapper history.
                continue
            evidence = {'method': 'harness-observation-v0.3', 'pc': pc, 'physical': physical,
                        'bank_at_step': bank, 'opcode': opcode, 'event': kind, 'step': step,
                        'guest_instruction_length': 'UNKNOWN', 'verified_translation': False}
            if source_backed:
                if physical not in regions:
                    store.region(con, sha, physical, 1, 'CODE_CANDIDATE',
                                 'RUNTIME_OBSERVED_UNVERIFIED', evidence)
                    regions.add(physical)
                if kind in {'FALLBACK_DISCOVERED', 'EXECUTION_BLOCKED'} and physical not in tasks:
                    store.task(con, sha, 'investigate_runtime_code',
                               subject=f'physical={physical:08x}', priority=85,
                               version='harness-v0.3')
                    tasks.add(physical)
            elif pc not in dynamic:
                store.task(con, sha, 'investigate_dynamic_cpu_execution',
                           subject=f'pc={pc:04x}', priority=85, version='harness-v0.3')
                dynamic.add(pc)
        result = {'schema': 'recompdev-harness-sidecar-v0.3', 'source_sha256': sha,
                  'source_bytes': len(raw), 'events': len(observations),
                  'candidate_start_bytes': len(regions), 'review_tasks': len(tasks) + len(dynamic),
                  'main_catalogue_mutated': False, 'qualified_translation': False,
                  'note': 'Runtime observations only; instruction lengths and semantics unverified.'}
    except BaseException:
        if con is not None:
            con.close()
        out.unlink(missing_ok=True)
        raise
    else:
        con.close()
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom', type=Path, required=True)
    p.add_argument('--events', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--report', type=Path)
    args = p.parse_args()
    try:
        print(json.dumps(convert(args.rom, args.events, args.output, args.report), sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f'RUNTIME_OBSERVATION_IMPORT_REJECTED: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
