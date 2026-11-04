"""Evidence-only cross-game and Z80 control-flow triage.

No inference about MAME parity, gameplay correctness, or valid RAM code execution.
A source-authenticated native trace is not an independent reference trace.
"""
from pathlib import Path
import hashlib
import json

FIELDS=('step','pc_before','pc_after','physical_offset','sp_before','sp_after',
        'stack_word_before','iff1_before','iff2_before','mapper_before',
        'interrupt_count_before','interrupt_count_after','opcode_class','kind',
        'vdp_writes_before','psg_writes_before','cram_writes_before')

def _load(path):
    p=Path(path).resolve(strict=True)
    if not p.is_file() or p.stat().st_size>8_000_000:raise ValueError('Unbounded or missing evidence file')
    return json.loads(p.read_text(encoding='utf-8'))

def analyze_session(doc):
    if not isinstance(doc,dict):raise ValueError('Invalid native session')
    sha=doc.get('source_sha256')
    if not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):
        raise ValueError('Native session has no source identity')
    tail=doc.get('trace_tail',[])
    if not isinstance(tail,list) or len(tail)>256 or any(not isinstance(e,dict) for e in tail):
        raise ValueError('Invalid bounded transition history')
    if any(type(e.get('pc_before'))!=int or type(e.get('pc_after'))!=int or not 0<=e['pc_before']<=65535 or not 0<=e['pc_after']<=65535 for e in tail):
        raise ValueError('Invalid PC in native transition')
    per_frame=doc.get('frame_hardware',[])
    if not isinstance(per_frame,list) or len(per_frame)>36000 or any(not isinstance(f,dict) for f in per_frame):
        raise ValueError('Invalid frame hardware evidence')
    status=doc.get('status','UNKNOWN')
    summary={'schema':'recomp-session-triage-v0436','source_sha256':sha,
             'status':status,'native_steps':doc.get('native_steps'), 'frames':doc.get('frames'),
             'last_pc':doc.get('pc'),'transition_count':len(tail),
             'frame_hardware_count':len(per_frame),
             'final_frame_hardware':per_frame[-1] if per_frame else None,
             'reference_parity':'NOT_ESTABLISHED','root_cause':'NOT_ESTABLISHED',
             'gameplay':'NOT_ESTABLISHED','findings':[],'entry_provenance':None,
             'latest_transitions':[{k:t.get(k) for k in FIELDS} for t in tail[-8:]]}
    if status=='RAM_EXECUTION_NOT_TRANSLATED':
        entry=next((e for e in reversed(tail[:-1]) if e.get('pc_after')==doc.get('pc')),None)
        if entry:
            summary['entry_provenance']={k:entry.get(k) for k in FIELDS}
            summary['findings'].append('RAM_PC_PREDECESSOR_OBSERVED_NOT_PROVEN_CORRECT')
        else:summary['findings'].append('RAM_ENTRY_PREDECESSOR_NOT_IN_BOUNDED_HISTORY')
        summary['findings'].append('RAM_EXECUTION_NOT_PROVEN_OR_TRANSLATED')
    if tail:
        first,last=tail[0],tail[-1]
        for metric,tag in [('vdp_writes_before','NO_LATE_VDP_ACTIVITY_IN_TRACE_WINDOW'),
                           ('psg_writes_before','NO_LATE_PSG_ACTIVITY_IN_TRACE_WINDOW')]:
            if first.get(metric) is not None and last.get(metric)==first.get(metric) and len(tail)>=32:
                summary['findings'].append(tag)
        if any(e.get('interrupt_count_after',0)>e.get('interrupt_count_before',0) for e in tail):
            summary['findings'].append('MASKABLE_IRQ_ACCEPTANCE_IN_TRACE_WINDOW')
    if len(per_frame)>=2:
        last=per_frame[-1];before=per_frame[-2]
        for field,label in [('vdp_writes','NO_VDP_WRITES_IN_LAST_FRAME_INTERVAL'),
                            ('psg_writes','NO_PSG_WRITES_IN_LAST_FRAME_INTERVAL')]:
            if type(last.get(field))==int and last[field]==before.get(field):
                summary['findings'].append(label)
    if doc.get('cram_nonzero_bytes')==0:
        summary['findings'].append('PALETTE_UNPOPULATED_AT_END_OF_SESSION')
    if doc.get('video_backend')=='null':
        summary['findings'].append('NO_CAPTURED_FRAME_HASHES_NULL_VIDEO_BACKEND')
    if doc.get('reference_parity')!='NOT_TESTED':
        raise ValueError('Native session includes unexpected reference parity assertion')
    return summary

def analyze_campaign(campaign,root):
    """Scan only bounded named session evidence in the owner campaign folder."""
    if not isinstance(campaign,dict) or not isinstance(campaign.get('games'),list) or len(campaign['games'])>32:
        raise ValueError('Invalid campaign')
    root=Path(root).resolve(strict=True)
    games=[]
    for g in campaign['games']:
        slug=g.get('slug','')
        if not isinstance(slug,str) or not slug or any(x not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for x in slug):
            raise ValueError('Invalid campaign slug')
        folders=(root/slug/'recovery'/'sessions')
        sessions=sorted(folders.glob('attempt-*/continuous-session.json')) if folders.exists() else []
        report=None
        if sessions:
            report=analyze_session(_load(sessions[-1]))
        games.append({'slug':slug,'game':g.get('game'),'campaign_status':g.get('status'),
                      'session_triage':report})
    patterns={}
    for g in games:
        if g['session_triage']:
            for finding in g['session_triage']['findings']:
                patterns.setdefault(finding,[]).append(g['slug'])
    return {'schema':'recomp-cross-game-triage-v0436', 'source_campaign_schema':campaign.get('schema'),
            'games':games,'shared_observations':{k:v for k,v in patterns.items() if len(v)>=2},
            'causal_attribution':'NOT_ESTABLISHED','reference_parity':'NOT_ESTABLISHED',
            'note':'Shared symptoms only; no causal relationship is asserted.'}
