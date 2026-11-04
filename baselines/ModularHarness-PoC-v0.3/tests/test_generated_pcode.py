"""v0.2 production generator -> real DLL acceptance. Windows/Linux compatible."""
import hashlib,json,subprocess,sys,tempfile
from pathlib import Path
root=Path(sys.argv[1]);reports=Path(sys.argv[2]);exe=Path(sys.argv[3]);plugindir=Path(sys.argv[4]);ex=root/'examples'/'recomp-pcode'
r=json.loads((reports/'production_pcode.report.json').read_text())
assert r['differential_pass'] is True and r['halted'] is True and not r['step_budget_exhausted'],r
assert r['native_steps']==8 and r['fallback_steps']==2,r
assert r['bank3']==3 and r['ram_c000']==0x66 and r['cpu_a']==0x66,r
assert r['psg_writes']==1,r
assert r['game_module']=='rd_game_recomp_v0445' and r['case']=='rom',r
m=json.loads((root/'generated'/'game_module.manifest.json').read_text())
assert m['source_sha256']==hashlib.sha256((ex/'synthetic.sms').read_bytes()).hexdigest()
assert m['translated_instructions']==8 and not m['rejected_instructions'],m
assert {x['physical'] for x in m['attested_instructions']}=={0,3,5,8,10,13,0xc000,0xc004}
events=[json.loads(line) for line in (reports/'production_pcode.events.jsonl').read_text().splitlines()]
assert sum(ev['event']=='NATIVE_EXECUTED' for ev in events)==8,events
assert sum(ev['event']=='FALLBACK_DISCOVERED' for ev in events)==2,events
assert any(ev['event']=='BANK_SWITCH' for ev in events),events
assert any(ev['pc']==0x8000 and ev['physical']==0xc000 and ev['event']=='NATIVE_EXECUTED' for ev in events)
assert any(ev['pc']==0x8004 and ev['physical']==0xc004 and ev['event']=='NATIVE_EXECUTED' for ev in events)
assert (reports/'production_pcode.ppm').is_file() and (reports/'production_pcode.wav').is_file()
alternate=json.loads((reports/'production_alternate.report.json').read_text())
assert alternate['differential_pass'] and alternate['native_steps']==8 and alternate['fallback_steps']==2,alternate
assert alternate['ram_c000']==r['ram_c000'] and alternate['bank3']==r['bank3'],alternate

print('PRODUCTION_PCODE_BANK_SWITCH_NATIVE_FALLBACK_RESUME_PASS')
# Verify the *unmodified* production verifier rejects forged instruction hashes.
sys.path.insert(0,str(root/'tools'))
from build_pcode_plugin import generate
with tempfile.TemporaryDirectory() as directory:
    path=Path(directory); export=json.loads((ex/'function-export.json').read_text())
    export['functions'][0]['instructions'][0]['bytes_sha256']='0'*64
    invalid=path/'fake-export.json';invalid.write_text(json.dumps(export))
    try:generate(ex/'synthetic.sms',invalid,[],path/'invalid.cpp')
    except ValueError as err:assert 'mismatch' in str(err).lower(),str(err)
    else:raise AssertionError('forged P-code export was accepted')
    assert not (path/'invalid.cpp').exists()
    # Reject wrong ROM bytes while running native: not a best-effort fallback.
    bad=bytearray((ex/'synthetic.sms').read_bytes());bad[0]=0
    wrong=path/'bad.sms';wrong.write_bytes(bad)
    cmd=[str(exe),'--plugin-dir',str(plugindir),'--game','rd_game_recomp_v0445',
         '--case','rom','--rom',str(wrong),'--steps','10','--out',str(path/'wrong')]
    proc=subprocess.run(cmd,capture_output=True,text=True,timeout=20)
    assert proc.returncode!=0 and 'ROM_SHA256_MISMATCH' in proc.stderr,(proc.returncode,proc.stdout,proc.stderr)
    print('FORGED_EVIDENCE_AND_RUNTIME_BYTE_MISMATCH_REJECTED')
