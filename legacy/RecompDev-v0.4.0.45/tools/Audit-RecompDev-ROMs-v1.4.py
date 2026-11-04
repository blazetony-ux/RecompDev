#!/usr/bin/env python3
"""Read-only complete-inventory ROM identity audit for RecompDev v0.3 (v1.4).

No catalog mutations, ROM writes, disassembly, game execution, or Internet access.
Reads bounded header bytes; disc metadata uses bounded ISO9660 seeks, with optional 7-Zip UDF fallback.
Does not SHA256-hash multi-gigabyte disc images. Uses current bridge adapters and
additional conservative Nintendo cartridge-header readers.
Every ordinary file under scanned roots appears in the CSV, even unknown extensions.
Adds Amiga ADF, PC Engine HuCard candidates, Wii WAD TMD, Xbox 360 XISO
volume headers and extensionless STFS package identification.
Jaguar .j64 is recognised as a format, NOT as a verified title.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
import os
from pathlib import Path
import re
import sys
import zipfile
import subprocess
import shutil
import xml.etree.ElementTree as ET

ROM_EXTENSIONS = frozenset('''
.md .gen .bin .smd .32x .sms .gg .iso .img .psx .exe .elf .xex .xbe
.con .stfs .live .pirs .sfo .pkg .pbp .nes .fds .unf .sfc .smc
.gb .gbc .sgb .gba .nds .3ds .cia .n64 .z64 .v64 .gcm .rvz .wbfs
.wud .wux .wad .dol .cue .gdi .cdi .chd .cso .nsp .xci .nca
.zip .7z .rar .j64 .jag .rom .abs .cof .prg .adf .pce .ccd .sub
'''.split())
ARCHIVE_EXTENSIONS = {'.zip', '.7z', '.rar'}
CONTAINER_EXTENSIONS = {'.chd', '.cso', '.rvz', '.wbfs', '.wud', '.wux', '.cdi', '.pkg', '.nsp', '.xci', '.nca', '.cia', '.3ds'}
COMPANION_EXTENSIONS = {'.cue', '.gdi', '.ccd', '.sub'}
FIELDS = ['file', 'system', 'format', 'status', 'detected_title', 'title_source', 'game_reference', 'reference_source', 'size_bytes', 'notes', 'filename_hint']
HEADER_BYTES = 0x11000
JAGUAR_EXPLICIT_EXTENSIONS = {'.j64', '.jag'}
JAGUAR_CONTEXT_EXTENSIONS = {'.rom', '.abs', '.cof', '.prg'}
JAGUAR_FOLDER_NAMES = {'jaguar', 'atari jaguar', 'jag', 'atarijaguar'}


def clean_ascii(raw: bytes, minimum_letters=2):
    if not raw:
        return None
    if any(b != 0 and not 32 <= b <= 126 for b in raw):
        return None
    title = ' '.join(raw.decode('ascii').replace('\x00', ' ').split())
    if len(title) > 100 or sum(c.isalpha() for c in title) < minimum_letters:
        return None
    return title


def jaguar_extension_identity(path: Path):
    """Classify Jaguar image candidates without inventing a title.

    .j64 and .jag are explicitly associated with Jaguar; .rom/.abs/.cof/.prg
    require a Jaguar directory context because other platforms use them.
    Does not claim that the ROM has a standard title header or valid contents.
    """
    ext=path.suffix.lower()
    context=any(part.casefold() in JAGUAR_FOLDER_NAMES for part in path.parts[:-1])
    if ext not in JAGUAR_EXPLICIT_EXTENSIONS and not (context and ext in JAGUAR_CONTEXT_EXTENSIONS):
        return None
    typename=('j64-cartridge-candidate' if ext == '.j64' else
              'jaguar-format-candidate' if ext == '.jag' else
              'jaguar-context-candidate')
    evidence = 'extension' if ext in JAGUAR_EXPLICIT_EXTENSIONS else 'folder and extension'
    return dict(system='jaguar',format=typename,display_name=None,name_source=None,
                game_id=None,id_source=None,confidence='format_hint',notes=(
                    f'Atari Jaguar classification based on {evidence}, not a verified image signature.',
                    'A format hint is not an embedded game title or authenticated revision; use an external ROM hash database.',))


def supplement(data: bytes, ext: str):
    """Additional conservative cartridge metadata readers. Return a dict or None."""
    # Game Boy: Nintendo logo, title (newer CGB carts shorten field).
    if ext in ('.gb', '.gbc', '.sgb') and len(data) >= 0x150 and data[0x104:0x108] == bytes.fromhex('CE ED 66 66'):
        cgb = data[0x143] in (0x80, 0xC0)
        title = clean_ascii(data[0x134:0x13F] if cgb else data[0x134:0x144])
        return dict(system='gameboy', format='gb-cartridge', display_name=title, name_source='cartridge_header' if title else None,
                    game_id=None, id_source=None, confidence='embedded_title' if title else 'partial',
                    notes=('CGB header title may be truncated to 11 characters.',) if cgb else ())
    # GBA fixed byte and logo prefix protect against misidentification.
    if ext == '.gba' and len(data) >= 0xC0 and data[4:8] == bytes.fromhex('24 FF AE 51') and data[0xB2] == 0x96:
        title = clean_ascii(data[0xA0:0xAC])
        code = clean_ascii(data[0xAC:0xB0], minimum_letters=1)
        return dict(system='gba', format='gba-cartridge', display_name=title, name_source='cartridge_header' if title else None,
                    game_id=code, id_source='cartridge_header' if code else None,
                    confidence='embedded_title' if title else ('serial' if code else 'partial'), notes=())
    # N64 native big-endian / halfword swapped / word swapped byte orders.
    if ext in ('.z64', '.v64', '.n64') and len(data) >= 0x40:
        magic=data[:4]
        if magic == bytes.fromhex('80 37 12 40'):
            normal=data[:0x40]
        elif magic == bytes.fromhex('37 80 40 12'):
            normal=b''.join(data[i:i+2][::-1] for i in range(0, 0x40, 2))
        elif magic == bytes.fromhex('40 12 37 80'):
            normal=b''.join(data[i:i+4][::-1] for i in range(0, 0x40, 4))
        else:
            normal=None
        if normal:
            title=clean_ascii(normal[0x20:0x34])
            code=clean_ascii(normal[0x3B:0x3F], minimum_letters=1)
            return dict(system='n64', format='n64-cartridge', display_name=title, name_source='cartridge_header' if title else None,
                        game_id=code, id_source='cartridge_header' if code else None,
                        confidence='embedded_title' if title else ('serial' if code else 'partial'),notes=())
    # SNES: a candidate header must pass checksum/complement plus map mode & ASCII checks.
    # Copier headers can prefix the actual ROM by 512 bytes.
    if ext in ('.sfc', '.smc'):
        candidates=[]
        for copier in (0, 512):
            for base, expected in ((0x7FC0, 0), (0xFFC0, 1)):
                off=base+copier
                if off+0x40>len(data):
                    continue
                title=clean_ascii(data[off:off+21])
                check=int.from_bytes(data[off+0x1E:off+0x20],'little')
                comp=int.from_bytes(data[off+0x1C:off+0x1E],'little')
                mode=data[off+0x15]&0x0F
                if not title or check+comp!=0xFFFF or (mode!=expected and not (expected==0 and mode in (2,3))):
                    continue
                reset=int.from_bytes(data[off+0x3C:off+0x3E],'little')
                candidates.append((1 if reset >= 0x8000 and reset != 0xFFFF else 0,title,base,copier))
        if candidates:
            candidates.sort(reverse=True)
            _,title,base,copier=candidates[0]
            return dict(system='snes',format='snes-hirom' if base==0xFFC0 else 'snes-lorom',display_name=title,
                        name_source='cartridge_header',game_id=None,id_source=None,confidence='embedded_title',
                        notes=('512-byte copier prefix detected.',) if copier else ())
    # iNES provides mapper/memory information but no standard game title.
    if ext == '.nes' and data.startswith(b'NES\x1a'):
        return dict(system='nes',format='ines',display_name=None,name_source=None,game_id=None,id_source=None,
                    confidence='partial',notes=('iNES has no standard embedded game-title field.',))
    # GameCube/Wii optical disc headers carry plain game title and disc identifier.
    if ext in ('.iso','.gcm') and len(data) >= 0x100:
        wii=data[0x18:0x1C]==bytes.fromhex('5D 1C 9E A3')
        gc=data[0x1C:0x20]==bytes.fromhex('C2 33 9F 3D')
        if wii or gc:
            system='wii' if wii else 'gamecube'
            title=clean_ascii(data[0x20:0x60])
            code=clean_ascii(data[:6],minimum_letters=1)
            return dict(system=system,format='disc-header',display_name=title,name_source='disc_header' if title else None,
                        game_id=code,id_source='disc_header' if code else None,
                        confidence='embedded_title' if title else ('serial' if code else 'partial'),notes=())
    return None


def dict_from_bridge(identity):
    return identity.json() if hasattr(identity,'json') else identity


def identify_header(data: bytes, path: Path, bridge, *, allow_seek: bool):
    ext=path.suffix.lower()
    # .j64 files were entirely skipped in v1.2. Report them even if no game
    # title can be extracted, without falsely claiming a header-derived name.
    jaguar=jaguar_extension_identity(path)
    if jaguar is not None:
        return jaguar
    # Supplement tries known magic, before generic ISO9660 and unknown results.
    add=supplement(data,ext)
    if add is not None:
        return add
    ident=(bridge._md(data) or bridge._psx_exe(data,path) or bridge._stfs(data) or
           bridge._xex(data) or bridge._sfo(data))
    if ident is None and path.name.upper()=='SYSTEM.CNF':
        ident=bridge._from_system_cnf(data.decode('ascii','replace'),'ps2' if b'BOOT2' in data.upper() else 'ps1')
    if ident is None and allow_seek and ext in ('.iso','.bin','.img'):
        ident=bridge._disc_system_cnf(path)
    if ident is not None:
        result=dict_from_bridge(ident)
        if result.get('system')=='megadrive' and not result.get('game_id') and len(data)>=0x18E:
            product=data[0x180:0x18E].decode('ascii','replace').strip().strip('\x00')
            if len(product)>=4 and re.fullmatch(r'[A-Za-z0-9 ._/-]+',product) and any(c.isdigit() for c in product):
                result['game_id']=product
                result['id_source']='rom_header'
        return result
    return dict(system='unknown', format='unrecognised', display_name=None, name_source=None,
                game_id=None,id_source=None,confidence='unresolved',notes=())



# v1.4: Conservative, seek-bounded metadata adapters. Source files remain untouched.
# Classification from context/extension is deliberately NOT labelled as a header title.

def _identity(system, fmt, title=None, title_source=None, game_id=None,
              reference_source=None, notes=()):
    return dict(system=system, format=fmt, display_name=title, name_source=title_source,
                game_id=game_id, id_source=reference_source,
                confidence=('embedded_title' if title_source else 'serial' if game_id else 'format_hint'),
                notes=tuple(notes))


def _amiga_adf(data, size):
    if size not in (901120, 1802240):
        return _identity('amiga','adf-size-unusual',notes=(
            'ADF extension and nonstandard size only; Amiga format not verified.',))
    if data[:3] == b'DOS' and len(data) >= 4 and data[3] <= 7:
        return _identity('amiga','adf-amigados',notes=(
            'AmigaDOS bootblock signature and disk size match; this is not a game title.',))
    return _identity('amiga','adf-raw-candidate',notes=(
        'Standard Amiga floppy image size; bootblock does not establish an AmigaDOS filesystem. May be copy-protected.',
        'Game name is not embedded in a standard ADF title header.'))


def _pce_hucard_candidate(size):
    return _identity('pcengine','hucard-candidate',notes=(
        'PC Engine HuCard attribution is extension-only; no validated internal game title.',
        'A ROM hash database is needed for reliable game/revision identification.',))


def _wii_wad_identity(path):
    """Read installable WAD header and TMD title ID, never content/tickets."""
    with path.open('rb') as f:
        header=f.read(0x40)
        if len(header) < 0x40 or int.from_bytes(header[0:4],'big') != 0x20 or header[4:6] not in (b'Is',b'ib'):
            return _identity('wii','wad-candidate',notes=(
                'Wii attribution inferred from .wad extension; installable WAD signature not validated.',))
        cert_size=int.from_bytes(header[8:12],'big')
        ticket_size=int.from_bytes(header[16:20],'big')
        tmd_size=int.from_bytes(header[20:24],'big')
        # Header/cert/ticket/TMD are stored consecutively with 0x40 alignment.
        align=lambda n:(n+0x3f)&~0x3f
        tmd_offset=0x40+align(cert_size)+align(ticket_size)
        size=path.stat().st_size
        if (cert_size>8*1024*1024 or ticket_size>4096 or
            not 0x1e4<=tmd_size<=512*1024 or tmd_offset+tmd_size>size):
            return _identity('wii','wad-installable',notes=(
                'Installable Wii WAD header recognised, but section sizes prevent safe TMD inspection.',))
        f.seek(tmd_offset)
        tmd=f.read(min(tmd_size,0x1e4))
    if len(tmd)<0x1e4 or int.from_bytes(tmd[:4],'big')!=0x00010001:
        return _identity('wii','wad-installable',notes=(
            'WAD header recognised, but TMD signature/type was not validated.',))
    count=int.from_bytes(tmd[0x1de:0x1e0],'big')
    tid=int.from_bytes(tmd[0x18c:0x194],'big')
    kind=tid>>32
    if count>2048 or tmd_size<0x1e4+36*count or kind not in (1,0x10000,0x10001,0x10002,0x10004,0x10005,0x10008):
        return _identity('wii','wad-installable',notes=(
            'WAD header recognised; TMD identity fields were implausible or incomplete.',))
    return _identity('wii','wad-installable-tmd',game_id=f'{tid:016X}',
                     reference_source='wad_tmd_title_id',notes=(
        'Wii Title ID extracted from installable WAD TMD, not a verified game name.',
        'WAD signatures and payload were not cryptographically authenticated.',))


XDVDFS_MAGIC=b'MICROSOFT*XBOX*MEDIA'
# The bare game partition and common XGD2/XGD3 data-partition offsets.
XISO_BASES=((0,'xbox-disc-partition'),(0x0FD90000,'xgd2-disc'),
            (0x02080000,'xgd3-disc'),(0x18300000,'xgd1-disc'))


def _xbox_iso_identity(path):
    """Seek for both XDVDFS markers, not the first 8 GB of an image."""
    size=path.stat().st_size
    with path.open('rb') as f:
        for base,fmt in XISO_BASES:
            offset=base+32*2048
            if offset+2048>size:
                continue
            f.seek(offset)
            sec=f.read(2048)
            if sec[:20]==XDVDFS_MAGIC and sec[0x7ec:0x800]==XDVDFS_MAGIC:
                folder_is_360=any(part.casefold().replace(' ','')=='xbox360' for part in path.parts[:-1])
                system=('xbox' if fmt=='xgd1-disc' else
                        'xbox360' if fmt!='xbox-disc-partition' or folder_is_360 else 'xbox-family')
                return _identity(system,fmt+'-xdvdfs',notes=(
                    'Verified both XDVDFS volume descriptor markers; no title is embedded in this header.',
                    'Executable metadata or a database is needed to resolve the actual game.'))
    xbox_folder=any(p.casefold().replace(' ','') in ('xbox360','xbox') for p in path.parts[:-1])
    if xbox_folder:
        return _identity('xbox360','xbox360-iso-folder-candidate',notes=(
            'Xbox 360 inferred from containing directory; no XDVDFS volume descriptor confirmed.',
            'Disc layout may require a specialised reader; the filename is not a header title.',))
    return None


def _disc_companion_row(path, size):
    ext=path.suffix.lower()
    system='ps1' if any(p.casefold() in ('ps1','psx','playstation','playstation 1') for p in path.parts[:-1]) else 'unknown'
    description={'.cue':'Track layout', '.gdi':'Dreamcast-style track layout',
                 '.ccd':'CloneCD disc metadata', '.sub':'CD subchannel data'}.get(ext,'Disc companion')
    row=special_row(path,size,'COMPANION_FILE',
            description+'; listed in inventory, but not a separate game or embedded title.')
    row['system']=system
    row['format']=ext.lstrip('- .')+'-companion'
    return row

def lookup_title(ident, title_index):
    if ident.get('display_name') or not ident.get('game_id'):
        return ident
    system=ident.get('system','').lower().strip()
    key=ident['game_id'].upper().replace('_','-').replace('.','')
    titles=title_index.get((system,key),set())
    if len(titles)==1:
        ident['display_name']=next(iter(titles))
        ident['name_source']='owner_supplied_title_db'
    elif len(titles)>1:
        ident['notes']=tuple(ident.get('notes',()))+('Conflicting titles for ID in supplied title database.',)
    return ident


def outcome(source, size, identity, title_index):
    ident=lookup_title(identity.copy(),title_index)
    title=ident.get('display_name')
    origin=ident.get('name_source')
    code=ident.get('game_id')
    if origin=='owner_supplied_title_db':
        status='TITLE_DB_MATCH'
    elif origin in ('rom_header','cartridge_header','disc_header','stfs_display_name','param_sfo_title') and title:
        status='HEADER_TITLE'
    elif code:
        status='REFERENCE_ONLY'
    elif origin=='project_path_hint' and title:
        status='PROJECT_HINT_ONLY'
    elif ident.get('system')!='unknown':
        status='KNOWN_FORMAT_NO_TITLE'
    else:
        status='UNRECOGNISED'
    return dict(file=source,system=ident.get('system') or 'unknown',format=ident.get('format') or '',status=status,
                detected_title=title or '',title_source=origin or '',game_reference=code or '',reference_source=ident.get('id_source') or '',
                size_bytes=size,notes=' | '.join(ident.get('notes',())))


def special_row(path,size, status, detail):
    return dict(file=str(path),system='unknown',format=Path(str(path).split('::')[-1]).suffix.lower().lstrip('.'),status=status,
                detected_title='',title_source='',game_reference='',reference_source='',size_bytes=size,notes=detail)


# PS3 disc metadata adapter, intentionally kept separate from code extraction.
# Read only PS3_GAME/PARAM.SFO, never entire games or the disc image into memory.
PS3_SFO_LIMIT = 128 * 1024
PS3_DIRECTORY_LIMIT = 2 * 1024 * 1024


def _iso_records(stream, extent, length, sector_size=2048):
    """Read a bounded ISO9660 directory, retaining file/directory flags."""
    if not 0 < length <= PS3_DIRECTORY_LIMIT or extent < 0:
        return []
    stream.seek(extent * sector_size)
    data=stream.read(length)
    if len(data)!=length:
        return []
    items=[]
    for offset in range(0,len(data),sector_size):
        pos=offset
        stop=min(offset+sector_size,len(data))
        while pos<stop:
            reclen=data[pos]
            if reclen==0:
                break
            if reclen<34 or pos+reclen>stop:
                return []
            item=data[pos:pos+reclen]
            namelen=item[32]
            if 33+namelen>len(item):
                return []
            raw=item[33:33+namelen]
            if raw not in (b'\x00',b'\x01'):
                name=raw.decode('ascii','replace').upper().split(';',1)[0]
                items.append((name,int.from_bytes(item[2:6],'little'),int.from_bytes(item[10:14],'little'),bool(item[25]&2)))
            pos+=reclen
    return items


def _ps3_sfo_from_iso9660(path):
    """Seek-only ISO9660 traversal: root/PS3_GAME/PARAM.SFO.

    PS3 images can also use UDF; unsupported UDF layouts are routed to 7-Zip.
    """
    with path.open('rb') as stream:
        stream.seek(16*2048)
        pvd=stream.read(2048)
        if len(pvd)!=2048 or pvd[:7]!=b'\x01CD001\x01':
            return None
        root=pvd[156:]
        if len(root)<34 or root[0]<34:
            return None
        extent=int.from_bytes(root[2:6],'little')
        length=int.from_bytes(root[10:14],'little')
        for name in ('PS3_GAME','PARAM.SFO'):
            rec=next((r for r in _iso_records(stream,extent,length) if r[0]==name),None)
            if rec is None: return None
            _,extent,length,is_dir=rec
            if name=='PS3_GAME' and not is_dir:
                return None
            if name=='PARAM.SFO':
                if is_dir or not 20<=length<=PS3_SFO_LIMIT:
                    return None
                stream.seek(extent*2048)
                contents=stream.read(length)
                return contents if len(contents)==length else None
    return None


def _locate_7z(explicit=None):
    if explicit:
        p=Path(explicit)
        if not p.is_file():
            raise ValueError(f'7-Zip executable not found: {explicit}')
        return str(p)
    for name in ('7z','7zz','7za'):
        found=shutil.which(name)
        if found: return found
    if os.name=='nt':
        p=Path(os.environ.get('ProgramFiles',r'C:\Program Files'))/'7-Zip'/'7z.exe'
        if p.is_file(): return str(p)
    return None


def _ps3_sfo_with_7z(path,seven_zip_exe):
    """Optional UDF fallback: extract only one named SFO to stdout, no files written."""
    if not seven_zip_exe:
        return None
    for member in ('PS3_GAME/PARAM.SFO',r'PS3_GAME\PARAM.SFO'):
        try:
            proc=subprocess.run([seven_zip_exe,'e','-so','-bd','-y',str(path),member],
                                stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=60,check=False)
            if 20<=len(proc.stdout)<=PS3_SFO_LIMIT and proc.stdout.startswith(b'\x00PSF'):
                return proc.stdout
        except (OSError,subprocess.TimeoutExpired):
            continue
    return None


def _ps3_identity_from_sfo(data,bridge,source):
    ident=bridge._sfo(data)
    if ident is None:
        return None
    info=dict_from_bridge(ident)
    title=info.get('display_name')
    code=info.get('game_id')
    # Avoid treating malformed or unrelated SFO content as a PS3 game.
    if not title and not (code and re.fullmatch(r'[A-Za-z]{4}[-]?[0-9]{5}',code)):
        return None
    if title and (len(title)>256 or not title.isprintable()):
        return None
    info.update(system='ps3',format='ps3-disc-param-sfo',
                confidence='embedded_title' if title else 'serial',
                notes=(f'PS3_GAME/PARAM.SFO read via {source}.',
                       'Disc edition is not authenticated by a full-image hash.'))
    return info


def _ps3_disc_reader(path,bridge,seven_zip_exe):
    payload=_ps3_sfo_from_iso9660(path)
    if payload:
        identity=_ps3_identity_from_sfo(payload,bridge,'iso9660')
        if identity:return identity
    payload=_ps3_sfo_with_7z(path,seven_zip_exe)
    if payload:
        identity=_ps3_identity_from_sfo(payload,bridge,'7zip')
        if identity:return identity
    return None


def _ps3_folder_hint(path):
    return any(p.casefold() in ('ps3','playstation 3','playstation3') for p in path.parts[:-1])


def _unresolved_ps3_row(path,size,seven_zip_exe):
    row=special_row(path,size,'ADAPTER_NEEDED',
        'PS3 is inferred from the folder path, not verified from internal disc metadata. '
        'Could not read PS3_GAME/PARAM.SFO from ISO9660 or the optional 7-Zip UDF reader. '
        + ('7-Zip was not found; install 7-Zip or pass --7z-exe.' if not seven_zip_exe else
           '7-Zip found, but SFO extraction was unavailable or returned no valid PS3 metadata.'))
    row['system']='ps3'
    row['format']='ps3-disc-unresolved'
    return row


def from_file(path, bridge, title_index, seven_zip_exe=None):
    ext=path.suffix.lower(); size=path.stat().st_size
    if ext in COMPANION_EXTENSIONS:
        return _disc_companion_row(path,size)
    if ext=='.wad':
        return outcome(str(path),size,_wii_wad_identity(path),title_index)
    if ext in CONTAINER_EXTENSIONS:
        return special_row(path,size,'ADAPTER_NEEDED','Container is known, but not supported by this header-only reader.')
    with path.open('rb') as stream:
        head=stream.read(HEADER_BYTES)
    identity=identify_header(head,path,bridge,allow_seek=True)
    if identity.get('system')=='unknown':
        if ext=='.adf':
            identity=_amiga_adf(head,size)
        elif ext=='.pce':
            identity=_pce_hucard_candidate(size)
        elif ext=='.iso':
            xbox_ident=_xbox_iso_identity(path)
            if xbox_ident is not None: identity=xbox_ident
    # Only inspect PS3 disc metadata after other known disc identities have been ruled out.
    if ext in ('.iso','.img') and identity.get('system')=='unknown':
        ps3_identity=_ps3_disc_reader(path,bridge,seven_zip_exe if (_ps3_folder_hint(path) or path.name.lower().endswith('.dec.iso')) else None)
        if ps3_identity is not None:
            identity=ps3_identity
        elif _ps3_folder_hint(path):
            return _unresolved_ps3_row(path,size,seven_zip_exe)
    # Standalone PS3_GAME/PARAM.SFO can be correctly attributed by its directory context.
    if ext=='.sfo' and identity.get('system')=='playstation-family' and \
          path.name.upper()=='PARAM.SFO' and path.parent.name.upper()=='PS3_GAME':
        identity['system']='ps3'
    return outcome(str(path),size,identity,title_index)


def mame_description(mame_exe, shortname):
    """Optional offline lookup from MAME's own driver database (never run game code)."""
    if not mame_exe or not re.fullmatch(r'[A-Za-z0-9_+.-]{1,90}', shortname):
        return None
    try:
        proc = subprocess.run([str(mame_exe), '-listxml', shortname],
                              capture_output=True, timeout=30, check=False)
        if proc.returncode != 0 or len(proc.stdout) > 8_000_000:
            return None
        root = ET.fromstring(proc.stdout)
        for machine in root.findall('machine'):
            if machine.attrib.get('name', '').casefold() == shortname.casefold() and machine.attrib.get('isdevice') != 'yes':
                desc = machine.findtext('description')
                return desc.strip() if desc and desc.strip() else None
    except (OSError, subprocess.TimeoutExpired, ET.ParseError):
        pass
    return None


