#!/usr/bin/env python3
"""Deterministic source-created synthetic SMS ROM + RecompDev Ghidra-format exports.
The example format comes from RecompDev v0.4.0.45 tests/test_native_execution_v0404.py.
This is NOT a real Ghidra analysis or genuine commercial game evidence.
"""
import hashlib,json,sys
from pathlib import Path
out=Path(sys.argv[1] if len(sys.argv)>1 else Path(__file__).resolve().parents[1]/'examples'/'recomp-pcode')
out.mkdir(parents=True,exist_ok=True)
data=bytearray(0x10000)
def put(pc,b):data[pc:pc+len(b)]=bytes(b)
put(0,[0xc3,0x03,0x00]);put(3,[0x3e,0x42]);put(5,[0x32,0x00,0xc0]);put(8,[0x3e,0x03]);put(10,[0x32,0xff,0xff]);put(13,[0xc3,0x00,0x80]);put(0xc000,[0x3e,0x66]);put(0xc002,[0xd3,0x7f]);put(0xc004,[0x32,0x00,0xc0]);put(0xc007,[0x76]);put(0x7ff0,b'TMR SEGA')
rom=out/'synthetic.sms';rom.write_bytes(data)
sha=hashlib.sha256(data).hexdigest()
def var(sp,o,size=1):return {'space':sp,'offset':o,'size':size}
def copy(dst,src):return {'op':'COPY','inputs':[src],'output':dst}
def entry(pc,length,mnemonic,pcode,fallthrough=None,phys=None):
    if phys is None:phys=pc
    return {'address':pc,'length':length,'fallthrough':(pc+length if fallthrough is None else fallthrough),
            'mnemonic':mnemonic,'bytes_sha256':hashlib.sha256(data[phys:phys+length]).hexdigest(),'pcode':pcode}
def jmp(pc,target,phys=None):return entry(pc,3,'JP',[{'op':'BRANCH','inputs':[var('ram',target)]}],None,phys)
def lda(pc,n,phys=None):return entry(pc,2,'LD',[copy(var('register',1),var('const',n))],None,phys)
def storea(pc,addr,phys=None):return entry(pc,3,'LD',[copy(var('ram',addr),var('register',1))],None,phys)
base=[jmp(0,3),lda(3,0x42),storea(5,0xc000),lda(8,3),storea(10,0xffff),jmp(13,0x8000)]
# Intentionally no P-code for OUT/HALT: they must be handled by interpreter fallback.
bank=[lda(0x8000,0x66,0xc000),storea(0x8004,0xc000,0xc004)]
common={'schema':'recomp-function-pcode-v1','language':'z80:LE:16:default','target_id':'synthetic-pcode-v02',
        'source_sha256':sha,'analyzer':'synthetic-pcode-shape-not-ghidra'}
(out/'function-export.json').write_text(json.dumps({**common,'functions':[{'entry':0,'name':'SYNTHETIC_BOOT','instructions':base}]},indent=2)+'\n')
(out/'bank3-export.json').write_text(json.dumps({**common,'bank_context':{'slot':2,'bank':3,'base':0x8000,'physical_start':0xc000},
            'functions':[{'entry':0x8000,'name':'SYNTHETIC_BANK3','instructions':bank}]},indent=2)+'\n')
print('SYNTHETIC_PCODE_SAMPLE sha256='+sha)
