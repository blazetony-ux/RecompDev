"""ROM-hash-bound code evidence and dependency frontier, usable across game titles.

Every edge originates from an authenticated instruction record. Addresses are
resolved by the owning system adapter; unmappable/dynamic edges stay unresolved.
This graph is an analysis index, NOT proof that an edge executes at runtime.
"""
import sqlite3
from pathlib import Path

SCHEMA = '''
CREATE TABLE IF NOT EXISTS native_code_nodes_v0410(
 source_id TEXT NOT NULL, physical_offset INTEGER NOT NULL,
 logical_pc INTEGER NOT NULL, slot INTEGER NOT NULL, bank INTEGER NOT NULL,
 mnemonic TEXT NOT NULL, length INTEGER NOT NULL, instruction_sha256 TEXT NOT NULL,
 PRIMARY KEY(source_id, physical_offset));
CREATE TABLE IF NOT EXISTS native_code_edges_v0410(
 source_id TEXT NOT NULL, from_physical INTEGER NOT NULL,
 to_physical INTEGER NOT NULL, to_pc INTEGER NOT NULL,
 kind TEXT NOT NULL, state TEXT NOT NULL,
 PRIMARY KEY(source_id,from_physical,to_physical,kind));
CREATE INDEX IF NOT EXISTS native_code_edges_frontier_v0410
 ON native_code_edges_v0410(source_id,state,to_physical);
'''


def evidence_index(documents, rom_path, system='mastersystem'):
    """Return physical instruction nodes and explicit flow edges; reject bad hashes.

    The shared data model has no names of games, no magic program addresses and
    no ISA-specific instruction semantics. Address mapping is delegated.
    """
    from nativepilot.generator import verify_export
    from nativecore.adapters import provider_for
    provider=provider_for(system)
    size=Path(rom_path).stat().st_size
    nodes={}
    for doc in documents:
        recovered, _, _=verify_export(doc,rom_path)
        context=doc.get('bank_context')
        for physical,ins in recovered.items():
            slot=(ins['address']//0x4000)
            bank=(context['bank'] if context else slot)
            if physical in nodes and nodes[physical]['instruction_sha256']!=ins['bytes_sha256']:
                raise ValueError('Conflicting authenticated instruction at '+hex(physical))
            nodes[physical]={'physical_offset':physical,'logical_pc':ins['address'],
                             'slot':slot,'bank':bank,'mnemonic':ins.get('mnemonic',''),
                             'length':ins['length'],'instruction_sha256':ins['bytes_sha256'],
                             'flows':ins.get('flows',[]),'fallthrough':ins.get('fallthrough'),
                             'pcode':ins.get('pcode',[]),'context':context}
    edges={};unknown=0
    for physical,ins in nodes.items():
        destinations=[]
        flows=ins['flows']
        if isinstance(flows,list):
            destinations.extend((target,'branch') for target in flows if type(target)==int)
        fall=ins['fallthrough']
        if type(fall)==int:destinations.append((fall,'fallthrough'))
        if any(op.get('op')=='BRANCHIND' for op in ins['pcode']):unknown+=1
        seen=set()
        for pc,kind in destinations:
            if not 0<=pc<0xc000 or (pc,kind) in seen:continue
            seen.add((pc,kind))
            # Snapshot bank context of this instruction, not Shinobi's runtime.
            # Initial 48KB maps three independent physical banks.
            mapper=[0,0,1,2]
            if ins['context'] is not None:
                mapper[ins['slot']+1]=ins['bank']
            try:context=provider.map_entry(size,pc,mapper)
            except (ValueError,TypeError,KeyError):continue
            to_phys=context['entry_physical']
            edges[(physical,to_phys,kind)]={'from_physical':physical,'to_physical':to_phys,
                                            'to_pc':pc,'kind':kind,
                                            'state':'RESOLVED' if to_phys in nodes else 'UNRESOLVED'}
    return nodes,edges,unknown


def save_graph(db,source_id,documents,rom_path,system='mastersystem'):
    """Atomic, source-scoped graph rebuild; never store raw game bytes."""
    if not isinstance(source_id,str) or len(source_id)!=64:
        raise ValueError('Source SHA-256 required')
    nodes,edges,unknown=evidence_index(documents,rom_path,system)
    con=sqlite3.connect(str(db),timeout=30)
    try:
        con.executescript(SCHEMA)
        with con:
            con.execute('DELETE FROM native_code_edges_v0410 WHERE source_id=?',(source_id,))
            con.execute('DELETE FROM native_code_nodes_v0410 WHERE source_id=?',(source_id,))
            con.executemany('INSERT INTO native_code_nodes_v0410 VALUES(?,?,?,?,?,?,?,?)',
              ((source_id,n['physical_offset'],n['logical_pc'],n['slot'],n['bank'],n['mnemonic'],n['length'],n['instruction_sha256']) for n in nodes.values()))
            con.executemany('INSERT INTO native_code_edges_v0410 VALUES(?,?,?,?,?,?)',
              ((source_id,e['from_physical'],e['to_physical'],e['to_pc'],e['kind'],e['state']) for e in edges.values()))
        summary={'schema':'recomp-code-dependency-v0.4.0.10','source_sha256':source_id,
                 'authenticated_instructions':len(nodes),'edges':len(edges),
                 'resolved_edges':sum(e['state']=='RESOLVED' for e in edges.values()),
                 'unresolved_edges':sum(e['state']=='UNRESOLVED' for e in edges.values()),
                 'indirect_branches_unresolved':unknown,
                 'parity':'NOT_TESTED'}
        return summary
    finally:con.close()


def frontier(db,source_id,limit=12):
    """Report unresolved physical targets, prioritized by incoming branch edges."""
    if type(limit)!=int or not 1<=limit<=100:raise ValueError('Invalid frontier limit')
    con=sqlite3.connect(str(db),timeout=30)
    try:
        con.executescript(SCHEMA)
        return [{'physical_offset':p,'logical_pc':pc,'incoming_edges':hits,
                 'kind':kind} for p,pc,hits,kind in con.execute('''
           SELECT to_physical,to_pc,COUNT(*),MIN(kind) FROM native_code_edges_v0410
            WHERE source_id=? AND state='UNRESOLVED'
            GROUP BY to_physical,to_pc ORDER BY SUM(kind='branch') DESC,COUNT(*) DESC,to_physical
            LIMIT ?''',(source_id,limit))]
    finally:con.close()


def reachable_branch_frontier(documents,rom_path,system,entry_physical,known_physical,limit=2):
    """Speculative direct branch targets reachable from one attested entry.

    Only walks explicitly decoded fallthrough/branch edges; it does not invent
    targets for indirect jumps or use all unrelated Ghidra function candidates.
    """
    if type(limit)!=int or not 0<=limit<=10:raise ValueError('Invalid prefetch budget')
    nodes,edges,_=evidence_index(documents,rom_path,system)
    adjacent={}
    for e in edges.values():
        adjacent.setdefault(e['from_physical'],[]).append(e)
    seen=set();queue=[entry_physical];candidates=[];queued=set()
    while queue and len(seen)<4096:
        current=queue.pop(0)
        if current in seen or current not in nodes:continue
        seen.add(current)
        for e in sorted(adjacent.get(current,[]),key=lambda x:x['kind']!='branch'):
            dest=e['to_physical']
            if dest in nodes:
                if dest not in seen:queue.append(dest)
            elif e['kind']=='branch' and dest not in known_physical and dest not in queued:
                candidates.append(e);queued.add(dest)
                if len(candidates)>=limit:return candidates
    return candidates
