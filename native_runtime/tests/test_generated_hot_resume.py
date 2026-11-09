"""End-to-end native Z80/SMS same-process dynamic instruction activation.
No commercial ROM or Ghidra; synthetic disjoint source-attested code sets.
"""
import hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path
exe,plugins,source=map(lambda x:Path(x).resolve(strict=True),sys.argv[1:4])
def run(args,timeout=120):
 p=subprocess.run([str(x) for x in args],capture_output=True,text=True,timeout=timeout)
 if p.returncode:raise AssertionError((p.returncode,p.stdout[-2500:],p.stderr[-5000:]))
 return p
with tempfile.TemporaryDirectory(prefix='rd-v27-sms-hot-resume-') as scratch:
 root=Path(scratch)
 rombytes=bytearray(0x8000)
 rombytes[0x7ff0:0x7ff8]=b'TMR SEGA'
 rom=root/'synthetic.sms';rom.write_bytes(rombytes)
 source_sha=hashlib.sha256(rombytes).hexdigest()
 modules=[]
 for n in (1,2):
  exported={'schema':'recomp-function-pcode-v1','target_id':'synthetic-hot-resume',
   'source_sha256':source_sha,'language':'z80:LE:16:default','analyzer':'synthetic-test',
   'bank_context':None,'functions':[{'entry':0,'body_min':0,'body_max':n-1,
      'instructions':[{'address':pc,'length':1,'bytes_sha256':hashlib.sha256(b'\0').hexdigest(),
       'mnemonic':'NOP','pcode':[]} for pc in range(n)]}]}
  export=root/f'export-{n}.json';export.write_text(json.dumps(exported))
  dest=root/f'compiled-{n}'
  run([exe,'--stage','native-translate','--rom',rom,'--export',export,
       '--allow-synthetic-export','--backend','full','--plugin-dir',plugins,
       '--source-root',source,'--out',dest],timeout=240)
  module=next((p for p in [dest/'build/Release/rd_generated_translation_hot.dll',dest/'build/rd_generated_translation_hot.so',dest/'build/rd_generated_translation_hot.dylib'] if p.is_file()),None)
  assert module, f'No shared hot module emitted for fixture {n}'
  modules.append(module)
  if n==1:
   (dest/'CMakeLists.txt').open('a').write('''\nadd_executable(rd_v27_sms_hot_resume "${RECOMPDEV_SOURCE_ROOT}/runtime_sms/tests/native_hot_resume_smoke.cpp" native_app_loader_bridge.cpp)\ntarget_include_directories(rd_v27_sms_hot_resume PRIVATE "${RECOMPDEV_SOURCE_ROOT}/runtime_sms/include" "${RECOMPDEV_SOURCE_ROOT}/runtime_sms/templates" "${RECOMPDEV_SOURCE_ROOT}/native_runtime/include" "${RECOMPDEV_SOURCE_ROOT}/runtime_host/include" "${RECOMPDEV_SOURCE_ROOT}/harness/include" "${RECOMPDEV_SOURCE_ROOT}/video_sms/include")\ntarget_link_libraries(rd_v27_sms_hot_resume PRIVATE rd_sms_native_runtime rd_video_sms_mode4 rd_runtime_host rd_native_module_loader)\n''')
   # Reconfigure only: the generated sources and first built module stay unchanged.
   run(['cmake','-S',dest,'-B',dest/'build','-DRECOMPDEV_SOURCE_ROOT='+str(source),'-DCMAKE_BUILD_TYPE=Release'])
   run(['cmake','--build',dest/'build','--config','Release','--target','rd_v27_sms_hot_resume','--parallel','2'],timeout=180)
   runner=next((p for p in [dest/'build/Release/rd_v27_sms_hot_resume.exe',dest/'build/rd_v27_sms_hot_resume'] if p.is_file()),None)
   assert runner,'Generated SMS hot resume smoke runner missing'
 assert len(modules)==2
 evidence=run([runner,rom,*modules],timeout=30)
 assert 'RD_V27_SMS_NATIVE_HOT_RESUME=PASS' in evidence.stdout,evidence.stdout
 print(evidence.stdout.strip())
