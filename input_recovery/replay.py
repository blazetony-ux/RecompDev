"""Untrusted host evidence -> bounded source-owned guest-cycle input replay.

Exact guest-cycle captures are authoritative as to the sampled logical input;
old wall-clock observations are explicitly ESTIMATED and require validation.
No CPU, console, ROM title or pixel assumptions are encoded here.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import zipfile

HEADER='RECOMP_INPUT_CYCLES_V1'
MAX_BYTES=1048576

def sha256(data:bytes)->str:return hashlib.sha256(data).hexdigest()

def validate_replay(path:Path)->dict:
    path=Path(path)
    data=path.read_bytes()
    if not data or len(data)>MAX_BYTES:raise ValueError('Invalid guest-cycle replay length')
    try:lines=data.decode('ascii').splitlines()
    except UnicodeDecodeError:raise ValueError('Input replay requires ASCII CSV') from None
    if not lines or lines[0]!=HEADER:raise ValueError('UNSUPPORTED_INPUT_REPLAY_SCHEMA')
    events=[];last=-1
    for line in lines[1:]:
        if not line:continue
        parts=line.split(',')
        if len(parts)!=3 or any(not re.fullmatch(r'[0-9]{1,19}',p) for p in parts):
            raise ValueError('INVALID_INPUT_REPLAY_ROW')
        cycle,port,buttons=map(int,parts)
        if cycle<last or cycle>1000000000 or port>15 or buttons>18446744073709551615:
            raise ValueError('INPUT_REPLAY_OUT_OF_RANGE')
        events.append((cycle,port,buttons));last=cycle
        if len(events)>10000:raise ValueError('INPUT_REPLAY_EVENT_LIMIT')
    if not events or not any(b!=0 for _,_,b in events):
        raise ValueError('No non-neutral input transitions in replay')
    return {'events':len(events),'last_guest_cycle':last,'sha256':sha256(data),
            'active_events':sum(1 for _,_,b in events if b!=0)}

def _safe_read(z:zipfile.ZipFile,relative:str)->bytes|None:
    try:info=z.getinfo('evidence/'+relative)
    except KeyError:return None
    limit=MAX_BYTES if relative.endswith(('.jsonl','.csv')) else 2*MAX_BYTES
    if info.file_size>limit:
        raise ValueError('Evidence member too large: '+relative)
    return z.read(info)

def create_replay(evidence:Path,rom_hash:str,output:Path,*,guest_hz:int|None=None)->dict:
    """Copy a cycle-perfect capture or convert legacy wall-clock events.

    Never extract source paths from the ZIP. Verify the original run ROM hash.
    """
    evidence=Path(evidence)
    if not evidence.is_file() or evidence.stat().st_size>512*1024*1024:
        raise ValueError('Missing or oversized evidence ZIP')
    output=Path(output)
    if output.exists():raise FileExistsError('Replay already exists; refusing to overwrite')
    with zipfile.ZipFile(evidence) as z:
        if len(z.namelist())>10000:raise ValueError('Evidence archive member limit exceeded')
        # Upload manifests cover every bundled diagnostic file; reject
        # tampering with the few members trusted by this workflow.
        try:
            manifest_info=z.getinfo('bundle-manifest.json')
            if manifest_info.file_size>MAX_BYTES:raise ValueError('Oversized evidence manifest')
            manifest=json.loads(z.read(manifest_info))
            for member in ('runtime-host-report.json','native-stdout.log','guest-input-cycles.csv','input-events.jsonl'):
                name='evidence/'+member
                entries=[x for x in manifest.get('files',[]) if x.get('path')==name]
                if name in z.namelist():
                    if len(entries)!=1 or sha256(_safe_read(z,member))!=entries[0].get('sha256'):
                        raise ValueError('Evidence manifest checksum mismatch: '+member)
        except KeyError:
            raise ValueError('Evidence ZIP lacks a verified bundle manifest') from None
        report_raw=_safe_read(z,'runtime-host-report.json')
        if not report_raw:raise ValueError('Not a generic native-runtime evidence ZIP')
        report=json.loads(report_raw)
        if report.get('source_rom_sha256')!=rom_hash:
            raise ValueError('ROM_IDENTITY_MISMATCH: previous input belongs to another ROM')
        exact=_safe_read(z,'guest-input-cycles.csv')
        if exact:
            method='GUEST_CYCLES_EXACT'
            # Validation requires a real, non-neutral transition.
            output.parent.mkdir(parents=True,exist_ok=True)
            output.write_bytes(exact)
        else:
            raw=_safe_read(z,'input-events.jsonl')
            if not raw:raise ValueError('Evidence lacks input transitions')
            if not guest_hz or not 1<=guest_hz<=1000000000:
                raise ValueError('Legacy millisecond captures require explicit --guest-hz')
            last_ms=-1;events=[(0,0,0)]
            for line in raw.splitlines():
                if not line:continue
                item=json.loads(line)
                elapsed=item.get('elapsed_ms');buttons=item.get('buttons')
                if type(elapsed)!=int or not 0<=elapsed<=600000 or elapsed<last_ms:
                    raise ValueError('Invalid host elapsed_ms')
                if type(buttons)!=int or not 0<=buttons<=18446744073709551615:
                    raise ValueError('Invalid host button bitmask')
                events.append(((elapsed*guest_hz+500)//1000,0,buttons))
                last_ms=elapsed
                if len(events)>10000:raise ValueError('Input event limit exceeded')
            if not any(x[2] for x in events):raise ValueError('No active button input to replay')
            output.parent.mkdir(parents=True,exist_ok=True)
            output.write_text(HEADER+'\n'+''.join(f'{c},{p},{b}\n' for c,p,b in events),encoding='ascii',newline='\n')
            method='HOST_MILLISECONDS_ESTIMATED'
        result=validate_replay(output)
        result.update(schema='recompdev-input-replay-v0.4.9',method=method,
                      guest_hz=guest_hz if method!='GUEST_CYCLES_EXACT' else None,
                      original_rom_sha256=rom_hash,
                      prior_status=report.get('guest_status'),
                      prior_frames=report.get('frames_observed'),
                      prior_pc=report.get('guest_stop_pc'),
                      prior_physical_offset=report.get('guest_stop_physical_offset'),
                      prior_generated_project=report.get('original_project'),
                      prior_runtime_host=report.get('runtime_host'),
                      exact_replay_guarantee=method=='GUEST_CYCLES_EXACT',
                      original_evidence_sha256=sha256(evidence.read_bytes()))
        # Older reports lack stop PC; read the structured native run if available.
        if result['prior_pc'] is None:
            text=_safe_read(z,'native-stdout.log')
            if text:
                for line in text.splitlines():
                    if line.startswith(b'NATIVE_APP_RESULT='):
                        outcome=json.loads(line.split(b'=',1)[1]);result['prior_pc']=outcome.get('pc')
                        result['prior_physical_offset']=outcome.get('physical_offset')
                        result['prior_guest_cycles']=outcome.get('guest_cycles')
                        break
    return result
