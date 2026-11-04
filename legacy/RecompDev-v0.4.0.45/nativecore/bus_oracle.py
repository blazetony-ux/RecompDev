"""Narrow Master System externally observed I/O effects; never gameplay parity.

MAME Lua can observe raw PSG and VDP-control port writes without decoding VDP
internals. The candidate runtime emits these same logical effects. Compare
exact kind/8-bit-port/value ordering, not uncertain MAME callback PC/step timing.
"""
import json
from pathlib import Path
from nativecore.eventstream import iter_verified
from nativecore.frame_oracle import sha256

SCHEMA='recomp-mame-sms-selected-io-v1'
SELECTED=('VDP_CONTROL_WRITE','PSG_WRITE')

def import_bus(path, source_sha256, producer):
    path=Path(path)
    if not path.is_file() or path.is_symlink() or path.stat().st_size>24*1024*1024:
        raise ValueError('MAME I/O evidence missing, symlinked or oversized')
    events=[]
    with path.open('rb') as file:
        for raw in file:
            try:doc=json.loads(raw)
            except (TypeError,ValueError) as exc:raise ValueError('Invalid bus JSONL record') from exc
            if not isinstance(doc,dict) or doc.get('type')!='bus' or doc.get('ordinal')!=len(events)+1:
                raise ValueError('Non-contiguous external bus ordinals')
            if set(doc)!=set(('type','ordinal','kind','address','value','pc')):
                raise ValueError('Unexpected bus record shape')
            if doc['kind'] not in SELECTED or any(type(doc[k])!=int or not 0<=doc[k]<=65535 for k in ('address','value','pc')):
                raise ValueError('Invalid selected MAME bus operation')
            if not 0<=doc['address']<=255 or not 0<=doc['value']<=255:
                raise ValueError('MAME bus is not byte-address/byte-value')
            events.append({k:doc[k] for k in ('kind','address','value','pc')})
            if len(events)>200000:raise ValueError('Too many MAME bus writes')
    return {'schema':SCHEMA,'source_sha256':source_sha256,'independent_source':producer,
            'events':len(events),'raw_sha256':sha256(path),'selected_kinds':list(SELECTED),
            'status':'CAPTURED_SELECTED_IO_NOT_PARITY_VERIFIED',
            'scope':'PSG + VDP control-port writes only; no VDP data-port/VRAM/CRAM, mapper, IRQ, video frame or PC equivalence.'}

def compare_bus(reference, bus_file, candidate, native_stream_root, context=4):
    if reference.get('schema')!=SCHEMA or reference.get('selected_kinds')!=list(SELECTED):
        raise ValueError('Invalid external MAME bus provenance')
    if candidate.get('source_id')!=reference.get('source_sha256'):
        raise ValueError('Original ROM SHA-256 differs from MAME reference')
    if sha256(bus_file)!=reference.get('raw_sha256'):raise ValueError('External MAME raw trace SHA-256 mismatch')
    validated=import_bus(bus_file,reference['source_sha256'],reference['independent_source']) # full validation
    if any(reference.get(field)!=validated[field] for field in ('schema','events','raw_sha256','source_sha256','independent_source','selected_kinds')):
        raise ValueError('Selected I/O reference metadata mismatch')
    raw=[json.loads(line) for line in Path(bus_file).read_text(encoding='utf-8').splitlines()]
    trace=candidate.get('trace') or candidate
    if trace.get('event_stream_manifest',{}).get('status')!='COMPLETE':
        raise ValueError('Native full event stream is required')
    if trace.get('event_stream_manifest',{}).get('count') != trace.get('events_total'):
        raise ValueError('Candidate runtime count and chunk manifest disagree')
    native=[{k:x[k] for k in ('kind','address','value','pc')} for x in
            iter_verified(native_stream_root,trace['event_stream_manifest']) if x['kind'] in SELECTED]
    if len(native)>200000:raise ValueError('Excessive selected native bus operations')
    first=None;matched=0
    for i in range(min(len(raw),len(native))):
        e=raw[i];got=native[i]
        if any(e[k]!=got[k] for k in ('kind','address','value')):
            first={'bus_index':i,'reference':{k:e[k] for k in ('kind','address','value','pc')},
                   'native':got,'preceding':[], 'following':[]}
            for j in range(max(0,i-context),i):
                first['preceding'].append({'index':j,'reference':raw[j],'native':native[j]})
            for j in range(i+1,min(len(raw),len(native),i+1+context)):
                first['following'].append({'index':j,'reference':raw[j],'native':native[j]})
            break
        matched+=1
    if first is not None:status='SELECTED_IO_DIVERGED'
    elif len(native)<len(raw):status='INSUFFICIENT_NATIVE_IO_COVERAGE'
    elif not raw:status='NO_COMPARABLE_IO_EVENTS'
    else:status='MATCHED_SELECTED_IO_PREFIX'
    return {'schema':'recomp-mame-sms-bus-comparison-v1','status':status,
            'source_sha256':reference['source_sha256'],'independent_source':reference['independent_source'],
            'selected_kinds':list(SELECTED), 'reference_writes':len(raw),'native_writes':len(native),
            'matching_prefix_writes':matched,'first_divergence':first,
            'pc_aligned':False,'step_aligned':False,'frame_aligned':False,
            'scope':'Strict ordinal ordering for selected PSG/VDP-control I/O effects only. No automatic skipped events of those kinds; all other event types intentionally excluded. Does not establish instruction/frame/game parity.',
            'automatic_repair':False,'native_qualified':False}
