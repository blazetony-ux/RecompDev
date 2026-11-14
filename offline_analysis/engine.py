"""Hardware-neutral, offline whole-input interrogation and static frontier walker.

No game launch, emulator, native compilation, tool download, or ROM mutation.
Every decoded candidate is anchored to exact immutable source bytes; full
semantic, reachability and gameplay qualification are explicitly unavailable.
"""
from __future__ import annotations
import collections
from dataclasses import replace
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

def release_identity():
    # One source of truth; old scan receipts must not retain a hard-coded release.
    from workspace.release_identity import release
    return release(ROOT)

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
    """One hardware-neutral abstract traversal over CPU facts + machine mapping.

    CPU providers alone interpret register constants/indirect targets; machine
    providers alone interpret physical addresses and memory mapping. Bounded
    call contexts recover returns. Unknown callees retain a separately marked
    speculative continuation rather than silently claiming reachability.
    """
    MAX_RETURN_DEPTH=16
    MAX_CONTEXTS_PER_PC=96
    # pc, machine state, CPU abstract facts, return stack, seed, speculative
    todo=collections.deque((s.pc,machine.initial(image),cpu.initial(image),(),s.reason,False)
                           for s in image.entries)
    seen=set();visits=collections.Counter()
    records={};gaps=[];gap_seen=set();edges=0
    resolved_returns=set();resolved_indirect=set();delay_slots=set()
    def record(pc,physical,ins,raw,seed,speculative):
        ident=(pc,physical)
        row={'pc':pc,'physical':physical,'length':ins.length,
             'bytes_sha256':_hash(raw),'flow':ins.flow,'target':ins.target,
             'mnemonic':ins.mnemonic,'seed':seed,
             'classification':('SPECULATIVE_CALL_CONTINUATION_NOT_REACHABILITY_PROOF'
                               if speculative else 'STATIC_DECODE_CANDIDATE_NOT_SEMANTICALLY_QUALIFIED')}
        old=records.get(ident)
        if old is not None and (old['length'],old['bytes_sha256'])!=(row['length'],row['bytes_sha256']):
            _record_gap(gaps,gap_seen,pc,'DECODE_CONFLICT_FOR_PHYSICAL_OFFSET')
            return False
        if old is None or (old['classification'].startswith('SPECULATIVE') and not speculative):
            records[ident]=row
        return True
    def decode(pc,ms,regs,seed,speculative):
        physical=machine.resolve(image,pc,ms)
        ins=cpu.decode(lambda address,n:_fetch(data,image,machine,ms,address,n),pc)
        if (not isinstance(ins,Instruction) or type(ins.length)!=int or not 1<=ins.length<=16 or
            ins.flow not in ('next','jump','branch','call','return','indirect','stop') or
            ins.delay_slots not in (0,1)):
            raise Unresolved('CPU_DECODE_ABI_INVALID')
        raw=_fetch(data,image,machine,ms,pc,ins.length)
        if not record(pc,physical,ins,raw,seed,speculative):
            raise Unresolved('DECODE_CONFLICT_FOR_PHYSICAL_OFFSET')
        return ins
    def add(pc,ms,regs,returns,seed,speculative):
        nonlocal edges
        todo.append((pc,ms,regs,returns,seed,speculative));edges+=1
    while todo and len(seen)<budget:
        pc,ms,regs,returns,seed,speculative=todo.popleft()
        key=(pc,machine.key(ms),cpu.key(regs),returns,speculative)
        if key in seen:continue
        seen.add(key)
        context_key=(pc,machine.key(ms))
        visits[context_key]+=1
        if visits[context_key]>MAX_CONTEXTS_PER_PC:
            _record_gap(gaps,gap_seen,pc,'ABSTRACT_CONTEXT_LIMIT');continue
        try:
            ins=decode(pc,ms,regs,seed,speculative)
            # Targets of computed branches are read before the delay slot:
            # instructions inside that slot may overwrite the source register.
            indirect_target=(cpu.indirect(ins,regs) if ins.flow in ('indirect','return','call')
                             and ins.target is None else None)
            next_ms,warnings=machine.transition(image,ins,ms,regs)
            next_regs=cpu.advance(ins,regs)
            other_ms=other_regs=None
            if ins.conditional and ins.flow in ('call','return'):
                # Untaken conditional CALL/RET must not change the emulated
                # stack or link register. Never borrow its taken-path facts.
                neutral={k:v for k,v in ins.effects.items()
                         if k not in ('stack_push','stack_pop','link_reg')}
                other_ins=replace(ins,effects=neutral)
                other_ms,other_warn=machine.transition(image,other_ins,ms,regs)
                other_regs=cpu.advance(other_ins,regs)
                for reason in other_warn:_record_gap(gaps,gap_seen,pc,reason)
            for reason in warnings:_record_gap(gaps,gap_seen,pc,reason)
            after=pc+ins.length
            if ins.delay_slots:
                slot=decode(after,next_ms,next_regs,'delay-slot',speculative)
                if slot.delay_slots or slot.flow!='next':
                    _record_gap(gaps,gap_seen,after,'CONTROL_TRANSFER_OR_STOP_IN_DELAY_SLOT')
                    continue
                delay_slots.add(after)
                slot_ms,slot_warnings=machine.transition(image,slot,next_ms,next_regs)
                for reason in slot_warnings:_record_gap(gaps,gap_seen,after,reason)
                next_regs=cpu.advance(slot,next_regs)
                next_ms=slot_ms
                if other_ms is not None:
                    # A different machine mapping for the alternate path
                    # invalidates a shared delay-slot assumption.
                    other_slot=cpu.decode(lambda address,n:_fetch(data,image,machine,other_ms,address,n),after)
                    if other_slot.length!=slot.length or other_slot.flow!='next':
                        raise Unresolved('CONDITIONAL_DELAY_SLOT_CONTEXT_CONFLICT')
                    other_ms,other_warn=machine.transition(image,other_slot,other_ms,other_regs)
                    other_regs=cpu.advance(other_slot,other_regs)
                    for reason in other_warn:_record_gap(gaps,gap_seen,after,reason)
                after+=slot.length
        except Unresolved as exc:
            _record_gap(gaps,gap_seen,pc,exc.reason)
            continue
        if ins.flow=='stop':continue
        if ins.flow in ('next','branch'):
            add(after,next_ms,next_regs,returns,'static-fallthrough',speculative)
        if ins.flow in ('jump','branch','call','indirect'):
            target=ins.target if ins.target is not None else indirect_target
            if target is None:
                _record_gap(gaps,gap_seen,pc,'INDIRECT_TARGET_UNRESOLVED' if
                            ins.flow in ('indirect','call') else 'UNRESOLVED_DIRECT_BRANCH')
            elif ins.flow=='call':
                if len(returns)>=MAX_RETURN_DEPTH:
                    _record_gap(gaps,gap_seen,pc,'RETURN_STACK_BOUND_EXCEEDED')
                else:
                    add(target,next_ms,next_regs,returns+(after,),'call-target',speculative)
                    if indirect_target is not None:resolved_indirect.add(pc)
            else:
                add(target,next_ms,next_regs,returns,
                    'abstract-register-target' if indirect_target is not None else 'direct-control-flow',
                    speculative)
                if indirect_target is not None:resolved_indirect.add(pc)
        if ins.flow=='call':
            # A callee might fail to return or change any known state. Explore
            # caller continuation as a clearly marked *hypothesis* (not an
            # endorsed reachable edge). No CPU constant survives this fallback.
            if ins.conditional:
                add(after,other_ms,other_regs,returns,'conditional-call-not-taken',speculative)
            else:
                add(after,next_ms,cpu.initial(image),returns,
                    'unverified-callee-continuation',True)
        if ins.flow=='return':
            if ins.conditional:
                add(after,other_ms,other_regs,returns,'conditional-return-not-taken',speculative)
            if returns:
                expected=returns[-1]
                if indirect_target is not None and expected!=indirect_target:
                    _record_gap(gaps,gap_seen,pc,'LINK_REGISTER_RETURN_MISMATCH')
                    add(indirect_target,next_ms,next_regs,returns,'link-register-target',True)
                else:
                    resolved_returns.add(pc)
                    add(expected,next_ms,next_regs,returns[:-1],'matched-call-return',speculative)
            elif indirect_target is not None:
                resolved_indirect.add(pc)
                add(indirect_target,next_ms,next_regs,returns,'register-return-target',True)
            else:
                _record_gap(gaps,gap_seen,pc,'RETURN_TARGET_NOT_STOCKED')
    if todo:_record_gap(gaps,gap_seen,todo[0][0],'WORKLIST_BUDGET_EXHAUSTED')
    results=sorted(records.values(),key=lambda r:(r['physical'],r['pc']))
    gaps.sort(key=lambda r:(r['pc'],r['reason']))
    evidence={'resolved_return_sites':len(resolved_returns),
              'resolved_indirect_sites':len(resolved_indirect),
              'delay_slots_decoded':len(delay_slots),
              'speculative_instruction_candidates':sum(x['classification'].startswith('SPECULATIVE') for x in results),
              'abstract_contexts_visited':len(seen),
              'max_call_depth':MAX_RETURN_DEPTH,
              'provider_abstract_state_abi':ANALYSIS_ABI}
    return results,gaps,edges,evidence

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
    report={'schema':'recompdev.offline.analysis.v1','release':release_identity(),
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
        if not all(callable(getattr(cpu,k,None)) for k in ('decode','initial','key','advance','indirect')) or not all(
                callable(getattr(machine,k,None)) for k in ('initial','key','resolve','transition','inventory','probes')):
            raise AnalysisFailure('PLUGIN_CONTRACT_METHOD_MISSING')
        instructions,gaps,edges,abstract_evidence=_one_pass(data,image,cpu,machine,budget)
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
                      abstract_execution=abstract_evidence,
                      status_note='Bounded abstract CFG with speculation explicitly classified; no reachability, semantics or gameplay qualification.')
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
