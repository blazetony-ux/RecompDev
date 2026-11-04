"""Explicit aligned, provenance-based hardware contract checking.

Unaligned samples are diagnostic only, never a verification pass.
"""
import hashlib
from pathlib import Path

COMPONENTS=('vram','cram','vdp-registers','ram','audio-pcm')
def compare(reference,candidate,alignment):
    if alignment.get('status')!='MATCHED_CODE_IDENTITY_WITH_SELECTED_REGISTERS' or not alignment.get('hardware_aligned'):
        return {'schema':'recomp-hardware-contract-v1','status':'BLOCKED_UNALIGNED_HARDWARE_STATE',
                'qualified':False,'components':{},'reason':'Matching code identity alone does not establish equal hardware sample boundaries'}
    if reference.get('source_sha256')!=candidate.get('source_sha256'):
        raise ValueError('Hardware reference source identity mismatch')
    findings={}
    for kind in COMPONENTS:
        a=reference.get('components',{}).get(kind)
        b=candidate.get('components',{}).get(kind)
        if a is None or b is None:findings[kind]='NOT_MEASURED'
        elif a==b and isinstance(a,str) and len(a)==64 and all(c in '0123456789abcdef' for c in a):findings[kind]='MATCHED_DIGEST'
        else:findings[kind]='DIFFERENT_OR_INVALID_DIGEST'
    return {'schema':'recomp-hardware-contract-v1',
            'status':'DIVERGED' if 'DIFFERENT_OR_INVALID_DIGEST' in findings.values() else 'INCOMPLETE' if 'NOT_MEASURED' in findings.values() else 'MATCHED_ALIGNED_SAMPLES',
            'qualified':False,'components':findings,
            'reason':'Hashes of aligned samples only; device timing, all frames, bus ordering, and gameplay are not proven'}
