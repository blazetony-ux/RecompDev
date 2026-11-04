"""Compare candidate execution with owner-supplied *external* reference evidence.

The comparison authenticates the ROM hash but cannot certify that the external
producer is genuinely independent. Labels are declarations, never proof.
Never derive reference records from the native candidate output.
"""
import argparse
import json
import re
from pathlib import Path
from nativecore.eventstream import iter_verified

SCHEMA='recomp-independent-checkpoint-reference-v1'
EVENT_SCHEMA='recomp-independent-event-trace-v1'
STREAM_SCHEMA='recomp-independent-stream-reference-v1'
CPU_FIELDS=('pc','af','bc','de','hl','sp','mapper')
EVENT_FIELDS=('vram_writes','cram_writes','psg_writes','io_writes','frames','irqs','tstates')
HARDWARE_REGIONS=('vram','cram','vdp-registers')


def _source_validation(reference,candidate):
    if not isinstance(reference,dict) or not isinstance(candidate,dict):
        raise ValueError('Expected reference and candidate JSON objects')
    ident=reference.get('source_sha256')
    if not isinstance(ident,str) or re.fullmatch(r'[0-9a-fA-F]{64}',ident) is None:
        raise ValueError('Source identity required (64-character SHA-256)')
    origin=reference.get('independent_source')
    if not isinstance(origin,str) or not origin.strip() or len(origin)>250:
        raise ValueError('Independent reference provenance required')
    if candidate.get('source_id')!=ident:
        raise ValueError('Reference and candidate ROM hashes do not match')
    return ident


def _checkpoint_fields(expected,observed):
    if not isinstance(expected,list) or not isinstance(observed,list):
        raise ValueError('Missing independent/observed checkpoint data')
    lookup={}
    for item in observed:
        if not isinstance(item,dict) or type(item.get('step'))!=int:
            raise ValueError('Invalid observed checkpoint')
        if item['step'] in lookup:raise ValueError('Duplicate candidate checkpoint step')
        lookup[item['step']]=item
    mismatches=[];matched=0;missing=[]
    seen=set()
    for ref in expected:
        if not isinstance(ref,dict) or type(ref.get('step'))!=int or ref['step']<0:
            raise ValueError('Invalid reference step')
        step=ref['step']
        if step in seen:raise ValueError('Duplicate reference checkpoint step')
        seen.add(step);got=lookup.get(step)
        if got is None:missing.append(step);continue
        for field in CPU_FIELDS+EVENT_FIELDS:
            if field not in ref:continue
            if got.get(field)!=ref[field]:
                mismatches.append({'step':step,'field':field,'expected':ref[field],'observed':got.get(field)})
            else:matched+=1
    return mismatches,matched,missing


def compare_checkpoints(reference,candidate):
    if reference.get('schema')!=SCHEMA:
        raise ValueError('Reference schema missing or invalid')
    ident=_source_validation(reference,candidate)
    observed=candidate.get('trace') or candidate
    expected=reference.get('checkpoints',[])
    if not isinstance(expected,list) or not expected:
        raise ValueError('Missing independent/observed checkpoint data')
    mismatches,matched,missing=_checkpoint_fields(expected,observed.get('checkpoints',[]))
    return {'schema':'recomp-parity-comparison-v1',
            'status':('DIVERGED' if mismatches else 'INCOMPLETE_REFERENCE_COVERAGE' if missing else 'MATCHED_SAMPLED_CHECKPOINTS'),
            'source_sha256':ident,'independent_source':reference['independent_source'],
            'compared_fields':matched+len(mismatches),'matching_fields':matched,
            'mismatches':mismatches[:100],'missing_steps':missing[:100],
            'scope':'Sampled checkpoint equality only; not verified frame or whole-game parity.'}


