"""Release charter gate that tests actual cross-ISA code paths and fails closed.

A fixture-orchestration PASS never asserts real external tool verification,
full-game conversion or independent native CPU parity.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]

def sha(data):return hashlib.sha256(data).hexdigest()

def _fixture_gate():
    from tooling.analysis import reconcile
    from tempfile import TemporaryDirectory
    results=[]
    with TemporaryDirectory(prefix='recomp-arch-') as tmp:
        folder=Path(tmp)
        fixtures=[('z80',0,bytes.fromhex('3e423200c0c9')),
                  ('m68k',0x1000,bytes.fromhex('70014e75')),
                  ('mips',0x80000000,bytes.fromhex('010008240800e003'))]
        for isa,base,raw in fixtures:
            source=folder/(isa+'.bin');source.write_bytes(raw)
            source_hash=sha(raw)
            gh=folder/(isa+'-ghidra.json');rz=folder/(isa+'-rizin.json')
            gh.write_text(json.dumps({'schema':'recomp-function-pcode-v1',
                'source_sha256':source_hash,'functions':[{'entry':base,'body_min':base,
                'body_max':base+len(raw)-1,'instructions':[{'address':base,'length':len(raw),
                 'bytes_sha256':source_hash}]}]}))
            rz.write_text(json.dumps([{'offset':base,'size':len(raw)}]))
            doc=reconcile(source,base,isa,gh,rz)
            if doc['stats'].get('AGREED_ENTRY_AND_EXTENT')!=1 or doc['verification']['native_parity']!='NOT_TESTED':
                raise ValueError('Cross-ISA reconciliation contract failed')
            results.append({'isa':isa,'source_sha256':source_hash,'run_status':'SYNTHETIC_RECONCILED',
                            'parity':'NOT_TESTED'})
    if len(set(r['isa'] for r in results))<2 or len(set(r['source_sha256'] for r in results))<2:
        raise ValueError('Insufficient independent target fixtures')
    return results

def validate(root=ROOT,run_tests=True):
    root=Path(root).resolve()
    charter=json.loads((root/'PLATFORM_CHARTER.json').read_text())
    if charter.get('schema')!='recomp-platform-charter-v1':raise ValueError('Missing architecture charter')
    policy=charter['release_policy']
    for key in ('architecture_first','single_game_debugging_is_not_a_release_milestone',
                'source_provenance_required','suppress_unsubstantiated_parity',
                'no_invisible_semantic_repair','third_party_tools_opt_in_only'):
        if policy.get(key) is not True:raise ValueError('Release policy violation: '+key)
    fixtures=_fixture_gate()
    test={'status':'NOT_RUN'}
    if run_tests:
        proc=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests',
            '-p','test_tool_orchestration_v0414.py','-q'],cwd=root,capture_output=True,text=True,timeout=100)
        if proc.returncode or 'OK' not in proc.stderr:
            raise ValueError('Architecture regression tests failed: '+proc.stderr[-1200:])
        test={'status':'PASSED','exit_code':0,'test_log_sha256':sha((proc.stdout+proc.stderr).encode()),
              'summary':next((x for x in proc.stderr.splitlines() if x.startswith('Ran ')),'UNKNOWN')}
    return {'schema':'recomp-architecture-gate-v1','release':'0.4.0.14',
            'status':'PASS_ARCHITECTURE_FOUNDATION_SYNTHETIC',
            'charter_sha256':sha((root/'PLATFORM_CHARTER.json').read_bytes()),
            'test_source_sha256':sha((root/'tests/test_tool_orchestration_v0414.py').read_bytes()),
            'fixtures':fixtures,'unit_tests':test,
            'milestones':{
                'M1':'PARTIAL_SYNTHETIC_CROSS_ISA_ANALYSIS',
                'M2':'BLOCKED_OWNER_REAL_GHIDRA_AND_RIZIN_PROVENANCE',
                'M3':'BLOCKED_SECOND_NATIVE_ISA_AND_INDEPENDENT_ORACLE',
                'M4':'BLOCKED_AUTOMATED_REPAIR_ROLLBACK',
                'M5':'BLOCKED_TRANSACTIONAL_LIVE_DISPATCH'},
            'real_tool_execution':'NOT_TESTED',
            'windows_owner_regression':'NOT_TESTED',
            'native_gameplay_parity':'NOT_TESTED',
            'qualified_native_functions_from_this_build':0}

def main():
    p=argparse.ArgumentParser();p.add_argument('--output');p.add_argument('--root',default=str(ROOT))
    p.add_argument('--skip-unit-tests',action='store_true')
    args=p.parse_args();result=validate(args.root,not args.skip_unit_tests)
    if args.output:
        file=Path(args.output)
        if file.exists():raise ValueError('Refuse to overwrite prior gate evidence')
        file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,indent=2));return 0
if __name__=='__main__':sys.exit(main())
