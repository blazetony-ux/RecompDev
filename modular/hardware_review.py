"""RecompDev 0.4.3: system-independent hardware capture review.

This is evidence analysis, NOT an emulation oracle. Captures retain provenance;
reference comparisons are opt-in, frame/cycle alignment is never assumed.
Native game bytes are not loaded. Only v0.4.2 generated capture artifacts
are inspected. Asset-format decoder plugins live in modular/asset_decoders/.
"""
from __future__ import annotations
import csv
import hashlib
import json
import math
import os
import struct
import wave
import zlib
from collections import Counter
from pathlib import Path
from modular.asset_decoders import sms

SCHEMA='recompdev-hardware-review-v0.4.3'
MAX_CAPTURE_BYTES=32*1024*1024


def _hash(data): return hashlib.sha256(data).hexdigest()

def _chunk(tag, data):
    return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data)&0xffffffff)

def write_png(path, width, height, rgb):
    if width<1 or height<1 or width*height>2048*2048 or len(rgb)!=width*height*3: raise ValueError('Invalid RGB image')
    rows=b''.join(b'\0'+rgb[y*width*3:(y+1)*width*3] for y in range(height))
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes(b'\x89PNG\r\n\x1a\n'+_chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+
                  _chunk(b'IDAT',zlib.compress(rows,6))+_chunk(b'IEND',b''))

def read_ppm(path):
    b=Path(path).read_bytes()
    if len(b)>MAX_CAPTURE_BYTES or not b.startswith(b'P6'):raise ValueError('Unsupported PPM format')
    pos=2; tokens=[]
    while len(tokens)<3:
        while pos<len(b) and b[pos] in b' \r\n\t':pos+=1
        if pos<len(b) and b[pos]==35:
            while pos<len(b) and b[pos] not in b'\r\n':pos+=1
            continue
        beg=pos
        while pos<len(b) and b[pos] not in b' \r\n\t':pos+=1
        if beg==pos or pos==len(b):raise ValueError('Truncated PPM header')
        tokens.append(int(b[beg:pos]))
    w,h,maximum=tokens
    if maximum!=255 or w<1 or h<1 or w*h>2048*2048:raise ValueError('Unsupported PPM size/depth')
    # Exactly one whitespace byte separates the last header token and the pixel payload.
    # A CRLF counts as one line ending.
    if b[pos:pos+2]==b'\r\n':pos+=2
    elif b[pos:pos+1] in (b' ',b'\n',b'\r',b'\t'):pos+=1
    else:raise ValueError('Missing PPM raster separator')
    data=b[pos:]
    if len(data)!=w*h*3:raise ValueError('Truncated or oversized PPM raster')
    return w,h,data

