"""Independent expected-content checks for the compiled SMS hardware fixture.

These tests qualify deterministic output plumbing under controlled device inputs,
not reference SMS timing, ROM recompilation, MAME parity or commercial gameplay.
"""
import hashlib
import struct
from pathlib import Path

WIDTH,HEIGHT=256,192

def reference_ppm():
    # Source-owned visual oracle: each scan line has 128 red then 128 blue pixels.
    return b'P6\n256 192\n255\n' + ((b'\xff\x00\x00'*128)+(b'\x00\x00\xff'*128))*192

def reference_pcm():
    # Independent numeric expectation for a 16-tick tone register in the
    # explicitly approximate synthesizer with corrected /16 tone half-period. Not a hardware PSG oracle.
    values=[]
    for n in range(4410):
        guest_cycle=n*3579545//44100
        values.append(1500 if (guest_cycle//256)%2==0 else -1500)
    return values

def reference_wav():
    samples=reference_pcm()
    pcm=struct.pack('<'+'h'*len(samples),*samples)
    return (b'RIFF'+struct.pack('<I',36+len(pcm))+b'WAVEfmt '+
            struct.pack('<IHHIIHH',16,1,1,44100,88200,2,16)+
            b'data'+struct.pack('<I',len(pcm))+pcm)

def verify_outputs(ppm_path,wav_path):
    ppm=Path(ppm_path).read_bytes();wav=Path(wav_path).read_bytes()
    pixel_match=ppm==reference_ppm()
    audio_match=wav==reference_wav()
    pcm=wav[44:] if wav.startswith(b'RIFF') and len(wav)>=44 else b''
    samples=struct.unpack('<'+'h'*(len(pcm)//2),pcm) if len(pcm)%2==0 else ()
    nonzero=sum(x!=0 for x in samples)
    colors=len(set(ppm[len(b'P6\n256 192\n255\n')+i*3:len(b'P6\n256 192\n255\n')+i*3+3]
                   for i in range(WIDTH*HEIGHT))) if len(ppm)==len(reference_ppm()) else 0
    report={'schema':'recomp-native-output-qualification-v0437',
            'video':{'status':'PASS' if pixel_match else 'FAIL',
                     'actual_sha256':hashlib.sha256(ppm).hexdigest(),
                     'expected_sha256':hashlib.sha256(reference_ppm()).hexdigest(),
                     'distinct_rgb_colors':colors,'expected_dimensions':[WIDTH,HEIGHT]},
            'audio':{'status':'PASS' if audio_match else 'FAIL',
                     'actual_sha256':hashlib.sha256(wav).hexdigest(),
                     'expected_sha256':hashlib.sha256(reference_wav()).hexdigest(),
                     'nonzero_samples':nonzero,'expected_samples':4410},
            'status':'PASS' if pixel_match and audio_match and nonzero>0 and colors==2 else 'FAIL',
            'scope':'Controlled synthetic SMS device/output checks only; no CPU recompilation, emulator hardware-parity or gameplay qualification.'}
    return report
