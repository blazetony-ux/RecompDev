#!/usr/bin/env python3
"""Cross-target controller/provider protocol regression; two unrelated synthetic ROMs.

Does not claim real installed Ghidra/Rizin or game parity. The mock external
commands test the real process boundary and maintained byte-attested evidence readers.
"""
from __future__ import annotations
import hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(sys.argv[3]).resolve(strict=True)
sys.path.insert(0,str(ROOT))
from analysis_integration.providers import acquire,ProviderBlocked,analyze_observed_bank_region
EXE=Path(sys.argv[1]).resolve(strict=True)
PLUGINS=Path(sys.argv[2]).resolve(strict=True)

def source_file(folder,contents,name):
    b=bytearray(0x8000);b[:len(contents)]=contents;b[0x7ff0:0x7ff8]=b'TMR SEGA'
    b[0x38]=b[0x66]=0x76
    rom=folder/name;rom.write_bytes(b)
    digest=hashlib.sha256(b).hexdigest()
    instructions=[{'address':0,'length':1,'bytes_sha256':hashlib.sha256(b[:1]).hexdigest(),
                  'mnemonic':'HALT' if b[0]==0x76 else 'NOP',
                  'pcode':[{'op':'CALLOTHER','inputs':[{'space':'const','offset':9,'size':1}]}] if b[0]==0x76 else []}]
    doc={'schema':'recomp-function-pcode-v1','target_id':'mastersystem-'+digest[:12],
         'source_sha256':digest,'language':'z80:LE:16:default','analyzer':'ghidra-raw-pcode',
         'bank_context':None,'functions':[{'entry':0,'body_min':0,'body_max':0,
          'instructions':instructions}]}
    exported=folder/(name+'.json');exported.write_text(json.dumps(doc))
    return rom,exported,digest