def read_png(path):
    """Read common 8-bit noninterlaced RGB/RGBA/gray/indexed PNG references.

    No Pillow/Python packages required on the owner's Windows machine.
    """
    b=Path(path).read_bytes()
    if len(b)>MAX_CAPTURE_BYTES or not b.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Unsupported PNG')
    pos=8; ihdr=None; idat=[]; palette=None; trans=None
    while pos<len(b):
        if pos+12>len(b):raise ValueError('Truncated PNG')
        length=struct.unpack_from('>I',b,pos)[0];tag=b[pos+4:pos+8];end=pos+12+length
        if length>MAX_CAPTURE_BYTES or end>len(b):raise ValueError('Invalid PNG chunk')
        data=b[pos+8:pos+8+length]
        if zlib.crc32(tag+data)&0xffffffff!=struct.unpack_from('>I',b,pos+8+length)[0]:raise ValueError('PNG CRC mismatch')
        if tag==b'IHDR': ihdr=struct.unpack('>IIBBBBB',data)
        elif tag==b'PLTE':palette=data
        elif tag==b'tRNS':trans=data
        elif tag==b'IDAT':idat.append(data)
        elif tag==b'IEND':break
        pos=end
    if not ihdr: raise ValueError('No PNG IHDR')
    w,h,depth,kind,comp,flt,interlace=ihdr
    if depth!=8 or comp!=0 or flt!=0 or interlace!=0 or kind not in (0,2,3,4,6) or w*h>2048*2048 or min(w,h)<1:
        raise ValueError('Unsupported reference PNG profile (requires noninterlaced 8-bit)')
    channels={0:1,2:3,3:1,4:2,6:4}[kind]; stride=w*channels
    decomp=zlib.decompressobj()
    raw=decomp.decompress(b''.join(idat),(stride+1)*h+1)
    if not decomp.eof or decomp.unconsumed_tail:raise ValueError('Oversized or truncated PNG deflate stream')
    if len(raw)!=(stride+1)*h:raise ValueError('Invalid PNG pixels')
    prev=bytearray(stride);pix=bytearray();off=0
    for _ in range(h):
        filt=raw[off];off+=1;row=bytearray(raw[off:off+stride]);off+=stride
        if filt not in range(5):raise ValueError('Unsupported PNG filter')
        for x in range(stride):
            a=row[x-channels] if x>=channels else 0;b0=prev[x];c=prev[x-channels] if x>=channels else 0
            if filt==1:row[x]=(row[x]+a)&255
            elif filt==2:row[x]=(row[x]+b0)&255
            elif filt==3:row[x]=(row[x]+((a+b0)//2))&255
            elif filt==4:
                p=a+b0-c;pa=abs(p-a);pb=abs(p-b0);pc=abs(p-c)
                row[x]=(row[x]+(a if pa<=pb and pa<=pc else b0 if pb<=pc else c))&255
        pix.extend(row);prev=row
    rgb=bytearray()
    for i in range(0,len(pix),channels):
        if kind==2:rgb.extend(pix[i:i+3])
        elif kind==6:
            a=pix[i+3];rgb.extend((pix[i+j]*a+255*(255-a))//255 for j in range(3))
        elif kind in (0,4):
            v=pix[i] if kind==0 else (pix[i]*pix[i+1]+255*(255-pix[i+1]))//255
            rgb.extend((v,v,v))
        else:
            idx=pix[i]
            if not palette or (idx+1)*3>len(palette):raise ValueError('Bad PNG palette')
            a=trans[idx] if trans and idx<len(trans) else 255
            rgb.extend((palette[3*idx+j]*a+255*(255-a))//255 for j in range(3))
    return w,h,bytes(rgb)

def read_image(path):
    p=Path(path)
    if p.suffix.lower()=='.ppm':return read_ppm(p)
    if p.suffix.lower()=='.png':return read_png(p)
    raise ValueError('Reference must be PNG or PPM')

def compare_image(a,b,out):
    aw,ah,ap=read_image(a);bw,bh,bp=read_image(b)
    result={'status':'DIMENSIONS_DIFFER','native_size':[aw,ah],'reference_size':[bw,bh]}
    if (aw,ah)!=(bw,bh):return result
    diff=bytearray(len(ap));n=0;err=0;maxerr=0
    for i in range(0,len(ap),3):
        d=[abs(ap[i+j]-bp[i+j]) for j in range(3)]
        if any(d):n+=1
        err+=sum(d);maxerr=max(maxerr,*d)
        diff[i:i+3]=bytes(d)
    write_png(out,aw,ah,diff)
    return {'status':'PIXEL_EXACT_MATCH' if n==0 else 'PIXEL_DIFFERENCE',
            'native_size':[aw,ah],'reference_size':[bw,bh],
            'pixels_different':n,'total_pixels':aw*ah,
            'fraction_different':round(n/(aw*ah),8),
            'mean_absolute_channel_difference':round(err/len(ap),6),
            'maximum_channel_difference':maxerr,'difference_png':str(out),
            'qualification':'PIXEL_COMPARISON_ONLY_NOT_TIMING_OR_GAMEPLAY_PARITY'}

def wav_diagnostic(path):
    with wave.open(str(path),'rb') as w:
        frames=w.getnframes(); channels=w.getnchannels(); depth=w.getsampwidth(); rate=w.getframerate();compressed=w.getcomptype()
        if channels not in (1,2) or depth not in (1,2,3,4) or compressed!='NONE' or frames>10_000_000:raise ValueError('Unsupported audio capture WAV')
        raw=w.readframes(frames)
    if len(raw)!=frames*channels*depth:raise ValueError('Truncated PCM')
    count=frames*channels;nonzero=0;peak=0;sum_sq=0;first=None
    for i in range(count):
        b=raw[i*depth:(i+1)*depth]
        if depth==1:v=(b[0]-128)*256
        else:v=int.from_bytes(b,'little',signed=True) / (2**(depth*8-16))
        if v:nonzero+=1;first=i//channels if first is None else first
        peak=max(peak,abs(v));sum_sq+=v*v
    return {'status':'SILENT_PCM' if nonzero==0 else 'PCM_ACTIVITY',
            'sample_rate':rate,'channels':channels,'sample_width_bytes':depth,
            'frames':frames,'samples_nonzero':nonzero,'peak_normalized':round(peak/32768,8),
            'rms_normalized':round(math.sqrt(sum_sq/max(count,1))/32768,8),
            'first_active_sample_frame':first,'duration_seconds':round(frames/rate,6) if rate else 0,
            'sha256':_hash(Path(path).read_bytes())}

def _safe_sessions(root):
    base=root/'recovery'
    if not base.exists():return []
    hits=[]
    for f in base.glob('round-*/sessions/attempt-*/frame-*/continuous-session.json'):
        if f.is_symlink() or not f.resolve().is_relative_to(root.resolve()) or f.stat().st_size>8*1024*1024:continue
        hits.append(f)
    return sorted(hits)[:256]

def _int(v): return v if type(v) is int and v>=0 else 0

def _csv_trace(rows,path):
    keys=['frame','guest_cycles','delta_cycles','steps','delta_steps','irqs','delta_irqs','vdp_writes','delta_vdp_writes',
          'psg_writes','delta_psg_writes','cram_writes','delta_cram_writes','palette_nonzero_bytes']
    with path.open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader()
        prev={}
        for src in rows:
            row={k:_int(src.get(k)) for k in keys if not k.startswith('delta_')}
            for k in ('guest_cycles','steps','irqs','vdp_writes','psg_writes','cram_writes'):
                row['delta_'+('cycles' if k=='guest_cycles' else k)]=row[k]-_int(prev.get(k))
            writer.writerow(row);prev=src

def _timing(rows,frame_hashes):
    if not rows:return {'status':'NO_FRAME_TELEMETRY'}
    issues=[];deltas=[];prev=None
    for row in rows:
        if prev:
            delta=_int(row.get('guest_cycles'))-_int(prev.get('guest_cycles'))
            deltas.append(delta)
            if delta<=0:issues.append('NONINCREASING_FRAME_CYCLES')
            for key in ('steps','irqs','vdp_writes','psg_writes','cram_writes'):
                if _int(row.get(key))<_int(prev.get(key)):
                    issues.append('NONMONOTONIC_'+key.upper())
        prev=row
    return {'status':'OBSERVED_NOT_REFERENCE_VALIDATED','frames_with_telemetry':len(rows),
            'first_frame':_int(rows[0].get('frame')),'last_frame':_int(rows[-1].get('frame')),
            'guest_cycles_at_last_frame':_int(rows[-1].get('guest_cycles')),
            'cycles_per_frame_delta_min':min(deltas) if deltas else None,
            'cycles_per_frame_delta_max':max(deltas) if deltas else None,
            'cycles_per_frame_delta_mean':round(sum(deltas)/len(deltas),3) if deltas else None,
            'maskable_interrupts_observed':_int(rows[-1].get('irqs')),
            'vdp_writes_observed':_int(rows[-1].get('vdp_writes')),
            'cram_writes_observed':_int(rows[-1].get('cram_writes')),
            'psg_writes_observed':_int(rows[-1].get('psg_writes')),
            'frame_hashes':len(frame_hashes),'distinct_frame_hashes':len(set(map(str,frame_hashes))),
            'issues':sorted(set(issues)),
            'note':'A VBlank does not imply that one maskable IRQ must be accepted. Interrupt parity requires an independent reference with matched input/timing.'}

def _reference_session_compare(rows,reference_path):
    reference=json.loads(Path(reference_path).read_text(encoding='utf8'))
    comparison=reference.get('frame_hardware') or []
    if not isinstance(comparison,list) or not comparison:return {'status':'REFERENCE_HAS_NO_FRAME_TELEMETRY'}
    native={r.get('frame'):r for r in rows};other={r.get('frame'):r for r in comparison};shared=sorted(set(native)&set(other))
    diffs=[]
    for frame in shared:
        for key in ('guest_cycles','steps','irqs','vdp_writes','psg_writes','cram_writes'):
            a=native[frame].get(key);b=other[frame].get(key)
            if type(a) is int and type(b) is int and a!=b:
                diffs.append({'frame':frame,'field':key,'native':a,'reference':b})
                if len(diffs)==100:break
        if len(diffs)>=100:break
    return {'status':'MATCHED_OBSERVATIONS' if not diffs and shared else 'TELEMETRY_DIFFS',
            'shared_frames':len(shared),'differences_first_100':diffs,
            'reference_sha256':_hash(Path(reference_path).read_bytes()),
            'qualification':'REFERENCE_TIMELINE_ALIGNMENT_AND_INDEPENDENCE_MUST_BE_USER_VERIFIED'}

def analyze_evidence(input_dir, output_dir, reference_image=None, reference_session=None):
    root=Path(input_dir).resolve(strict=True)
    if not root.is_dir():raise ValueError('Evidence input must be a directory')
    out=Path(output_dir).resolve()
    if out.exists():raise FileExistsError('Refusing to overwrite hardware review: '+str(out))
    if out==root:raise ValueError('Review output must be a separate directory')
    out.mkdir(parents=True)
    sessions=_safe_sessions(root)
    report={'schema':SCHEMA,'status':'REVIEW_COMPLETE','source_evidence':str(root),
            'source_evidence_unchanged':True,'sessions_found':len(sessions),
            'capture_images':[],'audio_captures':[],
            'reference_image':{'status':'NOT_PROVIDED'},
            'reference_timing':{'status':'NOT_PROVIDED'},
            'independent_gameplay_parity':'NOT_ESTABLISHED',
            'frame_by_frame_pixel_capture_available':False,
            'asset_recovery':{'status':'NO_SOURCE_BUFFERS'},
            'issues':[]}
    newest=None
    for f in sessions:
        try:
            s=json.loads(f.read_text(encoding='utf8'))
            if type(s.get('frames')) is not int:continue
            rel=f.relative_to(root)
            capture_key='-'.join((rel.parts[1],rel.parts[3],rel.parts[4]))
            ppm=f.with_name('native-frame.ppm')
            wav=f.with_name('native-frame.wav')
            item={'source_session':str(rel),'frames_reported':s.get('frames')}
            if ppm.is_file():
                w,h,pixels=read_ppm(ppm)
                png=out/'screenshots'/(capture_key+'.png')
                write_png(png,w,h,pixels)
                histogram=Counter(tuple(pixels[i:i+3]) for i in range(0,len(pixels),3))
                item.update({'png':str(png.relative_to(out)),'width':w,'height':h,
                             'distinct_rgb_colors':len(histogram),'nonblack_pixels':w*h-histogram.get((0,0,0),0),
                             'source_ppm_sha256':_hash(ppm.read_bytes())})
            if wav.is_file():
                audio=wav_diagnostic(wav)
                report['audio_captures'].append({'session':str(rel),'audio':audio})
            report['capture_images'].append(item)
            newest=(f,s,ppm,item)
        except (OSError,ValueError,KeyError,struct.error) as exc:
            report['issues'].append(f'INVALID_SESSION_CAPTURE {f.relative_to(root)} {type(exc).__name__}: {exc}')
    if newest:
        f,s,ppm,item=newest
        rows=s.get('frame_hardware') or []
        if not isinstance(rows,list): rows=[]
        report['timing']=_timing(rows,s.get('frame_hashes') or [])
        if rows:
            _csv_trace(rows,out/'hardware-timeline.csv')
            report['hardware_timeline_csv']='hardware-timeline.csv'
        psg=_int(s.get('guest_psg_writes'));sample=_int(s.get('audio_nonzero_samples'))
        if psg and not sample:report['issues'].append('PSG_WRITES_BUT_SILENT_PCM: verify PSG register state/muting and capture backend; cause NOT established')
        report['last_session']={'source':str(f.relative_to(root)),'status':s.get('status'),
                                'frames':_int(s.get('frames')),'native_steps':_int(s.get('native_steps')),
                                'psg_writes':psg,'audio_nonzero_samples':sample,'irq_accepted':_int(s.get('maskable_interrupts')),
                                'vblank_events':_int(s.get('vblank_events')),'frame_hashes':len(s.get('frame_hashes') or [])}
        if reference_image:
            try:
                if not ppm.is_file(): raise FileNotFoundError('No native PPM to compare')
                report['reference_image']=compare_image(ppm,reference_image,out/'pixel-difference.png')
                report['reference_image']['reference_sha256']=_hash(Path(reference_image).read_bytes())
            except (OSError,ValueError,struct.error) as exc:
                report['reference_image']={'status':'UNSUPPORTED_OR_MISSING','error':str(exc)}
        if reference_session:
            try:report['reference_timing']=_reference_session_compare(rows,reference_session)
            except (OSError,ValueError) as exc:report['reference_timing']={'status':'UNSUPPORTED_OR_MISSING','error':str(exc)}
    else:
        report['timing']={'status':'NO_SESSION_TELEMETRY'}
    # True VRAM/CRAM are necessary for faithful source tile and palette export.
    # A framebuffer is NOT a lossless substitute for source graphics or sprite metadata.
    report['asset_recovery']=sms.export_if_present(root,out/'assets')
    report['asset_recovery']['extraction_does_not_load_rom']=True
    report['asset_recovery']['full_game_rom_independence']='NOT_ESTABLISHED'
    report['asset_recovery']['note']='Only true captured VRAM/CRAM can produce source tile patterns; screenshots are display observations, not extracted source assets.'
    report['recovery_scope']='Captured terminal-frame PNG(s), WAV PCM diagnostics, per-frame counter CSV, optional image/reference comparisons and tile/palette export when raw VRAM/CRAM is available.'
    (out/'hardware-review.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf8')
    markdown=['# RecompDev hardware review v0.4.3','',
      'Execution hardware observations do not establish independent gameplay correctness.','',
      f'- Source evidence: `{root}`',f'- Captured terminal frames converted: {sum("png" in x for x in report["capture_images"])}',
      f'- WAVs analysed: {len(report["audio_captures"])}',
      f'- Timing observations: {report["timing"].get("status")}',
      f'- Reference pixel comparison: {report["reference_image"]["status"]}',
      f'- Reference timing comparison: {report["reference_timing"]["status"]}',
      f'- Asset recovery: {report["asset_recovery"]["status"]}',
      '', '## Review flags', '']
    markdown+=['- '+x for x in report['issues']] or ['- None from supported observations']
    markdown+=['','## Limitations','',
      '- Terminal capture images are not pixel snapshots for each video frame.',
      '- PCM silence with PSG register writes does not identify the root cause.',
      '- Interrupt count alone cannot prove a timing fault.',
      '- Independent emulator parity requires user-supplied, aligned reference captures.',
      '- No ROM bytes are copied by this review.','']
    (out/'HARDWARE-REVIEW.md').write_text('\n'.join(markdown),encoding='utf8')
    return report
