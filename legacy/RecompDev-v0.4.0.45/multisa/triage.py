"""Generic unresolved-control-flow classification for bounded recovery queues.

This classifies evidence; it does not execute game logic or invent jump targets.
"""
import hashlib,json
from collections import Counter
from pathlib import Path


def triage(path,out=None):
    blob=Path(path).read_bytes();d=json.loads(blob)
    if d.get('schema')!='recomp-flow-evidence-v1':raise ValueError('requires source-attested flow evidence')
    sha=d.get('source_sha256','')
    if not isinstance(sha,str) or len(sha)!=64:raise ValueError('missing source identity')
    seen=set(d.get('observed_addresses',[]));queue=[]
    for b in d.get('barriers',[]):
        pc=b['address'];why=str(b['reason']).lower()
        if 'register jump' in why or 'indirect' in why or 'target unknown' in why:
            category='INDIRECT_TARGET';action='BOUNDED_DATAFLOW_THEN_EXTERNAL_ANALYZER'
        elif 'delay slot' in why:category='DELAY_SLOT';action='ISA_DELAY_SEMANTICS_CHECK'
        elif 'outside mapped' in why or 'unmapped' in why:category='MAPPING';action='REVIEW_CONTAINER_AND_BANK_MAP'
        elif 'system call' in why or 'exception' in why or 'trap' in why:category='SYSTEM_DEPENDENCY';action='REFERENCE_OS_OR_DEVICE_TRACE'
        elif 'exhausted' in why:category='RESOURCE_BUDGET';action='BOUND_AND_RETEST'
        elif 'decoder' in why:category='DECODE_OR_DATA';action='INDEPENDENT_DISASSEMBLY_REVIEW'
        else:category='UNCLASSIFIED';action='INDEPENDENT_ANALYZER_REVIEW'
        queue.append({'address':pc,'reason':b['reason'],'class':category,'next_action':action,
                      'reached_by_static_scan':pc in seen,'priority':'REACHABLE_UNRESOLVED' if pc in seen else 'POTENTIAL_UNREACHABLE',
                      'confidence':'DIAGNOSTIC_ONLY_NO_TARGET_PROOF'})
    result={'schema':'recomp-universal-recovery-triage-v0432','source_sha256':sha,
            'architecture':d.get('architecture'),'evidence_sha256':hashlib.sha256(blob).hexdigest(),
            'barrier_count':len(queue),'classes':dict(Counter(q['class'] for q in queue)),
            'queue':queue,'qualification':'NO_AUTOMATIC_NATIVE_PROMOTION'}
    if out:
        out=Path(out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n')
    return result
