"""Normalize *source-attested* Ghidra and Rizin function-boundary candidates.

Independent tool agreement is NOT instruction correctness, verified control flow,
function completeness, or original/native execution parity.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

SCHEMA='recomp-analysis-reconciliation-v1'
MAX_FUNCTIONS=20000
MAX_EXPORT_BYTES=32*1024*1024

def sha256_file(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
    return h.hexdigest()

def load_json(path):
    path=Path(path)
    if not path.is_file() or path.stat().st_size>MAX_EXPORT_BYTES:raise ValueError('Missing/oversized analysis evidence')
    return json.loads(path.read_text(encoding='utf-8'))

def _integer(v,name):
    if type(v) is not int or v<0 or v>=2**64:raise ValueError('Invalid '+name)
    return v

def _within(address,length,base,size):
    return address>=base and length>0 and address+length<=base+size

def parse_rizin(doc,base,size):
    # Rizin aflj reports only boundary/size hypotheses. This schema is NOT the
    # RecompDev Ghidra P-code evidence schema.
    if not isinstance(doc,list) or len(doc)>MAX_FUNCTIONS:raise ValueError('Invalid Rizin aflj list')
    funcs={};warnings=[]
    for obj in doc:
        if not isinstance(obj,dict):raise ValueError('Invalid Rizin function object')
        address=_integer(obj.get('offset'),'Rizin offset')
        length=_integer(obj.get('size'),'Rizin size')
        if not _within(address,length,base,size):
            warnings.append({'entry':address,'reason':'OUTSIDE_INPUT_MAP'});continue
        if address in funcs:
            warnings.append({'entry':address,'reason':'DUPLICATE_ENTRY'});continue
        funcs[address]={'entry':address,'length':length,'name':str(obj.get('name',''))[:128],
                        'claim':'RIZIN_FUNCTION_BOUNDARY_HYPOTHESIS','verified_instruction_bytes':0}
    return funcs,warnings

def parse_ghidra(doc,sha,source_bytes,base):
    if not isinstance(doc,dict) or doc.get('schema')!='recomp-function-pcode-v1':
        raise ValueError('Unexpected Ghidra export schema')
    if doc.get('source_sha256','').lower()!=sha:raise ValueError('Ghidra source identity mismatch')
    if not isinstance(doc.get('functions'),list) or len(doc['functions'])>MAX_FUNCTIONS:
        raise ValueError('Ghidra functions missing or over limit')
    funcs={};warnings=[]
    for obj in doc['functions']:
        if not isinstance(obj,dict):raise ValueError('Invalid Ghidra function object')
        entry=_integer(obj.get('entry'),'Ghidra entry')
        low=_integer(obj.get('body_min'),'Ghidra body_min')
        high=_integer(obj.get('body_max'),'Ghidra body_max')
        if not (base<=low<=entry<=high<base+len(source_bytes)):
            warnings.append({'entry':entry,'reason':'OUTSIDE_INPUT_MAP'});continue
        instructions=obj.get('instructions')
        if not isinstance(instructions,list) or not instructions or len(instructions)>10000:
            warnings.append({'entry':entry,'reason':'INCOMPLETE_INSTRUCTION_EXPORT'});continue
        verified=0;locations=set()
        for ins in instructions:
            if not isinstance(ins,dict):raise ValueError('Malformed Ghidra instruction')
            addr=_integer(ins.get('address'),'instruction address')
            length=_integer(ins.get('length'),'instruction length')
            if not _within(addr,length,base,len(source_bytes)) or addr<low or addr+length-1>high:
                raise ValueError('Ghidra instruction is outside attested source mapping')
            expected=ins.get('bytes_sha256')
            if (not isinstance(expected,str) or len(expected)!=64 or
                expected.lower()!=hashlib.sha256(source_bytes[addr-base:addr-base+length]).hexdigest()):
                raise ValueError('Ghidra instruction byte hash mismatch')
            if any(i in locations for i in range(addr,addr+length)):
                raise ValueError('Overlapping Ghidra instructions')
            locations.update(range(addr,addr+length));verified+=1
        if entry in funcs:
            warnings.append({'entry':entry,'reason':'DUPLICATE_ENTRY'});continue
        funcs[entry]={'entry':entry,'length':high-low+1,'name':str(obj.get('name',''))[:128],
                      'body_min':low,'body_max':high,'verified_instruction_bytes':verified,
                      'claim':'GHIDRA_BYTE_ATTESTED_INSTRUCTIONS_BOUNDARY_HYPOTHESIS'}
    return funcs,warnings

def reconcile(source,base,isa,ghidra=None,rizin=None):
    source=Path(source).resolve(strict=True)
    if not source.is_file() or source.stat().st_size>32*1024*1024:raise ValueError('Invalid/oversized source')
    source_bytes=source.read_bytes();sha=hashlib.sha256(source_bytes).hexdigest()
    if base<0 or base>=2**63:raise ValueError('Invalid address map')
    if isa not in ('z80','m68k','mips'):raise ValueError('Unsupported ISA')
    gh=None;rz=None;warnings=[]
    if ghidra is not None:
        gh,w=parse_ghidra(load_json(ghidra),sha,source_bytes,base)
        warnings.extend({'engine':'ghidra',**x} for x in w)
    if rizin is not None:
        rz,w=parse_rizin(load_json(rizin),base,len(source_bytes))
        warnings.extend({'engine':'rizin',**x} for x in w)
    if gh is None and rz is None:raise ValueError('No analyzer evidence supplied')
    items=[];counts={}
    for addr in sorted(set(gh or {}) | set(rz or {})):
        a=(gh or {}).get(addr);b=(rz or {}).get(addr)
        if a and b:
            # Rizin size and Ghidra body size need not be identical: high-level
            # function bodies can be discontiguous. Agreement on entry only.
            status='AGREED_ENTRY_DIFFERENT_EXTENT' if a['length']!=b['length'] else 'AGREED_ENTRY_AND_EXTENT'
        else:status='GHIDRA_ONLY' if a else 'RIZIN_ONLY'
        counts[status]=counts.get(status,0)+1
        items.append({'entry':addr,'status':status,'ghidra':a,'rizin':b,
                      'native_qualified':False,'boundary_complete':False})
    return {'schema':SCHEMA,'source_sha256':sha,'source_size':len(source_bytes),
            'isa':isa,'base':base,'analysis_engines':[x for x,v in [('ghidra',gh),('rizin',rz)] if v is not None],
            'stats':counts,'candidates':items,'warnings':warnings,
            'verification':{'source_identity':'SHA256_VERIFIED','ghidra_instruction_bytes':
                'SHA256_CHECKED_WHERE_EXPORTED' if gh is not None else 'NOT_AVAILABLE',
                'rizin_instruction_bytes':'NOT_PROVIDED','native_parity':'NOT_TESTED',
                'function_completeness':'NOT_ESTABLISHED'}}
