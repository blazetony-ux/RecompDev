"""Owner-local seeded discovery, all systems through container/ISA adapters.

Emits metadata-only observations and call/transfer graph. Never contains ROM bytes.
"""
import hashlib
import json
from collections import deque
from pathlib import Path
from adapters.formats import open_image
from adapters.isa import make_capstone, classify_operands
from adapters.flow import classify, Flow
from adapters.indirect import recover as recover_local_targets
from graph_store import connect,import_scan
from target_names import migrate,update,megadrive_title


def decode(engine,image,pc):
    if not image.valid(pc):return None
    offset=image.offset(pc)
    room=min(image.stop-pc, 16, len(image.data)-offset)
    if room<image.alignment:return None
    try:
        ins=next(iter(engine.disasm(image.data[offset:offset+room],pc,count=1)),None)
    except (ValueError,IndexError):return None
    if ins is None or ins.address!=pc or ins.size<image.alignment or pc+ins.size>image.stop:return None
    return ins


def _discover_once(image,engine,max_instructions=250000, extra_seeds=(), resolved=None):
    resolved=resolved or {}
    seeds=[image.entry,*extra_seeds]
    for s in seeds:
        if not image.valid(s):raise ValueError(f'invalid entry seed: 0x{s:x}')
    q=deque(seeds);instr={};edges=set();barriers=set();slots={}
    while q and len(instr)<max_instructions:
        pc=q.popleft()
        if pc in instr:continue
        ins=decode(engine,image,pc)
        if not ins:
            barriers.add((pc,'decoder rejected candidate / unmapped address'))
            continue
        flow=classify(image,ins)
        if pc in resolved:
            recovered=resolved[pc]
            if flow.kind not in ('indirect_call','indirect_jump'):
                raise ValueError('recovered edge no longer matches indirect control transfer')
            continuations=[(x,k) for x,k in flow.edges if k=='return_site']
            flow=Flow('recovered_'+flow.kind,
                [(recovered['target'],recovered['kind']),*continuations],None,flow.delay_slot)
        instr[pc]=(ins,flow)
        if flow.barrier: barriers.add((pc,flow.barrier))
        if flow.delay_slot:
            slot_pc=pc+4
            slot=decode(engine,image,slot_pc)
            if slot is None or slot.size!=4:
                barriers.add((pc,'missing or invalid MIPS branch delay slot'))
                continue
            slot_flow=classify(image,slot)
            if slot_flow.kind not in ('sequential',):
                barriers.add((pc,'control transfer in MIPS delay slot requires manual review'))
                continue
            if slot_pc not in instr:
                instr[slot_pc]=(slot,slot_flow)
            slots[slot_pc]=pc
            edges.add((pc,slot_pc,'delay_slot'))
        for dst,kind in flow.edges:
            inside=(dst is not None and image.valid(dst))
            edges.add((pc,dst,kind))
            if dst is not None and not inside:
                barriers.add((pc,f'{kind} target outside mapped region: 0x{dst:x}'))
            if inside and dst not in instr:q.append(dst)
    if q:barriers.add((image.entry,f'bounded instruction discovery exhausted at {max_instructions}'))
    records=[]
    for addr,(ins,flow) in sorted(instr.items()):
        records.append(dict(address=addr,file_offset=image.offset(addr),size=ins.size,
            mnemonic=ins.mnemonic.lower(),operand_kinds=classify_operands(ins.op_str),
            flow_kind='delay_slot_instruction' if addr in slots else flow.kind,
            instruction_sha256=hashlib.sha256(ins.bytes).hexdigest(),evidence='static_reachable'))
    evidence=[dict(source=src,target=dst,kind=k,inside_region=(dst is not None and image.valid(dst)),
             **({'evidence':'recovered_local_constant'} if src in resolved and dst==resolved[src]['target'] and k==resolved[src]['kind'] else {}))
         for src,dst,k in sorted(edges,key=lambda x:(x[0],x[1] if x[1] is not None else -1,x[2]))]
    return records,evidence,[dict(address=a,reason=r) for a,r in sorted(barriers)]


