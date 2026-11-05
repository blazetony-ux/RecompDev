"""Real compiled source-attested game adapter, without a window or real ROM."""
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
ROM=ROOT/'harness/examples/recomp-pcode/synthetic.sms'
DOC=json.loads((ROOT/'harness/examples/recomp-pcode/function-export.json').read_text())

with tempfile.TemporaryDirectory(prefix='recomp-native-host-generated-') as folder:
    temp=Path(folder);project=temp/'native-project';build=temp/'build'
    summary=generate_project(DOC,ROM,project)
    original=hashlib.sha256((project/'translated.cpp').read_bytes()).hexdigest()
    assert summary['translated_instructions']==6
    setup=install(project)
    assert setup['generated_game_code_sha256']==original
    assert install(project)['files_changed']==[]
    conf=['cmake','-S',str(project),'-B',str(build),'-DCMAKE_BUILD_TYPE=Release']
    if os.name=='nt':conf+=['-A','x64']
    subprocess.run(conf,capture_output=True,text=True,check=True,timeout=120)
    subprocess.run(['cmake','--build',str(build),'--config','Release','--target','RecompDevNativeApp','--parallel','2'],capture_output=True,text=True,check=True,timeout=180)
    app=next((p for p in [build/'Release/RecompDevNativeApp.exe',build/'RecompDevNativeApp.exe',build/'RecompDevNativeApp'] if p.is_file()),None)
    assert app, 'Source-attested native generated game failed to compile'
    env=os.environ.copy()
    env['RECOMPDEV_RUNTIME_HOST_DLL']=sys.argv[1]
    out=temp/'capture'
    p=subprocess.run([str(app),str(ROM),str(out),'2','200','-',
                      '--video','capture','--audio','capture','--input','neutral'],
                     capture_output=True,text=True,timeout=90,env=env)
    assert p.returncode==0,(p.returncode,p.stdout[-500:],p.stderr[-1200:])
    marker=next((line for line in p.stdout.splitlines() if line.startswith('NATIVE_APP_RESULT=')),None)
    assert marker,p.stdout[-500:]
    result=json.loads(marker.split('=',1)[1])
    assert result['native_steps']==6 and result['status']=='BANKED_CODE_NOT_TRANSLATED',result
    assert result['hardware_parity']=='NOT_TESTED'
    assert hashlib.sha256((project/'translated.cpp').read_bytes()).hexdigest()==original
    print('GENERATED_NATIVE_APP_HOST_BRIDGE_PASS; verified translated C++ unchanged; expected stop at missing bank code')
