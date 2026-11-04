#!/usr/bin/env python3
"""Source-attested launcher for the experimental generated continuous native app.

Owner supplies the original ROM; it is never copied, published, or embedded.
This is not CPU/hardware/gameplay parity qualification.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

def sha256(path):
    digest=hashlib.sha256()
    with open(path,'rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()

def run(project,rom,source_sha256,output,frames=120,steps=2000000,window=False,input_events=None,
        mode=None,video_backend=None,audio_backend=None,input_backend=None,snapshot_every=0):
    if mode not in (None,'HEADLESS_AUTONOMOUS'):raise ValueError('Invalid host mode')
    if mode and window:raise ValueError('HEADLESS_AUTONOMOUS cannot open a window')
    if mode:
        video_backend=video_backend or 'null'
        audio_backend=audio_backend or 'null'
        input_backend=input_backend or ('replay' if input_events is not None else 'neutral')
    else:
        video_backend=video_backend or ('window' if window else 'capture')
        audio_backend=audio_backend or ('speaker' if window else 'capture')
        input_backend=input_backend or ('live' if window else ('replay' if input_events is not None else 'neutral'))
    if video_backend not in ('null','capture','window') or audio_backend not in ('null','capture','speaker') or input_backend not in ('neutral','replay','live'):
        raise ValueError('Invalid presentation/input backend')
    if (window and video_backend!='window') or (input_backend=='live' and video_backend!='window'):
        raise ValueError('Live input/window backend mismatch')
    if (input_events is None)!=(input_backend!='replay'):
        raise ValueError('Replay input requires --input-events and input=replay')
    if mode and (video_backend=='window' or audio_backend=='speaker' or input_backend=='live'):
        raise ValueError('Autonomous mode cannot require physical devices')
    project=Path(project).resolve(strict=True)
    rom=Path(rom).resolve(strict=True)
    output=Path(output).resolve()
    if not project.is_dir() or not rom.is_file() or rom.stat().st_size>64*1024*1024:
        raise ValueError('Invalid original-ROM or generated-project path')
    if not re.fullmatch('[a-fA-F0-9]{64}',source_sha256):raise ValueError('Invalid expected source SHA256')
    generation=project/'generation.json'
    if not generation.is_file() or generation.stat().st_size>1048576:
        raise ValueError('Missing bounded generated-code provenance')
    provenance=json.loads(generation.read_text(encoding='utf-8'))
    real_sha=sha256(rom)
    if real_sha.lower()!=source_sha256.lower() or provenance.get('original_source_sha256','').lower()!=real_sha.lower():
        raise ValueError('ROM source differs from verified generated-code provenance')
    if type(snapshot_every)!=int or not 0<=snapshot_every<=600:raise ValueError('Invalid bounded framebuffer snapshot cadence')
    if snapshot_every and video_backend=='null':raise ValueError('Snapshot capture requires video backend')
    if not 1<=frames<=36000 or not 1<=steps<=20000000:
        raise ValueError('Invalid bounded frame or instruction count')
    executable=next((candidate for candidate in (
        project/'build'/'Release'/'RecompDevNativeApp.exe',project/'build'/'RecompDevNativeApp.exe',
        project/'build'/'RecompDevNativeApp') if candidate.is_file()),None)
    if not executable:raise ValueError('Compiled RecompDevNativeApp missing; build generated project first')
    output.mkdir(parents=True,exist_ok=True)
    if not output.is_dir() or output.is_symlink():raise ValueError('Invalid output directory')
    inp='-';input_hash=None
    if input_events is not None:
        if input_backend=='live':raise ValueError('Live input and replay are mutually exclusive')
        p=Path(input_events).resolve(strict=True)
        if not p.is_file() or p.stat().st_size>1048576:raise ValueError('Invalid input replay')
        inp=str(p);input_hash=sha256(p)
    prefix=output/'native-frame'
    cmd=[str(executable),str(rom),str(prefix),str(frames),str(steps),inp]
    if mode:cmd+=['--mode',mode]
    if not mode and window:cmd+=['--window']
    # Backend flags supersede legacy defaults and are recorded in evidence.
    cmd+=['--video',video_backend,'--audio',audio_backend,'--input',input_backend]
    if snapshot_every:cmd+=['--snapshot-every',str(snapshot_every)]
    try:proc=subprocess.run(cmd,capture_output=True,text=True,timeout=min(600,max(125,frames//3)),errors='replace')
    except subprocess.TimeoutExpired as error:raise ValueError('Native session exceeded bounded wall time') from error
    (output/'native-run-stdout.log').write_text(proc.stdout[-1048576:],encoding='utf-8')
    (output/'native-run-stderr.log').write_text(proc.stderr[-65536:],encoding='utf-8')
    if proc.returncode:
        code=proc.returncode & 0xffffffff
        classification='HOST_STACK_OVERFLOW' if code==0xc00000fd else 'NATIVE_PROCESS_NONZERO_EXIT'
        raise ValueError(f'{classification}: exit_signed={proc.returncode} exit_hex=0x{code:08X}; stderr={proc.stderr[-900:]}')
    match=re.search(r'^NATIVE_APP_RESULT=(\{.*\})$',proc.stdout,re.M)
    if not match:raise ValueError('Native application returned no structured evidence')
    observed=json.loads(match.group(1))
    if observed.get('native_qualified') is not False or observed.get('hardware_parity')!='NOT_TESTED':
        raise ValueError('Unexpected native application parity assertion')
    if any(observed.get(key)!=value for key,value in (
            ('video_backend',video_backend),('audio_backend',audio_backend),('input_backend',input_backend))):
        raise ValueError('Native host did not honor requested backend selection')
    frame_hardware=observed.get('frame_hardware',[])
    if not isinstance(frame_hardware,list) or len(frame_hardware)>36000 or any(not isinstance(x,dict) for x in frame_hardware):
        raise ValueError('Invalid bounded per-frame hardware history')
    tail=observed.get('trace_tail',[])
    if not isinstance(tail,list) or len(tail)>256 or any(not isinstance(t,dict) for t in tail):
        raise ValueError('Native host returned unbounded or invalid transition history')
    if not isinstance(observed.get('guest_state_fingerprint'),int):
        raise ValueError('Native host did not supply guest state fingerprint')
    if observed.get('discarded_frames') != (observed.get('frames') if video_backend=='null' else 0):
        raise ValueError('Null frame accounting mismatch')
    if observed.get('discarded_audio_samples') != (observed.get('audio_samples') if audio_backend=='null' else 0):
        raise ValueError('Null audio accounting mismatch')
    if type(observed.get('pc'))!=int or not 0<=observed['pc']<=0xffff:
        raise ValueError('Native host did not supply final program counter')
    if (not isinstance(observed.get('mapper'),list) or len(observed['mapper'])!=4 or
            any(type(x)!=int or not 0<=x<=255 for x in observed['mapper'])):
        raise ValueError('Native host did not supply bounded mapper state')
    if sha256(rom)!=real_sha:raise ValueError('ROM changed during execution')
    if input_events is not None and sha256(inp)!=input_hash:raise ValueError('Input replay changed during execution')
    assets={}
    for suffix in ('ppm','wav'):
        file=output/('native-frame.'+suffix)
        if file.is_file():assets[suffix]={'size':file.stat().st_size,'sha256':sha256(file)}
    result={'schema':'recomp-continuous-owner-session-v1','source_sha256':real_sha,
       'generated_code_source_sha256':provenance['original_source_sha256'],
       'executable_sha256':sha256(executable),'input_sha256':input_hash,
       'status':observed['status'],'pc':observed['pc'],'mapper':observed['mapper'],
       'physical_offset':observed.get('physical_offset'),'native_steps':observed['native_steps'],
       'guest_cycles':observed['guest_cycles'],'frames':observed['frames'],
       'frame_hashes':observed['frame_hashes'],'audio_samples':observed['audio_samples'],
       'audio_nonzero_samples':observed.get('audio_nonzero_samples'),
       'snapshots_written':observed.get('snapshots_written'),
       'snapshot_every':observed.get('snapshot_every'),
       'guest_state_fingerprint':observed['guest_state_fingerprint'],
       'trace_tail':observed.get('trace_tail',[]),
       'frame_hardware':frame_hardware,
       'guest_vdp_writes':observed['guest_vdp_writes'],'guest_psg_writes':observed['guest_psg_writes'],
       'cram_writes':observed.get('cram_writes'),'cram_nonzero_bytes':observed.get('cram_nonzero_bytes'),
       'vblank_events':observed.get('vblank_events'),'maskable_interrupts':observed.get('maskable_interrupts'),
       'bank_switches':observed.get('bank_switches'),'nmi_events':observed.get('nmi_events'),
       'timing_qualified_steps':observed.get('timing_qualified_steps'),
       'timing_unqualified_steps':observed.get('timing_unqualified_steps'),
       'vcounter_reads':observed.get('vcounter_reads'),
       'first_vcounter_read_step':observed.get('first_vcounter_read_step'),
       'hcounter_reads':observed.get('hcounter_reads'),
       'discarded_frames':observed['discarded_frames'],'discarded_audio_samples':observed['discarded_audio_samples'],
       'host_mode':mode or 'SELECTABLE','video_backend':video_backend,'audio_backend':audio_backend,'input_backend':input_backend,
       'assets':assets,'reference_parity':'NOT_TESTED','gameplay':'NOT_ESTABLISHED',
       'runtime_scope':'Experimental generated Z80 + Master System bridge; approximate device timing and rendering'}
    (output/'continuous-session.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',required=True);p.add_argument('--rom',required=True)
    p.add_argument('--source-sha256',required=True);p.add_argument('--output-dir',required=True)
    p.add_argument('--frames',type=int,default=120);p.add_argument('--steps',type=int,default=2000000)
    p.add_argument('--window',action='store_true');p.add_argument('--input-events')
    p.add_argument('--snapshot-every',type=int,default=0)
    p.add_argument('--mode',choices=['HEADLESS_AUTONOMOUS'])
    p.add_argument('--video',choices=['null','capture','window'])
    p.add_argument('--audio',choices=['null','capture','speaker'])
    p.add_argument('--input',choices=['neutral','replay','live'])
    a=p.parse_args()
    try:print(json.dumps(run(a.project,a.rom,a.source_sha256,a.output_dir,a.frames,a.steps,a.window,a.input_events,a.mode,a.video,a.audio,a.input,a.snapshot_every),indent=2))
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as e:p.error(str(e))
if __name__=='__main__':main()
