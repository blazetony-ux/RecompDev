"""Normalize a locally captured EXTERNAL emulator JSONL trace for RecompDev.

An external trace line must be a JSON object, e.g.:
{"type":"event","step":15,"pc":205,"kind":"VDP_CONTROL_WRITE","address":191,"value":128}
{"type":"checkpoint","step":1000,"pc":120,"af":1234}

This is an interchange format, not an emulator or a guarantee of independence.
Never pass RecompDev pilot-report.json or its candidate event stream as input.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
# Support single-line absolute-path PowerShell invocations from any directory.
import sys
if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nativecore.eventstream import CHUNK_EVENTS,MAX_BYTES,MAX_EVENTS,_valid_event


def import_trace(source,source_sha256,producer,alignment='ordinal',prefix_only=True):
    source=Path(source)
    if not source.is_file() or source.stat().st_size>768*1024:
        raise ValueError('External JSONL trace missing or exceeds 768 KiB')
    if not re.fullmatch('[0-9a-fA-F]{64}',source_sha256):
        raise ValueError('ROM source identity must be a SHA-256 hex string')
    if not isinstance(producer,str) or not producer.strip() or len(producer)>250:
        raise ValueError('Name the independently operated reference tool and version')
    if alignment not in ('ordinal','step'):raise ValueError('Invalid alignment')
    events=[];checkpoints=[];last_step=-1
    raw=source.read_bytes()
    for lineno,line in enumerate(raw.splitlines(),1):
        if not line.strip():continue
        try:item=json.loads(line)
        except (ValueError,TypeError) as exc:raise ValueError(f'Invalid JSONL line {lineno}') from exc
        if not isinstance(item,dict):raise ValueError(f'Non-object line {lineno}')
        if item.get('type')=='event':
            event={k:v for k,v in item.items() if k in ('step','pc','kind','address','value')}
            if set(event)!={'step','pc','kind','address','value'}:
                raise ValueError(f'Incomplete external event line {lineno}')
            if type(event['step'])!=int or event['step']<last_step:
                raise ValueError(f'Non-monotonic external event step at line {lineno}')
            if not isinstance(event['kind'],str) or not re.fullmatch('[A-Z][A-Z0-9_]{1,39}',event['kind']):
                raise ValueError(f'Invalid event kind at line {lineno}')
            if any(type(event[k])!=int or not 0<=event[k]<=65535 for k in ('pc','address','value')):
                raise ValueError(f'Invalid event registers at line {lineno}')
            last_step=event['step'];events.append(event)
            if len(events)>4096:raise ValueError('More than 4096 reference events; split into bounded traces')
        elif item.get('type')=='checkpoint':
            cp={k:v for k,v in item.items() if k in ('step','pc','af','bc','de','hl','sp','mapper','vram_writes','cram_writes','psg_writes','io_writes','frames','irqs','tstates')}
            if type(cp.get('step'))!=int or cp['step']<0 or not any(k in cp for k in ('pc','af','bc','de','hl','sp','mapper')):
                raise ValueError(f'Invalid checkpoint at line {lineno}')
            checkpoints.append(cp)
            if len(checkpoints)>128:raise ValueError('Too many checkpoints')
        else:raise ValueError(f'Unknown JSONL record type at line {lineno}')
    if not events:raise ValueError('External trace must contain at least one hardware event')
    return {'schema':'recomp-independent-event-trace-v1','source_sha256':source_sha256,
            'independent_source':producer,'external_raw_trace_sha256':hashlib.sha256(raw).hexdigest(),
            'alignment':alignment,'prefix_only':prefix_only,'events':events,'checkpoints':checkpoints,
            'provenance_note':'External source and claimed independence are user-supplied, not certified by RecompDev.'}


def import_stream_trace(source,output,source_sha256,producer,alignment='ordinal',prefix_only=True):
    """Import complete or prefix external JSONL into bounded SHA-verified chunks.

    The source is read locally and never synthesized from native candidate logs.
    RecompDev cannot attest that the stated producer actually generated it.
    """
    source=Path(source).resolve();output=Path(output).resolve()
    if source==output or output.exists() or not source.is_file() or source.stat().st_size>MAX_BYTES:
        raise ValueError('Input missing/too large, or output already exists')
    if not re.fullmatch('[0-9a-fA-F]{64}',source_sha256):raise ValueError('Invalid ROM source SHA-256')
    if not isinstance(producer,str) or not producer.strip() or len(producer)>250:
        raise ValueError('An external producer and version are required')
    if alignment not in ('ordinal','step'):raise ValueError('Invalid alignment')
    if type(prefix_only)!=bool:raise ValueError('Explicit prefix_only required')
    from nativecore.eventstream import _read_chunk,MAX_CHUNKS
    import shutil
    root=output.parent
    if not root.is_dir():raise ValueError('Output directory must exist')
    if list(root.glob('hardware-events-*.jsonl')):
        raise ValueError('Destination already contains an event stream; use a dedicated reference directory')
    chunks=[];buffer=[];cp=[];last=-1;total=0;total_bytes=0
    created=[];raw_hash=hashlib.sha256()
    try:
        with open(source,'rb') as f:
            for lineno,line in enumerate(f,1):
                raw_hash.update(line)
                if not line.strip():continue
                try:item=json.loads(line)
                except (ValueError,TypeError) as e:raise ValueError('Invalid JSONL at line '+str(lineno)) from e
                if not isinstance(item,dict):raise ValueError('Non-object external record')
                if item.get('type')=='event':
                    ev=_valid_event(item)
                    if ev['step']<last:raise ValueError('Nonmonotonic external event steps')
                    last=ev['step'];buffer.append(ev);total+=1
                    if total>MAX_EVENTS:raise ValueError('Too many external events')
                    if len(buffer)==CHUNK_EVENTS:
                        name=f'hardware-events-{len(chunks):06d}.jsonl'
                        dest=root/name
                        with open(dest,'xb') as out:
                            out.write((''.join(json.dumps(x,separators=(',',':'))+'\n' for x in buffer)).encode('utf-8'))
                        created.append(dest)
                        records,digest,nbytes=_read_chunk(dest)
                        total_bytes+=nbytes
                        chunks.append({'name':name,'events':len(records),'size_bytes':nbytes,'sha256':digest})
                        buffer=[]
                elif item.get('type')=='checkpoint':
                    checkpoint={k:v for k,v in item.items() if k in ('step','pc','af','bc','de','hl','sp','mapper','vram_writes','cram_writes','psg_writes','io_writes','frames','irqs','tstates')}
                    if type(checkpoint.get('step'))!=int or checkpoint['step']<0:raise ValueError('Invalid checkpoint')
                    cp.append(checkpoint)
                    if len(cp)>128:raise ValueError('Too many checkpoints')
                else:raise ValueError('Unknown record type')
        if not total:raise ValueError('External reference contains no events')
        if buffer:
            name=f'hardware-events-{len(chunks):06d}.jsonl'
            dest=root/name
            with open(dest,'xb') as out:
                out.write((''.join(json.dumps(x,separators=(',',':'))+'\n' for x in buffer)).encode('utf-8'))
            created.append(dest)
            records,digest,nbytes=_read_chunk(dest)
            total_bytes+=nbytes
            chunks.append({'name':name,'events':len(records),'size_bytes':nbytes,'sha256':digest})
        if total_bytes>MAX_BYTES or len(chunks)>MAX_CHUNKS:raise ValueError('Bounded external chunk storage exceeded')
        ref={'schema':'recomp-independent-stream-reference-v1',
             'source_sha256':source_sha256.lower(),'independent_source':producer,
             'external_raw_trace_sha256':raw_hash.hexdigest(),
             'alignment':alignment,'prefix_only':prefix_only,'checkpoints':cp,
             'event_stream_manifest':{'schema':'recomp-event-stream-manifest-v1',
                 'status':'COMPLETE','count':total,'bytes':total_bytes,'chunks':chunks},
             'provenance_note':'Producer independence and captured hardware behaviour are user claims, not authenticated by RecompDev.'}
        with open(output,'x',encoding='utf-8') as out:json.dump(ref,out,indent=2);out.write('\n')
        return ref
    except BaseException:
        for path in created:path.unlink(missing_ok=True)
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True,help='Raw JSONL captured by an external emulator/tool, not by the native pilot')
    p.add_argument('--source-sha256',required=True,help='SHA-256 of locally owned source ROM')
    p.add_argument('--producer',required=True,help='Specific independently operated CPU/VDP reference and version')
    p.add_argument('--alignment',choices=('ordinal','step'),default='ordinal')
    p.add_argument('--complete',action='store_true',help='This reference is the entire emitted event stream, not a prefix')
    p.add_argument('--stream',action='store_true',help='Import up to 500K events in SHA-verified JSONL chunks; output to an empty dedicated directory')
    p.add_argument('--output',required=True,help='New independent reference JSON')
    a=p.parse_args()
    output=Path(a.output)
    if output.exists():p.error('Refusing to overwrite an existing reference')
    if a.stream:
        reference=import_stream_trace(a.input,output,a.source_sha256,a.producer,a.alignment,not a.complete)
        count=reference['event_stream_manifest']['count']
    else:
        reference=import_trace(a.input,a.source_sha256,a.producer,a.alignment,not a.complete)
        output.write_text(json.dumps(reference,indent=2)+'\n',encoding='utf-8')
        count=len(reference['events'])
    print('Imported',count,'external events and',len(reference['checkpoints']),'CPU checkpoints')
    print('External raw trace SHA-256:',reference['external_raw_trace_sha256'])
    print('Independence and completeness must be established by the owner, not inferred from this import.')

if __name__=='__main__':main()
