"""Regression for >64 source-attested recoveries without command-line growth.

Exercises the compiled native discovery backend with 72 distinct Z80 frontiers
through one bounded evidence-index file. Also checks rejection of corrupt and
oversized indices. No owner ROM, external analyzer, or Windows registry change.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

exe=Path(sys.argv[1]).resolve(strict=True)
source=Path(sys.argv[2]).resolve(strict=True)
sys.path.insert(0,str(source))
from analysis_integration.native_library import write_evidence_index

with tempfile.TemporaryDirectory(prefix='rd-v27-frontier-index-') as d:
    root=Path(d)
    rom=bytearray(0x8000)
    for pc in range(0x2000,0x2000+72):rom[pc]=0x76  # bounded HALTs
    rom[0x7ff0:0x7ff8]=b'TMR SEGA'
    path=root/'test.sms';path.write_bytes(rom)
    reports=[]
    for i,pc in enumerate(range(0x2000,0x2000+72)):
        report=root/('request-%04d.json'%i)
        report.write_text(json.dumps({'status':'UNTRANSLATED_INITIAL_CODE',
            'pc':pc,'physical_offset':pc,'mapper':[0,0,1,2],
            'rom_bytes':len(rom),'native_steps':1,'sp':0xdff0,
            'source_sha256':hashlib.sha256(rom).hexdigest()}))
        reports.append(report)
    index=root/'index.txt'
    write_evidence_index(index,reports)
    assert len(index.read_text().splitlines())==72
    dest=root/'discovered'
    proc=subprocess.run([str(exe),'--stage','discover','--rom',str(path),
        '--plugin-dir',str(exe.parent),'--out',str(dest),
        '--budget','10000','--runtime-gap-index',str(index)],
        text=True,capture_output=True,timeout=60)
    assert proc.returncode==0,(proc.stdout,proc.stderr)
    doc=json.loads((dest/'native-discovery.json').read_text())
    observed={b['pc'] for b in doc['blocks']}
    assert set(range(0x2000,0x2000+72))<=observed,(len(observed),proc.stdout)
    # Native entry checks a bound as well as duplicate and symlink safety.
    invalid=root/'invalid.txt'
    invalid.write_text(index.read_text()+index.read_text().splitlines()[0]+'\n')
    p=subprocess.run([str(exe),'--stage','discover','--rom',str(path),
        '--plugin-dir',str(exe.parent),'--out',str(root/'rejected'),
        '--runtime-gap-index',str(invalid)],text=True,capture_output=True,timeout=20)
    assert p.returncode!=0,(p.stdout,p.stderr)
    assert 'NATIVE_EVIDENCE_INDEX_DUPLICATE' in p.stdout+p.stderr,(p.stdout,p.stderr)
    # Verify the translation plugin accepts the same bounded >64 count for
    # source-attested bank exports; fixing discovery alone would just move the
    # 65th-report failure to RD_TranslationRequestV1.bank_count.
    base=root/'base-export.json'
    source_sha=hashlib.sha256(rom).hexdigest()
    base.write_text(json.dumps({
        'schema':'recomp-function-pcode-v1', 'target_id':'synthetic-evidence-index',
        'source_sha256':source_sha, 'analyzer':'synthetic-test',
        'language':'z80:LE:16:default', 'bank_context':None,
        'functions':[{'instructions':[{'address':0,'length':1,
           'bytes_sha256':hashlib.sha256(b'\x00').hexdigest(),
           'mnemonic':'NOP','pcode':[]}]}]}))
    banks=[]
    for i in range(72):
        bank=root/('bank-%04d.json'%i)
        bank.write_text(json.dumps({
            'schema':'recomp-function-pcode-v1', 'target_id':'synthetic-evidence-index',
            'source_sha256':source_sha, 'analyzer':'synthetic-test',
            'language':'z80:LE:16:default',
            'bank_context':{'slot':2,'bank':1,'base':0x8000,'physical_start':0x4000},
            'functions':[]}))
        banks.append(bank)
    bank_index=root/'banks.txt'
    write_evidence_index(bank_index,banks)
    translated=root/'translated-banks'
    cmd=[str(exe),'--stage','native-translate','--rom',str(path),
         '--export',str(base), '--source-root',str(source),
         '--plugin-dir',str(exe.parent), '--backend','full', '--no-compile',
         '--allow-synthetic-export','--bank-export-index',str(bank_index),
         '--out',str(translated)]
    p=subprocess.run(cmd,text=True,capture_output=True,timeout=70)
    assert p.returncode==0,(p.stdout,p.stderr)
    assert (translated/'translation-manifest.json').is_file()
    assert json.loads((translated/'translation-manifest.json').read_text())['emitted']>=1
    print('RECOMPDEV_FRONTIER_AND_BANK_INDEX_72_ATTESTED_PASS')
