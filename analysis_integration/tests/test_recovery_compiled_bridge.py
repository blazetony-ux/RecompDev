"""Actual compiled controller accepts verified opt-in previous bank/stop evidence.

Uses a source-distinct synthetic ROM. It does not claim game parity, nor
execute a historical runtime or reuse a prior native binary.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

EXE=Path(sys.argv[1]).resolve(strict=True)
PLUGINS=Path(sys.argv[2]).resolve(strict=True)
SOURCE=Path(sys.argv[3]).resolve(strict=True)
sha=lambda data:hashlib.sha256(data).hexdigest()

with tempfile.TemporaryDirectory(prefix='recompdev-compiled-replay-') as td:
    root=Path(td)
    data=bytearray(0x8000)
    data[0]=0x76
    data[1]=0x76
    data[0x7ff0:0x7ff8]=b'TMR SEGA'
    rom=root/'synthetic.sms';rom.write_bytes(data)
    digest=sha(data)
    def instruction(at):
        return {'address':at,'length':1,'bytes_sha256':sha(data[at:at+1]),
                'mnemonic':'HALT',
                'pcode':[{'op':'CALLOTHER','inputs':[{'space':'const','offset':9,'size':1}]}]}
    base={'schema':'recomp-function-pcode-v1','analyzer':'ghidra-raw-pcode',
          'target_id':'mastersystem-'+digest[:12], 'source_sha256':digest,
          'language':'z80:LE:16:default',
          'functions':[{'entry':0,'body_min':0,'body_max':0,'instructions':[instruction(0)]}]}
    base_file=root/'base.json';base_file.write_text(json.dumps(base))
    previous=root/'previous';previous.mkdir()
    focused=previous/'round-01-ghidra-recovery';focused.mkdir()
    stop={'schema':'recompdev.native.app.stop.v1','status':'UNTRANSLATED_INITIAL_CODE',
          'pc':1,'physical_offset':1,'sp':0xd000,'native_steps':100,
          'mapper':[0,0,1,2], 'rom_bytes':len(data),'source_sha256':digest}
    seed=previous/'round-01-observed-stop.json';seed.write_text(json.dumps(stop))
    overlay=dict(base)
    overlay['bank_context']={'slot':0,'bank':0,'base':0,'physical_start':0}
    overlay['functions']=[{'entry':1,'body_min':1,'body_max':1,'instructions':[instruction(1)]}]
    (focused/'source-verified-bank-functions.json').write_text(json.dumps(overlay))
    (focused/'recovery-audit.json').write_text(json.dumps({
        'observed_pc':1,'observed_physical':1,'observed_mapper':stop['mapper'],
        'source_sha256':digest}))
    (previous/'orchestration.json').write_text(json.dumps({
        'schema':'recompdev.native.orchestrator.v1','source_sha256':digest,
        'rounds':[{'round':1,'recovery_seed':str(seed),
                   'ghidra_focused_region':{'backend':'ghidra-headless'}}]}))
    out=root/'fresh'
    command=[str(EXE),'--stage','native-orchestrate','--rom',str(rom),'--out',str(out),
             '--plugin-dir',str(PLUGINS),'--export',str(base_file),
             '--resume-from',str(previous),'--no-compile','--no-execute',
             '--max-rounds','1','--target-frames','10','--timeout','35']
    result=subprocess.run(command,env={**os.environ,'RECOMPDEV_SOURCE_ROOT':str(SOURCE)},
                          capture_output=True,text=True,timeout=100)
    assert result.returncode==0,(result.stdout[-1000:],result.stderr[-1000:])
    report=json.loads((out/'orchestration.json').read_text())
    assert report['status']=='TRANSLATED_NOT_EXECUTED',report
    assert report['recovery_history']['imported_stops']==1,report
    assert report['recovery_history']['imported_bank_exports']==1,report
    assert report['rounds'][0]['runtime_gap_seeds']==1,report
    assert report['rounds'][0]['focused_ghidra_bank_exports']==1,report
    assert report['rounds'][0]['emitted']>0,report
    assert (out/'imported-history/history-import.json').is_file()
print('PASS: compiled controller consumed reverified stop+Ghidra bank overlay via --resume-from')
