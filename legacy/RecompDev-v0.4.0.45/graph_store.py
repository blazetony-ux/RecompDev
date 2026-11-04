"""Evidence-preserving, system-neutral function/call graph index.

Function rows are hypotheses based on an entry seed or statically proven direct-call
entry, never claimed to be fully recovered functions. No original code bytes stored.
"""
import hashlib
import json
import sqlite3
from collections import defaultdict, deque
from pathlib import Path

DDL = '''
CREATE TABLE IF NOT EXISTS graph_runs (
 run_id TEXT PRIMARY KEY, target_id TEXT NOT NULL, source_sha256 TEXT NOT NULL,
 analyzer TEXT NOT NULL, evidence_sha256 TEXT NOT NULL, entry INTEGER NOT NULL,
 mapped_start INTEGER NOT NULL, mapped_stop INTEGER NOT NULL,
 instruction_count INTEGER NOT NULL, completeness TEXT NOT NULL,
 FOREIGN KEY(target_id) REFERENCES targets(target_id)
);
CREATE TABLE IF NOT EXISTS graph_functions (
 run_id TEXT NOT NULL, entry INTEGER NOT NULL, origin TEXT NOT NULL,
 confidence TEXT NOT NULL, instruction_count INTEGER NOT NULL, boundary_state TEXT NOT NULL,
 PRIMARY KEY(run_id,entry), FOREIGN KEY(run_id) REFERENCES graph_runs(run_id)
);
CREATE TABLE IF NOT EXISTS graph_transfers (
 run_id TEXT NOT NULL, source INTEGER NOT NULL, dest INTEGER,
 kind TEXT NOT NULL, evidence TEXT NOT NULL, inside_region INTEGER NOT NULL,
 caller_entry INTEGER, ownership TEXT NOT NULL, 
 UNIQUE(run_id,source,dest,kind), FOREIGN KEY(run_id) REFERENCES graph_runs(run_id)
);
CREATE TABLE IF NOT EXISTS graph_barriers (
 run_id TEXT NOT NULL, address INTEGER NOT NULL, reason TEXT NOT NULL,
 UNIQUE(run_id,address,reason), FOREIGN KEY(run_id) REFERENCES graph_runs(run_id)
);
CREATE TABLE IF NOT EXISTS graph_function_labels (
 run_id TEXT NOT NULL, entry INTEGER NOT NULL, name TEXT NOT NULL,
 PRIMARY KEY(run_id,entry), FOREIGN KEY(run_id,entry) REFERENCES graph_functions(run_id,entry)
);
CREATE INDEX IF NOT EXISTS graph_runs_target ON graph_runs(target_id);
CREATE INDEX IF NOT EXISTS graph_transfer_src ON graph_transfers(run_id,source);
CREATE INDEX IF NOT EXISTS graph_transfer_dest ON graph_transfers(run_id,dest);
'''

def connect(dbfile, readonly=False):
    if readonly:
        con=sqlite3.connect(Path(dbfile).resolve().as_uri()+'?mode=ro', uri=True)
        con.row_factory=sqlite3.Row
        con.execute('PRAGMA query_only=ON')
        return con
    dbfile=Path(dbfile);dbfile.parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(str(dbfile));con.execute('PRAGMA foreign_keys=ON')
    con.row_factory=sqlite3.Row
    # Standalone scans must initialise an empty database without copying a
    # populated catalogue. Existing catalogue schemas/data remain untouched.
    con.executescript('''CREATE TABLE IF NOT EXISTS targets (
      target_id TEXT PRIMARY KEY, isa TEXT NOT NULL, source_sha256 TEXT NOT NULL,
      system_tag TEXT NOT NULL, analyzer TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS observations (
      target_id TEXT NOT NULL, address INTEGER NOT NULL, file_offset INTEGER,
      size INTEGER NOT NULL, mnemonic TEXT NOT NULL, operand_kinds TEXT NOT NULL,
      form_key TEXT NOT NULL, evidence TEXT NOT NULL, flow_kind TEXT NOT NULL,
      instruction_sha256 TEXT, semantic_key TEXT, analyzer TEXT NOT NULL,
      PRIMARY KEY(target_id,address),
      FOREIGN KEY(target_id) REFERENCES targets(target_id));
    CREATE TABLE IF NOT EXISTS candidate_forms (
      target_id TEXT NOT NULL, form_key TEXT NOT NULL,
      candidate_count INTEGER NOT NULL, PRIMARY KEY(target_id,form_key),
      FOREIGN KEY(target_id) REFERENCES targets(target_id));''')
    con.executescript(DDL)
    return con

