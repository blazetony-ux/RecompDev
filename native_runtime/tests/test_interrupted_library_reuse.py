"""Interrupted live execution must preserve activated native code for later sessions.

One synthetic ROM, three independent processes:
  1) stop at the next missing region after the first successful activation;
  2) start with consolidated partial coverage and extend that source history;
  3) preload the completed unified library without recompiling either gap.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

controller=Path(sys.argv[1]).resolve(strict=True)
source=Path(sys.argv[2]).resolve(strict=True)
script=source/'analysis_integration'/'live_session.py'
with tempfile.TemporaryDirectory(prefix='rd-v27-native-interrupted-') as d:
    root=Path(d)
    home=root/'home';home.mkdir()
    content=bytearray(0x8000)
    content[0:11]=bytes.fromhex('00 31 f0 df 21 00 20 e5 e1 e9 76')
    content[0x38]=content[0x66]=0x76
    content[0x2000:0x2006]=bytes.fromhex('21 00 21 e9 76 76')
    content[0x2100:0x2102]=bytes.fromhex('18 fe')
    content[0x7ff0:0x7ff8]=b'TMR SEGA'
    rom=root/'source.sms';rom.write_bytes(content)
    digest=hashlib.sha256(content).hexdigest()
    export=root/'export.json'
    export.write_text(json.dumps({'schema':'recomp-function-pcode-v1',
        'target_id':'synthetic-interrupted-governed','source_sha256':digest,
        'language':'z80:LE:16:default','analyzer':'ghidra-raw-pcode',
        'bank_context':None,'functions':[{'entry':0,'body_min':0,'body_max':0,
        'instructions':[{'address':0,'length':1,'bytes_sha256':hashlib.sha256(b'\0').hexdigest(),
                         'mnemonic':'NOP','pcode':[]}]}]}))
    env=dict(os.environ,RECOMPDEV_TEST_MODE='1',RECOMPDEV_HOME=str(home),PYTHONDONTWRITEBYTECODE='1')
    history=home/'gs'/digest
    libs=home/'nl'/digest
    cache=home/'nc'
    for n,limit in enumerate((1,4,4)):
        args=[sys.executable,'-B',str(script),'play',str(rom),'--controller-exe',str(controller),
              '--source-root',str(source),'--no-monitor','--video','capture','--input','neutral',
              '--frames','12','--steps','1200000','--max-recoveries',str(limit),
              '--timeout','180','--allow-synthetic-test-export','--test-export',str(export)]
        proc=subprocess.run(args,env=env,capture_output=True,text=True,timeout=200)
        if proc.returncode!=(2 if n==0 else 0):
            evidence=[x for x in (home/'RecompDev-Evidence'/'v0.4.9.27'/'live').glob('live-*')]
            logs=[]
            for session in evidence:
                for f in ('native-game.log','consolidation-translation.log','recovery-0001-translation.log'):
                    if (session/f).is_file():logs.append(f+': '+(session/f).read_text(errors='replace')[-1200:])
            raise AssertionError(f'Session {n} exit {proc.returncode}: {proc.stdout[-2400:]}\n{proc.stderr[-900:]}\n'+ '\n'.join(logs))
        lines=[a[len('RECOMPDEV_LIVE_EVIDENCE='):] for a in proc.stdout.splitlines()
               if a.startswith('RECOMPDEV_LIVE_EVIDENCE=')]
        assert len(lines)==1,proc.stdout
        session=Path(lines[0]);doc=json.loads((session/'session.json').read_text())
        assert doc['cached_activations']==(1 if n<2 else 0),doc
        assert len(doc['hot_activations'])==(1 if n<2 else 0),doc
        assert doc['consolidated_library']['emitted']>=2 if n<2 else True,doc
        assert 'generated_source_commit' in doc,doc
        assert (history/'.git').is_dir(),history
        if n==0:
            assert doc['status']=='GUEST_BLOCKED_LIVE_RECOVERY_LIMIT_REACHED',doc
            assert doc['hot_activations'][0]['pc']==0x2000,doc
            assert 'consolidated_preload' not in doc
            assert len(list(cache.rglob('manifest.json')))==1
            assert (libs/'current.json').is_file(),doc
        elif n==1:
            assert doc['status']=='FRAME_BUDGET_REACHED_PARITY_UNVERIFIED',doc
            assert doc['consolidated_preload']['emitted']>=2,doc
            assert doc['hot_activations'][0]['pc']==0x2100,doc
            assert len(list(cache.rglob('manifest.json')))==2
            assert doc['consolidated_library']['emitted']>=3,doc
        else:
            assert doc['status']=='FRAME_BUDGET_REACHED_PARITY_UNVERIFIED',doc
            assert doc['consolidated_preload']['emitted']>=3,doc
            assert not list((session/'control').glob('request-*.json'))
    print('RECOMPDEV_INTERRUPTED_SESSION_INCREMENTAL_CONSOLIDATION=PASS')
