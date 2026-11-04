"""Secure source-authenticated headless Ghidra input preparation for MD/PS-X EXE.

Temporary mapped binaries remain *on the owner's PC*, are never distributed,
and are deleted on successful completion. Ghidra evidence is independently checked
against the original owner-local input during conversion.
"""
from __future__ import annotations
import sys
from pathlib import Path as _Path
sys.path.insert(0,str(_Path(__file__).resolve().parents[1]))
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
from adapters.formats import open_image
from native_batch import sha_file

ROOT=Path(__file__).resolve().parents[1]

def export(db,source,target,ghidra,output,timeout=600,keep_workspace=False):
    source=Path(source).resolve();output=Path(output).resolve()
    if not source.is_file():raise ValueError('source file missing')
    if not Path(ghidra).is_file():raise ValueError('Ghidra analyzeHeadless.bat not found: '+str(ghidra))
    con=sqlite3.connect(str(db));con.row_factory=sqlite3.Row
    try:row=con.execute('SELECT * FROM targets WHERE target_id=?',(target,)).fetchone()
    finally:con.close()
    if row is None:raise ValueError('target not registered in catalogue')
    sha=sha_file(source)
    if row['source_sha256']!=sha:raise ValueError('source does not match registered SHA256')
    if row['system_tag'] not in ('megadrive','psx-exe'):
        raise ValueError('no executable extractor for '+row['system_tag'])
    raw=source.read_bytes();img=open_image(raw,row['system_tag'])
    proc={'m68k':'68000:BE:32:default','mips':'MIPS:LE:32:default'}[img.isa]
    base=0 if img.container=='megadrive' else img.start
    mapped=raw if img.container=='megadrive' else raw[0x800:0x800+(img.stop-img.start)]
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='recompdev-ghidra-v031-') as temp:
        scratch=Path(temp); data_file=scratch/'source-mapped.bin';data_file.write_bytes(mapped)
        # On some Ghidra versions raw binary analysis needs additional entry seeds.
        cmd=[str(Path(ghidra)),str(scratch),'RecompDevFunctionRecovery',
             '-import',str(data_file),'-loader','BinaryLoader','-loader-baseAddr',f'0x{base:x}',
             '-processor',proc,'-scriptPath',str(ROOT/'ghidra'),
             '-preScript','SeedRecompEntry.java',f'0x{img.entry:x}',
             '-postScript','ExportFunctionBodies.java',str(output),target,sha,'5000',
             '-readOnly','-analysisTimeoutPerFile','360']
        try:
            result=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout,check=False,errors='replace')
        except subprocess.TimeoutExpired:
            raise ValueError('Ghidra headless analysis timed out')
        (output.with_suffix('.ghidra.log')).write_text((result.stdout+'\n'+result.stderr)[-200000:],encoding='utf-8')
        if result.returncode or not output.is_file():
            raise ValueError('Ghidra failed; check '+str(output.with_suffix('.ghidra.log')))
    d=json.loads(output.read_text(encoding='utf-8'))
    if d.get('source_sha256')!=sha or d.get('target_id')!=target:raise ValueError('Ghidra evidence identity mismatch')
    return {'target_id':target,'sha256':sha,'export':str(output),'function_candidates':len(d.get('functions',[])),
       'statement':'Ghidra boundaries are hypotheses; individual byte hashes are independently checked during conversion.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--source',required=True)
    p.add_argument('--target',required=True);p.add_argument('--ghidra-exe',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(export(a.db,a.source,a.target,a.ghidra_exe,a.output),indent=2))
