"""Strictly scoped original-MAME versus native execution observations.

Frame ordinals are not CPU instruction alignment. CPU parity is unproven even
when sampled PCs happen to agree. This tool refuses wrong-ROM and incomplete
emulator evidence and never auto-corrects or skips a mismatch.
"""
import hashlib
import json
import re
from pathlib import Path
from nativecore.frame_oracle import validate_frames,sha256

HEX=re.compile(r'[0-9a-f]{64}\Z')

def compare_frame_observations(reference_dir,native_session,rom):
    refroot=Path(reference_dir)
    session=Path(native_session)
    original=Path(rom)
    if not original.is_file() or original.is_symlink():raise ValueError('Original ROM must exist and be a regular file')
    if original.stat().st_size>64*1024*1024:raise ValueError('Original ROM exceeds limit')
    digest=sha256(original)
    refjson=refroot/'frame-observations.json'
    refraw=refroot/'mame-frames.jsonl'
    for path in (refjson,refraw,session):
        if not path.is_file() or path.is_symlink() or path.stat().st_size>8*1024*1024:
            raise ValueError('Missing, symbolic, or oversized original execution evidence: '+str(path))
    reference=json.loads(refjson.read_text(encoding='utf-8'))
    candidate=json.loads(session.read_text(encoding='utf-8'))
    if reference.get('schema')!='recomp-external-frame-observations-v1':raise ValueError('Invalid MAME capture schema')
    if candidate.get('schema') not in ('recomp-continuous-native-v2','recomp-continuous-owner-session-v1'):
        raise ValueError('Invalid native session schema')
    if reference.get('source_sha256')!=digest or candidate.get('source_sha256')!=digest:
        raise ValueError('MAME/native/source ROM SHA-256 do not match')
    if reference.get('raw_sha256')!=sha256(refraw):raise ValueError('MAME raw capture digest mismatch')
    if not reference.get('independent_source','').startswith('MAME owner-installed '):
        raise ValueError('Expected explicit owner-installed MAME provenance')
    if not isinstance(reference.get('script_sha256'),str) or not HEX.fullmatch(reference['script_sha256']):
        raise ValueError('No MAME capture-script identity')
    if not isinstance(reference.get('executable_sha256'),str) or not HEX.fullmatch(reference['executable_sha256']):
        raise ValueError('No independent MAME executable identity')
    if not isinstance(candidate.get('executable_sha256'),str) or not HEX.fullmatch(candidate['executable_sha256']):
        raise ValueError('No compiled native executable identity')
    frame_count=reference.get('requested_frames')
    if type(frame_count)!=int or not 1<=frame_count<=1200:raise ValueError('Invalid MAME frame count')
    imported=validate_frames(refraw,digest,reference['independent_source'],frame_count)
    if imported['observations']!=reference.get('observations'):
        raise ValueError('Reference observations differ from immutable raw capture')
    frames=candidate.get('frame_hardware')
    if not isinstance(frames,list) or len(frames)>36000:raise ValueError('Missing native frame records')
    if any(not isinstance(f,dict) or f.get('frame')!=i+1 or type(f.get('pc'))!=int or not 0<=f['pc']<=0xffff
           for i,f in enumerate(frames)):
        raise ValueError('Non-contiguous or invalid native frame observations')
    compared=min(len(frames),len(imported['observations']))
    first=None;matching=0
    for i in range(compared):
        expected=imported['observations'][i];got=frames[i]
        diff={field:{'reference':expected[field],'native':got.get(field)}
              for field in ('pc','sp') if field in expected and expected[field]!=got.get(field)}
        if diff and first is None:
            first={'frame_ordinal':i+1,'differences':diff,
                   'reference':{k:expected[k] for k in ('pc','sp') if k in expected},
                   'native':{'pc':got['pc'],'sp':got.get('sp'),
                             'guest_cycles':got.get('guest_cycles'),'steps':got.get('steps')}}
        if not diff:matching+=1
    return {'schema':'recomp-mame-native-sampled-diagnostics-v0437',
            'status':('FRAME_SAMPLES_DIFFER_UNALIGNED' if first else
                      'INCOMPLETE_FRAME_COVERAGE' if compared<frame_count else
                      'FRAME_SAMPLES_AGREE_UNALIGNED'),
            'source_sha256':digest,'mame_executable_sha256':reference['executable_sha256'],
            'mame_script_sha256':reference['script_sha256'],
            'native_executable_sha256':candidate['executable_sha256'],
            'reference_frames':frame_count,'native_frames':len(frames),
            'compared_frame_ordinals':compared,'matching_sample_ordinals':matching,
            'first_unaligned_frame_difference':first,
            'reset_state_alignment':'NOT_ESTABLISHED',
            'instruction_boundary_alignment':'NOT_ESTABLISHED',
            'frame_phase_alignment':'NOT_ESTABLISHED',
            'cpu_parity':'NOT_ESTABLISHED','hardware_parity':'NOT_ESTABLISHED',
            'next_action':'Establish equivalent reset, input and exact instruction/frame-phase anchors before attributing a causal CPU mismatch.',
            'warning':'Matching ordinal samples do not establish CPU parity. MAME producer independence is asserted by owner, not cryptographically certified.'}
