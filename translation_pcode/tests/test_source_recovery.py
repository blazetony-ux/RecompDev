"""Cross-component CPU source lifting from a mapper-banked ROM into a freshly
compiled native executable. All ROM bytes are synthetic, created at test time.
This is NOT a commercial-game parity acceptance test.
"""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

EXE=Path(sys.argv[1]).resolve(strict=True)
PLUGINS=Path(sys.argv[2]).resolve(strict=True)
SOURCE=Path(sys.argv[3]).resolve(strict=True)


def call(*args, success=True, timeout=150):
    p=subprocess.run([str(EXE), *map(str,args)], capture_output=True, text=True, timeout=timeout)
    if success and p.returncode != 0:
        raise AssertionError((p.returncode,p.stdout[-3500:],p.stderr[-3500:]))
    if not success and p.returncode == 0:
        raise AssertionError('Unexpected success: '+p.stdout[-1000:])
    return p

with tempfile.TemporaryDirectory(prefix='rd-native-source-recovery-') as tmp:
    root=Path(tmp)
    data=bytearray(0x20000)
    # Z80 reset -> known RAM stack, IM1, mapper bank 6, banked call.
    data[:3]=bytes.fromhex('c3 85 00')
    data[0x85:0x94]=bytes.fromhex('f3 31 fe df ed 56 3e 06 32 ff ff cd 68 8a 76')
    # Bank 6: ten LDI instructions, then a DJNZ loop, followed by Z80
    # block-output I/O (OUTI) and register output OUT (C),D. Port writes
    # must never invalidate ROM mapper state.
    bank=bytes.fromhex('21 00 c1 11 00 c2 01 0a 00')+bytes.fromhex('ed a0')*10+bytes.fromhex(
        '06 0a 10 fe cd 00 8b 06 03 0e 7f 21 00 c0 ed a3 ed a3 ed a3 ed 51 76')
    data[0x18a68:0x18a68+len(bank)]=bank
    data[0x18b00:0x18b03]=bytes.fromhex('e5 e1 c9')  # source-verifiable subroutine return
    data[0x38]=0x76;data[0x66]=0x76 # explicit end of synthetic IRQ/NMI vectors
    data[0x7ff0:0x7ff8]=b'TMR SEGA'
    rom=root/'fixture.sms';rom.write_bytes(data)
    source_sha=hashlib.sha256(data).hexdigest()
    export=root/'empty-base.json'
    export.write_text(json.dumps({'schema':'recomp-function-pcode-v1','target_id':'mastersystem-test-banked-source',
      'source_sha256':source_sha,'analyzer':'synthetic-empty-base-for-source-recovery-test',
      'language':'z80:LE:16:default','functions':[],'bank_context':None}))
    discovered=root/'discovered'
    call('--stage','discover','--rom',rom,'--plugin-dir',PLUGINS,'--budget','10000','--out',discovered)
    report=json.loads((discovered/'native-discovery.json').read_text())
    assert report['source_sha256']==source_sha
    assert not any(g['reason']=='DISCOVERY_BUDGET_EXHAUSTED' for g in report['gaps']),report['gaps']
    unique={v['physical'] for v in report['blocks']}
    assert all(0x18a68+9+n*2 in unique for n in range(10)),unique
    assert 0x18a68+9+20 in unique,unique   # LD B,0x0A after the ten LDIs
    assert len(report['blocks'])<1500,len(report['blocks'])
    # A forged report must be rejected before source is translated.
    forged=json.loads((discovered/'native-discovery.json').read_text())
    forged['blocks'][0]['source_bytes_sha256']='0'*64
    forged_path=root/'forged-report.json';forged_path.write_text(json.dumps(forged))
    rejected=call('--stage','native-translate','--rom',rom,'--export',export,'--plugin-dir',PLUGINS,
       '--source-root',SOURCE,'--allow-synthetic-export','--backend','full','--no-compile',
       '--discovery-report',forged_path,'--out',root/'forged-output',success=False)
    assert 'DISCOVERY_INSTRUCTION_SOURCE_HASH_MISMATCH' in rejected.stderr,rejected.stderr
    result=root/'fresh-native'
    call('--stage','native-translate','--rom',rom,'--export',export,'--plugin-dir',PLUGINS,
         '--source-root',SOURCE,'--allow-synthetic-export','--backend','full','--discover-source',
         '--out',result,timeout=240)
    manifest=json.loads((result/'translation-manifest.json').read_text())
    assert manifest['source_sha256']==source_sha,manifest
    assert manifest['source_decoder_recovered']>=19 and manifest['rejected']==0,manifest
    candidates=[result/'build'/'RecompDevNativePilot',result/'build'/'Release'/'RecompDevNativePilot.exe']
    pilot=next((p for p in candidates if p.is_file()),None)
    assert pilot,candidates
    proc=subprocess.run([str(pilot),str(rom),'100'],capture_output=True,text=True,timeout=30)
    assert proc.returncode==0,(proc.stdout,proc.stderr)
    assert 'PILOT_RESULT=' in proc.stdout,proc.stdout
    observed=json.loads(proc.stdout.split('PILOT_RESULT=',1)[1].splitlines()[0])
    # Synthetic compile+execute proves CPU-owned recovered instructions become
    # native code; no assertion of Shinobi or other game's frame parity.
    assert observed['native_steps']>=34,observed
    assert observed['io_writes']>=4,observed
    assert observed['physical_offset']>=0x18a68,observed
print('PASS synthetic banked Z80 source discovery -> native CPU codegen -> translated C++ compile -> native pilot execution; forged report refused')
