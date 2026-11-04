"""Convert ONLY a fixed-size generated P6 diagnostic framebuffer to PNG.

No dependencies and no image data read from ROM uploads or browser requests.
This image shows background tile decoding only, not a verified game frame.
"""
import struct
import zlib
from pathlib import Path

def png_chunk(kind,data):
    return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)

def convert_ppm(ppm,png):
    ppm=Path(ppm);png=Path(png)
    raw=ppm.read_bytes()
    header=b'P6\n256 192\n255\n'
    if len(raw)!=len(header)+256*192*3 or not raw.startswith(header):
        raise ValueError('Unexpected generated framebuffer dimensions or encoding')
    pixels=memoryview(raw)[len(header):]
    rows=b''.join(b'\x00'+pixels[y*768:(y+1)*768].tobytes() for y in range(192))
    data=(b'\x89PNG\r\n\x1a\n'+png_chunk(b'IHDR',struct.pack('>IIBBBBB',256,192,8,2,0,0,0))+
          png_chunk(b'IDAT',zlib.compress(rows,7))+png_chunk(b'IEND',b''))
    png.write_bytes(data)
