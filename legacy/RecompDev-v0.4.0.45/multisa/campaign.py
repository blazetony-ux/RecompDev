"""One bounded source-attested scan -> triage -> native subset campaign.

Runs against owner-supplied source only. Does not automatically elevate static
candidates into verified whole functions or claim guest hardware correctness.
"""
import hashlib,json,subprocess
from pathlib import Path
from discovery_benchmark import benchmark
from multisa.native import generate,compile_project


def run(source,out,fmt='auto',isa=None,endian=None,base=None,entry=None,
        seed_vectors=False,max_instructions=100000,compile=False,run_steps=None,expected_sha256=None):
    source=Path(source).resolve(strict=True)
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    if expected_sha256 is not None and expected_sha256.lower()!=sha:raise ValueError('source SHA-256 mismatch')
    if run_steps is not None and not compile:raise ValueError('running a native slice requires native compilation')
    out=Path(out).resolve()
    if (out/'campaign-result.json').exists():raise ValueError('campaign result already exists; no silent overwrite')
    bench=benchmark(source,out/'discovery',fmt=fmt,isa=isa,endian=endian,base=base,entry=entry,
                    seed_vectors=seed_vectors,max_instructions=max_instructions,expected_sha256=sha)
    native=generate(source,out/'native-slice',fmt=fmt,isa=isa,endian=endian,base=base,entry=entry,
                    max_instructions=min(512,max_instructions),expected_sha256=sha)
    stage={'name':'native_compilation','status':'NOT_REQUESTED'};execution={'status':'NOT_REQUESTED'}
    if compile:
        try:
            exe=compile_project(out/'native-slice')
            stage={'name':'native_compilation','status':'COMPILED_SUBSET',
                   'executable_sha256':hashlib.sha256(exe.read_bytes()).hexdigest()}
            if run_steps is not None:
                if not 1<=run_steps<=10000000:raise ValueError('run step count out of range')
                p=subprocess.run([str(exe),str(run_steps)],capture_output=True,text=True,timeout=90)
                execution=json.loads(p.stdout) if p.stdout.strip().startswith('{') else {'status':'NO_RUN_REPORT','stderr':p.stderr[-1000:]}
                execution['process_exit_code']=p.returncode
        except Exception as exc:
            stage={'name':'native_compilation','status':'COMPILATION_BLOCKED','reason':str(exc)[-2000:]}
    result={'schema':'recomp-universal-conversion-campaign-v0432','release':'0.4.0.32',
            'source_sha256':sha,'container':bench['system'],'discovery_baseline':bench['baseline'],
            'discovery_enhanced':bench['enhanced'],'discovery_delta':bench['delta'],
            'barrier_triage':bench['barrier_triage'],'native_subset':{
                'translated_instructions':native['translated_instructions'],
                'unsupported_boundaries':native['unsupported_boundaries'],'bounded':native['bounded'],
                'generated_cpp_sha256':native['generated_cpp_sha256']},
            'compiler':stage,'execution':execution,'hardware_runtime':'NOT_INTEGRATED_FOR_NONZ80',
            'independent_parity':'NOT_ESTABLISHED','native_qualified':False,
            'next_action':('INVESTIGATE_UNSUPPORTED_ISA_SEMANTICS' if native['unsupported_boundaries'] else
                         'INDEPENDENT_CPU_CHECKPOINT_COMPARISON_REQUIRED'),
            'game_specific_fixes':0}
    out.mkdir(parents=True,exist_ok=True)
    (out/'campaign-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result
