"""Owner-approved external emulator capture adapter; NEVER claims independent parity.

Adapter JSON:
  {"schema":"recomp-external-oracle-adapter-v1",
   "producer":"Your independent emulator / version",
   "executable":"C:\\Tools\\ReferenceEmulator\\emulator.exe",
   "arguments":["--rom","{rom}","--events","{output}","--steps","{steps}"]}

The owner must supply an emulator that genuinely supports these options and
emits JSONL events in the RecompDev external interchange format. No emulator
is bundled, downloaded or silently installed. No shell/command templating.
"""
import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
# Support single-line absolute-path PowerShell invocations from any directory.
import sys
if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

SCHEMA='recomp-external-oracle-adapter-v1'
ALLOWED_VARS={'{rom}','{output}','{steps}'}

def _sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def capture(adapter_file,tool_root,rom_path,source_sha256,output_root,steps=500000,timeout=120):
    adapter_file=Path(adapter_file).resolve();root=Path(tool_root).resolve()
    rom=Path(rom_path).resolve();output=Path(output_root).resolve()
    if type(steps) is not int or not 1<=steps<=2000000 or type(timeout) is not int or not 1<=timeout<=300:
        raise ValueError('Invalid bounded step/time limits')
    if not re.fullmatch('[0-9a-fA-F]{64}',source_sha256):raise ValueError('ROM identity must be SHA-256')
    if not rom.is_file() or _sha(rom)!=source_sha256.lower():raise ValueError('Owner ROM SHA-256 mismatch')
    if not adapter_file.is_file() or adapter_file.stat().st_size>16*1024:
        raise ValueError('External adapter config missing/oversized')
    spec=json.loads(adapter_file.read_text(encoding='utf-8'))
    if not isinstance(spec,dict) or spec.get('schema')!=SCHEMA:raise ValueError('Invalid external adapter schema')
    producer=spec.get('producer');args=spec.get('arguments');command=spec.get('executable')
    if not isinstance(producer,str) or not producer.strip() or len(producer)>250:
        raise ValueError('Explicit external emulator/version provenance required')
    if not isinstance(command,str) or not Path(command).is_absolute():raise ValueError('Absolute executable required')
    executable=Path(command).resolve()
    if not executable.is_file() or not executable.is_relative_to(root):
        raise ValueError('Emulator executable must be under owner-approved tool root')
    if not isinstance(args,list) or len(args)>32 or any(not isinstance(x,str) or not x or len(x)>240 for x in args):
        raise ValueError('Invalid external emulator argv')
    if not ('{rom}' in args and '{output}' in args and '{steps}' in args):
        raise ValueError('Adapter must explicitly receive ROM, trace output and step bound')
    if any('{' in x or '}' in x for x in args if x not in ALLOWED_VARS):
        raise ValueError('Only whole-argument placeholders are permitted')
    if output.exists():raise ValueError('Capture output directory already exists; never overwrite previous evidence')
    output.mkdir(parents=True)
    raw=output/'external-events.jsonl'
    argv=[str(executable)]+[{'{rom}':str(rom),'{output}':str(raw),'{steps}':str(steps)}.get(x,x) for x in args]
    try:
        stdout_file=output/'oracle-stdout.log'
        stderr_file=output/'oracle-stderr.log'
        with open(stdout_file,'wb') as out,open(stderr_file,'wb') as err:
            process=subprocess.run(argv,cwd=output,stdin=subprocess.DEVNULL,
                                   stdout=out,stderr=err,timeout=timeout,check=False)
        def log_tail(f):
            with open(f,'rb') as handle:
                handle.seek(max(0,f.stat().st_size-1500))
                return handle.read(1500).decode('utf-8','replace')
        if process.returncode!=0:raise ValueError('External emulator process failed with exit '+str(process.returncode))
        if not raw.is_file():raise ValueError('External emulator did not produce the promised JSONL')
        module_file=Path(__file__).with_name('Import-Independent-Trace.py')
        spec=importlib.util.spec_from_file_location('recomp_external_trace_importer',module_file)
        imported=importlib.util.module_from_spec(spec);spec.loader.exec_module(imported)
        reference=imported.import_stream_trace(raw,output/'reference.json',source_sha256,producer,
                                               alignment='ordinal',prefix_only=True)
        report={'schema':'recomp-external-oracle-capture-v1','status':'CAPTURE_IMPORTED_NOT_PARITY_VERIFIED',
                'producer_claim':producer,'rom_sha256':source_sha256.lower(),
                'executable_sha256':_sha(executable),'adapter_sha256':_sha(adapter_file),
                'raw_trace_sha256':reference['external_raw_trace_sha256'],
                'events':reference['event_stream_manifest']['count'],
                'requested_max_steps':steps,'process_returncode':process.returncode,
                'stdout_tail':log_tail(stdout_file),
                'stderr_tail':log_tail(stderr_file),
                'independence':'UNVERIFIED_PRODUCER_CLAIM',
                'warning':'The adapter and producer are owner-supplied. This is not yet candidate/reference parity.'}
        (output/'capture-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        return report
    except (ValueError,subprocess.TimeoutExpired, OSError):
        # Evidence directory is intentionally retained for owner diagnostics.
        (output/'capture-failed.txt').write_text('External capture did not produce verified reference evidence.\n',encoding='utf-8')
        raise

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--adapter',required=True)
    p.add_argument('--allowed-tool-root',required=True)
    p.add_argument('--rom',required=True)
    p.add_argument('--source-sha256',required=True)
    p.add_argument('--output-dir',required=True)
    p.add_argument('--steps',type=int,default=500000)
    p.add_argument('--timeout',type=int,default=120)
    a=p.parse_args()
    report=capture(a.adapter,a.allowed_tool_root,a.rom,a.source_sha256,a.output_dir,a.steps,a.timeout)
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
