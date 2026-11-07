"""Black-box native DLL translator -> full preserved app parity and C++ game DLL.
Runs synthetic tests only. Real Shinobi gameplay qualification requires owner ROM.
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXE=Path(sys.argv[1]).resolve(strict=True)
PLUGINS=Path(sys.argv[2]).resolve(strict=True)
SOURCE=Path(sys.argv[3]).resolve(strict=True)
FIXTURE=SOURCE/'harness'/'examples'/'recomp-pcode'
ROM=FIXTURE/'synthetic.sms'
BASE=FIXTURE/'function-export.json'
BANK=FIXTURE/'bank3-export.json'

def run(*args, ok=True, timeout=180):
    p=subprocess.run([str(EXE), *map(str,args)],cwd=SOURCE,capture_output=True,text=True,timeout=timeout)
    if ok and p.returncode:
        raise AssertionError((p.returncode, p.stdout[-4000:], p.stderr[-4000:]))
    if not ok and not p.returncode:
        raise AssertionError('Expected rejection: '+p.stdout[-1200:])
    return p

def trace(exe, rom):
    proc=subprocess.run([str(exe),str(rom),'20'],capture_output=True,text=True,timeout=30)
    assert proc.returncode==0,(proc.stdout,proc.stderr)
    return json.loads(proc.stdout.split('PILOT_RESULT=',1)[1].splitlines()[0])

with tempfile.TemporaryDirectory(prefix='recompdev-04910-native-') as temporary:
    root=Path(temporary)
    actual=root/'full'
    # Default requires real Ghidra provenance, even for otherwise correct bytes.
    strict=run('--stage','native-translate','--rom',ROM,'--export',BASE,
        '--out',root/'strict','--plugin-dir',PLUGINS,'--no-compile',ok=False)
    assert 'GHIDRA_PROVENANCE_REQUIRED' in strict.stderr, strict.stderr
    # Reuse existing verified historical bank exports in an isolated test tree.
    history=root/'historic'/'recovery'/'attempt-01';history.mkdir(parents=True)
    shutil.copyfile(BANK,history/'bank-functions.json')
    p=run('--stage','native-translate','--rom',ROM,'--export',BASE,
        '--history-root',root/'historic','--out',actual,'--allow-synthetic-export',
        '--plugin-dir',PLUGINS,timeout=240)
    assert 'RECOMPDEV_HISTORY_BANK_EXPORTS=1' in p.stdout,p.stdout
    assert 'RECOMPDEV_NATIVE_TRANSLATION_EMITTED=8' in p.stdout,p.stdout
    manifest=json.loads((actual/'translation-manifest.json').read_text())
    assert manifest['backend']=='dll_sms_native_runtime'
    assert not (actual/'runtime.cpp').exists(), 'Generated project must not embed old machine state runtime'
    generated_cmake=(actual/'CMakeLists.txt').read_text()
    assert 'rd_sms_native_runtime' in generated_cmake and 'rd_runtime_host' in generated_cmake and 'rd_video_sms_mode4' in generated_cmake
    assert manifest['attested']==8 and manifest['emitted']==8 and manifest['rejected']==0,manifest
    assert manifest['source_sha256']==hashlib.sha256(ROM.read_bytes()).hexdigest()
    pilot=next((p for p in (actual/'build'/'RecompDevNativePilot.exe',actual/'build'/'RecompDevNativePilot',actual/'build'/'Release'/'RecompDevNativePilot.exe') if p.is_file()),None)
    assert pilot,p
    generated=trace(pilot,ROM)
    # Compare compiled C++ semantic effects against exactly preserved generator.
    sys.path.insert(0,str(SOURCE/'legacy'/'RecompDev-v0.4.0.45'))
    from nativepilot.generator import generate_project
    old=root/'historical-source'
    outcome=generate_project(json.loads(BASE.read_text()),ROM,old,[json.loads(BANK.read_text())])
    assert outcome['translated_instructions']==8,outcome
    cb=subprocess.run(['cmake','-S',str(old),'-B',str(root/'historical-build'),'-DCMAKE_BUILD_TYPE=Release'],capture_output=True,text=True,timeout=90)
    assert cb.returncode==0,(cb.stdout[-4000:],cb.stderr[-4000:])
    build=subprocess.run(['cmake','--build',str(root/'historical-build'),'--config','Release','--parallel','2'],capture_output=True,text=True,timeout=240)
    assert build.returncode==0,(build.stdout[-4000:],build.stderr[-4000:])
    historical=next(p for p in (root/'historical-build'/'RecompDevNativePilot.exe',root/'historical-build'/'RecompDevNativePilot',root/'historical-build'/'Release'/'RecompDevNativePilot.exe') if p.is_file())
    expected=trace(historical,ROM)
    for key in ('status','native_steps','pc','af','bc','de','hl','sp','ram_writes','vram_writes',
                'cram_writes','psg_writes','bank_switches','mapper','physical_offset',
                'tstates','last_pcs','events','checkpoints','timing_qualified_steps'):
        assert generated[key]==expected[key],(key,generated[key],expected[key])
    assert generated['native_steps']==7 and generated['status']=='BANKED_CODE_NOT_TRANSLATED',generated
    # An altered same-size ROM must never be run as if previously attested.
    wrong=root/'modified.sms';media=bytearray(ROM.read_bytes());media[42]^=0x20;wrong.write_bytes(media)
    assert trace(pilot,wrong)['status']=='ROM_SHA256_MISMATCH'
    wrong_export=run('--stage','native-translate','--rom',wrong,'--export',BASE,
        '--out',root/'wrong-export','--allow-synthetic-export','--plugin-dir',PLUGINS,'--no-compile',ok=False)
    assert 'PCODE_DOCUMENT_IDENTITY_MISMATCH' in wrong_export.stderr
    # Compile a separately interchangeable game DLL from the same P-code IR.
    dll=root/'dll'
    run('--stage','native-translate','--rom',ROM,'--export',BASE,'--bank-export',BANK,
        '--out',dll,'--backend','game-dll','--allow-synthetic-export','--plugin-dir',PLUGINS,timeout=180)
    run('--stage','native-execute','--rom',ROM,'--game','rd_game_pcode',
        '--steps','3','--out',root/'native','--plugin-dir',dll/'runtime')
    execution=json.loads((root/'native.report.json').read_text())
    assert execution['native_steps']==3 and execution['fallback_steps']==0,execution
    assert execution['source_sha256']==manifest['source_sha256']
    # Deliberately fake the first instruction's byte identity. Must not emit C++.
    forged=json.loads(BASE.read_text());forged['functions'][0]['instructions'][0]['bytes_sha256']='0'*64
    path=root/'forged.json';path.write_text(json.dumps(forged))
    rejected=run('--stage','native-translate','--rom',ROM,'--export',path,
        '--out',root/'forged-output','--plugin-dir',PLUGINS,'--allow-synthetic-export','--no-compile',ok=False)
    assert 'INSTRUCTION_SOURCE_HASH_MISMATCH' in rejected.stderr
    assert not (root/'forged-output'/'translated.cpp').exists()
    # Installed-layout DLL loading, independent of an in-tree build directory.
    installed=root/'installed';active=installed/'active';active.mkdir(parents=True)
    shutil.copy2(EXE,installed/EXE.name)
    for candidate in PLUGINS.glob('rd_translation_pcode.*'):
        if candidate.suffix in ('.dll','.so','.dylib'):
            shutil.copyfile(candidate,active/candidate.name)
    pointer=installed/'source-root.txt';pointer.write_text(str(SOURCE)+'\n')
    deployed=subprocess.run([str(installed/EXE.name),'--stage','native-translate',
        '--rom',str(ROM),'--export',str(BASE),'--allow-synthetic-export',
        '--out',str(root/'installed-run'),'--no-compile'],capture_output=True,text=True,timeout=60)
    assert deployed.returncode==0,(deployed.stdout,deployed.stderr)
print('PASS native DLL translates authentic-source P-code into full historical native application and independent game DLL; matching preserved execution effects')