with tempfile.TemporaryDirectory(prefix='rd-native-orchestrator-') as tmp:
    root=Path(tmp);tools=root/'tools';tools.mkdir()
    # Test real external-process adapters (executables are local test fixtures,
    # never shipped or interpreted as authentic Ghidra/Rizin software).
    ghscript=tools/('gh_mock.py' if os.name=='nt' else 'analyzeHeadless')
    ghscript.write_text('''#!/usr/bin/env python3
import sys,json,hashlib,pathlib
p=sys.argv.index('-postScript')
out=pathlib.Path(sys.argv[p+2]);target=sys.argv[p+3];digest=sys.argv[p+4]
window=pathlib.Path(sys.argv[sys.argv.index('-import')+1]).read_bytes()
seed=int(sys.argv[sys.argv.index('-preScript')+2],16)
doc={'schema':'recomp-function-pcode-v1','target_id':target,'source_sha256':digest,
'language':'z80:LE:16:default','analyzer':'ghidra-raw-pcode','functions':[{'entry':seed,'body_min':seed,'body_max':seed,
'instructions':[{'address':seed,'length':1,'bytes_sha256':hashlib.sha256(window[seed:seed+1]).hexdigest(),
'mnemonic':'HALT','pcode':[{'op':'CALLOTHER','inputs':[{'space':'const','offset':9,'size':1}]}]}]}]}
out.write_text(json.dumps(doc))
''')
    if os.name=='nt':
        # .bat is the real Ghidra executable name on Windows. Build a tiny
        # native fixture for rizin.exe; Windows cannot execute shebang files.
        gh=tools/'analyzeHeadless.bat'
        gh.write_text('@echo off\r\n"'+sys.executable+'" "'+str(ghscript)+'" %*\r\n',encoding='utf8')
        rz_src=root/'rizin-mock';rz_src.mkdir()
        (rz_src/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.20)\nproject(rd_test_rizin LANGUAGES CXX)\nadd_executable(rizin main.cpp)\n')
        (rz_src/'main.cpp').write_text('#include <cstdio>\nint main(){std::puts("\\x1b[2K");std::puts("WARNING: invalid address from 0x00009d81");std::puts("WARNING: invalid address from 0x0002a121");std::puts(R"([{\"offset\":0,\"size\":1,\"name\":\"fcn.0\"}])");}\n')
        build=root/'rizin-mock-build'
        subprocess.run(['cmake','-S',str(rz_src),'-B',str(build),'-G','Visual Studio 17 2022','-A','x64'],check=True,capture_output=True,timeout=65)
        subprocess.run(['cmake','--build',str(build),'--config','Release'],check=True,capture_output=True,timeout=75)
        rz=tools/'rizin.exe';rz.write_bytes((build/'Release'/'rizin.exe').read_bytes())
    else:
        gh=ghscript;rz=tools/'rizin'
        rz.write_text('''#!/usr/bin/env python3
import json
print('\\x1b[2K')
print('WARNING: invalid address from 0x00009d81')
print('WARNING: invalid address from 0x0002a121')
print(json.dumps([{'offset':0,'size':1,'name':'fcn.0'}]))
''')
        gh.chmod(0o755);rz.chmod(0o755)

    first,first_exp,first_sha=source_file(root,bytes.fromhex('76'),'first.sms')
    second,second_exp,second_sha=source_file(root,bytes.fromhex('00 02 76'),'second.sms')
    assert first_sha!=second_sha
    export,reconcile,manifest=acquire(first,root/'analyzers',export=None,ghidra=gh,rizin=rz,
        tool_roots=(tools,),timeout=40)
    assert reconcile is not None and export.is_file(),manifest
    assert manifest['external_tools_executed']==['ghidra','rizin']
    assert manifest['rizin_execution']['warning_count']==2,manifest
    assert manifest['rizin_execution']['historical_runner_used'] is False,manifest
    assert manifest['rizin_execution']['backend']=='recompdev-owned-rizin-v1',manifest
    assert (root/'analyzers'/'rizin'/'rizin-provider.json').is_file()
    assert (root/'analyzers'/'rizin'/'rizin-process.json').is_file()
    assert json.loads((root/'analyzers'/'rizin'/'rizin-aflj.json').read_text())[0]['offset']==0
    merged=json.loads(reconcile.read_text())
    assert merged['stats']['AGREED_ENTRY_AND_EXTENT']==1,merged['stats']
    # Controller-native format selection and input verification precede any
    # generated source. Both distinct source identities pass the *same* stage.
    for n,(rom,base,_) in enumerate(((first,first_exp,first_sha),(second,second_exp,second_sha))):
        cmd=[str(EXE),'--stage','native-orchestrate','--rom',str(rom),
            '--out',str(root/f'owner-{n}'),'--plugin-dir',str(PLUGINS),
            *(['--ghidra',str(gh),'--rizin',str(rz),'--allow-tool-root',str(tools)] if n==0 else ['--export',str(base)]),*(['--no-compile'] if n==0 else []),'--no-execute',
            '--max-rounds','2','--target-frames','10','--timeout','50']
        process=subprocess.run(cmd,capture_output=True,text=True,timeout=100)
        assert process.returncode==0,(process.stdout[-500:],process.stderr[-1500:], (root/f'owner-{n}'/'round-01-translation.log').read_text(errors='replace')[-4000:])
        result=json.loads((root/f'owner-{n}'/'orchestration.json').read_text())
        assert result['status']=='TRANSLATED_NOT_EXECUTED',result
        assert len(result['rounds'])==1 and result['rounds'][0]['emitted']>0,result
        assert not result['legacy_runtime_fallback']
        if n==0:assert 'rizin-direct-v1' in result['analysis']['selected_providers']
        if n==1:
            generated=root/f'owner-{n}'/'round-01'/'build'
            app=next((p for p in (generated/'RecompDevNativeApp',generated/'Release'/'RecompDevNativeApp.exe') if p.exists()),None)
            assert app is not None
            execute=subprocess.run([str(app),str(rom),str(root/'app-run'), '6','20000',
                '--mode','HEADLESS_AUTONOMOUS','--video','null','--audio','null','--input','neutral'],
                capture_output=True,text=True,timeout=30)
            assert execute.returncode==0,(execute.stdout[-1500:],execute.stderr[-1500:])
            report=json.loads(execute.stdout.split('NATIVE_APP_RESULT=',1)[1].splitlines()[0])
            assert report['rom_bytes']==rom.stat().st_size and 0<=report['sp']<=65535,report

    # Ghidra recovery must derive and authenticate a complete observed bank
    # mapping, rather than guessing from a naked 16-bit PC or a game title.
    data=bytearray(0x10000);data[0]=0x76;data[0x9000]=0x76;data[0x7ff0:0x7ff8]=b'TMR SEGA'
    banked=root/'banked.sms';banked.write_bytes(data)
    digest=hashlib.sha256(data).hexdigest()
    initial={'schema':'recomp-function-pcode-v1','target_id':'mastersystem-'+digest[:12],
        'source_sha256':digest,'language':'z80:LE:16:default','analyzer':'ghidra-raw-pcode',
        'functions':[{'entry':0,'body_min':0,'body_max':0,'instructions':[{
            'address':0,'length':1,'bytes_sha256':hashlib.sha256(data[:1]).hexdigest(),
            'mnemonic':'HALT','pcode':[]}]}]}
    initial_export=root/'banked-base.json';initial_export.write_text(json.dumps(initial))
    observation={'schema':'recompdev.native.app.stop.v1','source_sha256':digest,
        'rom_bytes':len(data),'pc':0x9000,'physical_offset':0x9000,
        'mapper':[0,0,1,2],'native_steps':500,'status':'UNTRANSLATED_INITIAL_CODE','sp':0xdffc}
    overlay,audit=analyze_observed_bank_region(banked,root/'banked-ghidra-recovery',
        ghidra=gh,tool_roots=(tools,),base_export=initial_export,observed=observation,timeout=40)
    assert audit['observed_instruction_verified'] and audit['slot']==2 and audit['bank']==2,audit
    instructions=json.loads(overlay.read_text())
    assert instructions['bank_context']=={'slot':2,'bank':2,'base':0x8000,'physical_start':0x8000}
    assert instructions['functions'][0]['instructions'][0]['address']==0x9000
    # Compiled translator independently re-verifies this banked Ghidra P-code
    # against the full original ROM, not just the temporary bank view.
    cmd=[str(EXE),'--stage','native-translate','--rom',str(banked),'--export',str(initial_export),
        '--bank-export',str(overlay),'--plugin-dir',str(PLUGINS),'--source-root',str(ROOT),
        '--backend','full','--out',str(root/'banked-compiled-translation'),'--no-compile']
    proc=subprocess.run(cmd,capture_output=True,text=True,timeout=70)
    assert proc.returncode==0,(proc.stdout[-1000:],proc.stderr[-1000:])
    invalid=dict(observation);invalid['physical_offset']=0x5000
    try:
        analyze_observed_bank_region(banked,root/'forged-bank-recovery',ghidra=gh,
           tool_roots=(tools,),base_export=initial_export,observed=invalid,timeout=40)
        raise AssertionError('forged runtime bank physical mapping was accepted')
    except ProviderBlocked as exc:assert 'PHYSICAL_MISMATCH' in str(exc),str(exc)
    # Explicitly reject unapproved external executables; never auto-run tools.
    try:
        acquire(first,root/'bad-tools',export=None,ghidra=gh,rizin=rz,
                tool_roots=(),timeout=40)
        raise AssertionError('unapproved external tool accepted')
    except ValueError as exc:
        assert 'allow-tool-root' in str(exc),str(exc)
    # The same source cannot masquerade as another ROM's Ghidra evidence.
    invalid=[str(EXE),'--stage','native-orchestrate','--rom',str(second),
        '--out',str(root/'forged-export'),'--plugin-dir',str(PLUGINS),
        '--export',str(first_exp),'--no-compile']
    proc=subprocess.run(invalid,capture_output=True,text=True,timeout=80)
    assert proc.returncode!=0,(proc.stdout,proc.stderr)
    report=json.loads((root/'forged-export'/'orchestration.json').read_text())
    assert report['status']=='BLOCKED' and 'IDENTITY' in report['reason'],report
    # Rizin cannot replace Ghidra's byte-attested P-code IR.
    no_gh=[str(EXE),'--stage','native-orchestrate','--rom',str(first),
        '--out',str(root/'no-ghidra'),'--plugin-dir',str(PLUGINS),
        '--no-compile']
    proc=subprocess.run(no_gh,capture_output=True,text=True,timeout=80)
    assert proc.returncode!=0,(proc.stdout,proc.stderr)
    report=json.loads((root/'no-ghidra'/'orchestration.json').read_text())
    assert 'GHIDRA_SOURCE_EXPORT_REQUIRED' in report.get('reason',''),report
print('PASS: two source-distinct synthetic ROMs, Ghidra/Rizin subprocesses, native translator, provenance and blockers')
