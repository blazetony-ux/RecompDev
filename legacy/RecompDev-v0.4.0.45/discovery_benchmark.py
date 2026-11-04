"""Replayable, owner-local cross-ISA discovery benchmark. Never reads a ROM from a URL.

Baseline/recovery scans have identical source, vector seeds, limits and decoder.
No increase is called real-game improvement unless an owner-local ROM was scanned.
"""
import hashlib
import json
from pathlib import Path
from scan_graph import run
from graph_store import connect


def benchmark(source,out,fmt='auto',isa=None,endian=None,base=None,entry=None,
              max_instructions=100000,extra_seeds=(),seed_vectors=False,expected_sha256=None):
    source=Path(source).resolve(strict=True)
    blob=source.read_bytes();sha=hashlib.sha256(blob).hexdigest()
    if expected_sha256 is not None and sha!=str(expected_sha256).lower():
        raise ValueError('source SHA-256 does not match requested benchmark identity')
    if max_instructions<=0 or max_instructions>500000:
        raise ValueError('benchmark instruction budget outside 1..500000')
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    db=out/'benchmark.sqlite'
    if db.exists():
        raise ValueError('benchmark destination already has a database; choose a new output directory')
    options=(str(source),str(db),None,fmt,isa,endian,base,entry,max_instructions,extra_seeds,seed_vectors)
    baseline=run(*options[:2],str(out/'baseline'),*options[3:],False)
    enhanced=run(*options[:2],str(out/'recovered'),*options[3:],True)
    con=connect(db,readonly=True)
    try:
        def counts(run_id):
            return {'function_candidates':con.execute('SELECT COUNT(*) FROM graph_functions WHERE run_id=?',(run_id,)).fetchone()[0],
                    'call_sites':con.execute("SELECT COUNT(*) FROM graph_transfers WHERE run_id=? AND kind IN ('direct_call','indirect_call')",(run_id,)).fetchone()[0],
                    'recovered_edges':con.execute("SELECT COUNT(*) FROM graph_transfers WHERE run_id=? AND evidence='recovered_local_constant'",(run_id,)).fetchone()[0]}
        b=counts(baseline['run_id']);r=counts(enhanced['run_id'])
    finally:con.close()
    result={'schema':'recomp-cross-isa-discovery-benchmark-v0430','release':'0.4.0.32',
            'source_sha256':sha,'system':enhanced['target_id'].split('-')[0],
            'same_input_and_seeds':True,'seed_vectors':bool(seed_vectors),
            'max_instructions':max_instructions,
            'baseline':{**baseline,**b},'enhanced':{**enhanced,**r},
            'delta':{'instructions':enhanced['instructions']-baseline['instructions'],
                     'function_candidates':r['function_candidates']-b['function_candidates'],
                     'unresolved_barriers':enhanced['barriers']-baseline['barriers'],
                     'resolved_local_constant_edges':r['recovered_edges']},
            'qualification':'SOURCE_SUPPORTED_STATIC_DISCOVERY_ONLY',
            'native_compilation':'NOT_ESTABLISHED_FOR_THIS_SOURCE',
            'independent_reference_parity':'NOT_ESTABLISHED'}
    recovered_doc=json.loads((out/'recovered'/'flow-evidence.json').read_text(encoding='utf-8'))
    queue={'schema':'recomp-source-supported-recovery-queue-v0430',
           'source_sha256':sha,'architecture':recovered_doc['architecture'],
           'entries':[{'source':p['source'],'target':p['target'],'kind':p['kind'],
                       'pattern':p['pattern'],'support':p['support'],
                       'target_instruction_sha256':p['target_instruction_sha256'],
                       'next_action':'INDEPENDENT_ANALYZER_OR_RUNTIME_CONFIRMATION_REQUIRED',
                       'native_compilation_status':'NOT_AUTOMATICALLY_QUALIFIED'}
                      for p in recovered_doc['indirect_recovery']['local_constant_edges']],
           'disclaimer':'Static recovered edges are leads; never automatically native-qualified.'}
    (out/'recovery-queue.json').write_text(json.dumps(queue,indent=2)+'\n',encoding='utf-8')
    (out/'benchmark-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    from multisa.triage import triage
    diagnostics=triage(out/'recovered'/'flow-evidence.json',out/'barrier-triage.json')
    result['barrier_triage']={'classes':diagnostics['classes'],'queue_report':'barrier-triage.json'}
    (out/'benchmark-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result
