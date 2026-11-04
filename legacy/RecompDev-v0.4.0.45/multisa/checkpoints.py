"""CPU-/system-neutral, fail-closed comparison of independent checkpoint streams.

No reference emulator is claimed. Inputs must come from separate measurement
processes and declare identical source and initial machine-state hashes.
"""
import hashlib
import json
from pathlib import Path

FIELDS=('pc','cycles','registers','memory','io','interrupts','device_state')


def load(path):
    path=Path(path);raw=path.read_bytes();obj=json.loads(raw)
    if obj.get('schema')!='recomp-checkpoints-v1':raise ValueError('checkpoint schema mismatch')
    if obj.get('role') not in ('reference','candidate'):raise ValueError('checkpoint role missing')
    for name in ('source_sha256','initial_state_sha256'):
        v=obj.get(name)
        if not isinstance(v,str) or len(v)!=64 or any(c not in '0123456789abcdef' for c in v):
            raise ValueError('invalid '+name)
    if not obj.get('isa') or not isinstance(obj.get('points'),list) or len(obj['points'])>100000:
        raise ValueError('invalid architecture or checkpoint limit')
    last=-1
    for p in obj['points']:
        if not isinstance(p,dict) or type(p.get('seq')) is not int or p['seq']<=last:
            raise ValueError('checkpoint sequence must increase monotonically')
        last=p['seq']
    return obj,hashlib.sha256(raw).hexdigest()


def compare(reference,candidate):
    ref,rsha=load(reference);cand,csha=load(candidate)
    if ref['role']!='reference' or cand['role']!='candidate':raise ValueError('roles must be reference and candidate')
    for key in ('source_sha256','initial_state_sha256','isa'):
        if ref[key]!=cand[key]:raise ValueError('unaligned checkpoint inputs: '+key)
    a=ref['points'];b=cand['points'];n=min(len(a),len(b));first=None;compared=0
    for i in range(n):
        x=a[i];y=b[i]
        if x['seq']!=y['seq']:
            first={'sequence_index':i,'reason':'CHECKPOINT_INDEX_MISMATCH','reference_seq':x['seq'],'candidate_seq':y['seq']}
            break
        keys_ref={key for key in FIELDS if key in x}
        keys_cand={key for key in FIELDS if key in y}
        if keys_ref!=keys_cand:
            first={'sequence_index':i,'seq':x['seq'],'reason':'OBSERVATION_SET_MISMATCH',
                   'reference_fields':sorted(keys_ref),'candidate_fields':sorted(keys_cand)}
            break
        overlap=[key for key in FIELDS if key in x and key in y]
        if not overlap:raise ValueError('checkpoint pair has no shared observations')
        for field in overlap:
            if x[field]!=y[field]:
                first={'sequence_index':i,'seq':x['seq'],'reason':'FIRST_OBSERVED_DIFFERENCE','field':field,
                       'reference':x[field],'candidate':y[field]}
                break
        compared+=1
        if first is not None:break
    if first is None and len(a)!=len(b):
        first={'sequence_index':n,'reason':'CHECKPOINT_STREAM_LENGTH_MISMATCH','reference_length':len(a),'candidate_length':len(b)}
    if first is None and not a:raise ValueError('empty checkpoint streams cannot establish parity')
    # A finite matching prefix is evidence of a prefix only, never a full-console parity claim.
    return {'schema':'recomp-independent-first-divergence-v0432','source_sha256':ref['source_sha256'],
            'isa':ref['isa'],'initial_state_sha256':ref['initial_state_sha256'],
            'reference_file_sha256':rsha,'candidate_file_sha256':csha,
            'compared_checkpoints':compared,'first_divergence':first,
            'status':'FIRST_DIFFERENCE_FOUND' if first is not None else 'MATCHING_OBSERVED_PREFIX',
            'independent_parity':'FINITE_OBSERVED_CHECKPOINTS_ONLY',
            'reference_provenance_claimed_not_independently_authenticated':True}
