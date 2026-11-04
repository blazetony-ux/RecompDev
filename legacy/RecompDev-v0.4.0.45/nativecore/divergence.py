"""Fail-closed, architecture-neutral first-divergence triage for external trace evidence.

This file proposes a *verification work item*, not a source patch. It only
accepts independently supplied, ROM-hash-matched reference evidence and checks
both chunk streams in full before publishing a divergence diagnosis.
"""
from collections import deque
from itertools import zip_longest
from pathlib import Path
import json
from nativecore.eventstream import iter_verified
from nativecore.parity import _source_validation, STREAM_SCHEMA, EVENT_SCHEMA, compare

FIELDS = ('kind', 'address', 'value', 'pc')
CLASSIFICATIONS = {
    'VDP': ('VIDEO_BUS_OR_TIMING', 'Check shared VDP port address decoding, latch sequence, register/VRAM/CRAM semantics and IRQ timing.'),
    'VRAM': ('VIDEO_MEMORY_SEMANTICS', 'Check shared VRAM address increment, data-port writes, latch state and video scheduling.'),
    'CRAM': ('PALETTE_SEMANTICS', 'Check palette address decoding, writes and video mode timing.'),
    'PSG': ('AUDIO_IO_SEMANTICS', 'Check PSG write ordering and shared audio port decoding.'),
    'MAPPER': ('CARTRIDGE_MAPPING', 'Check bank-register updates and original-ROM physical provenance; do not guess an indirect branch bank.'),
    'IRQ': ('CPU_INTERRUPT_TIMING', 'Check interrupt mode, enable flags, cycle accounting and VBlank scheduling.'),
    'NMI': ('CPU_INTERRUPT_TIMING', 'Check non-maskable interrupt entry and timing.'),
    'INPUT': ('CONTROLLER_INPUT', 'Check reset conditions, controller data and input sampling order.'),
}

def _classification(expected, observed, alignment):
    if expected is None or observed is None:
        return ('EVENT_COUNT_OR_ORDER', 'Identify the missing or additional operation; inspect upstream control flow and device scheduling.')
    if any(expected[k] != observed[k] for k in ('kind', 'address', 'value')):
        kinds=(expected['kind'], observed['kind'])
        prefix=next((p for p in CLASSIFICATIONS if any(k.startswith(p) for k in kinds)),None)
        return CLASSIFICATIONS.get(prefix, ('CPU_OR_IO_SEMANTICS','Inspect source-attested instruction lowering, ports, guest flags and ordered bus effects.'))
    if expected['pc'] != observed['pc']:
        return ('CPU_CONTROL_FLOW_OR_PROVENANCE', 'Compare Z80 PC mapping, instruction semantics and validated branch targets at this event.')
    if alignment == 'step' and expected['step'] != observed['step']:
        return ('CPU_STEP_ALIGNMENT', 'Verify instruction-count alignment and reset/input conditions before blaming CPU semantics.')
    return ('NO_DIVERGENCE', 'No distinct event effects at this ordinal position.')

def diagnose(reference, candidate, event_root=None, reference_root=None, context=4):
    if type(context) is not int or not 0<=context<=8:raise ValueError('Invalid context bound')
    _source_validation(reference,candidate)
    if reference.get('schema') not in (STREAM_SCHEMA,EVENT_SCHEMA):
        raise ValueError('First event divergence requires an external ordered event trace')
    alignment=reference.get('alignment','ordinal')
    if alignment not in ('ordinal','step'):raise ValueError('Invalid event alignment')
    # Run strict full comparison before any positive or mismatch diagnosis.
    result=compare(reference,candidate,event_root=event_root,reference_root=reference_root)
    observed=candidate.get('trace') or candidate
    if reference['schema']==STREAM_SCHEMA:
        if not reference_root or not event_root:raise ValueError('Full traces require reference and candidate stream roots')
        ref_iter=iter_verified(reference_root,reference['event_stream_manifest'])
        native_iter=iter_verified(event_root,observed['event_stream_manifest'])
    else:
        ref_iter=iter(reference['events'])
        # Inline traces may be truncated: candidate and reference evidence are honest about coverage.
        manifest=observed.get('event_stream_manifest')
        native_iter=(iter_verified(event_root,manifest) if event_root and isinstance(manifest,dict)
                     and manifest.get('status')=='COMPLETE' else iter(observed.get('events',[])))
    marker=object();before=deque(maxlen=context);first=None;after=[]
    for index,(ref,got) in enumerate(zip_longest(ref_iter,native_iter,fillvalue=marker)):
        er=None if ref is marker else ref
        ng=None if got is marker else got
        different=(not (er is None and reference.get('prefix_only') is True)
                   and (er is None or ng is None or any(er.get(k)!=ng.get(k) for k in FIELDS)
                        or (alignment=='step' and er['step']!=ng['step'])))
        if first is None and different:
            first={'event_index':index,'expected':er,'observed':ng,'preceding_events':list(before)}
        elif first is not None and len(after)<context:
            after.append({'event_index':index,'reference':er,'native':ng})
        if first is None:
            before.append({'event_index':index,'reference':er,'native':ng})
    if first is not None:first['following_events']=after
    # A checkpoint or final-state mismatch may precede or exist without event divergence.
    mismatches=result.get('mismatches',[])
    if first is not None:
        category,action=_classification(first['expected'],first['observed'],alignment)
    elif result['status']=='DIVERGED':
        category,action=('CPU_CHECKPOINT_OR_STATE','Inspect the reported checkpoint or hardware SHA mismatch; event equality alone does not prove CPU correctness.')
    else:
        category,action=('NONE','No demonstrated difference within compared coverage; do not claim full-game parity.')
    return {'schema':'recomp-divergence-diagnosis-v1','status':result['status'],
            'source_sha256':candidate['source_id'],'independent_source':reference['independent_source'],
            'classification':category,'suggested_investigation':action,
            'first_event_divergence':first,'other_mismatches':mismatches[:16],
            'alignment':alignment,'reference_prefix_only':reference['prefix_only'],
            'parity_comparison':result,
            'automatic_patch_applied':False,'native_dispatch_qualified':False,
            'scope':'Evidence-keyed investigation only. No code changes, automatic repair, independent-producer certification or gameplay qualification.'}

def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference',required=True);p.add_argument('--candidate',required=True);p.add_argument('--output',required=True)
    a=p.parse_args()
    ref_file=Path(a.reference).resolve();candidate_file=Path(a.candidate).resolve();destination=Path(a.output).resolve()
    if destination.exists():p.error('Output already exists: immutable evidence required')
    if destination in (ref_file,candidate_file):p.error('Cannot overwrite input evidence')
    if ref_file.stat().st_size>1024*1024 or candidate_file.stat().st_size>32*1024*1024:
        p.error('Reference or candidate report exceeds bounds')
    ref=json.loads(ref_file.read_text(encoding='utf-8'))
    candidate=json.loads(candidate_file.read_text(encoding='utf-8'))
    trace=candidate.get('trace') or candidate
    rel=trace.get('event_stream_directory')
    import re
    if rel and (not isinstance(rel,str) or not re.fullmatch(r'event-streams/attempt-\d{2}-budget-\d{1,7}',rel)):
        p.error('Invalid candidate stream path')
    native_root=(candidate_file.parent/rel if rel else candidate_file.parent)
    doc=diagnose(ref,candidate,native_root,ref_file.parent)
    destination.write_text(json.dumps(doc,indent=2)+'\n',encoding='utf-8')
    print('First-divergence status:',doc['status'],'classification:',doc['classification'])
    print('Evidence:',destination)

if __name__=='__main__':main()
