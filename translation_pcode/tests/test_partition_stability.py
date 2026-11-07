"""Native translator C++ partitioning must support incremental recovery builds.

A new independently byte-attested instruction may only change the generated
translation partition that contains its physical offset. The baseline fixture
contains no copyrighted ROM bytes and never invokes Ghidra.
"""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

exe=Path(sys.argv[1]).resolve(strict=True)
plugins=Path(sys.argv[2]).resolve(strict=True)
source_root=Path(sys.argv[3]).resolve(strict=True)

with tempfile.TemporaryDirectory(prefix='rd-translation-stable-partitions-') as temp:
 root=Path(temp)
 source=bytearray(0x8000)
 source[0x7ff0:0x7ff8]=b'TMR SEGA'
 rom=root/'synthetic.sms';rom.write_bytes(source)
 base={'schema':'recomp-function-pcode-v1',
       'target_id':'source-attested-partition-synthetic',
       'source_sha256':hashlib.sha256(source).hexdigest(),
       'analyzer':'synthetic-partition-test', 'language':'z80:LE:16:default',
       'bank_context':None,'functions':[{'instructions':[]}]}
 instruction_hash=hashlib.sha256(b'\x00').hexdigest()
 files=[]
 for count in (600,601):
  base['functions'][0]['instructions']=[
   {'address':n, 'length':1,'bytes_sha256':instruction_hash,
    'mnemonic':'NOP','pcode':[]} for n in range(0x200,0x200+count)]
  export=root/f'export-{count}.json';export.write_text(json.dumps(base))
  dest=root/f'generated-{count}'
  cmd=[str(exe),'--stage','native-translate','--rom',str(rom),
   '--export',str(export),'--allow-synthetic-export','--backend','full',
   '--source-root',str(source_root),'--plugin-dir',str(plugins),
   '--out',str(dest),'--no-compile']
  result=subprocess.run(cmd,text=True,capture_output=True,timeout=60)
  assert result.returncode==0,(cmd,result.stdout,result.stderr)
  manifest=json.loads((dest/'translation-manifest.json').read_text())
  assert manifest['emitted']==count and manifest['rejected']==0,manifest
  files.append({p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                for p in dest.glob('native_part_*.cpp')})
 # Critically, hundreds of source-attested cases create a separate STATIC
 # translation target. Its headers must be supplied directly to that target;
 # executable PRIVATE include paths do not propagate to object compilation.
 # This is the real-world Shinobi build layout, unlike the 8-case fixture.
 generated=root/'generated-600'
 cmake=(generated/'CMakeLists.txt').read_text()
 assert 'target_include_directories(rd_generated_translation PRIVATE' in cmake,cmake
 assert '${RECOMPDEV_SOURCE_ROOT}/runtime_sms/include' in cmake,cmake
 build=root/'partitioned-build'
 p=subprocess.run(['cmake','-S',str(generated),'-B',str(build),
                   '-DRECOMPDEV_SOURCE_ROOT='+str(source_root),'-DCMAKE_BUILD_TYPE=Release'],
                  capture_output=True,text=True,timeout=90)
 assert p.returncode==0,(p.stdout[-3000:],p.stderr[-3000:])
 p=subprocess.run(['cmake','--build',str(build),'--config','Release','--parallel','2'],
                  capture_output=True,text=True,timeout=240)
 assert p.returncode==0,(p.stdout[-4000:],p.stderr[-4000:])
 assert any(x.is_file() for x in (build/'RecompDevNativePilot',build/'Release'/'RecompDevNativePilot.exe'))
 assert len(files[0])==len(files[1])==24
 differing=[name for name in files[0] if files[0][name]!=files[1][name]]
 assert len(differing)==1,differing
print('PASS 600->601 source-verified native cases: 1 of 24 translation partitions rebuilt; partitioned native executable compiled and linked')