def arcade_zip_row(path, member_count, title_index, mame_exe=None):
    """Treat a MAME ROM set as ONE game, not one disc per chip."""
    shortname=path.stem
    desc=mame_description(mame_exe,shortname)
    ident=dict(system='arcade',format='mame-rom-set',display_name=desc,
               name_source='mame_listxml_description' if desc else None,
               game_id=shortname,id_source='mame_archive_shortname',
               confidence='catalogue' if desc else 'unresolved',
               notes=(f'{member_count} archive members; ROM chip names are not game title headers.',
                      'MAME shortname derived from archive filename; archive contents not validated.'))
    row=outcome(str(path),path.stat().st_size,ident,title_index)
    if row['title_source']=='mame_listxml_description':
        row['status']='EXTERNAL_CATALOGUE_MATCH'
    elif row['status']=='REFERENCE_ONLY':
        row['status']='ARCADE_SET_REFERENCE_ONLY'
    return row


def from_zip(path,bridge,title_index,mame_exe=None):
    results=[]
    with zipfile.ZipFile(path) as z:
        # MAME sets use multiple ROM chips named by their board positions.
        # An extension like .bin does NOT imply an optical disc. MAME/arcade
        # folders supply context, not a header title; report one set per ZIP.
        members=[x for x in z.infolist() if not x.is_dir()]
        if any(component.casefold() in ('mame','arcade') for component in path.parts):
            return [arcade_zip_row(path,len(members),title_index,mame_exe)]
        for member in members:
            if member.is_dir():
                continue
            member_path=Path(member.filename)
            source=f'{path}::{member.filename}'
            suffix=member_path.suffix.lower()
            if suffix not in ROM_EXTENSIONS:
                results.append(special_row(source,member.file_size,'UNCLASSIFIED_ZIP_MEMBER',
                                           'Archive member extension not recognised; listed to prevent silent omission.'))
                continue
            if suffix in ARCHIVE_EXTENSIONS or suffix in CONTAINER_EXTENSIONS:
                results.append(special_row(source,member.file_size,'ADAPTER_NEEDED','Nested archive or container requires a dedicated adapter.'))
                continue
            if suffix in COMPANION_EXTENSIONS:
                results.append(special_row(source,member.file_size,'COMPANION_FILE','Track definition; cannot identify game title from filename alone.'))
                continue
            # Never extract the member to disk and never decompress more than a header.
            with z.open(member,'r') as f:
                data=f.read(HEADER_BYTES)
            ident=identify_header(data,path.parent/member_path,bridge,allow_seek=False)
            # A bare .bin is also a common arcade ROM chip or cartridge dump,
            # not reliable evidence for an ISO optical-disc image.
            if suffix in ('.iso','.img') and ident.get('system')=='unknown':
                results.append(special_row(source,member.file_size,'DISC_IN_ZIP_NOT_INSPECTED',
                                           'Unrecognised disc-like ZIP member: inspect track metadata with a seekable reader.'))
            elif suffix == '.bin' and ident.get('system')=='unknown':
                results.append(special_row(source,member.file_size,'BIN_IN_ZIP_UNKNOWN',
                                           'Ambiguous .bin member: could be a ROM chip or a disc; not identified from extension.'))
            else:
                results.append(outcome(source,member.file_size,ident,title_index))
    if not results:
        results.append(special_row(path,path.stat().st_size,'ZIP_NO_KNOWN_ROMS','No recognised ROM extensions among ZIP members.'))
    return results


