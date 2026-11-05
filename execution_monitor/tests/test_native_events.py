"""Compiled native-game telemetry smoke; optional runtime DLLs are injected."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'legacy/RecompDev-v0.4.0.45')]
from nativepilot.generator import generate_project
from runtime_host.bridge import install

def checked_native_build(command, *, timeout):
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('NATIVE_BUILD_FAILED exit=' + str(result.returncode)
                           + ' command=' + repr(command)
                           + '\n=== COMPILER STDOUT ===\n' + result.stdout[-16000:]
                           + '\n=== COMPILER STDERR ===\n' + result.stderr[-16000:])
    return result

with tempfile.TemporaryDirectory(prefix='rd-monitor-native-') as d:
    temp=Path(d)
    project=temp/'project';build=temp/'build'
    rom=ROOT/'harness/examples/recomp-pcode/synthetic.sms'
    doc=json.loads((ROOT/'harness/examples/recomp-pcode/function-export.json').read_text())
    generate_project(doc,rom,project)
    digest=hashlib.sha256((project/'translated.cpp').read_bytes()).hexdigest()
    install(project)
    assert hashlib.sha256((project/'translated.cpp').read_bytes()).hexdigest()==digest
    args=['cmake','-S',str(project),'-B',str(build),'-DCMAKE_BUILD_TYPE=Release']
    if os.name=='nt':args+=['-A','x64']
    checked_native_build(args,timeout=120)
    checked_native_build(['cmake','--build',str(build),'--config','Release','--target','RecompDevNativeApp','--parallel','2'],timeout=180)
    apps=[build/'Release'/'RecompDevNativeApp.exe',build/'RecompDevNativeApp.exe',build/'RecompDevNativeApp']
    app=next(p for p in apps if p.is_file())
    env=os.environ.copy()
    env['RECOMPDEV_RUNTIME_HOST_DLL']=sys.argv[1]
    env['RECOMPDEV_SMS_MODE4_DLL']=sys.argv[2]
    events=temp/'events.jsonl'
    env['RECOMPDEV_CONTROLLER_DIAGNOSTIC_EVENTS']=str(events)
    env['RECOMPDEV_MONITOR_SAMPLE_EVERY']='1'
    pr=subprocess.run([str(app),str(rom),str(temp/'frame'),'2','200','-', '--video','capture','--audio','null','--input','neutral'], env=env,check=False,capture_output=True,text=True,timeout=90)
    assert pr.returncode==0,(pr.returncode,pr.stdout[-400:],pr.stderr[-800:])
    report=next(json.loads(line.partition('=')[2]) for line in pr.stdout.splitlines() if line.startswith('NATIVE_APP_RESULT='))
    assert report['status']=='BANKED_CODE_NOT_TRANSLATED',report
    rec=[json.loads(x) for x in events.read_text().splitlines()]
    assert any(x.get('type')=='instruction' for x in rec),rec
    assert any(x.get('type')=='stop' for x in rec),rec
    assert all('Shinobi' not in json.dumps(x) for x in rec)
    assert hashlib.sha256((project/'translated.cpp').read_bytes()).hexdigest()==digest
    print('CONTROLLER_MONITOR_COMPILED_NATIVE_PASS',len(rec),'events; guest stop preserved')
