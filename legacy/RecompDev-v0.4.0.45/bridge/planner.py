"""Read-only catalogue-to-native readiness report, not speculative C++ emission.

Caller/callee entry candidates are not verified whole-function boundaries.
No original bytes are stored in the SQLite catalogue, so it cannot translate
source instructions without re-opening and authenticating the original binary.
"""
from __future__ import annotations
from pathlib import Path
import sqlite3
from collections import Counter


def plan(db_path: str):
    db=Path(db_path)
    if not db.is_file():raise ValueError('catalogue database not found')
    con=sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA query_only=ON')
    try:
        has_names=bool(con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='target_names'").fetchone())
        name_sub="(SELECT display_name FROM target_names n WHERE n.target_id=t.target_id)" if has_names else 'NULL'
        targets=[];totals=Counter()
        for t in con.execute(f'SELECT t.*, {name_sub} display_name FROM targets t ORDER BY t.system_tag,t.target_id'):
            run=con.execute('SELECT * FROM graph_runs WHERE target_id=? ORDER BY rowid DESC LIMIT 1',(t['target_id'],)).fetchone()
            if not run:continue
            functions=[dict(r) for r in con.execute('SELECT entry,origin,confidence,instruction_count,boundary_state FROM graph_functions WHERE run_id=? ORDER BY entry',(run['run_id'],))]
            barriers=con.execute('SELECT COUNT(*) FROM graph_barriers WHERE run_id=?',(run['run_id'],)).fetchone()[0]
            call_count=con.execute("SELECT COUNT(*) FROM graph_transfers WHERE run_id=? AND kind IN ('direct_call','indirect_call')",(run['run_id'],)).fetchone()[0]
            unknown_calls=con.execute("SELECT COUNT(*) FROM graph_transfers WHERE run_id=? AND kind='indirect_call' AND dest IS NULL",(run['run_id'],)).fetchone()[0]
            forms=[dict(r) for r in con.execute('''SELECT o.form_key,COUNT(*) occurrences FROM observations o
                       WHERE o.target_id=? AND o.evidence='static_reachable' GROUP BY o.form_key ORDER BY occurrences DESC,form_key''',(t['target_id'],))]
            cap=con.execute('SELECT COUNT(*) FROM capabilities').fetchone()[0]
            boundaries=Counter(f['boundary_state'] for f in functions)
            eligible=[f for f in functions if f['boundary_state'] in ('verified','verified_complete')]
            # Conservative: even verified function boundaries cannot be translated until source bytes,
            # ISA semantics, guest memory and parity harness are authenticated.
            for f in functions:
                f['readiness']='NEEDS_VERIFIED_BOUNDARY' if f['boundary_state'] not in ('verified','verified_complete') else 'NEEDS_AUTHENTICATED_BINARY_AND_SEMANTICS'
            totals.update({'targets':1,'candidate_functions':len(functions),'call_sites':call_count,'unresolved_barriers':barriers})
            targets.append({'target_id':t['target_id'],'display_name':t['display_name'] or t['target_id'],
                'system':t['system_tag'],'isa':t['isa'],'source_sha256':t['source_sha256'],'latest_run':run['run_id'],
                'function_candidates':len(functions),'verified_boundary_candidates':len(eligible),
                'call_sites':call_count,'unresolved_indirect_calls':unknown_calls,'barriers':barriers,
                'boundary_states':dict(boundaries),'catalogue_capability_rows':cap,
                'reachable_instruction_forms':len(forms),'top_missing_form_families':forms[:25],
                'functions':functions})
        return {'schema':'recomp-batch-readiness-v1','scope':'metadata-only readiness; no C++ generation or parity',
            'totals':dict(totals),'targets':targets,'release_gates':[
                'Re-open original binary and verify exact SHA-256 before fetching instructions.',
                'Resolve complete function boundaries and ownership; report unresolved indirect calls.',
                'Build ISA-aware typed IR with ordered guest memory effects and exception semantics.',
                'Register exact semantic lowering capabilities supported by evidence-backed tests.',
                'Emit C++ for complete supported units; compile in isolated build jobs.',
                'Differentially execute against an independent reference engine with flags, memory, PC, cycles and rollback evidence.',
                'Batch retry all affected functions; never count C++ compilation as execution parity.'
            ]}
    finally:con.close()