def _integer(value,what):
    if type(value) is not int or value < 0 or value >= 1<<64:
        raise ValueError(f'{what} must be unsigned integer')
    # SQLite signed 64-bit storage
    if value>=1<<63:raise ValueError(f'{what} outside SQLite address domain')
    return value

def import_flow(con, filename, *, analyzer='capstone-seed-static-v1'):
    """Import attested static graph evidence. Idempotent by artifact digest; no ROM bytes."""
    blob=Path(filename).read_bytes()
    d=json.loads(blob)
    if d.get('schema') not in ('recomp-census-v1','recomp-flow-evidence-v1'):
        raise ValueError('requires recomp-census-v1 or recomp-flow-evidence-v1')
    target=d['target_id']; sha=d['source_sha256'].lower();arch=d['architecture']
    old=con.execute('SELECT isa,source_sha256 FROM targets WHERE target_id=?',(target,)).fetchone()
    if old is None: raise ValueError('target not registered: import its existing observations/census first')
    if old['isa'] != arch or old['source_sha256']!=sha:
        raise ValueError('target identity mismatch: refusing to associate unrelated graph evidence')
    entry=_integer(d['entry'],'entry')
    mapped=d['mapped_region'];start=_integer(mapped['start'],'mapped start');stop=_integer(mapped['stop'],'mapped stop')
    if start>=stop or not start<=entry<stop:raise ValueError('entry outside mapped region')
    edges=d.get('edges',[]);barriers=d.get('barriers',[])
    if not isinstance(edges,list) or not isinstance(barriers,list):raise ValueError('edges and barriers must be lists')
    # canonical hash from content, not local disk path. Reimport unchanged input is idempotent.
    digest=hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    run_id=f'{target}-{digest[:12]}'
    if con.execute('SELECT 1 FROM graph_runs WHERE run_id=?',(run_id,)).fetchone():return run_id
    ins_rows=con.execute('SELECT address FROM observations WHERE target_id=? AND evidence=?',(target,'static_reachable')).fetchall()
    observed={int(r['address']) for r in ins_rows}
    if 'observed_addresses' in d:
        permitted_addresses=d['observed_addresses']
        if not isinstance(permitted_addresses,list) or any(type(a) is not int for a in permitted_addresses):
            raise ValueError('observed_addresses must be a list of integers')
        if not set(permitted_addresses)<=observed:
            raise ValueError('flow evidence references unregistered observations')
        observed=set(permitted_addresses)
    # Recovered edges must refer to the exact source-hashed decoded supports,
    # not just a forged metadata-only destination. Still only static evidence.
    recovery=d.get('indirect_recovery') or {}
    proof_list=recovery.get('local_constant_edges',[])
    if not isinstance(proof_list,list):raise ValueError('invalid indirect recovery proofs')
    proofs={(x['source'],x['target'],x['kind']):x for x in proof_list}
    observed_hashes={int(row['address']):row['instruction_sha256'] for row in con.execute(
        'SELECT address,instruction_sha256 FROM observations WHERE target_id=?',(target,))}
    edges_set=[];unique=set()
    permitted={'direct_call','indirect_call','direct_jump','indirect_jump','return_site','fallthrough','taken','delay_slot','return','conditional','unresolved','branch'}
    for e in edges:
        src=_integer(e['source'],'edge source'); dst=e.get('target');dst=None if dst is None else _integer(dst,'edge target')
        kind=str(e['kind'])
        if kind not in permitted:raise ValueError(f'unknown edge kind: {kind}')
        if src not in observed:raise ValueError(f'edge source {src:#x} absent from observed instructions')
        provenance=e.get('evidence','static_reachable')
        if provenance not in ('static_reachable','recovered_local_constant'):
            raise ValueError('untrusted transfer evidence category')
        signature=(src,dst,kind)
        if provenance=='recovered_local_constant':
            proof=proofs.get(signature)
            if not recovery.get('enabled') or proof is None or not isinstance(proof.get('support'),list):
                raise ValueError('recovered transfer missing matching evidence')
            if not proof['support'] or len(proof['support'])>12:
                raise ValueError('recovered transfer support bound exceeded')
            if dst not in observed or observed_hashes.get(dst)!=proof.get('target_instruction_sha256'):
                raise ValueError('recovered transfer destination has no matching source hash')
            for support_item in proof['support']:
                if support_item['address'] not in observed or observed_hashes.get(support_item['address'])!=support_item['sha256']:
                    raise ValueError('recovered transfer source hash mismatch')
        if signature in unique:continue
        unique.add(signature)
        edges_set.append((src,dst,kind,1 if dst is not None and start<=dst<stop else 0,provenance))
    # Direct call sites define candidate starts, but not proven function boundaries.
    entries={entry:'reset_or_executable_entry'}
    for origin_list,origin_name in [('extra_seeds','owner_supplied_entry_seed'),('vector_seeds','cartridge_vector_candidate')]:
        for seeded in d.get(origin_list,[]):
            seeded=_integer(seeded,'additional seed')
            if seeded in observed:entries.setdefault(seeded,origin_name)
    for src,dst,kind,inside,_provenance in edges_set:
        if kind=='direct_call' and inside and dst in observed:
            entries.setdefault(dst,'static_direct_call_target')
    local=defaultdict(set)
    for src,dst,kind,inside,_provenance in edges_set:
        if not inside or dst not in observed:continue
        if kind not in ('direct_call','indirect_call','indirect_jump','return','delay_slot'):
            local[src].add(dst)
    owners=defaultdict(set);by_entry={}
    for origin in sorted(entries):
        visited=set();q=deque([origin])
        while q:
            pc=q.popleft()
            if pc in visited or pc not in observed or (pc in entries and pc!=origin):continue
            visited.add(pc);owners[pc].add(origin)
            q.extend(sorted(local.get(pc,())))
        by_entry[origin]=visited
    bset=set()
    for b in barriers:
        addr=_integer(b['address'],'barrier address'); reason=str(b['reason']).strip()
        if not reason:raise ValueError('empty barrier reason')
        bset.add((addr,reason))
    with con:
        con.execute('INSERT INTO graph_runs VALUES (?,?,?,?,?,?,?,?,?,?)',
            (run_id,target,sha,analyzer,digest,entry,start,stop,len(observed),'partial_static_discovery'))
        for fn,origin in entries.items():
            nodes=by_entry[fn];partial=bool(any(addr in nodes for addr,_ in bset))
            ambiguous=any(len(owners[pc])>1 for pc in nodes)
            state='overlapping_ownership' if ambiguous else ('unresolved_transfer' if partial else 'boundary_not_verified')
            con.execute('INSERT INTO graph_functions VALUES (?,?,?,?,?,?)',
                        (run_id,fn,origin,'static_candidate',len(nodes),state))
        for src,dst,kind,inside,provenance in edges_set:
            matched=owners.get(src,set());owner=next(iter(matched)) if len(matched)==1 else None
            state='unique_static_hypothesis' if len(matched)==1 else ('ambiguous' if matched else 'unassigned')
            con.execute('INSERT INTO graph_transfers VALUES (?,?,?,?,?,?,?,?)',
                        (run_id,src,dst,kind,provenance,inside,owner,state))
        for addr,reason in bset:
            con.execute('INSERT INTO graph_barriers VALUES (?,?,?)',(run_id,addr,reason))
    return run_id

