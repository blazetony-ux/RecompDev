"""Fail-closed migration inventory governance for independently owned boundaries."""
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REQUIRED={
 'Z80/68000/MIPS translation','SMS machine and hardware','Discovery/recovery/campaign',
 'Ghidra and analysis tools','Historical evidence & catalogues',
 'Mega Drive and PlayStation work','Tests and governance',
 'Diagnostic archive and privacy','Workspace and job persistence',
 'Asset discovery and export','Knowledge catalogue integration',
 'Operator Workbench and monitor','Native gameplay qualification',
 'Git and release promotion',
}
STATES={'preserved','adapter','independent','qualified'}

def check(root:Path=ROOT):
    reg=json.loads((root/'migration/capability-registry.json').read_text('utf-8'))
    assert reg['schema']=='recompdev-capability-registry-v1'
    rows=reg['capabilities']
    names=[x['name'] for x in rows]
    if len(names)!=len(set(names)) or not REQUIRED.issubset(names):
        raise ValueError('Incomplete or duplicate legacy capability inventory')
    for r in rows:
        if r.get('migration_state') not in STATES:
            raise ValueError('Invalid migration_state for '+r['name'])
        for field in ('owner','new_boundary','qualification','acceptance_test','exit_criteria'):
            if not isinstance(r.get(field),str) or len(r[field])<12:
                raise ValueError('Missing migration accountability '+r['name']+'/'+field)
        if not isinstance(r.get('legacy_paths'),list) or not r['legacy_paths']:
            raise ValueError('Unmapped legacy source '+r['name'])
        if r['migration_state']=='qualified':
            raise ValueError('No complete legacy equivalence has yet been qualified: '+r['name'])
    return {'status':'PASS','mapped_capabilities':len(rows),'unqualified':sum(r['migration_state']!='qualified' for r in rows)}

if __name__=='__main__':
    print(json.dumps(check(),sort_keys=True))