def get_title_db(path):
    index={}
    if not path: return index
    with open(path,encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if not {'system','id','title'} <= set(reader.fieldnames or []):
            raise ValueError('title DB requires CSV columns: system,id,title')
        for row in reader:
            system=row['system'].lower().strip()
            code=row['id'].upper().replace('_','-').replace('.','').strip()
            title=row['title'].strip()
            if system and code and title:
                index.setdefault((system,code),set()).add(title)
    return index


def audit(roots, bridge, title_index, limit=None, progress=100, mame_exe=None, seven_zip_exe=None):
    results=[]; seen=0; errors=[]
    for root in roots:
        if not root.is_dir():
            raise ValueError(f'ROM folder does not exist: {root}')
        for current,dirs,files in os.walk(root,followlinks=False):
            dirs[:]=sorted(d for d in dirs if d not in {'.git','$RECYCLE.BIN','System Volume Information'})
            for name in sorted(files):
                path=Path(current)/name
                seen+=1
                try:
                    if path.is_symlink():
                        results.append(special_row(path,0,'SKIPPED_SYMLINK',
                                                   'Symbolic link is listed, not followed or read.'))
                    elif path.suffix.lower() not in ROM_EXTENSIONS:
                        with path.open('rb') as stream:
                            signature=stream.read(4)
                            header=signature+stream.read(HEADER_BYTES-4) if signature in (b'CON ',b'LIVE',b'PIRS',b'XEX2',b'XEX1') else b''
                        package=(bridge._stfs(header) or bridge._xex(header)) if header else None
                        if package is not None:
                            results.append(outcome(str(path),path.stat().st_size,dict_from_bridge(package),title_index))
                        else:
                            results.append(special_row(path,path.stat().st_size,'UNCLASSIFIED_EXTENSION',
                                                       'No recognised format signature or extension; included in inventory.'))
                    elif path.suffix.lower()=='.zip':
                        results.extend(from_zip(path,bridge,title_index,mame_exe))
                    elif path.suffix.lower() in ('.7z','.rar'):
                        results.append(special_row(path,path.stat().st_size,'ARCHIVE_NOT_INSPECTED',
                                                   '7z/RAR requires a separate archive adapter; title not inferred from filename.'))
                    else:
                        results.append(from_file(path,bridge,title_index,seven_zip_exe))
                except (OSError,ValueError,zipfile.BadZipFile,RuntimeError,EOFError) as err:
                    errors.append(dict(file=str(path),error=f'{type(err).__name__}: {err}'))
                    results.append(special_row(path,0,'READ_ERROR',str(err)))
                if progress and seen%progress==0:
                    print(f'FILES_VISITED={seen};ROWS={len(results)}',flush=True)
                if limit and seen>=limit:
                    return results,errors,seen
    return results,errors,seen


def main(argv=None):
    parser=argparse.ArgumentParser(description='Read-only complete ROM file inventory with Jaguar, PS3, Wii, Amiga, PC Engine and Xbox formats (no imports or renaming).')
    parser.add_argument('--root',required=True,action='append',help='ROM folder; repeat to audit multiple drives')
    parser.add_argument('--bridge',default=r'C:\Projects\RecompDev-v0.3\bridge',help='Path to existing RecompDev v0.3 bridge directory')
    parser.add_argument('--output-dir',default=None,help='Output folder (default: under current working directory)')
    parser.add_argument('--title-db',help='Optional existing CSV: system,id,title; no online lookup')
    parser.add_argument('--mame-exe',help='Optional path to MAME executable; resolves arcade ZIP shortnames using offline -listxml')
    parser.add_argument('--7z-exe',help='Optional 7-Zip executable for PS3 UDF ISO metadata (auto-detected if available)')
    parser.add_argument('--limit',type=int,help='Inspect only the first N matching files, for a quick test')
    parser.add_argument('--progress-every',type=int,default=100)
    args=parser.parse_args(argv)
    if args.limit is not None and args.limit<1: parser.error('--limit must be positive')
    bridge_dir=Path(args.bridge).resolve()
    if not (bridge_dir/'adapters'/'identity.py').is_file():
        parser.error(f'RecompDev identity adapter not found: {bridge_dir / "adapters" / "identity.py"}')
    sys.path.insert(0,str(bridge_dir))
    from adapters import identity as bridge
    roots=[Path(r).resolve() for r in args.root]
    try:
        title_index=get_title_db(args.title_db)
        if args.mame_exe and not Path(args.mame_exe).is_file():
            parser.error(f'--mame-exe was not found: {args.mame_exe}')
        seven_zip_exe=_locate_7z(args.__dict__.get('7z_exe'))
        rows,errors,seen=audit(roots,bridge,title_index,args.limit,args.progress_every,args.mame_exe,seven_zip_exe)
        out=Path(args.output_dir).resolve() if args.output_dir else Path.cwd()/'rom-name-audit'
        out.mkdir(parents=True,exist_ok=True)
        csv_file=out/'rom-name-audit.csv'
        json_file=out/'rom-name-audit-summary.json'
        for row in rows:
            # Useful for inventory, intentionally NOT a verified detected title.
            row['filename_hint'] = Path(row['file'].split('::')[-1]).stem
        with csv_file.open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=FIELDS)
            writer.writeheader();writer.writerows(rows)
        statuses=Counter(r['status'] for r in rows)
        systems=Counter(r['system'] for r in rows)
        # Every filesystem file visited must have at least one CSV row, including
        # ZIPs whose contents are individually reported. This is the key v1.3 gate.
        reported_sources = {r['file'].split('::',1)[0] for r in rows}
        filesystem_sources = set()
        for root in roots:
            for current, dirs, names in os.walk(root, followlinks=False):
                dirs[:] = [d for d in dirs if d not in {'.git', '$RECYCLE.BIN', 'System Volume Information'}]
                for name in names:
                    filesystem_sources.add(str(Path(current)/name))
        # --limit deliberately stops early, so only enforce on a complete audit.
        unreported = [] if args.limit is not None else sorted(filesystem_sources-reported_sources)
        if unreported:
            errors.append({'error':'Missing filesystem inventory entries', 'files':unreported[:20]})
        summary=dict(schema='recomp-rom-name-audit-v1.4',roots=[str(r) for r in roots],source_files_visited=seen,
                     unreported_source_files=len(unreported),
                     items_reported=len(rows),status_counts=dict(sorted(statuses.items())),systems=dict(sorted(systems.items())),
                     errors=errors,disclaimer='Metadata only. Header titles are not authoritative edition IDs. Filename hints are not header titles. Catalogue not modified.')
        json_file.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        print('CSV='+str(csv_file))
        print('SUMMARY='+str(json_file))
        print('FILES_VISITED='+str(seen))
        print('ITEMS_REPORTED='+str(len(rows)))
        for status,count in sorted(statuses.items()):print(f'STATUS_{status}={count}')
        print('UNREPORTED_SOURCE_FILES='+str(len(unreported)))
        print('READ_ERRORS='+str(len(errors)))
        print('CATALOGUE_MODIFIED=NO')
        return 0 if not errors else 2
    except (OSError,ValueError) as error:
        print('ERROR='+str(error),file=sys.stderr)
        return 1

if __name__=='__main__':raise SystemExit(main())
