"""Bounded, SHA-attested ordered JSONL streams for candidate and external reference.

Stream provenance describes the producer; it never authenticates independence.
Files are local, under an explicitly supplied root. Each chunk is hashed and
fully parsed before a positive comparison result is permitted.
"""
import hashlib
import json
import re
from pathlib import Path

CHUNK_EVENTS = 1024
MAX_EVENTS = 500000
MAX_BYTES = 64 * 1024 * 1024
MAX_CHUNKS = (MAX_EVENTS + CHUNK_EVENTS - 1) // CHUNK_EVENTS
NAME = re.compile(r'hardware-events-\d{6}\.jsonl\Z')
HEX = re.compile('[0-9a-f]{64}\\Z')

def _valid_event(event):
    if not isinstance(event, dict) or any(k not in event for k in ('step', 'pc', 'kind', 'address', 'value')):
        raise ValueError('Incomplete stream event')
    if type(event['step']) is not int or event['step'] < 0:
        raise ValueError('Invalid stream event step')
    if not isinstance(event['kind'], str) or not re.fullmatch('[A-Z][A-Z0-9_]{1,39}', event['kind']):
        raise ValueError('Invalid stream event kind')
    for key in ('pc', 'address', 'value'):
        if type(event[key]) is not int or not 0 <= event[key] <= 65535:
            raise ValueError('Invalid stream event '+key)
    return {key:event[key] for key in ('step','pc','kind','address','value')}

def _read_chunk(path, expected_sha=None):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 1024*1024:
        raise ValueError('Event stream chunk missing, symlinked or oversized')
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha is not None and digest != expected_sha:
        raise ValueError('Event stream chunk hash mismatch: '+path.name)
    events = []
    for line in raw.splitlines():
        if not line:raise ValueError('Empty event stream record')
        try:events.append(_valid_event(json.loads(line)))
        except (TypeError, ValueError, KeyError) as e:raise ValueError('Invalid event stream record: '+path.name) from e
    if not events or len(events)>CHUNK_EVENTS:
        raise ValueError('Invalid event stream chunk count')
    return events, digest, len(raw)

def manifest_for_native(directory, trace, basename='hardware-events'):
    """Inspect every generated chunk and reject partial/inconsistent output."""
    root=Path(directory).resolve()
    files=sorted(root.glob(basename+'-*.jsonl'))
    declared=trace.get('event_stream_chunks')
    count=trace.get('event_stream_events')
    if type(declared) is not int or type(count) is not int or not 0<=declared<=MAX_CHUNKS or not 0<=count<=MAX_EVENTS:
        raise ValueError('Invalid native event stream counters')
    if len(files)!=declared or trace.get('event_stream_complete') is not True or count!=trace.get('events_total'):
        raise ValueError('Native event stream incomplete or missing chunks')
    preview=trace.get('events',[])
    if not isinstance(preview,list) or len(preview)>4096:
        raise ValueError('Invalid runtime inline event preview')
    chunks=[];previous=-1;total=0;size=0
    for i,path in enumerate(files):
        if path.name!=f'{basename}-{i:06d}.jsonl':raise ValueError('Noncontiguous event chunks')
        events,digest,nbytes=_read_chunk(path)
        for ev in events:
            if ev['step']<previous:raise ValueError('Nonmonotonic event stream steps')
            if total<len(preview) and _valid_event(preview[total])!=ev:
                raise ValueError('Inline event preview differs from full stream')
            previous=ev['step'];total+=1
        size+=nbytes
        chunks.append({'name':path.name,'events':len(events),'size_bytes':nbytes,'sha256':digest})
    if total!=count or size!=trace.get('event_stream_bytes') or size>MAX_BYTES:
        raise ValueError('Native event stream byte/event counts differ')
    return {'schema':'recomp-event-stream-manifest-v1','status':'COMPLETE',
            'count':count,'bytes':size,'chunks':chunks,
            'scope':'Candidate observations, not an independent emulator oracle'}

def iter_verified(root, manifest):
    """Stream from a local root, rehash every chunk, validate total and order.
    No absolute paths, traversal, implicit file discovery, or symlinks allowed.
    """
    root=Path(root).resolve()
    if not isinstance(manifest,dict) or manifest.get('schema')!='recomp-event-stream-manifest-v1' or manifest.get('status')!='COMPLETE':
        raise ValueError('Invalid/incomplete event stream manifest')
    chunks=manifest.get('chunks');expected=manifest.get('count')
    if not isinstance(chunks,list) or len(chunks)>MAX_CHUNKS or type(expected)!=int or not 0<=expected<=MAX_EVENTS:
        raise ValueError('Invalid event chunk manifest bounds')
    found=0;bytes_read=0;previous=-1
    for i,entry in enumerate(chunks):
        if not isinstance(entry,dict):raise ValueError('Invalid chunk entry')
        name=entry.get('name')
        if not isinstance(name,str) or not NAME.fullmatch(name):raise ValueError('Unsafe chunk filename')
        if name!=f'hardware-events-{i:06d}.jsonl':
            raise ValueError('Noncontiguous chunk manifest')
        digest=entry.get('sha256')
        if not isinstance(digest,str) or not HEX.fullmatch(digest):raise ValueError('Missing event chunk SHA-256')
        events,_,size=_read_chunk(root/name,digest)
        if len(events)!=entry.get('events') or size!=entry.get('size_bytes'):
            raise ValueError('Event stream chunk metadata mismatch')
        bytes_read+=size
        if bytes_read>MAX_BYTES:raise ValueError('Event stream exceeds bounded total bytes')
        for event in events:
            if event['step']<previous:raise ValueError('Nonmonotonic event stream')
            previous=event['step'];found+=1;yield event
    if found!=expected or bytes_read!=manifest.get('bytes'):
        raise ValueError('Event stream final count mismatch')
