"""Bounded structural discovery. Does NOT infer game identity from a filename."""
from __future__ import annotations
import struct
from pathlib import Path

SCAN_BYTES_LIMIT=64*1024*1024
MAX_ASSET_BYTES=8*1024*1024


def probe(path):
    with open(path,'rb') as f:
        header=f.read(0x800)
    size=Path(path).stat().st_size
    if header.startswith(b'PS-X EXE'):
        return 'psx-exe', 'PS-X EXE magic',None
    if len(header)>0x200 and header[0x100:0x104] in (b'SEGA',b' SEG'):
        name=header[0x120:0x150].decode('ascii','replace').strip(' \0')
        return 'megadrive','Mega Drive header at 0x100',name or None
    if header[:4]==b'\x10\x00\x00\x00' and len(header)>=8:
        return 'ps1-tim','TIM signature candidate',None
    # Structural ISO9660 inspection, not a filename guess. Supports 2048 and raw 2352 sectors.
    try:
        iso=IsoReader(path)
        if iso.valid():return 'iso9660','ISO9660 primary volume descriptor',iso.volume_name()
    except (OSError,ValueError):pass
    if header[:4] in (b'CON ',b'LIVE',b'PIRS'):
        # Xbox 360 STFS package; naming belongs to the catalogue identity adapter.
        return 'xbox360-stfs','STFS header magic',None
    if header[:4] in (b'XEX1',b'XEX2'):
        return 'xbox360-xex','XEX executable magic',None
    if header[:4]==b'\x00PSF':
        return 'param-sfo','PARAM.SFO header magic',None
    if header[:4]==b'NES\x1a':
        return 'nes','iNES header',None
    # Store container candidates with explicit limited support.
    suffix=Path(path).suffix.lower()
    if header.startswith(b'MComprHD') or suffix=='.chd':return 'chd','CHD candidate; decoder unavailable',None
    if suffix=='.wad':return 'wii-wad-candidate','WAD extension; structure not checked here',None
    if suffix=='.nes' and header.startswith(b'NES\x1a'):return 'nes','iNES header',None
    if suffix in ('.z64','.v64','.n64') and header[:4] in (b'\x80\x37\x12\x40',b'\x37\x80\x40\x12',b'\x40\x12\x37\x80'):
        return 'n64','Nintendo 64 ROM header',None
    if suffix in ('.sms','.gg'):
        # Sega 8-bit export headers are at 0x1FF0/0x3FF0/0x7FF0.
        # The header has NO reliable plain-text game title.
        for off in (0x7FF0,0x3FF0,0x1FF0):
            if size>=off+16:
                with open(path,'rb') as stream:
                    stream.seek(off)
                    if stream.read(8)==b'TMR SEGA':
                        system='mastersystem' if suffix=='.sms' else 'gamegear'
                        return system,f'Sega 8-bit TMR SEGA header at 0x{off:X}',None
        return ('mastersystem-candidate' if suffix=='.sms' else 'gamegear-candidate',
                'Sega 8-bit extension only; header not confirmed',None)
    if suffix=='.j64':return 'jaguar-candidate','Jaguar extension; header not validated by this worker',None
    if suffix=='.adf' and size in (901120,1802240):return 'amiga-adf','Standard floppy image length',None
    if suffix=='.pce':return 'pcengine-candidate','HuCard extension; no title evidence',None
    if suffix in ('.sfc','.smc'):return 'snes-candidate','SNES extension; header not validated by this worker',None
    if suffix in ('.cue','.ccd','.sub'):return 'disc-companion','Disc companion; not a standalone game image',None
    if suffix=='.zip':return 'archive-candidate','ZIP archive; not unpacked by discovery',None
    if suffix=='.smd':return 'megadrive-interleaved-candidate','SMD interleaved ROM needs a separate decoder',None
    return 'unknown','No structural classifier matched',None


def tim_span(reader,offset,limit):
    """Read only the TIM lengths; bounds check before allocating a buffer."""
    if offset+20>limit:return None
    reader.seek(offset)
    hdr=reader.read(20)
    if len(hdr)<20 or hdr[:4]!=b'\x10\x00\x00\x00':return None
    flags=int.from_bytes(hdr[4:8],'little')
    if flags&~0xF or flags&7>3:return None
    pos=offset+8
    if flags&8:
        reader.seek(pos);chunk=reader.read(12)
        if len(chunk)<12:return None
        length,x,y,w,h=struct.unpack('<IHHHH',chunk)
        if not w or not h or w*h>65536 or length!=12+2*w*h:return None
        pos+=length
    if pos+12>limit:return None
    reader.seek(pos);chunk=reader.read(12)
    if len(chunk)<12:return None
    length,x,y,w,h=struct.unpack('<IHHHH',chunk)
    if not w or not h or w*h>8192*8192 or length!=12+w*2*h:return None
    total=pos+length-offset
    if not (20<=total<=MAX_ASSET_BYTES and offset+total<=limit):return None
    return total


