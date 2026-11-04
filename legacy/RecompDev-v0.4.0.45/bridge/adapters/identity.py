"""Read-only game identity discovery from authenticated container metadata.

Never guesses code/CPU semantics. No decryption, no firmware, no network calls.
Every result carries its provenance and identification strength.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import hashlib
from pathlib import Path
import re

SERIAL_RE = re.compile(r'(?<![A-Z0-9])((?:S[LCEIP][A-Z]{2}|S[PCL][A-Z]{2})[_-][0-9]{3}[.\-_]?[0-9]{2})(?![A-Z0-9])', re.I)
# Accept widely seen PS1/PS2 boot identifiers without accepting arbitrary file names.
SERIAL_GENERIC = re.compile(r'\b([A-Z]{4})[_-]([0-9]{3})\.?(\d{2})\b', re.I)

@dataclass(frozen=True)
class Identity:
    system: str
    format: str
    display_name: str | None = None
    name_source: str | None = None
    game_id: str | None = None
    id_source: str | None = None
    confidence: str = 'unresolved'
    notes: tuple[str, ...] = ()

    def json(self):
        return asdict(self)


def serial_from_text(text: str) -> str | None:
    found = SERIAL_GENERIC.search(text.upper())
    return (f'{found.group(1)}-{found.group(2)}{found.group(3)}') if found else None


def _safe_title(raw: bytes) -> str | None:
    if not raw:return None
    if any(x not in (0,9,10,13) and not 32<=x<127 for x in raw):return None
    s=' '.join(raw.decode('ascii','strict').replace('\x00',' ').split())
    return s if len(s)>=3 and sum(c.isalpha() for c in s)>=3 else None


def _project_hint(path: Path):
    # Historical owner-local project folders: ps1-ridge-racer-68468e09be/sources/boot.psx
    for p in (path.parent, *path.parents):
        m=re.fullmatch(r'(?:ps1|ps2|psx|megadrive|md|xbox360|xbox)-([a-z0-9][a-z0-9-]*?)-[a-f0-9]{8,12}', p.name.lower())
        if m:
            label=m.group(1).replace('-',' ').strip().title()
            return label if label and label not in ('Boot','Game') else None
    return None


def _md(data: bytes):
    if len(data)<0x200 or b'SEGA' not in data[0x100:0x110]:return None
    title = _safe_title(data[0x150:0x180]) or _safe_title(data[0x120:0x150])
    product = _safe_title(data[0x180:0x18e])
    return Identity('megadrive','cartridge',title,'rom_header' if title else None,product,'rom_header' if product else None,'embedded_title' if title else 'partial',('Header title is publisher-provided, not a complete edition fingerprint.',))


def _psx_exe(data: bytes,path:Path):
    if not data.startswith(b'PS-X EXE') or len(data)<0x800:return None
    hint = _project_hint(path)
    serial=serial_from_text(path.name)
    return Identity('ps1','ps-x-exe',hint,'project_path_hint' if hint else None,serial,'executable_filename' if serial else None,'serial' if serial else ('hint_only' if hint else 'unresolved'),('PS-X EXE header has no standard commercial game-title or disc serial field.','Read disc SYSTEM.CNF for boot identifier when available.'))


def _from_system_cnf(text:str,system:str):
    m=re.search(r'^\s*(BOOT2?|BOOT)\s*=\s*([^\r\n]+)', text,flags=re.I|re.M)
    if not m:return Identity(system,'system-cnf',notes=('Boot path missing.',))
    serial=serial_from_text(m.group(2))
    return Identity(system,'system-cnf',None,None,serial,'system_cnf_boot' if serial else None,'serial' if serial else 'partial',('Serial may resolve to multiple releases or editions; confirm via hashes.',))


def _stfs(data: bytes):
    if data[:4] not in (b'CON ',b'LIVE',b'PIRS') or len(data)<0x500:return None
    title_id=data[0x360:0x364].hex().upper()
    # Display title is UTF-16BE, NUL terminated; sanity-check length and printability.
    raw=data[0x411:0x411+0x100]
    try:
        name=raw.decode('utf-16-be',errors='strict').split('\x00',1)[0].strip()
    except UnicodeDecodeError:
        name=''
    if not name or len(name)>100 or not name.isprintable():name=None
    return Identity('xbox360','stfs',name,'stfs_display_name' if name else None,title_id,'stfs_title_id','embedded_title' if name else 'serial',('Only package header metadata read; no licensed content or encrypted payload extracted.',))


def _xex(data:bytes):
    if data[:4] not in (b'XEX2',b'XEX1') or len(data)<0x18:return None
    count=int.from_bytes(data[0x14:0x18],'big')
    if count>16384 or 0x18+8*count>len(data):
        return Identity('xbox360','xex',notes=('Malformed or unsupported optional header table.',))
    title_id=None
    for n in range(count):
        k=int.from_bytes(data[0x18+8*n:0x1c+8*n],'big')
        v=int.from_bytes(data[0x1c+8*n:0x20+8*n],'big')
        if k==0x00040006 and v+16<=len(data):
            title_id=data[v+12:v+16].hex().upper()
            break
    return Identity('xbox360','xex',None,None,title_id,'xex_execution_id' if title_id else None,'serial' if title_id else 'partial',('Executable may be compressed/encrypted; metadata parsing is not code extraction.',))


def _sfo(data: bytes):
    if data[:4]!=b'\x00PSF' or len(data)<20:return None
    key_start=int.from_bytes(data[8:12],'little');value_start=int.from_bytes(data[12:16],'little')
    count=int.from_bytes(data[16:20],'little')
    if count>4096 or 20+16*count>len(data):return None
    vals={}
    for n in range(count):
        offset=20+16*n
        ko=int.from_bytes(data[offset:offset+2],'little');fmt=int.from_bytes(data[offset+2:offset+4],'little')
        size=int.from_bytes(data[offset+4:offset+8],'little');vo=int.from_bytes(data[offset+12:offset+16],'little')
        if size>65536 or key_start+ko>=len(data) or value_start+vo+size>len(data):continue
        key=data[key_start+ko:].split(b'\x00',1)[0][:64].decode('ascii','replace')
        if fmt & 0xFF == 4:
            vals[key]=data[value_start+vo:value_start+vo+size].split(b'\x00',1)[0].decode('utf-8','replace').strip()
    name=vals.get('TITLE');serial=vals.get('TITLE_ID') or vals.get('DISC_ID')
    return Identity('playstation-family','param-sfo',name,'param_sfo_title' if name else None,serial,'param_sfo_id' if serial else None,'embedded_title' if name else ('serial' if serial else 'partial'))


def _iso_read_block(path:Path,lba:int,sector:int,offset:int):
    # CD Mode1/2352 layout has 16-byte headers. Disc tracks that start elsewhere
    # require a separate CUE/track mapping adapter; do not silently offset-guess.
    with path.open('rb') as f:
        f.seek(lba*sector+offset)
        return f.read(2048)


def _iso_record(buf:bytes,pos:int):
    if pos>=len(buf) or buf[pos]==0:return None
    size=buf[pos]
    if size<34 or pos+size>len(buf):return None
    d=buf[pos:pos+size]
    extent=int.from_bytes(d[2:6],'little');length=int.from_bytes(d[10:14],'little')
    name=d[33:33+d[32]].decode('ascii','replace').upper()
    return extent,length,name,size


def _disc_system_cnf(path:Path):
    if path.suffix.lower() not in ('.iso','.bin','.img'):return None
    for sector,offset in ((2048,0),(2352,16),(2352,24)):
        pvd=_iso_read_block(path,16,sector,offset)
        if len(pvd)!=2048 or pvd[0:1]!=b'\x01' or pvd[1:6]!=b'CD001':continue
        root=_iso_record(pvd,156)
        if not root:continue
        start,length,_,_=root
        if length>2*1024*1024:continue
        sectors=min((length+2047)//2048,1024)
        files=b''.join(_iso_read_block(path,start+n,sector,offset) for n in range(sectors))[:length]
        for ofs in range(0,len(files),2048):
            pos=ofs
            while pos<min(ofs+2048,len(files)):
                item=_iso_record(files,pos)
                if not item:break
                fstart,flen,name,step=item
                if name in ('SYSTEM.CNF;1','SYSTEM.CNF') and flen<=32768:
                    payload=b''.join(_iso_read_block(path,fstart+n,sector,offset) for n in range((flen+2047)//2048))[:flen]
                    text=payload.decode('ascii','replace')
                    system='ps2' if re.search(r'^\s*BOOT2\s*=',text,re.I|re.M) else 'ps1'
                    return _from_system_cnf(text,system)
                pos+=step
    return None


def identify(path: str):
    path=Path(path)
    # Bytes read from existing owner-local source; never written or embedded in reports.
    with path.open('rb') as f:
        first=f.read(0x8000)
    identity=_md(first) or _psx_exe(first,path) or _stfs(first) or _xex(first) or _sfo(first)
    if identity is None and path.name.upper().startswith('SYSTEM.CNF'):
        identity=_from_system_cnf(first.decode('ascii','replace'),'ps2' if b'BOOT2' in first.upper() else 'ps1')
    if identity is None:
        identity=_disc_system_cnf(path)
    if identity is None:
        identity=Identity('unknown','unrecognised',notes=('No supported identity evidence; preserve source for future adapters.',))
    # Read-only stream hash used for exact association with an existing target.
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return {'source_path':str(path),'source_sha256':h.hexdigest(),'size':path.stat().st_size,'identity':identity.json()}
