"""Game-independent byte-level confidence screening before native code generation.

Identifies suspicious fill runs without guessing game control flow. A suspicion
is not a declaration that the bytes are definitely data or padding.
"""
from pathlib import Path


def inspect_entry(path, physical_offset):
    path=Path(path)
    size=path.stat().st_size
    if type(physical_offset)!=int or not 0<=physical_offset<size:
        raise ValueError('Source offset outside authenticated ROM')
    with path.open('rb') as f:
        f.seek(max(0,physical_offset-128))
        start=max(0,physical_offset-128)
        blob=f.read(min(size-start,257))
    pivot=physical_offset-start
    byte=blob[pivot]
    left=pivot
    while left>0 and blob[left-1]==byte:left-=1
    right=pivot+1
    while right<len(blob) and blob[right]==byte:right+=1
    run=right-left
    suspicious=(byte==0xff and run>=8)
    return {'physical_offset':physical_offset,'entry_byte_hex':f'{byte:02x}',
            'fill_run_lower_bound':run,'fill_value_hex':f'{byte:02x}',
            'classification':('REPETITIVE_FF_SUSPECTED_PADDING' if suspicious else
                             'REPETITIVE_ZERO_LOW_CONFIDENCE' if byte==0 and run>=16 else
                             'UNCLASSIFIED_BYTES'),
            'translation_allowed':not suspicious,
            'warning':'Byte pattern is only a heuristic; reference execution is needed to establish intent.'}
