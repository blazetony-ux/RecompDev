"""Source-keyed, read-only reconciliation of native pilots and host sessions.

No score here claims behavioural correctness. Old job paths are untrusted, and
observations are imported only after source identity and artifact checks.
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from nativecore.eventstream import iter_verified

SHA = re.compile(r'[0-9a-f]{64}\Z')
VERSION = re.compile(r'RecompDev-v0\.4\.0\.\d+\Z')
JOB = re.compile(r'[0-9a-f]{16}\Z')
MAX_DOC = 4*1024*1024

def _sha(file):
    digest=hashlib.sha256()
    with open(file,'rb') as stream:
        for blob in iter(lambda:stream.read(1024*1024),b''):digest.update(blob)
    return digest.hexdigest()

def _load(file):
    if file.is_symlink() or not file.is_file() or file.stat().st_size>MAX_DOC:
        raise ValueError('Missing, symlinked or oversized document')
    return json.loads(file.read_text(encoding='utf-8'))

def _job_directories(installs,limit=100):
    """Allow only well-formed immutable job roots in sibling, numbered installs."""
    if not isinstance(installs,(tuple,list)) or len(installs)>32:raise ValueError('Invalid installation roots')
    for install in installs:
        install=Path(install).resolve()
        if not VERSION.fullmatch(install.name):continue
        evidence=install/'evidence'
        if not evidence.is_dir() or evidence.is_symlink():continue
        for root in sorted(evidence.glob('native-pilot-v*/jobs'),reverse=True):
            if root.is_symlink() or not re.fullmatch('native-pilot-v[0-9]+',root.parent.name):continue
            if root.resolve()!=root or not root.is_dir():continue
            jobs=sorted((p for p in root.iterdir() if p.is_dir() and not p.is_symlink() and JOB.fullmatch(p.name)),
                key=lambda p:p.stat().st_mtime,reverse=True)
            for job in jobs[:limit]:yield job

def inspect_native_job(folder,source_sha,check_events=True):
    """Revalidate original source identity and complete chunks, not a report's PASS text."""
    if not isinstance(source_sha,str) or not SHA.fullmatch(source_sha):raise ValueError('Invalid source SHA')
    folder=Path(folder).resolve()
    doc=_load(folder/'pilot-report.json')
    if doc.get('source_id')!=source_sha:
        raise ValueError('Pilot source hash differs')
    trace=doc.get('trace') or {}
    if not isinstance(trace,dict):raise ValueError('Invalid trace')
    stream=trace.get('event_stream_manifest') or {}
    events='NOT_CAPTURED'
    if stream.get('status')=='COMPLETE':
        relative=trace.get('event_stream_directory')
        if not isinstance(relative,str) or '\\' in relative or not relative.startswith('event-streams/'):
            raise ValueError('Untrusted event directory')
        candidate=(folder/relative).resolve()
        if folder not in candidate.parents or candidate.is_symlink():raise ValueError('Event directory escaped job')
        if check_events:
            count=sum(1 for _ in iter_verified(candidate,stream))
            if count!=stream.get('count'):raise ValueError('Complete event stream count mismatch')
            events='SHA256_VERIFIED_FULL_STREAM'
        else:events='UNVERIFIED_DECLARATION'
    elif stream.get('status') in ('INCOMPLETE',None):events='NOT_COMPLETE'
    else:raise ValueError('Unknown stream state')
    generation=doc.get('generation') or {}
    return {'source_sha256':source_sha,'job_id':folder.name,'install':folder.parents[3].name if len(folder.parents)>3 else 'unknown',
            'native_status':str(doc.get('status','UNKNOWN'))[:90],
            'translated_instructions':doc.get('translated_instructions',0),
            'native_steps':doc.get('native_steps',0),
            'bank_exports_reused':doc.get('reused_bank_exports',0),
            'unresolved_dependency_edges':(doc.get('dependency_graph') or {}).get('unresolved_edges'),
            'events':trace.get('events_total',0),'event_integrity':events,
            'generated_app_reported':bool((doc.get('native_app') or {}).get('executable')),
            'native_qualified':False,'reference_parity':doc.get('reference_parity','NOT_TESTED'),
            'gameplay':'NOT_ESTABLISHED',
            'report_path':str(folder/'pilot-report.json')}

