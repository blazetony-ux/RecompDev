"""Validate independently captured emulator *frame observations*.

Frame PC/register samples do NOT share native step boundaries. A passing import
must NEVER be promoted to CPU-instruction, event-stream, frame-pixel or gameplay
parity. The frame data are useful for an honest independent execution baseline.
"""
import hashlib
import json
import re
from pathlib import Path

SCHEMA='recomp-external-frame-observations-v1'

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def validate_frames(source,rom_hash,producer,requested_frames):
    source=Path(source)
    if not source.is_file() or source.is_symlink() or source.stat().st_size>256*1024:
        raise ValueError('Frame observation file missing, symlinked or oversized')
    if not isinstance(rom_hash,str) or not re.fullmatch(r'[0-9a-f]{64}',rom_hash):
        raise ValueError('Invalid original ROM hash')
    if not isinstance(producer,str) or not producer or len(producer)>200:
        raise ValueError('Emulator provenance is required')
    if type(requested_frames) is not int or not 1<=requested_frames<=1200:
        raise ValueError('Invalid frame budget')
    entries=[]
    for line in source.read_text(encoding='utf-8').splitlines():
        try:entry=json.loads(line)
        except (TypeError,ValueError) as exc:raise ValueError('Invalid frame JSONL') from exc
        if not isinstance(entry,dict) or entry.get('type')!='frame' or entry.get('ordinal')!=len(entries)+1:
            raise ValueError('Frame observations must be contiguous and ordered')
        if set(entry)-{'type','ordinal','pc','af','bc','de','hl','sp'}:
            raise ValueError('Unknown frame observation field')
        if type(entry.get('pc')) is not int or not 0<=entry['pc']<=0xffff:
            raise ValueError('Missing/invalid observed PC')
        for name in ('af','bc','de','hl','sp'):
            if name in entry and (type(entry[name]) is not int or not 0<=entry[name]<=0xffff):
                raise ValueError('Invalid CPU register '+name)
        entries.append(entry)
        if len(entries)>requested_frames:raise ValueError('Frame observations exceed requested bound')
    if len(entries)!=requested_frames:raise ValueError('Missing frame observations; capture incomplete')
    return {'schema':SCHEMA,'status':'IMPORTED_UNALIGNED_FRAME_OBSERVATIONS',
            'source_sha256':rom_hash,'independent_source':producer,
            'captured_frames':len(entries),'raw_sha256':sha256(source),
            'first_frame':entries[0],'last_frame':entries[-1],
            'observations':entries,
            'parity':'NOT_TESTED',
            'alignment':'frame ordinal only; native pilot samples at instruction steps, not at the same frame boundary',
            'warning':'Unverified owner-run emulator provenance. No CPU-step, ordered I/O, frame-pixel or gameplay parity is established.'}
