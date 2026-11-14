"""Hardware-neutral, offline whole-input interrogation and static frontier walker.

No game launch, emulator, native compilation, tool download, or ROM mutation.
Every decoded candidate is anchored to exact immutable source bytes; full
semantic, reachability and gameplay qualification are explicitly unavailable.
"""
from __future__ import annotations
import collections
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

# Direct execution via the compiled controller starts from this file's path.
if __package__ in (None, ''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from offline_analysis.model import ANALYSIS_ABI,Image,Instruction,Unresolved

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=Path(__file__).with_name('profiles.json')
MAX_INPUT=64*1024*1024
MAX_BUDGET=100000

class AnalysisFailure(Exception):pass

def _hash(data:bytes)->str:return hashlib.sha256(data).hexdigest()

def _read_json(path):return json.loads(path.read_text(encoding='utf8'))

def _plugin(name:str):
    # No arbitrary Python entrypoints or path traversal from a registry update.
    if not re.fullmatch(r'offline_analysis\.plugins\.[a-z][a-z0-9_]*',name):
        raise AnalysisFailure('PROVIDER_MODULE_OUTSIDE_REGISTERED_NAMESPACE')
    m=importlib.import_module(name)
    file=Path(m.__file__).resolve(strict=True)
    if file.parent!=ROOT/'offline_analysis'/'plugins' or file.is_symlink():
        raise AnalysisFailure('PROVIDER_SOURCE_OUTSIDE_PLUGIN_DIRECTORY')
    if getattr(m,'ANALYSIS_ABI',None)!=ANALYSIS_ABI:
        raise AnalysisFailure('PROVIDER_ABI_MISMATCH: '+name)
    return m,{'module':name,'source_sha256':_hash(file.read_bytes()),'abi':ANALYSIS_ABI}

def registry(path:Path=REGISTRY):
    d=_read_json(path)
    if d.get('schema')!='recompdev.offline.profiles.v1' or not isinstance(d.get('profiles'),list):
        raise AnalysisFailure('INVALID_PROFILE_REGISTRY')
    entries=d['profiles'];ids=set()
    for e in entries:
        if not isinstance(e,dict) or set(e)!={'id','format','cpu','machine'}:
            raise AnalysisFailure('INVALID_PROFILE_DESCRIPTOR')
        if not re.fullmatch('[a-z][a-z0-9-]{2,63}',e['id']) or e['id'] in ids:
            raise AnalysisFailure('DUPLICATE_OR_INVALID_PROFILE_ID')
        ids.add(e['id'])
    return entries

def _record_gap(gaps:list,seen:set,pc:int,reason:str):
    pair=(pc,reason)
    if pair not in seen and len(gaps)<MAX_BUDGET:
        seen.add(pair);gaps.append({'pc':pc,'reason':reason})

def _fetch(data,image,machine,state,addr,n):
    if not isinstance(n,int) or n<=0 or n>16:raise Unresolved('INVALID_INSTRUCTION_FETCH_LENGTH')
    r=bytearray()
    for delta in range(n):
        physical=machine.resolve(image,addr+delta,state)
        if not isinstance(physical,int) or physical<0 or physical>=len(data):
            raise Unresolved('SOURCE_ADDRESS_MAPPING_INVALID')
        r.append(data[physical])
    return bytes(r)

def _one_pass(data,image,cpu,machine,budget):
    todo=collections.deque((s.pc,machine.initial(image),False,s.reason) for s in image.entries)
    seen=set();visits=collections.Counter()
    records={};gaps=[];gap_seen=set();edges=0
    while todo and len(seen)<budget:
        pc,state,delay_only,seed=todo.popleft()
        key=(pc,machine.key(state),delay_only)
        if key in seen:continue
        seen.add(key)
        visits[pc]+=1
        if visits[pc]>64:
            _record_gap(gaps,gap_seen,pc,'ABSTRACT_CONTEXT_LIMIT')
            continue
        try:
            physical=machine.resolve(image,pc,state)
            ins=cpu.decode(lambda addr,n:_fetch(data,image,machine,state,addr,n),pc)
            if (not isinstance(ins,Instruction) or type(ins.length)!=int or not 1<=ins.length<=16 or
                ins.flow not in ('next','jump','branch','call','return','indirect','stop') or
                ins.delay_slots not in (0,1)):
                raise Unresolved('CPU_DECODE_ABI_INVALID')
            b=_fetch(data,image,machine,state,pc,ins.length)
            # Disallow decode ambiguities that overlap different source bytes at
            # the same physical position. This is a reportable conflict, not a
            # justification to discard the previously verified exact source.
            ident=(pc,physical)
            row={'pc':pc,'physical':physical,'length':ins.length,
                 'bytes_sha256':_hash(b),'flow':ins.flow,'target':ins.target,
                 'mnemonic':ins.mnemonic,'seed':seed,
                 'classification':'STATIC_DECODE_CANDIDATE_NOT_SEMANTICALLY_QUALIFIED'}
            old=records.get(ident)
            if old is not None and (old['length'],old['bytes_sha256'])!=(row['length'],row['bytes_sha256']):
                _record_gap(gaps,gap_seen,pc,'DECODE_CONFLICT_FOR_PHYSICAL_OFFSET')
                continue
            if old is None:records[ident]=row
            next_state,warnings=machine.transition(image,ins,state)
            for warning in warnings:
                _record_gap(gaps,gap_seen,pc,warning)
        except Unresolved as exc:
            _record_gap(gaps,gap_seen,pc,exc.reason)
            continue
        # Delay slot is decoded exactly once, without incorrectly following its
        # own fallthrough independently of the branch that executed it.
        after=pc+ins.length
        if ins.delay_slots:
            todo.append((after,state,True,'delay-slot'))
            edges+=1
            after+=ins.length*ins.delay_slots
        if delay_only:continue
        if ins.flow in ('next','branch','call') or (ins.flow=='return' and ins.conditional):
            next_seed='call-continuation-hypothesis' if ins.flow=='call' else 'static-fallthrough'
            todo.append((after,next_state,False,next_seed));edges+=1
        if ins.flow in ('jump','branch','call'):
            if ins.target is None:
                _record_gap(gaps,gap_seen,pc,'UNRESOLVED_DIRECT_BRANCH')
            else:
                todo.append((ins.target,next_state,False,'direct-control-flow'))
                edges+=1
        if ins.flow=='indirect':_record_gap(gaps,gap_seen,pc,'INDIRECT_TARGET_UNRESOLVED')
        if ins.flow=='return':_record_gap(gaps,gap_seen,pc,'RETURN_TARGET_NOT_STOCKED')
    if todo:_record_gap(gaps,gap_seen,todo[0][0],'WORKLIST_BUDGET_EXHAUSTED')
    results=sorted(records.values(),key=lambda r:(r['physical'],r['pc']))
    gaps.sort(key=lambda r:(r['pc'],r['reason']))
    return results,gaps,edges

def _candidates(data,image,cpu,machine,max_probes=512):
    """Look at possible orphan-bank entry bytes without blessing them as code."""
    out=[]
    for ix,(label,pc,state) in enumerate(machine.probes(image)):
        if ix>=max_probes:break
        try:
            physical=machine.resolve(image,pc,state)
            ins=cpu.decode(lambda addr,n:_fetch(data,image,machine,state,addr,n),pc)
            b=_fetch(data,image,machine,state,pc,ins.length)
            out.append({'candidate':label,'pc':pc,'physical':physical,'length':ins.length,
                        'bytes_sha256':_hash(b),'status':'UNVERIFIED_ORPHAN_ENTRY_HYPOTHESIS'})
        except Unresolved as e:
            out.append({'candidate':label,'pc':pc,'status':'UNRESOLVED','reason':e.reason})
    return out

def interrogate(source:Path,output:Path,*,budget:int=40000,profile:str|None=None)->dict:
    source=Path(source).absolute();output=Path(output).absolute()
    if source.is_symlink() or not source.is_file():raise AnalysisFailure('REGULAR_SOURCE_FILE_REQUIRED')
    size=source.stat().st_size
    if not 0<size<=MAX_INPUT:raise AnalysisFailure('SOURCE_SIZE_OUTSIDE_64M_LIMIT')
    if not 1<=budget<=MAX_BUDGET:raise AnalysisFailure('INVALID_INSTRUCTION_BUDGET')
    if output.exists():raise AnalysisFailure('OUTPUT_EXISTS_REFUSING_OVERWRITE')
    data=source.read_bytes()
    if len(data)!=size:raise AnalysisFailure('SOURCE_CHANGED_DURING_READ')
    original=_hash(data)
    profiles=registry()
    selected=[]
    for desc in profiles:
        if profile is not None and desc['id']!=profile:continue
        fmt,meta=_plugin(desc['format'])
        image=fmt.inspect(data)
        if image is not None:
            if not isinstance(image,Image) or image.profile!=desc['id']:
                raise AnalysisFailure('FORMAT_PLUGIN_RESULT_INVALID')
            selected.append((desc,image,meta))
    if profile is not None and not any(d['id']==profile for d in profiles):
        raise AnalysisFailure('UNKNOWN_REQUESTED_PROFILE')
    if len(selected)>1:raise AnalysisFailure('AMBIGUOUS_FORMAT_PROVIDERS')
    report={'schema':'recompdev.offline.analysis.v1','release':'workspace/v0.4.9.35',
            'source_sha256':original,'source_bytes':len(data),
            'launches_game':False,'requires_gameplay_discovery':False,
            'semantic_parity_qualified':False,'whole_game_code_coverage_qualified':False,
            'native_compilation_performed':False,'standalone_export_ready':False,
            'qualification':'SOURCE_HASHED_STATIC_ANALYSIS_ONLY',
            'source_filename':source.name}
    instructions=[];gaps=[];hypotheses=[];inventory=[];edges=0
    if not selected:
        report.update(status='UNSUPPORTED_FORMAT',supported_profiles=[x['id'] for x in profiles],
                      recognition='NO_PLUGIN_CLAIMED_SOURCE',instructions=0,unresolved=0)
    else:
        desc,image,format_meta=selected[0]
        cpu,cpu_meta=_plugin(desc['cpu']);machine,machine_meta=_plugin(desc['machine'])
        if not all(callable(getattr(cpu,k,None)) for k in ('decode',)) or not all(
                callable(getattr(machine,k,None)) for k in ('initial','key','resolve','transition','inventory','probes')):
            raise AnalysisFailure('PLUGIN_CONTRACT_METHOD_MISSING')
        instructions,gaps,edges=_one_pass(data,image,cpu,machine,budget)
        hypotheses=_candidates(data,image,cpu,machine)
        inventory=machine.inventory(image,data)
        visited_offsets=set()
        for row in instructions:visited_offsets.update(range(row['physical'],row['physical']+row['length']))
        for region in inventory:
            start=region['start'];stop=start+region['bytes']
            region['static_candidate_bytes']=sum(start<=offset<stop for offset in visited_offsets)
            region['static_candidate_instructions']=sum(start<=r['physical']<stop for r in instructions)
            region['coverage_qualified']=False
        report.update(status='ANALYSED_PARTIAL' if gaps else 'ANALYSED_STATIC_CANDIDATES',
                      profile=image.profile,cpu=image.cpu,machine=image.machine,
                      plugin_provenance={'format':format_meta,'cpu':cpu_meta,'machine':machine_meta},
                      image_details=image.details,entry_points=[s.__dict__ for s in image.entries],
                      decoded_candidates=len(instructions),static_candidate_bytes=len(visited_offsets),
                      total_source_bytes=len(data),unresolved=len(gaps),control_flow_edges=edges,
                      possible_orphan_entries=len(hypotheses),instruction_budget=budget,
                      status_note='Bytes and lengths attested; static CFG is not proof of reachability or semantics.')
    # Re-read before publishing any report. Never write to the input file.
    if _hash(source.read_bytes())!=original:raise AnalysisFailure('SOURCE_CHANGED_DURING_OFFLINE_ANALYSIS')
    output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_name(output.name+'.partial-'+str(os.getpid()))
    if temp.exists():raise AnalysisFailure('STAGING_DESTINATION_ALREADY_EXISTS')
    temp.mkdir()
    try:
        def save(name,value):
            path=temp/name
            content=(json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False)+'\n').encode('utf8')
            path.write_bytes(content)
            return {'file':name,'bytes':len(content),'sha256':_hash(content)}
        members={}
        for name,value in (('instructions.json',instructions),('unresolved.json',gaps),
                           ('bank-inventory.json',inventory),('orphan-hypotheses.json',hypotheses)):
            members[name]=save(name,value)
        report['artifacts']=members
        save('analysis.json',report)
        temp.rename(output)
    except Exception:
        import shutil
        shutil.rmtree(temp,ignore_errors=True)
        raise
    return report