def compare_events(reference,candidate,event_root=None):
    """Strict in-order prefix or full-stream comparison, with optional step alignment.

    ordinal: compare the Nth event from each engine, allowing CPU step counts to
    differ but never skipping, deleting or reordering effects. Include step drift.
    step: compare the event's exact step as well as its effects.
    """
    if reference.get('schema')!=EVENT_SCHEMA:raise ValueError('Invalid event trace reference schema')
    ident=_source_validation(reference,candidate)
    alignment=reference.get('alignment','ordinal')
    if alignment not in ('ordinal','step'):raise ValueError('Invalid event alignment')
    if type(reference.get('prefix_only'))!=bool:
        raise ValueError('Explicit boolean prefix_only required')
    expected=reference.get('events')
    if not isinstance(expected,list) or not (1<=len(expected)<=4096):
        raise ValueError('External reference needs 1..4096 ordered events')
    observed=candidate.get('trace') or candidate
    manifest=observed.get('event_stream_manifest')
    stream_verified=bool(event_root is not None and isinstance(manifest,dict) and manifest.get('status')=='COMPLETE')
    if stream_verified:
        # Read and attest *all* records, even when comparing a prefix. The
        # legacy inline 4096-event preview is not the complete runtime log.
        actual=[]
        stream_total=0
        for record in iter_verified(event_root,manifest):
            if stream_total<len(expected):actual.append(record)
            stream_total+=1
        if stream_total!=observed.get('events_total'):
            raise ValueError('Candidate stream total inconsistent with runtime')
    else:
        actual=observed.get('events')
    if not isinstance(actual,list) or len(actual)>4096:
        raise ValueError('Candidate event trace missing or unbounded')
    if type(observed.get('events_total'))!=int or observed['events_total']<len(actual):
        raise ValueError('Candidate event count inconsistent with recorded events')
    truncated=False if stream_verified else observed.get('events_truncated')
    if type(truncated)!=bool or (not stream_verified and truncated!=(observed['events_total']>len(actual))):
        raise ValueError('Candidate event truncation evidence inconsistent')
    mismatches=[];matched=0;drift=[]
    fields=('kind','address','value','pc')+ (('step',) if alignment=='step' else ())
    for index,ref in enumerate(expected):
        if not isinstance(ref,dict) or any(field not in ref for field in fields):
            raise ValueError('Reference event missing required fields')
        if not isinstance(ref['kind'],str) or re.fullmatch(r'[A-Z][A-Z0-9_]{1,39}',ref['kind']) is None:
            raise ValueError('Invalid reference event type')
        for key in ('address','value','pc'):
            if type(ref[key])!=int or not 0<=ref[key]<=0xffff:
                raise ValueError('Invalid reference event '+key)
        if 'step' in ref and (type(ref['step'])!=int or ref['step']<0):
            raise ValueError('Invalid reference event step')
        if index>=len(actual):continue
        got=actual[index]
        if not isinstance(got,dict):raise ValueError('Invalid observed event')
        for field in fields:
            if got.get(field)!=ref[field]:
                mismatches.append({'event_index':index,'field':field,'expected':ref[field],
                                   'observed':got.get(field)})
            else:matched+=1
        if type(ref.get('step'))==int and type(got.get('step'))==int and ref['step']!=got['step']:
            drift.append({'event_index':index,'reference_step':ref['step'],'native_step':got['step']})
    missing_count=max(0,len(expected)-len(actual))
    complete=not reference['prefix_only']
    if complete and len(expected)!=observed['events_total'] and not truncated:
        mismatches.append({'field':'events_total','expected':len(expected),'observed':observed['events_total']})
    # Optional final VDP state content hashes, compared without distributing the bytes.
    state_ref=reference.get('final_hardware_sha256',{})
    if not isinstance(state_ref,dict) or any(k not in HARDWARE_REGIONS for k in state_ref):
        raise ValueError('Unsupported final hardware region')
    for region,digest in state_ref.items():
        if not isinstance(digest,str) or re.fullmatch(r'[0-9a-fA-F]{64}',digest) is None:
            raise ValueError('Invalid external hardware SHA-256')
        got=(observed.get('hardware_sha256') or {}).get(region)
        if got!=digest:
            mismatches.append({'field':'hardware_sha256.'+region,'expected':digest,'observed':got})
        else:matched+=1
    expected_checkpoints=reference.get('checkpoints',[])
    if not isinstance(expected_checkpoints,list):raise ValueError('Invalid reference checkpoints')
    cp_mismatches,cp_matches,cp_missing=_checkpoint_fields(expected_checkpoints,observed.get('checkpoints',[]))
    mismatches.extend(cp_mismatches);matched+=cp_matches
    incomplete=bool(missing_count or cp_missing or truncated)
    status=('DIVERGED' if mismatches else 'INCOMPLETE_EVENT_COVERAGE' if incomplete
            else 'MATCHED_EVENT_PREFIX' if reference['prefix_only'] else 'MATCHED_EVENT_TRACE')
    return {'schema':'recomp-parity-comparison-v2','status':status,
            'source_sha256':ident,'independent_source':reference['independent_source'],
            'alignment':alignment,'reference_events':len(expected),'candidate_events_recorded':observed['events_total'] if stream_verified else len(actual),
            'candidate_events_total':observed['events_total'],'candidate_events_truncated':truncated,
            'candidate_full_stream_verified':stream_verified,'inline_preview_truncated':observed.get('events_truncated',False),
            'prefix_only':reference['prefix_only'],'compared_fields':matched+len(mismatches),
            'matching_fields':matched,'mismatches':mismatches[:100],
            'mismatch_count':len(mismatches),'missing_events':missing_count,'missing_steps':cp_missing[:100],
            'step_drift':drift[:32],
            'scope':'Ordered event equality within selected trace interval only. External independence is claimed by the provider, not authenticated by this comparison; does not prove gameplay, CPU cycles or frame parity.'}


