"""Import *observations*, not verified functions, into a NEW v0.4.0.45 schema SQLite sidecar.

Never writes to the main RecompDev catalogue. Synthetic fixture only in v0.1.
Run: python tools/import_discovery.py --events build/reports/main.events.jsonl --output build/reports/discovery-sidecar.sqlite
"""
import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent/'legacy'/'RecompDev-v0.4.0.45'))
from discovery import store


def fixture():
    rom=bytearray(0xc000)
    for off,b in (
        (0,b'\x3e\x90\xd3\x7f\x3e\x01\x32\xff\xff\xc3\x00\x80'),
        (0x4000,b'\x3e\x2a\x32\x00\xc0\x3e\x02\x32\xff\xff'),
        (0x8000,b'\x3e\x99\x76'),
        (0x800a,b'\xdb\xdc\x76'),
    ):
        rom[off:off+len(b)]=b
    return bytes(rom)


def convert(events_path, out):
    # Always new file: no accidental import into the user's existing catalogue.
    if out.exists():raise ValueError(f'Output already exists; refusing to modify: {out}')
    if not events_path.is_file():raise FileNotFoundError(events_path)
    data=fixture()
    source_id=hashlib.sha256(data).hexdigest()
    validated=[]
    for line in events_path.read_text(encoding='utf-8').splitlines():
        x=json.loads(line)
        if x.get('event') not in {'FALLBACK_DISCOVERED','NATIVE_EXECUTED','BANK_SWITCH'}:
            raise ValueError('Unknown event type')
        addr=x.get('physical')
        if not isinstance(addr,int) or not 0<=addr<len(data):
            raise ValueError('Physical address outside fixture')
        if x.get('opcode')!=data[addr]:
            raise ValueError('Opcode/source mismatch at physical '+hex(addr))
        if not isinstance(x.get('pc'),int) or not 0<=x['pc']<=0xffff:
            raise ValueError('Invalid guest program counter')
        if not isinstance(x.get('step'),int) or x['step']<1:
            raise ValueError('Invalid sequence number')
        validated.append(x)
    if not validated:raise ValueError('Empty event log')
    out.parent.mkdir(parents=True,exist_ok=True)
    con=store.connect(out)
    try:
        store.store_source(con,source_id,'synthetic-fixture-generated-in-memory',len(data),
            'SHA256_COMPLETE','mastersystem','Harness synthetic fixture','harness-poc-runtime-v0.1')
        regions=set();tasks=set()
        for x in validated:
            if x['event']=='BANK_SWITCH':continue
            addr=x['physical'];kind=x['event']
            # Length=1 only: execution event doesn't prove the instruction span or semantics.
            key=(addr,kind)
            if key not in regions:
                store.region(con,source_id,addr,1,'CODE_CANDIDATE','RUNTIME_OBSERVED_UNVERIFIED',
                    {'harness':'poc-v0.1','pc':x['pc'],'bank_context':x['bank'],
                     'kind':kind,'source_opcode':x['opcode'],'claim_length_only':1})
                regions.add(key)
            if kind=='FALLBACK_DISCOVERED' and addr not in tasks:
                store.task(con,source_id,'investigate_runtime_fallback',subject=f'physical={addr:08x}',
                           priority=80,version='harness-poc-v0.1')
                tasks.add(addr)
        result={'source_sha256':source_id,'source_size':len(data),'events':len(validated),
                'candidate_start_bytes':len(regions),'review_tasks':len(tasks),
                'catalogue_schema':'RecompDev 0.4.0.45 discovery/store.py',
                'main_catalogue_mutated':False,'qualified_translation':False}
        print(json.dumps(result,sort_keys=True))
    finally:
        con.close()
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--events',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    try:convert(args.events,args.output)
    except Exception as e:
        print(f'DISCOVERY_SIDECAR_REJECTED: {e}',file=sys.stderr)
        sys.exit(2)