def register_target_if_absent(con,target,isa,sha,system,analyzer):
    old=con.execute('SELECT isa,source_sha256 FROM targets WHERE target_id=?',(target,)).fetchone()
    if old is not None and (old['isa'],old['source_sha256'])!=(isa,sha):
        raise ValueError('target identity conflict')
    with con:
        con.execute('INSERT OR IGNORE INTO targets VALUES (?,?,?,?,?)',(target,isa,sha,system,analyzer))

def import_scan(con, observations, evidence_file):
    """Fresh scanner inserts observations independently; rejects changed evidence."""
    target=observations['target'];tid=target['id'];sha=target['source_sha256']
    register_target_if_absent(con,tid,target['isa'],sha,target['system_tag'],target['analyzer'])
    with con:
        for r in observations['records']:
            row=con.execute('SELECT instruction_sha256 FROM observations WHERE target_id=? AND address=?',(tid,r['address'])).fetchone()
            if row and row[0] and row[0]!=r['instruction_sha256']:
                raise ValueError('conflicting instruction evidence: refusing overwrite')
            from adapters.isa import classify_operands # use forms generated in scan already
            op_kinds=r['operand_kinds']
            form='|'.join([target['isa'],r['mnemonic'],*op_kinds])
            con.execute('''INSERT OR REPLACE INTO observations
                    (target_id,address,file_offset,size,mnemonic,operand_kinds,form_key,evidence,flow_kind,instruction_sha256,semantic_key,analyzer)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                (tid,r['address'],r['file_offset'],r['size'],r['mnemonic'],json.dumps(op_kinds),form,
                 'static_reachable',r['flow_kind'],r['instruction_sha256'],None,target['analyzer']))
    return import_flow(con,evidence_file,analyzer=target['analyzer'])

def import_analyzer(con,path):
    """Import independently reported function/call analysis; never upgrade to verified."""
    d=json.loads(Path(path).read_text(encoding='utf-8'))
    if d.get('schema')!='recomp-analyzer-discovery-v1':raise ValueError('unsupported analyzer evidence schema')
    tid=d['target_id'];sha=d['source_sha256'].lower();analyzer=d['analyzer']
    if not analyzer or len(sha)!=64:raise ValueError('incomplete analyzer identity')
    old=con.execute('SELECT source_sha256 FROM targets WHERE target_id=?',(tid,)).fetchone()
    if old is None or old['source_sha256']!=sha:raise ValueError('source identity does not match registered target')
    funcs=d.get('functions',[]);calls=d.get('calls',[])
    if not isinstance(funcs,list) or not isinstance(calls,list):raise ValueError('invalid function/call arrays')
    run_row=con.execute('SELECT entry,mapped_start,mapped_stop FROM graph_runs WHERE target_id=? ORDER BY rowid DESC LIMIT 1',(tid,)).fetchone()
    if not run_row:raise ValueError('import base graph first')
    entry,start,stop=run_row
    digest=hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    run_id=f'{tid}-external-{digest[:12]}'
    if con.execute('SELECT 1 FROM graph_runs WHERE run_id=?',(run_id,)).fetchone():return run_id
    entries=set()
    for f in funcs:
        addr=_integer(f['entry'],'function entry');entries.add(addr)
    inspected=[]
    for c in calls:
        src=_integer(c['source'],'call site');dst=c.get('target');dst=None if dst is None else _integer(dst,'callee')
        kind=c.get('kind')
        if kind not in ('direct_call','indirect_call'):raise ValueError('unrecognised call kind')
        if kind=='direct_call' and dst is None:raise ValueError('direct call must name a callee address')
        caller=c.get('caller_entry');caller=None if caller is None else _integer(caller,'caller function entry')
        if caller is not None and caller not in entries: raise ValueError('caller entry not in declared function list')
        inspected.append((src,dst,kind,caller))
    with con:
        con.execute('INSERT INTO graph_runs VALUES (?,?,?,?,?,?,?,?,?,?)',(run_id,tid,sha,analyzer,digest,entry,start,stop,0,'external_analyzer_unverified'))
        for fn in sorted(entries):
            con.execute('INSERT INTO graph_functions VALUES (?,?,?,?,?,?)',
                         (run_id,fn,'external_analyzer_candidate','analyzer_reported',0,'boundary_not_verified'))
        for fn in funcs:
            if isinstance(fn.get('name'),str) and fn['name'].strip():
                con.execute('INSERT INTO graph_function_labels VALUES (?,?,?)',(run_id,fn['entry'],fn['name'][:200]))
        for src,dst,kind,caller in inspected:
            con.execute('INSERT OR IGNORE INTO graph_transfers VALUES (?,?,?,?,?,?,?,?)',
                 (run_id,src,dst,kind,'external_analysis',1 if dst is not None and start<=dst<stop else 0,caller,
                  'external_analyzer' if caller is not None else 'unassigned'))
    return run_id
