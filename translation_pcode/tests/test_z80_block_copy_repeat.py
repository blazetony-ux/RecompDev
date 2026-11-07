"""Generic ED B0/B8 Z80 block-repeat source-lifting, runtime and timing regression.

Compiles a full native application and executes the emitted code through the
independent SMS state/video/host DLL path. No game identity or game offsets.
"""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

exe = Path(sys.argv[1]).resolve(strict=True)
plugins = Path(sys.argv[2]).resolve(strict=True)
source_root = Path(sys.argv[3]).resolve(strict=True)

with tempfile.TemporaryDirectory(prefix='rd-z80-block-copy-repeat-') as tmp:
    root = Path(tmp)
    for code, backward in ((0xb0, False), (0xb8, True)):
        name = 'lddr' if backward else 'ldir'
        rom = bytearray(0x8000)
        rom[0x7ff0:0x7ff8] = b'TMR SEGA'
        rom[0:3] = bytes.fromhex('c3 00 53')  # JP 5300
        rom[0x38] = rom[0x66] = 0x76
        # LD BC,3; LD HL,source; LD DE,destination; LDIR/LDDR; HALT
        hl = 0x5372 if backward else 0x5370
        de = 0xc102 if backward else 0xc100
        rom[0x5300:0x530c] = bytes([0x01, 0x03, 0x00, 0x21, hl & 255, hl >> 8,
                                   0x11, de & 255, de >> 8, 0xed, code, 0x76])
        rom[0x5370:0x5373] = b'ABC'
        path = root / (name + '.sms')
        path.write_bytes(rom)
        doc = {'schema': 'recomp-function-pcode-v1', 'target_id': 'z80-copy-repeat-' + name,
               'source_sha256': hashlib.sha256(rom).hexdigest(),
               'analyzer': 'synthetic-generic-codegen-test', 'language': 'z80:LE:16:default',
               'bank_context': None, 'functions': [{'instructions': []}]}
        export = root / (name + '-export.json')
        export.write_text(json.dumps(doc))
        out = root / (name + '-native')
        translate = subprocess.run([str(exe), '--stage', 'native-translate',
            '--rom', str(path), '--export', str(export), '--allow-synthetic-export',
            '--source-root', str(source_root), '--plugin-dir', str(plugins),
            '--discover-source', '--backend', 'full', '--out', str(out)],
            capture_output=True, text=True, timeout=110)
        assert translate.returncode == 0, (name, translate.stdout[-3000:], translate.stderr[-3000:])
        manifest = json.loads((out / 'translation-manifest.json').read_text())
        assert manifest['rejected'] == 0, (name, manifest['rejections'])
        assert 0x5309 in {p['physical'] for p in manifest['accepted_instructions']}, (name, manifest['source_decoder_recovered'])
        generated = '\n'.join(p.read_text() for p in [out / 'translated.cpp', *out.glob('native_part_*.cpp')])
        assert 'if(rd_bc!=0u)next=s.pc;' in generated, (name, 'repeat not lowered')
        pilot = next((p for p in (out / 'build' / 'Release' / 'RecompDevNativePilot.exe',
                                   out / 'build' / 'RecompDevNativePilot') if p.is_file()), None)
        assert pilot, (name, 'pilot compilation missing')
        run = subprocess.run([str(pilot), str(path), '7', '', '', '0xC100,0xC101,0xC102'],
            capture_output=True, text=True, timeout=20)
        assert run.returncode == 0, (name, run.stdout[-2000:], run.stderr[-2000:])
        result_line = next(x.removeprefix('PILOT_RESULT=') for x in run.stdout.splitlines()
                           if x.startswith('PILOT_RESULT='))
        result = json.loads(result_line)
        expected_hl = 0x536f if backward else 0x5373
        expected_de = 0xc0ff if backward else 0xc103
        assert result['status'] == 'STEP_BUDGET_REACHED', (name, result['status'])
        assert result['native_steps'] == 7, (name, result['native_steps'])
        assert result['pc'] == 0x530b, (name, result['pc'])
        assert result['bc'] == 0 and result['hl'] == expected_hl and result['de'] == expected_de, (name, result['bc'], result['hl'], result['de'])
        assert result['ram_writes'] == 3, (name, result['ram_writes'])
        assert [r['value'] for r in result['watched_memory']] == [65, 66, 67], (name, result['watched_memory'])
        assert result['last_pcs'][-3:] == [0x5309] * 3, (name, result['last_pcs'])
        # JP 10 + three 16-bit loads 10 each + two repeat cycles of 21 + one exit of 16 = 98.
        assert result['tstates'] == 98 and result['timing_qualified_steps'] == 7, (name, result['tstates'], result['timing_qualified_steps'])
    print('PASS ED B0 LDIR / ED B8 LDDR: source-attested native emission, compiled DLL app, 3-byte copy and 21/16T timing')
