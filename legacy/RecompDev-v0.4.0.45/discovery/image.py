"""Dependency-free PNG encoder for deterministic previews."""
import struct
import zlib

def _chunk(typ,data):
    return struct.pack('>I',len(data))+typ+data+struct.pack('>I',zlib.crc32(typ+data)&0xffffffff)

def png_rgba(width,height,rgba):
    if width<=0 or height<=0 or width*height>8_000_000 or len(rgba)!=width*height*4:
        raise ValueError('invalid PNG dimensions or byte length')
    rows=b''.join(b'\0'+rgba[y*width*4:(y+1)*width*4] for y in range(height))
    return (b'\x89PNG\r\n\x1a\n'+_chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,6,0,0,0))+
            _chunk(b'IDAT',zlib.compress(rows,6))+_chunk(b'IEND',b''))

def bgr555(word):
    r=(word&31)*255//31;g=((word>>5)&31)*255//31;b=((word>>10)&31)*255//31
    # PS1 bit-15 controls semi-transparency, not conventional alpha. Preview does not emulate blending.
    return r,g,b,255

def render_tim(raw):
    """Validate PS1 TIM and return (format,width,height,RGBA). Reject truncated/implausible structures."""
    if len(raw)<20 or raw[:4]!=b'\x10\x00\x00\x00':raise ValueError('not TIM')
    flags=struct.unpack_from('<I',raw,4)[0]
    mode=flags&7
    if flags&~0xF or mode>3:raise ValueError('unknown TIM flags')
    pos=8;palette=None
    if flags&8:
        if len(raw)<pos+12:raise ValueError('short CLUT')
        n,x,y,w,h=struct.unpack_from('<IHHHH',raw,pos)
        if n<12 or w==0 or h==0 or n!=12+2*w*h or pos+n>len(raw) or w*h>65536:
            raise ValueError('invalid CLUT')
        palette=[bgr555(struct.unpack_from('<H',raw,pos+12+i*2)[0]) for i in range(w*h)]
        pos+=n
    if len(raw)<pos+12:raise ValueError('short image block')
    n,x,y,words,high=struct.unpack_from('<IHHHH',raw,pos)
    if not words or not high or n<12 or n!=12+words*2*high or pos+n>len(raw):
        raise ValueError('invalid TIM pixel block')
    if mode==0: width=words*4
    elif mode==1:width=words*2
    elif mode==2:width=words
    else:
        if words*2%3:raise ValueError('24-bit TIM row not RGB-aligned')
        width=words*2//3
    if width*high>4_000_000:raise ValueError('TIM exceeds preview budget')
    if mode in (0,1) and (not palette or len(palette)<(16 if mode==0 else 256)):
        raise ValueError('indexed TIM missing CLUT')
    pixels=raw[pos+12:pos+n];out=bytearray()
    stride=words*2
    for line in range(high):
        row=pixels[line*stride:(line+1)*stride]
        if mode==0:
            indices=[v for b in row for v in (b&15,b>>4)]
            for idx in indices:out.extend(palette[idx])
        elif mode==1:
            for idx in row:out.extend(palette[idx])
        elif mode==2:
            for i in range(0,len(row),2):out.extend(bgr555(row[i]|(row[i+1]<<8)))
        else:
            for i in range(0,len(row),3):out.extend((row[i+2],row[i+1],row[i],255))
    return f'PS1_TIM_{(4,8,16,24)[mode]}BPP',width,high,bytes(out),pos+n

def render_md_tiles(raw,tiles_per_row=8):
    """Unverified Mega Drive 4bpp tile interpretation, grayscale, no claimed real palette."""
    if len(raw)%32 or not raw:raise ValueError('MD tile bytes must be multiple of 32')
    nt=len(raw)//32; cols=min(tiles_per_row,nt);rows=(nt+cols-1)//cols
    width=cols*8;height=rows*8;out=bytearray(width*height*4)
    for tile in range(nt):
        tx=(tile%cols)*8;ty=(tile//cols)*8
        for y in range(8):
            for x in range(8):
                b=raw[tile*32+y*4+x//2];v=(b>>4) if x%2==0 else (b&15)
                p=((ty+y)*width+tx+x)*4;out[p:p+4]=bytes((v*17,v*17,v*17,255))
    return width,height,bytes(out)