def inspect_session(folder,source_sha):
    doc=_load(Path(folder)/'continuous-session.json')
    if doc.get('schema')!='recomp-continuous-owner-session-v1' or doc.get('source_sha256')!=source_sha:
        raise ValueError('Session source identity does not match')
    assets=doc.get('assets',{})
    # Null outputs intentionally have no PPM/WAV files, but must still carry
    # bounded native step/cycle/state evidence. Old v0424 reports are accepted.
    if doc.get('host_mode')=='HEADLESS_AUTONOMOUS':
        for media,asset,discarded in (
            ('video_backend','ppm','discarded_frames'),
            ('audio_backend','wav','discarded_audio_samples')):
            if doc.get(media)=='null':
                if asset in doc.get('assets',{}):raise ValueError('Null presentation unexpectedly emitted '+asset)
                expected=doc.get('frames') if asset=='ppm' else doc.get('audio_samples')
                if doc.get(discarded)!=expected:raise ValueError('Null output accounting mismatch: '+asset)
        if not isinstance(doc.get('guest_state_fingerprint'),int):
            raise ValueError('Missing null-mode guest state fingerprint')
    for suffix in ('ppm','wav'):
        item=assets.get(suffix)
        if item:
            file=Path(folder)/('native-frame.'+suffix)
            if file.is_symlink() or not file.is_file() or file.stat().st_size!=item.get('size') or _sha(file)!=item.get('sha256'):
                raise ValueError('Session asset hash mismatch: '+suffix)
    return {'status':doc['status'],'native_steps':doc['native_steps'],'frames':doc['frames'],
            'audio_samples':doc['audio_samples'],'source_sha256':source_sha,
            'asset_integrity':'SHA256_VERIFIED' if assets else 'NO_PRESENTATION_ASSETS_BY_DESIGN',
            'guest_state_fingerprint':doc.get('guest_state_fingerprint'),
            'host_mode':doc.get('host_mode','LEGACY'),
            'reference_parity':'NOT_TESTED','native_qualified':False}

def _integrated_history(source_sha, installations, max_jobs=12):
    sessions=[];rejected=[]
    for install in installations:
        install=Path(install).resolve()
        if not VERSION.fullmatch(install.name):continue
        # Discover new versioned campaign roots instead of hard-coding releases.
        evidence_root=install/'evidence'
        roots=[]
        if evidence_root.is_dir() and not evidence_root.is_symlink():
            roots=[p/'jobs' for p in evidence_root.glob('integrated-native-v*')
                   if p.is_dir() and not p.is_symlink()
                   and re.fullmatch(r'integrated-native-v[0-9]{4}',p.name)]
        jobs=[]
        for root in roots:
            if root.is_dir() and not root.is_symlink():
                jobs.extend(x for x in root.iterdir() if x.is_dir() and not x.is_symlink() and JOB.fullmatch(x.name))
        jobs=sorted(jobs,key=lambda p:p.stat().st_mtime,reverse=True)
        for job in jobs[:max_jobs]:
            file=job/'campaign-result.json'
            if not file.is_file():continue
            try:
                data=_load(file)
                if data.get('source_sha256')!=source_sha:continue
                if data.get('schema')!='recomp-end-to-end-campaign-v0424':raise ValueError('Unrecognized campaign schema')
                pilot=inspect_native_job(job/'pilot',source_sha)
                session=None
                if (job/'host'/'continuous-session.json').is_file():session=inspect_session(job/'host',source_sha)
                sessions.append({'job_id':job.name,'status':data.get('status'),
                     'native_pilot':pilot['native_status'],'event_integrity':pilot['event_integrity'],
                     'translated_instructions':pilot['translated_instructions'],
                     'unresolved_dependency_edges':pilot['unresolved_dependency_edges'],
                     'native_steps':session['native_steps'] if session else pilot['native_steps'],
                     'frames':session['frames'] if session else 0,
                     'host':session,'reference_parity':'NOT_ESTABLISHED','native_qualified':False})
            except (ValueError,OSError,KeyError,TypeError,json.JSONDecodeError) as exc:
                rejected.append({'job':job.name,'reason':str(exc)[:140]})
            if len(sessions)>=max_jobs:break
    return sessions,rejected

def history(source_sha,installations,max_jobs=12,check_events=True):
    if not SHA.fullmatch(source_sha):raise ValueError('Invalid source')
    result=[];blocked=[]
    for folder in _job_directories(installations):
        report=folder/'pilot-report.json'
        if not report.is_file():continue
        try:
            # Cheap identification before expensive event integrity checking.
            doc=_load(report)
            if doc.get('source_id')!=source_sha:continue
            result.append(inspect_native_job(folder,source_sha,check_events))
        except (ValueError,OSError,KeyError,TypeError,json.JSONDecodeError) as exc:
            blocked.append({'job':folder.name,'reason':str(exc)[:140]})
        if len(result)>=max_jobs:break
    sessions,rejected=_integrated_history(source_sha,installations,max_jobs)
    return {'schema':'recomp-source-history-v0424','source_sha256':source_sha,
            'pilots':result,'integrated_campaigns':sessions,'rejected_evidence':(blocked+rejected)[:15],
            'native_qualified':False,'gameplay':'NOT_ESTABLISHED',
            'note':'Prior pilot counts are observational; no completed game parity is inferred.'}
