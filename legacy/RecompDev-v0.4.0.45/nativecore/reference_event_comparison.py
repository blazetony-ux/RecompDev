"""Bounded ROM-identified MAME/native event comparison.

This is event-provenance triage, *not* instruction-aligned CPU equivalence.
Input MAME events are port taps. Reconstruct SMS CRAM writes from the VDP
command latch rather than assuming every port BE write targets the palette.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path

MAX_EVENTS = 250000
MAX_BYTES = 32 * 1024 * 1024


def _read_json_lines(paths):
    paths = list(paths)
    if not paths or len(paths) > 512:
        raise ValueError('Missing or excessive event files')
    if sum(Path(p).stat().st_size for p in paths) > MAX_BYTES:
        raise ValueError('Evidence too large')
    records = []
    for p in paths:
        with Path(p).open('rb') as fp:
            for line in fp:
                if len(line) > 4096 or len(records) >= MAX_EVENTS:
                    raise ValueError('Event count or record size exceeded')
                e = json.loads(line)
                if not isinstance(e, dict):
                    raise ValueError('Expected JSON object per line')
                records.append(e)
    return records


def _int(value, minv, maxv):
    if type(value) is not int or not minv <= value <= maxv:
        raise ValueError('Invalid event numeric field')
    return value


def _cram_events_mame(events):
    """Decode port BF 2-byte commands / port BE data writes (SMS VDP)."""
    pending = None
    mode = 0
    address = 0
    out = []
    for e in events:
        if e.get('type') != 'io_write':
            continue
        subtype = e.get('subtype')
        if subtype not in ('vdp_control', 'vdp_data'):
            continue
        v = _int(e.get('value'), 0, 255)
        pc = _int(e.get('pc'), 0, 65535)
        frame = _int(e.get('frame'), 0, 1000000)
        if subtype == 'vdp_control':
            if pending is None:
                pending = v
            else:
                mode = v >> 6
                address = ((v & 0x3f) << 8) | pending
                pending = None
        else:
            if mode == 3:
                out.append({'frame': frame, 'pc': pc, 'address': address & 31, 'value': v})
            address = (address + 1) & 0x3fff
    return out


def compare_reference_native(mame_events, native_events, native_frames, source_sha256, summary=None):
    """Compare observed source-attributed I/O and RAM effects, never CPU parity."""
    if not isinstance(source_sha256, str) or len(source_sha256) != 64 or any(c not in '0123456789abcdef' for c in source_sha256):
        raise ValueError('Invalid source identity')
    if summary is not None:
        if summary.get('metadata', {}).get('rom_sha256') != source_sha256:
            raise ValueError('Reference ROM identity differs')
        if summary.get('trace', {}).get('status') != 'COMPLETE_CARTRIDGE_EXECUTION_OBSERVATION':
            raise ValueError('No accepted cartridge execution')
        if not summary.get('trace', {}).get('cartridge_cpu_execution'):
            raise ValueError('Cartridge CPU execution not attested')
    if len(mame_events) > MAX_EVENTS or len(native_events) > MAX_EVENTS:
        raise ValueError('Excessive event count')

    mr = [e for e in mame_events if e.get('type') == 'io_read' and e.get('port') in (0xdc, 0xdd)]
    nr = [e for e in native_events if e.get('kind') == 'INPUT_READ' and e.get('address') in (0xdc, 0xdd)]
    def group_port_reads(events, origin):
        by = {}
        for e in events:
            pc = _int(e.get('pc'), 0, 65535)
            port = _int(e.get('port' if origin == 'mame' else 'address'), 0, 255)
            val = _int(e.get('value'), 0, 255)
            by.setdefault((pc, port), []).append(val)
        return by
    mreads = group_port_reads(mr, 'mame')
    nreads = group_port_reads(nr, 'native')
    differing = []
    for k in sorted(set(mreads) & set(nreads)):
        mvals = mreads[k]
        nvals = nreads[k]
        for idx, (a,b) in enumerate(zip(mvals, nvals)):
            if a != b:
                differing.append({'pc': f'0x{k[0]:04X}', 'port': f'0x{k[1]:02X}',
                                  'occurrence': idx+1, 'mame': f'0x{a:02X}', 'native': f'0x{b:02X}'})
    mcram = _cram_events_mame(mame_events)
    ncram = []
    for e in native_events:
        if e.get('kind') == 'CRAM_WRITE':
            ncram.append({'step': _int(e.get('step'),0,10**12), 'pc':_int(e.get('pc'),0,65535),
                          'address':_int(e.get('address'),0,31),'value':_int(e.get('value'),0,255)})
    mram = [e for e in mame_events if e.get('type') == 'ram_write']
    nram = [e for e in native_events if e.get('kind') == 'RAM_WATCH_WRITE']
    def ram_values(events, engine):
        out = {}
        for e in events:
            a = _int(e.get('address'), 0, 65535)
            if a < 0xc000:raise ValueError('RAM event address outside RAM')
            val = _int(e.get('value'),0,255)
            d = out.setdefault(f'0x{a:04X}', {'values':[], 'writer_pcs':[]})
            if not d['values'] or d['values'][-1] != val:
                d['values'].append(val)
            pc = f"0x{_int(e.get('pc'),0,65535):04X}"
            if pc not in d['writer_pcs']:
                d['writer_pcs'].append(pc)
        return out
    ram_m = ram_values(mram, 'mame')
    ram_n = ram_values(nram, 'native')
    m_nonzero = [x for x in mcram if x['value'] != 0]
    n_nonzero = [x for x in ncram if x['value'] != 0]
    findings = []
    if differing:
        findings.append('MATCHED_PC_INPUT_READ_VALUE_MISMATCH')
    if m_nonzero and not n_nonzero:
        findings.append('REFERENCE_NONZERO_CRAM_NATIVE_NO_NONZERO_CRAM')
    for a in sorted(set(ram_m)&set(ram_n)):
        if ram_m[a]['values'] != ram_n[a]['values']:
            findings.append('WATCHED_RAM_STATE_SEQUENCE_DIFFERS:' + a)
    msamples = [e for e in mame_events if e.get('type') == 'frame']
    return {
      'schema':'recompdev-cartridge-reference-events-v1',
      'source_sha256':source_sha256,
      'reference_cartridge_execution':'ATTESTED' if summary else 'UNVERIFIED',
      'reference_frame_samples':len(msamples),
      'native_frame_samples':len(native_frames),
      'matching_guest_pc_input_mismatches':differing,
      'mame_cram':{'writes':len(mcram),'nonzero_writes':len(m_nonzero),
                   'first_write':mcram[0] if mcram else None,
                   'first_nonzero':m_nonzero[0] if m_nonzero else None,
                   'nonzero_values':dict(sorted(Counter(f"0x{v['value']:02X}" for v in m_nonzero).items()))},
      'native_cram':{'writes':len(ncram),'nonzero_writes':len(n_nonzero),
                    'first_write':ncram[0] if ncram else None,
                    'first_nonzero':n_nonzero[0] if n_nonzero else None},
      'ram_state_values':{'mame':ram_m,'native':ram_n},
      'findings':findings,
      'first_instruction_divergence':'NOT_ESTABLISHED',
      'cpu_parity':'NOT_ESTABLISHED',
      'note':'Event sequence analysis. Frame indices and instruction boundaries are not proven aligned; mismatched values at the same source PC are observed I/O disagreements, not proof of the first causal CPU divergence.'
    }


def run_files(mame_jsonl, native_jsonl_files, native_session_path, source_sha256, summary_path, output_path):
    summary = json.loads(Path(summary_path).read_text(encoding='utf-8'))
    native = json.loads(Path(native_session_path).read_text(encoding='utf-8'))
    if native.get('source_sha256') != source_sha256:
        raise ValueError('Native ROM identity differs')
    report = compare_reference_native(_read_json_lines([mame_jsonl]), _read_json_lines(native_jsonl_files),
                                      native.get('frame_hardware',[]), source_sha256, summary)
    Path(output_path).write_text(json.dumps(report,indent=2)+'\n', encoding='utf-8')
    return report
