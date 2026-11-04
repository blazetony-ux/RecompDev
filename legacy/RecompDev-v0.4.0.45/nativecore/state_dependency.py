"""Bounded source-labelled native event triage, without invented causal parity claims.

The input is a native hardware event stream, not an independent CPU reference.
Never infer MAME equivalence or game correctness from this diagnostic alone.
"""
from collections import Counter, defaultdict
from pathlib import Path
import hashlib
import json

EVENT_KINDS = frozenset(('RAM_WATCH_WRITE', 'CRAM_WRITE', 'VDP_CONTROL_WRITE',
                         'VRAM_WRITE', 'PSG_WRITE', 'IRQ', 'INPUT_READ',
                         'IO_CONTROL_WRITE', 'MAPPER_WRITE', 'VDP_STATUS_READ'))
MAX_FILES = 512
MAX_BYTES = 64 * 1024 * 1024
MAX_EVENTS = 500_000


def analyze_event_files(paths, source_sha256=None):
    files = [Path(p).resolve(strict=True) for p in paths]
    if not files or len(files) > MAX_FILES or len(set(files)) != len(files):
        raise ValueError('Missing, duplicate or unbounded event chunks')
    if source_sha256 is not None and (not isinstance(source_sha256, str) or
       len(source_sha256) != 64 or any(c not in '0123456789abcdef' for c in source_sha256)):
        raise ValueError('Invalid source SHA-256')
    ordered = sorted(files)
    total_bytes = sum(p.stat().st_size for p in ordered)
    if any(not p.is_file() for p in ordered) or total_bytes > MAX_BYTES:
        raise ValueError('Invalid or oversized event evidence')
    counts = Counter()
    cram_values, cram_origins = Counter(), Counter()
    cram_first = None
    watch = defaultdict(lambda: {'writes': 0, 'observed_values': Counter(), 'writers': Counter(),
                                 'first_step': None, 'last_step': None})
    irq_steps = []
    event_count = 0
    prev_step = -1
    digest = hashlib.sha256()
    for path in ordered:
        with path.open('rb') as stream:
            for raw in stream:
                digest.update(raw)
                event_count += 1
                if event_count > MAX_EVENTS or len(raw) > 2048:
                    raise ValueError('Unbounded event stream')
                event = json.loads(raw)
                if not isinstance(event, dict):
                    raise ValueError('Invalid event record')
                step, pc, kind = event.get('step'), event.get('pc'), event.get('kind')
                addr, value = event.get('address'), event.get('value')
                if any(type(n) is not int for n in (step, pc, addr, value)) or not (
                    0 <= step <= 10**12 and 0 <= pc < 65536 and
                    0 <= addr < 65536 and 0 <= value < 65536
                ) or not isinstance(kind, str) or len(kind) > 48:
                    raise ValueError('Invalid event field')
                if step < prev_step:
                    raise ValueError('Nonmonotonic event sequence')
                prev_step = step
                counts[kind] += 1
                if kind == 'CRAM_WRITE':
                    cram_values[value] += 1
                    cram_origins[pc] += 1
                    if cram_first is None:
                        cram_first = {'step': step, 'guest_pc': f'0x{pc:04X}',
                                      'cram_address': addr, 'value': value}
                elif kind == 'RAM_WATCH_WRITE':
                    if addr < 0xC000 or value > 255:
                        raise ValueError('Invalid RAM watch event')
                    record = watch[addr]
                    record['writes'] += 1
                    record['observed_values'][value] += 1
                    record['writers'][pc] += 1
                    if record['first_step'] is None:
                        record['first_step'] = step
                    record['last_step'] = step
                elif kind == 'IRQ' and len(irq_steps) < 64:
                    irq_steps.append(step)
    def ordered_counts(counter, fmt=str):
        return [{'value': fmt(value), 'count': count} for value, count in sorted(counter.items())]
    results = {}
    for addr, record in sorted(watch.items()):
        results[f'0x{addr:04X}'] = {
            'writes': record['writes'],
            'values_written': ordered_counts(record['observed_values'], lambda v: f'0x{v:02X}'),
            'writer_pcs': ordered_counts(record['writers'], lambda v: f'0x{v:04X}'),
            'first_step': record['first_step'], 'last_step': record['last_step']}
    findings = []
    if cram_values and all(v == 0 for v in cram_values):
        findings.append('OBSERVED_CRAM_WRITES_ALL_ZERO')
    if not results:
        findings.append('RAM_WRITER_PROVENANCE_NOT_CAPTURED')
    if counts['IRQ']:
        findings.append('IRQ_EVENTS_OBSERVED_NOT_REFERENCE_ALIGNED')
    return {
        'schema': 'recompdev-state-dependency-dev-v1',
        'source_sha256': source_sha256,
        'event_stream_sha256': digest.hexdigest(),
        'event_chunks': len(ordered), 'event_count': event_count,
        'recorded_kinds': dict(sorted(counts.items())),
        'cram': {'writes': counts['CRAM_WRITE'],
                 'first': cram_first,
                 'values': ordered_counts(cram_values, lambda v: f'0x{v:02X}'),
                 'writer_pcs': ordered_counts(cram_origins, lambda v: f'0x{v:04X}')},
        'watched_ram': results, 'first_irq_steps': irq_steps,
        'findings': findings,
        'root_cause': 'NOT_ESTABLISHED',
        'reference_equivalence': 'NOT_ESTABLISHED',
        'note': 'Native event provenance only. No first causal divergence asserted.'
    }