def find_tims(path,scan_limit=SCAN_BYTES_LIMIT,max_count=40):
    """Stream signatures in a binary. Structural validation follows every hit."""
    file_size=Path(path).stat().st_size
    stop=min(file_size,scan_limit)
    found=[];pos=0;chunk_size=1024*1024;pattern=b'\x10\x00\x00\x00'
    with open(path,'rb') as f:
        while pos<stop and len(found)<max_count:
            f.seek(pos);data=f.read(min(chunk_size+3,stop-pos))
            if not data:break
            scan_start=0
            while len(found)<max_count:
                idx=data.find(pattern,scan_start)
                if idx<0 or pos+idx>=stop:break
                off=pos+idx
                span=tim_span(f,off,stop)
                if span is not None:
                    f.seek(off)
                    raw=f.read(span)
                    try:
                        from discovery.image import render_tim
                        fmt,w,h,pixels,consumed=render_tim(raw)
                        if consumed==span:
                            found.append((off,raw,fmt,w,h,pixels))
                    except (ValueError,IndexError,struct.error):pass
                scan_start=idx+4
            pos+=chunk_size
    return found


class IsoReader:
    """Read user-data sectors from 2048 ISO and MODE1/MODE2 2352 raw track images."""
    def __init__(self,path):
        self.path=Path(path)
        self.size=self.path.stat().st_size
        self.sector_size=0;self.data_offset=0
        with open(self.path,'rb') as f:
            for sector_size,offset in ((2048,0),(2352,24),(2352,16)):
                physical=16*sector_size+offset
                if physical+2048>self.size:continue
                f.seek(physical);data=f.read(2048)
                if data[0]==1 and data[1:6]==b'CD001' and data[6]==1:
                    self.sector_size=sector_size;self.data_offset=offset;break
        self._pvd=None

    def valid(self):return self.sector_size>0

    def sector_physical(self,lba):return lba*self.sector_size+self.data_offset

    def read(self,lba,offset=0,n=2048):
        if not self.valid() or lba<0 or offset<0 or n<0 or n>MAX_ASSET_BYTES:
            raise ValueError('invalid ISO sector read')
        if lba*2048+offset+n>self.size*2048//self.sector_size+4096:
            raise ValueError('ISO read outside source')
        out=bytearray()
        with open(self.path,'rb') as f:
            current=lba+offset//2048
            start=offset%2048
            remaining=n
            while remaining:
                count=min(2048-start,remaining)
                physical=self.sector_physical(current)+start
                if physical+count>self.size:raise ValueError('ISO sector outside source')
                f.seek(physical);b=f.read(count)
                if len(b)!=count:raise ValueError('short ISO sector read')
                out.extend(b);remaining-=count;start=0;current+=1
        return bytes(out)

    def pvd(self):
        if self._pvd is None:self._pvd=self.read(16)
        return self._pvd

    def volume_name(self):
        if not self.valid():return None
        return self.pvd()[40:72].decode('ascii','replace').strip(' \0') or None

    def _entry(self,data,pos):
        if pos>=len(data):return None
        n=data[pos]
        if n==0:return None
        if n<34 or pos+n>len(data):raise ValueError('malformed ISO directory record')
        rec=data[pos:pos+n]
        extent=int.from_bytes(rec[2:6],'little');length=int.from_bytes(rec[10:14],'little')
        idlen=rec[32]
        if 33+idlen>n:raise ValueError('malformed ISO identifier')
        name=rec[33:33+idlen].decode('ascii','replace')
        return {'name':name.split(';')[0], 'extent':extent,'size':length,'is_dir':bool(rec[25]&2),'record_size':n}

    def files(self,max_entries=5000,max_depth=8,max_directory_bytes=2*1024*1024):
        if not self.valid():raise ValueError('not ISO9660')
        root=self._entry(self.pvd(),156)
        if root is None or not root['is_dir']:raise ValueError('ISO root directory missing')
        pending=[('',root,0)];visited=set();out=[]
        while pending and len(out)<max_entries:
            prefix,folder,depth=pending.pop()
            if depth>max_depth or folder['size']>max_directory_bytes:continue
            key=(folder['extent'],folder['size'])
            if key in visited:continue
            visited.add(key)
            listing=self.read(folder['extent'],0,folder['size'])
            off=0
            while off<len(listing) and len(out)<max_entries:
                if listing[off]==0:
                    off=((off//2048)+1)*2048;continue
                entry=self._entry(listing,off)
                if entry is None:break
                off+=entry['record_size']
                if entry['name'] in ('\x00','\x01','.', '..'):continue
                fullname=prefix+'/'+entry['name']
                if entry['is_dir']:
                    if depth<max_depth:pending.append((fullname,entry,depth+1))
                else:
                    out.append({'path':fullname,'extent':entry['extent'],'size':entry['size'],
                                'physical_offset':self.sector_physical(entry['extent'])})
        return out
