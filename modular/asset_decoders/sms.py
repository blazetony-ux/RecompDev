"""Sega Master System raw 4bpp 8x8 tile/palette extraction from hardware dumps.

VRAM: 16,384 bytes; each 8x8 pattern is 32 bytes, four bitplanes per line.
CRAM: 32 bytes, two 16-colour palettes, RR GG BB 2-bit channel fields.
This does not infer sprite tables, maps, ROM compression or animation timing.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path


def decode_tile(block):
    if len(block)!=32:raise ValueError('Master System tile pattern must be 32 bytes')
    pixels=[]
    for y in range(8):
        planes=block[y*4:y*4+4]
        for x in range(8):
            mask=0x80>>x
            pixels.append(sum(((planes[p]&mask)!=0)<<p for p in range(4)))
    return pixels

def decode_cram(cram):
    if len(cram)!=32:raise ValueError('Master System CRAM must be 32 bytes')
    return [((x&3)*85,((x>>2)&3)*85,((x>>4)&3)*85) for x in cram]

def export_if_present(root,out):
    from modular.hardware_review import write_png
    root=Path(root)
    vrams=sorted(root.glob('**/hardware-state-vram.bin'))
    crams=sorted(root.glob('**/hardware-state-cram.bin'))
    # Review a single matching captured state. Never search raw ROM files.
    vrams=[p for p in vrams if p.is_file() and not p.is_symlink() and p.stat().st_size==16384 and 'native-project' not in p.parts]
    crams=[p for p in crams if p.is_file() and not p.is_symlink() and p.stat().st_size==32 and 'native-project' not in p.parts]
    if not vrams:
        return {'status':'RAW_VRAM_REQUIRED','vram_expected_bytes':16384,
                'cram_expected_bytes':32,'available_raw_vram_captures':0,
                'source_tile_patterns_exported':0,'note':'The uploaded capture has PPM/WAV but no raw VRAM buffer; cannot assert any source sprite/tile extraction.'}
    src=vrams[-1];vram=src.read_bytes();cram=crams[-1].read_bytes() if crams else None
    palette=decode_cram(cram) if cram is not None else [(i*17,i*17,i*17) for i in range(16)]*2
    tiles=[decode_tile(vram[k:k+32]) for k in range(0,len(vram),32)]
    width=16*8;height=((len(tiles)+15)//16)*8
    outputs=[]
    out.mkdir(parents=True,exist_ok=True)
    for palette_bank in (0,1) if cram is not None else (0,):
        canvas=bytearray(width*height*3)
        for idx,tile in enumerate(tiles):
            tx=(idx%16)*8;ty=(idx//16)*8
            for j,index in enumerate(tile):
                px=tx+j%8;py=ty+j//8
                v=palette[palette_bank*16+index]
                canvas[(py*width+px)*3:(py*width+px)*3+3]=bytes(v)
        name=f'sms-tiles-palette{palette_bank}.png'
        write_png(out/name,width,height,canvas);outputs.append(name)
    manifest={'schema':'recompdev-sms-tiles-v1','status':'EXPORTED_SOURCE_VRAM',
              'machine':'mastersystem','format':'sms-vdp-4bpp-8x8-planar',
              'vram_capture_source':str(src.relative_to(root)),
              'vram_capture_sha256':hashlib.sha256(vram).hexdigest(),
              'cram_capture_source':str(crams[-1].relative_to(root)) if cram is not None else None,
              'cram_capture_sha256':hashlib.sha256(cram).hexdigest() if cram is not None else None,
              'palette_source':'CAPTURED_2BIT_CRAM' if cram is not None else 'GRAYSCALE_FALLBACK_NOT_ORIGINAL_PALETTE',
              'patterns':len(tiles),'tile_pattern_bytes':32,'width':width,'height':height,
              'output_atlases':outputs,'distinct_tile_patterns':len(set(vram[i:i+32] for i in range(0,len(vram),32))),
              'limitations':['No sprite composition or animation recovery','VRAM state is one capture, not a full game asset catalogue',
                             'No ROM contents included']}
    (out/'sms-tile-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
    return manifest
