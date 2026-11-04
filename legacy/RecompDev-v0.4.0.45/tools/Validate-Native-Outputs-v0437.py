#!/usr/bin/env python3
"""Compile real RecompDev SMS device/output code and independently verify exact PPM/WAV bytes."""
import argparse,json,shutil,subprocess,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nativecore.output_qualification_v0437 import verify_outputs
ROOT=Path(__file__).resolve().parents[1]

def run(output=None):
    src=ROOT/'hardware/tests/output_probe_v0437'
    with tempfile.TemporaryDirectory(prefix='recomp-v0437-') as tmp:
        build=Path(tmp)/'build'
        for cmd in (['cmake','-S',str(src),'-B',str(build),'-DCMAKE_BUILD_TYPE=Release'],
                    ['cmake','--build',str(build),'--config','Release']):
            p=subprocess.run(cmd,capture_output=True,text=True,timeout=150,errors='replace')
            if p.returncode:
                raise RuntimeError('Compiled output probe build failed: '+(p.stdout+p.stderr)[-3500:])
        binaries=[p for p in build.rglob('*') if p.is_file() and p.stem=='RecompDevNativeOutputProbe'
                  and (p.suffix in ('','.exe'))]
        if len(binaries)!=1:raise RuntimeError('Cannot uniquely locate compiled native output probe')
        prefix=Path(tmp)/'output'
        p=subprocess.run([str(binaries[0]),str(prefix)],capture_output=True,text=True,timeout=30)
        if p.returncode or 'NATIVE_OUTPUT_PROBE=CREATED' not in p.stdout:
            raise RuntimeError('Compiled probe failed: '+(p.stdout+p.stderr)[-2000:])
        report=verify_outputs(str(prefix)+'.ppm',str(prefix)+'.wav')
        if output:
            target=Path(output);target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        if report['status']!='PASS':raise ValueError('Native output expected bytes diverged; '+json.dumps(report))
        return report

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--output',type=Path)
    args=a.parse_args()
    if not shutil.which('cmake'):raise SystemExit('CMake not installed')
    print(json.dumps(run(args.output),indent=2))
