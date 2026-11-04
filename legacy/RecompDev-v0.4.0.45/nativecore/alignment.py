"""Versioned provenance-bearing instruction anchors, never auto-skip mismatches.

A frame number or a shared PC is not enough to align two executions. For raw
binary test programs physical offsets are verified directly. Banked cartridge
observations must supply an authenticated physical mapping before comparison.
"""
import hashlib
import json
from pathlib import Path

SCHEMA='recomp-execution-anchor-v1'
REGISTERS={'z80':('af','bc','de','hl','sp'), 'm68k':tuple(f'd{i}' for i in range(8))}

def make_anchor(source,isa,origin,physical_offset,pc,registers,bank=None,step=None,bytes_count=2):
    raw=Path(source).read_bytes()
    if len(raw)>32*1024*1024 or not raw:raise ValueError('Invalid source bytes')
    if isa not in REGISTERS:raise ValueError('Unsupported ISA')
    if origin not in ('raw','cartridge','bios'):raise ValueError('Unknown code origin')
    if type(physical_offset)!=int or not 0<=physical_offset<len(raw):raise ValueError('Unknown physical mapping')
    if not type(bytes_count)==int or not 1<=bytes_count<=8 or physical_offset+bytes_count>len(raw):
        raise ValueError('Instruction bytes outside authenticated source')
    if type(pc)!=int or not 0<=pc<=0xffffffff:raise ValueError('Invalid logical PC')
    if origin=='cartridge' and (type(bank)!=int or not 0<=bank<=65535):
        raise ValueError('Cartridge bank identity required')
    if origin=='raw' and bank is not None:raise ValueError('Raw source must not invent cartridge bank')
    if not isinstance(registers,dict) or any(type(registers.get(r)) is not int for r in REGISTERS[isa]):
        raise ValueError('Incomplete register evidence')
    if step is not None and (type(step)!=int or step<0):raise ValueError('Invalid step')
    return {'schema':SCHEMA,'source_sha256':hashlib.sha256(raw).hexdigest(),
            'isa':isa,'origin':origin,'bank':bank,'physical_offset':physical_offset,
            'pc':pc,'instruction_hex':raw[physical_offset:physical_offset+bytes_count].hex(),
            'registers':{r:registers[r] for r in REGISTERS[isa]},'step':step,
            'mapping_attestation':'OWNER_SOURCE_BYTES_ONLY'}

def validate_anchor(anchor,source):
    if not isinstance(anchor,dict) or anchor.get('schema')!=SCHEMA:raise ValueError('Invalid anchor schema')
    raw=Path(source).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=anchor.get('source_sha256'):raise ValueError('Anchor original source hash changed')
    h=anchor.get('instruction_hex')
    if not isinstance(h,str) or not h or len(h)%2 or len(h)>16:raise ValueError('Invalid anchor bytes')
    try:bytecode=bytes.fromhex(h)
    except ValueError as exc:raise ValueError('Nonhex anchor bytes') from exc
    off=anchor.get('physical_offset')
    if type(off)!=int or off<0 or raw[off:off+len(bytecode)]!=bytecode:
        raise ValueError('Anchor instruction byte mismatch')
    if anchor.get('origin')=='cartridge' and type(anchor.get('bank'))!=int:
        raise ValueError('Bank mapping missing')
    if anchor.get('isa') not in REGISTERS:raise ValueError('Unsupported anchor ISA')
    if any(type(anchor.get('registers',{}).get(k))!=int for k in REGISTERS[anchor['isa']]):
        raise ValueError('Incomplete anchor register state')
    return True

def compare_anchors(reference,native,source):
    """Requires *explicit* owner-supplied anchors; no substring search/skip.

    Matching bytes + source hash is evidence of shared instruction identity, not
    of shared CPU state, timing, ROM-to-bus mapping, or device state.
    """
    validate_anchor(reference,source);validate_anchor(native,source)
    identity=('source_sha256','isa','origin','bank','physical_offset','pc','instruction_hex')
    different=[k for k in identity if reference.get(k)!=native.get(k)]
    result={'schema':'recomp-anchor-alignment-v1','identity_fields':list(identity),
       'different_identity_fields':different,'step_aligned':False,'frame_aligned':False,
       'hardware_aligned':False,'native_qualified':False,'automatic_repair':False}
    if different:
        result.update(status='UNALIGNED_EXECUTION_IDENTITY',cpu_state='NOT_COMPARED')
        return result
    differing_registers={k:{'reference':v,'native':native['registers'][k]}
                          for k,v in reference['registers'].items() if native['registers'][k]!=v}
    result['different_registers']=differing_registers
    result['cpu_state']='MATCHED_SELECTED_REGISTERS' if not differing_registers else 'DIVERGED_SELECTED_REGISTERS'
    result['status']='MATCHED_CODE_IDENTITY_WITH_SELECTED_REGISTERS' if not differing_registers else 'DIVERGED_AT_COMMON_CODE_IDENTITY'
    return result
