"""Isolated v0.3 ROM probe -> event provenance -> v0445 sidecar acceptance tests."""
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path

root = Path(sys.argv[1])
exe = Path(sys.argv[2])
plugindir = Path(sys.argv[3])
sys.path.insert(0, str(root / 'tools'))
from import_runtime_observations import convert
from build_pcode_plugin import generate

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    raw = bytearray(0x8000)
    raw[:8] = bytes((0x3e, 0x51, 0x32, 0x00, 0xc0, 0xf3, 0x00, 0x76))
    raw[0x7ff0:0x7ff8] = b'TMR SEGA'
    rom = tmp / 'owner.sms'
    rom.write_bytes(raw)
    prefix = tmp / 'probe'
    cmd = [str(exe), '--plugin-dir', str(plugindir), '--case', 'rom', '--rom', str(rom),
           '--game', 'rd_game_probe', '--probe', '--steps', '20', '--out', str(prefix)]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert res.returncode == 0, (res.stdout, res.stderr)
    assert 'HARNESS_PROBE_INCOMPLETE' in res.stdout, res.stdout
    report = json.loads((tmp / 'probe.report.json').read_text())
    assert report['source_sha256'] == hashlib.sha256(raw).hexdigest()
    assert report['probe_mode'] and report['blocked_unsupported_opcode']
    assert report['blocked_pc'] == 5 and report['blocked_opcode'] == 0xf3, report
    assert report['fallback_steps'] == 2 and report['native_steps'] == 0, report
    events = tmp / 'probe.events.jsonl'
    parsed = [json.loads(line) for line in events.read_text().splitlines()]
    assert [x['event'] for x in parsed] == ['FALLBACK_DISCOVERED', 'FALLBACK_DISCOVERED', 'EXECUTION_BLOCKED'], parsed
    out = tmp / 'sidecar.sqlite'
    summary = convert(rom, events, out, tmp / 'probe.report.json')
    assert summary['candidate_start_bytes'] == 3 and summary['review_tasks'] == 3, summary
    assert not summary['main_catalogue_mutated'] and not summary['qualified_translation']
    with closing(sqlite3.connect(out)) as db:
        assert db.execute('select count(*) from discovery_sources').fetchone()[0] == 1
        assert db.execute('select count(*) from discovery_regions').fetchone()[0] == 3
        assert db.execute('select count(*) from discovery_tasks').fetchone()[0] == 3
        assert db.execute('select count(*) from discovery_regions where status="RUNTIME_OBSERVED_UNVERIFIED"').fetchone()[0] == 3
    try: convert(rom, events, out)
    except ValueError as err: assert 'Refusing' in str(err), str(err)
    else: raise AssertionError('sidecar overwrite was permitted')
    forged = tmp / 'forged.jsonl'
    fake = [dict(e) for e in parsed]
    fake[0]['opcode'] ^= 1
    forged.write_text('\n'.join(json.dumps(x) for x in fake)+'\n')
    try: convert(rom, forged, tmp / 'forged.sqlite')
    except ValueError as err: assert 'mismatch' in str(err), str(err)
    else: raise AssertionError('forged source bytes accepted')
    assert not (tmp / 'forged.sqlite').exists()
    fake = [dict(e) for e in parsed]
    fake[1]['physical'] = 0x4002
    forged.write_text('\n'.join(json.dumps(x) for x in fake)+'\n')
    try: convert(rom, forged, tmp / 'forged-bank.sqlite')
    except ValueError as err: assert 'identity' in str(err), str(err)
    else: raise AssertionError('forged bank mapping accepted')
    changed = tmp / 'changed.sms'
    altered = bytearray(raw)
    altered[0x4000] = 0x99
    changed.write_bytes(altered)
    try: convert(changed, events, tmp / 'mismatched.sqlite', tmp / 'probe.report.json')
    except ValueError as err: assert 'identity' in str(err), str(err)
    else: raise AssertionError('wrong ROM image accepted')
    # Probe restrictions cannot be bypassed with an ordinary translated game module.
    bad = subprocess.run([str(exe), '--plugin-dir', str(plugindir), '--case', 'rom',
                          '--rom', str(rom), '--probe', '--game', 'rd_game_fixture'],
                         capture_output=True, text=True, timeout=15)
    assert bad.returncode != 0 and 'PROBE_REQUIRES' in bad.stderr, bad.stderr
    # A synthetic export cannot masquerade as a real owner Ghidra export in strict mode.
    sample = root / 'examples/recomp-pcode'
    try: generate(sample / 'synthetic.sms', sample / 'function-export.json', [],
                  tmp / 'synthetic-pretending-ghidra.cpp', require_ghidra=True)
    except ValueError as err: assert 'Ghidra' in str(err), str(err)
    else: raise AssertionError('fake real export accepted')
    assert not (tmp / 'synthetic-pretending-ghidra.cpp').exists()
    # Existing generated native P-code path is independently importable using real ROM bytes.
    # The events are source-checked rather than considered verified translations.
    production = root / 'examples/recomp-pcode/synthetic.sms'
    p = tmp / 'generated-pcode'
    gen = subprocess.run([str(exe), '--plugin-dir', str(plugindir), '--case', 'rom',
                          '--rom', str(production), '--game', 'rd_game_recomp_v0445',
                          '--validate', '--out', str(p)], capture_output=True, text=True, timeout=30)
    assert gen.returncode == 0, (gen.stdout, gen.stderr)
    summary2 = convert(production, tmp / 'generated-pcode.events.jsonl', tmp / 'native-sidecar.sqlite',
                       tmp / 'generated-pcode.report.json')
    assert summary2['events'] >= 10 and summary2['candidate_start_bytes'] >= 8, summary2
    print('REAL_ROM_PROBE_SOURCE_BOUND_SIDECAR_AND_NATIVE_EVENTS_PASS')