def compare_stream(reference,candidate,event_root=None,reference_root=None):
    """Full SHA-verified external JSONL vs candidate JSONL comparison.

    Both streams are iterated fully and bounded, and the first divergence is
    reported. Missing, reordered, forged or truncated chunks cannot pass.
    The *independence* of the external producer is a user-supplied claim.
    """
    if reference.get('schema')!=STREAM_SCHEMA:raise ValueError('Unsupported stream reference schema')
    ident=_source_validation(reference,candidate)
    if type(reference.get('prefix_only'))!=bool:raise ValueError('Explicit prefix_only required')
    alignment=reference.get('alignment','ordinal')
    if alignment not in ('ordinal','step'):raise ValueError('Invalid event alignment')
    if event_root is None or reference_root is None:raise ValueError('Both local stream roots required')
    observed=candidate.get('trace') or candidate
    nat=observed.get('event_stream_manifest')
    ext=reference.get('event_stream_manifest')
    if not isinstance(nat,dict) or nat.get('status')!='COMPLETE':
        raise ValueError('Candidate full event stream unavailable')
    if not isinstance(ext,dict) or ext.get('status')!='COMPLETE':
        raise ValueError('External full event stream unavailable')
    from itertools import zip_longest
    sentinel=object(); mismatches=[];matched=0;drift=[];missing=0;index=0
    refcount=ext.get('count');nativecount=nat.get('count')
    for expected,got in zip_longest(iter_verified(reference_root,ext),iter_verified(event_root,nat),fillvalue=sentinel):
        if expected is sentinel:
            # Must consume the entire native stream to verify final metadata,
            # but extra candidate events are fine for a reference prefix.
            if not reference['prefix_only']:
                if len(mismatches)<100:mismatches.append({'event_index':index,'field':'additional_native_event','observed':got})
            index+=1;continue
        if got is sentinel:
            missing+=1;index+=1;continue
        for field in ('kind','address','value','pc')+(('step',) if alignment=='step' else ()):
            if expected[field]!=got[field]:
                if len(mismatches)<100:mismatches.append({'event_index':index,'field':field,'expected':expected[field],'observed':got[field]})
            else:matched+=1
        if expected['step']!=got['step'] and len(drift)<32:
            drift.append({'event_index':index,'reference_step':expected['step'],'native_step':got['step']})
        index+=1
    cp_expected=reference.get('checkpoints',[])
    if not isinstance(cp_expected,list) or len(cp_expected)>128:raise ValueError('Invalid stream checkpoint list')
    cp_mismatch,cp_matched,cp_missing=_checkpoint_fields(cp_expected,observed.get('checkpoints',[]))
    mismatches.extend(cp_mismatch[:max(0,100-len(mismatches))]);matched+=cp_matched
    # Optional final exact hardware-state hashes; no ROM or VRAM bytes distributed.
    final=reference.get('final_hardware_sha256',{})
    if not isinstance(final,dict) or any(region not in HARDWARE_REGIONS for region in final):
        raise ValueError('Invalid external hardware regions')
    for region,digest in final.items():
        if not isinstance(digest,str) or not re.fullmatch('[0-9a-fA-F]{64}',digest):raise ValueError('Invalid hardware SHA-256')
        got=(observed.get('hardware_sha256') or {}).get(region)
        if digest!=got:
            if len(mismatches)<100:mismatches.append({'field':'hardware_sha256.'+region,'expected':digest,'observed':got})
        else:matched+=1
    if nativecount!=observed.get('events_total'):raise ValueError('Native event counts do not match')
    if refcount!=reference.get('event_stream_manifest',{}).get('count'):raise ValueError('External event counts do not match')
    status=('DIVERGED' if mismatches else 'INCOMPLETE_EVENT_COVERAGE' if missing or cp_missing
            else 'MATCHED_EVENT_PREFIX' if reference['prefix_only'] else 'MATCHED_EVENT_TRACE')
    return {'schema':'recomp-parity-comparison-v3','status':status,'source_sha256':ident,
            'independent_source':reference['independent_source'],'alignment':alignment,
            'reference_events':refcount,'candidate_events_total':nativecount,
            'candidate_full_stream_verified':True,'compared_fields':matched,
            'mismatches':mismatches[:100],'mismatch_count_at_least':len(mismatches),
            'missing_events':missing,'missing_steps':cp_missing[:100],
            'step_drift':drift,'prefix_only':reference['prefix_only'],
            'scope':'SHA-attested ordered hardware effects. Producer independence and exact CPU/VDP semantics require external validation.'}