def discover(image,engine,max_instructions=250000,extra_seeds=(),recover_indirect=False,recovery_evidence=None):
    """Default scan stays unchanged. Explicit recovery uses bounded fixed-point reseeding.

    A candidate must be both source-locally supported and independently decodable.
    Unproven indirect transfers remain barriers. No native parity is implied.
    """
    if not recover_indirect:
        return _discover_once(image,engine,max_instructions,extra_seeds)
    resolved={}
    for round_index in range(8):
        records,edges,barriers=_discover_once(image,engine,max_instructions,extra_seeds,resolved)
        # Recheck earlier local-constant proofs after new code is reached:
        # newly discovered incoming paths may invalidate unique-predecessor proof.
        recheck=[{'address':pc,'reason':'revalidate resolved edge'} for pc in resolved]
        found=recover_local_targets(image,lambda a:decode(engine,image,a),
                                    records,edges,[*barriers,*recheck])
        if len(found)>2048:raise ValueError('indirect recovery bound exceeded')
        if found==resolved:break
        resolved=found
    else:
        raise ValueError('indirect recovery fixed-point round bound exceeded')
    if recovery_evidence is not None:
        recovery_evidence.extend({'source':pc,**value} for pc,value in sorted(resolved.items()))
    return records,edges,barriers


def run(source,dbfile,out,fmt='auto',isa=None,endian=None,base=None,entry=None,max_instructions=250000,extra_seeds=(),seed_vectors=False,recover_indirect=False):
    source=Path(source);data=source.read_bytes();sha=hashlib.sha256(data).hexdigest()
    image=open_image(data,fmt,isa,endian,base,entry)
    engine=make_capstone(image.isa,image.endian)
    vector_seeds=[]
    if seed_vectors and image.container=='megadrive':
        for n in range(1,64):
            candidate=int.from_bytes(data[n*4:n*4+4],'big')
            if image.valid(candidate) and candidate!=image.entry:
                vector_seeds.append(candidate)
        vector_seeds=sorted(set(vector_seeds))
    elif seed_vectors:
        raise ValueError('vector seed enumeration currently requires a Mega Drive cartridge')
    recovered=[]
    records,edges,barriers=discover(image,engine,max_instructions,[*extra_seeds,*vector_seeds],recover_indirect,recovered)
    tid=f'{image.container}-{sha[:12]}'
    obs={'schema':'recomp-observations-v1','target':dict(id=tid,isa=image.isa,system_tag=image.container,
        source_sha256=sha,analyzer='capstone-static-graph-v2'),'records':records}
    evidence={'schema':'recomp-flow-evidence-v1','target_id':tid,'architecture':image.isa,'container':image.container,
        'source_sha256':sha,'file_size':len(data),'entry':image.entry,'source_file_name':source.name,
        'mapped_region':dict(start=image.start,stop=image.stop,offset=image.file_offset),
        'decoded_seed_reachable':len(records),'observed_addresses':[r['address'] for r in records],'extra_seeds':list(extra_seeds),'vector_seeds':vector_seeds, 'edges':edges,'barriers':barriers,
        'indirect_recovery':{'enabled':bool(recover_indirect),'local_constant_edges':recovered,'status':'SOURCE_SUPPORTED_NOT_EXECUTION_VERIFIED'},
        'warnings':list(image.warnings)+[
        'Static reachability is not execution evidence or a complete function census.',
        'Function entries from direct calls are candidates, not verified complete functions.',
        'MIPS delay slots traversed statically; execution, load-delay and hardware are not verified.',
        'No original instructions or game bytes included in reports.']}
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    (out/'observations.json').write_text(json.dumps(obs,indent=2)+'\n',encoding='utf-8')
    ef=out/'flow-evidence.json';ef.write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    con=connect(dbfile)
    run_id=import_scan(con,obs,ef)
    migrate(con)
    title=megadrive_title(data) if image.container=='megadrive' else None
    update(con,tid,title or source.name,'megadrive_header' if title else 'local_filename',expected_sha=sha)
    con.close()
    return {'target_id':tid,'run_id':run_id,'instructions':len(records),
            'edges':len(edges),'barriers':len(barriers),'out':str(out),'sha256':sha,
            'recovered_indirect_edges':len(recovered),'recovery_status':'SOURCE_SUPPORTED_NOT_EXECUTION_VERIFIED'}
