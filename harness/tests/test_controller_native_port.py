"""Compiled-controller acceptance of existing v0445 P-code DLL runtime and
source-mapped Z80/SMS discovery. No Python execution by controller itself."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

exe=Path(sys.argv[1]).resolve(strict=True)
plugin_dir=Path(sys.argv[2]).resolve(strict=True)
rom=Path(sys.argv[3]).resolve(strict=True)

def run(*args,ok=True):
    p=subprocess.run([str(exe),*map(str,args)],capture_output=True,text=True,timeout=40)
    if ok:assert p.returncode==0,(p.stdout,p.stderr)
    else:assert p.returncode!=0,(p.stdout,p.stderr)
    return p

with tempfile.TemporaryDirectory(prefix='RecompDev native port ') as td:
    root=Path(td)
    out=root/'game'
    p=run('--stage','native-execute','--rom',rom,'--game','rd_game_recomp_v0445',
          '--plugin-dir',plugin_dir,'--steps','3','--out',out)
    report=json.loads((root/'game.report.json').read_text())
    assert report['native_steps']==3,report
    assert report['fallback_steps']==0,report
    assert report['source_sha256']==hashlib.sha256(rom.read_bytes()).hexdigest(),report
    assert 'HARNESS_POC_PASS native=3 fallback=0' in p.stdout,p.stdout
    assert (root/'game.events.jsonl').is_file()
    assert (root/'game.ppm').is_file()
    assert (root/'game.wav').is_file()
    # Production runtime layout differs from CMake: controller in runtime/,
    # all attached modules in runtime/active/.
    installed=root/'runtime';installed.mkdir()
    shutil.copy2(exe,installed/exe.name)
    active=installed/'active';active.mkdir()
    for name in ('rd_machine_sms','rd_cpu_z80','rd_game_recomp_v0445',
                 'rd_discovery_jsonl','rd_display_ppm','rd_audio_wav','rd_input_fixed',
                 'rd_sms_native_runtime','rd_video_sms_mode4'):
        options=[p for p in plugin_dir.glob(name+'.*') if p.suffix in ('.dll','.so','.dylib')]
        assert len(options)==1,(name,options)
        shutil.copy2(options[0],active/options[0].name)
    installed_run=subprocess.run([str(installed/exe.name),'--stage','native-execute',
       '--rom',str(rom),'--game','rd_game_recomp_v0445','--steps','2',
       '--out',str(root/'deployed')],capture_output=True,text=True,timeout=40)
    assert installed_run.returncode==0,(installed_run.stdout,installed_run.stderr)
    assert json.loads((root/'deployed.report.json').read_text())['native_steps']==2

    # Wrong source cannot reuse an otherwise legitimate P-code game DLL.
    corrupt=root/'changed.sms';data=bytearray(rom.read_bytes());data[42]^=0x01;corrupt.write_bytes(data)
    bad=run('--stage','native-execute','--rom',corrupt,'--game','rd_game_recomp_v0445',
            '--plugin-dir',plugin_dir,'--steps','2','--out',root/'bad',ok=False)
    assert 'ROM_SHA256_MISMATCH' in bad.stderr,bad.stderr
    missing=run('--stage','native-execute','--rom',rom,'--game','../escape',
                '--plugin-dir',plugin_dir,'--out',root/'escape',ok=False)
    assert 'INVALID_GAME_PLUGIN_NAME' in missing.stderr,missing.stderr
    # Reproduce the observed generic DI/IM 1/A=6/MMU write/banked-call
    # source pattern without packaging a copyrighted commercial ROM.
    fixture=bytearray(0x20000)
    fixture[:3]=bytes.fromhex('c38500')
    fixture[0x85:0x99]=bytes.fromhex('f3 31 fe df ed 56 3e 06 32 ff ff cd 68 8a 21 01 c0 11 02 c0 76')
    fixture[0x18a68:0x18a6b]=bytes.fromhex('3e 09 c9')
    fixture[0x7ff0:0x7ff8]=b'TMR SEGA'
    image=root/'banked.sms';image.write_bytes(fixture)
    out=root/'banked';run('--stage','discover','--rom',image,'--plugin-dir',plugin_dir,
                          '--out',out,'--budget','250')
    doc=json.loads((out/'native-discovery.json').read_text())
    assert doc['source_length_verified_candidates']>=10,doc
    blocks={b['pc']:b for b in doc['blocks']}
    assert blocks[0x89]['length']==2,blocks[0x89] # ED 56: IM 1
    assert blocks[0x90]['length']==3,blocks[0x90] # CALL 8A68
    assert blocks[0x8a68]['physical']==0x18a68,blocks[0x8a68]
    assert doc['source_fully_attested'] is True
    assert doc['translation_attempted'] is False
    # When A is not provably constant, no bank context may be invented.
    fixture[0x8b:0x8d]=bytes.fromhex('3a 00') # replace sequence with LD A,(nn) (3 bytes)
    # Make a dedicated correct-length layout for the unknown-source bank test.
    fixture[0x8b:0x99]=bytes.fromhex('3a 00 c0 32 ff ff cd 68 8a 21 01 c0 76 00')
    unknown=root/'unknown.sms';unknown.write_bytes(fixture)
    out=root/'unknown';run('--stage','discover','--rom',unknown,'--plugin-dir',plugin_dir,'--out',out)
    doc=json.loads((out/'native-discovery.json').read_text())
    assert not any(b['pc']==0x8a68 and b['physical']==0x18a68 for b in doc['blocks']),doc
    assert any(g['reason']=='BANK_CONTEXT_UNRESOLVED' for g in doc['gaps']),doc
print('PASS native controller executes authenticated preserved P-code game, source guard, Z80/SMS banked flow')