def compare(reference,candidate,event_root=None,reference_root=None):
    if not isinstance(reference,dict):raise ValueError('Reference JSON object required')
    if reference.get('schema')==SCHEMA:return compare_checkpoints(reference,candidate)
    if reference.get('schema')==EVENT_SCHEMA:return compare_events(reference,candidate,event_root)
    if reference.get('schema')==STREAM_SCHEMA:return compare_stream(reference,candidate,event_root,reference_root)
    raise ValueError('Unsupported independent reference schema')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference',required=True,help='External reference JSON (sampled checkpoints or ordered events)')
    p.add_argument('--candidate',required=True,help='Native pilot-report.json')
    p.add_argument('--output',help='Optional report JSON')
    a=p.parse_args()
    reference=json.loads(Path(a.reference).read_text(encoding='utf-8'))
    candidate=json.loads(Path(a.candidate).read_text(encoding='utf-8'))
    candidate_base=Path(a.candidate).resolve().parent
    trace=candidate.get('trace') or candidate
    rel=trace.get('event_stream_directory','')
    if rel:
        if not isinstance(rel,str) or not re.fullmatch(r'event-streams/attempt-\d{2}-budget-\d{1,7}',rel):
            raise ValueError('Unsafe event stream directory in report')
        candidate_base=candidate_base/rel
    result=compare(reference,candidate,event_root=candidate_base,reference_root=Path(a.reference).resolve().parent)
    message=json.dumps(result,indent=2)+'\n'
    if a.output:Path(a.output).write_text(message,encoding='utf-8')
    print(message)
    raise SystemExit(0 if result['status'] in ('MATCHED_SAMPLED_CHECKPOINTS','MATCHED_EVENT_PREFIX','MATCHED_EVENT_TRACE') else 1)

if __name__=='__main__':main()
