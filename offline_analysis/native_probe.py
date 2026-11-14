"""Strict offline-to-native *control-flow probe*, not a playable-game exporter.

Consumes a source-hashed offline-analysis report; asks the selected CPU provider
for an independently supported minimal native-control-flow operation. The host
compiler builds those operations into a standalone switch dispatch. Unsupported
instructions, speculative paths, unqualified mapper contexts and source changes
are never lifted. This probe deliberately does NOT implement CPU flags, RAM,
video, audio, interrupts or full game semantics.
"""
from __future__ import annotations
import argparse,hashlib,json,os,re,shutil,subprocess,sys,tempfile
from pathlib import Path
if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from offline_analysis.engine import AnalysisFailure,_plugin,registry

SCHEMA='recompdev.offline.native-probe.v1'
def sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def _inside_report(report_dir:Path,name:str)->Path:
    if not re.fullmatch(r'[a-z][a-z0-9-]*\.json',name):raise AnalysisFailure('PROBE_REPORT_PATH_UNSAFE')
    file=report_dir/name
    if file.is_symlink() or not file.is_file():raise AnalysisFailure('PROBE_REPORT_MEMBER_MISSING')
    return file

def _attest(source:Path,analysis:Path):
    if source.is_symlink() or not source.is_file() or analysis.is_symlink() or not analysis.is_dir():
        raise AnalysisFailure('PROBE_SOURCE_OR_ANALYSIS_INVALID')
    data=source.read_bytes()
    report=json.loads(_inside_report(analysis,'analysis.json').read_text(encoding='utf8'))
    if (report.get('schema')!='recompdev.offline.analysis.v1' or
        report.get('source_sha256')!=sha(data) or
        report.get('source_bytes')!=len(data) or
        report.get('launches_game') is not False or
        report.get('status') not in ('ANALYSED_PARTIAL','ANALYSED_STATIC_CANDIDATES')):
        raise AnalysisFailure('PROBE_SOURCE_OR_REPORT_ATTESTATION_FAILED')
    reg=next((p for p in registry() if p['id']==report.get('profile')),None)
    if reg is None:raise AnalysisFailure('PROBE_PROFILE_NOT_REGISTERED')
    provenance=report.get('plugin_provenance',{})
    for kind in ('format','cpu','machine'):
        if kind not in provenance or provenance[kind].get('module')!=reg[kind]:
            raise AnalysisFailure('PROBE_PROVIDER_IDENTITY_MISMATCH')
        _,att=_plugin(reg[kind])
        if provenance[kind].get('source_sha256')!=att['source_sha256']:
            raise AnalysisFailure('PROBE_PROVIDER_SOURCE_CHANGED')
    artifacts=report.get('artifacts',{})
    for name,entry in artifacts.items():
        if entry.get('file')!=name:raise AnalysisFailure('PROBE_ARTIFACT_PATH_MISMATCH')
        raw=_inside_report(analysis,name).read_bytes()
        if len(raw)!=entry.get('bytes') or sha(raw)!=entry.get('sha256'):
            raise AnalysisFailure('PROBE_ARTIFACT_TAMPERED')
    instructions=json.loads(_inside_report(analysis,'instructions.json').read_text(encoding='utf8'))
    if not isinstance(instructions,list):raise AnalysisFailure('PROBE_INSTRUCTIONS_INVALID')
    return data,report,reg,instructions

def prepare(source:Path,analysis:Path,output:Path,*,rights_confirmed=False)->dict:
    """Produce a native-code source tree. No game image is embedded or executed."""
    if not rights_confirmed:raise AnalysisFailure('PROBE_EXPLICIT_SOURCE_RIGHTS_CONFIRMATION_REQUIRED')
    output=Path(output).absolute()
    if output.exists():raise AnalysisFailure('PROBE_OUTPUT_EXISTS_REFUSING_OVERWRITE')
    data,report,reg,rows=_attest(Path(source),Path(analysis))
    cpu,_=_plugin(reg['cpu'])
    lift=getattr(cpu,'lift_probe',None)
    if not callable(lift):raise AnalysisFailure('PROBE_CPU_LIFTER_UNAVAILABLE')
    bypc={};excluded={'speculative':0,'unsupported':0,'ambiguous':0}
    for row in rows:
        if row.get('classification')!='STATIC_DECODE_CANDIDATE_NOT_SEMANTICALLY_QUALIFIED':
            excluded['speculative']+=1;continue
        pc=row.get('pc');off=row.get('physical');size=row.get('length')
        if not all(type(x)==int for x in (pc,off,size)) or size<1 or size>16 or off<0 or off+size>len(data):
            raise AnalysisFailure('PROBE_SOURCE_RANGE_INVALID')
        raw=data[off:off+size]
        if sha(raw)!=row.get('bytes_sha256'):raise AnalysisFailure('PROBE_INSTRUCTION_HASH_MISMATCH')
        op=lift(raw,pc)
        if op is None:
            excluded['unsupported']+=1;continue
        if type(op)!=dict or op.get('kind') not in ('next','jump','stop'):
            raise AnalysisFailure('PROBE_LIFTER_CONTRACT_INVALID')
        target=pc+size if op['kind']=='next' else op.get('target')
        if op['kind']=='jump' and (type(target)!=int or target<0 or target>0xffffffff):
            raise AnalysisFailure('PROBE_LIFTER_TARGET_INVALID')
        if pc in bypc and bypc[pc]!=(off,size,op['kind'],target):
            excluded['ambiguous']+=1
            bypc[pc]=None
        elif pc not in bypc:
            bypc[pc]=(off,size,op['kind'],target)
    usable=sorted((pc,item) for pc,item in bypc.items() if item is not None)
    if not usable:raise AnalysisFailure('PROBE_NO_SUPPORTED_NON_SPECULATIVE_INSTRUCTIONS')
    entry=next((v['pc'] for v in report.get('entry_points',[]) if v['reason'] in ('reset','reset-vector','ps-x-exe-entry')),None)
    if type(entry)!=int or entry not in bypc or bypc[entry] is None:
        raise AnalysisFailure('PROBE_ENTRY_IS_NOT_LIFTABLE')
    cases=[]
    for pc,(off,size,kind,target) in usable:
        statement=('status="HALTED";break;' if kind=='stop' else
                   'pc='+str(target)+'u;break;')
        cases.append(f'    case {pc}u: {statement}')
    content='''// RecompDev offline native control-flow probe. Source-attested only.
// Generated from independently selected CPU plugin; NO emulation/runtime parity.
#include <cstdint>
#include <cstdio>
#include <cstdlib>
int main(int argc,char** argv){
 unsigned long long budget=1000u;
 if(argc>1){char* end=nullptr;budget=std::strtoull(argv[1],&end,10);
   if(!end||*end||budget<1||budget>1000000)return 3;}
 std::uint32_t pc=ENTRYu; unsigned long long steps=0;
 const char* status="STEP_BUDGET_REACHED";
 for(;steps<budget;){
  bool stop=false;
  switch(pc){
CASES
    default: status="UNTRANSLATED_PATH";stop=true;break;
  }
  if(stop)break;
  ++steps;
  if(status[0]=='H')break;
 }
 std::printf("RECOMPDEV_OFFLINE_NATIVE_PROBE={\\"status\\":\\"%s\\",\\"native_steps\\":%llu,\\"pc\\":%u}\\n",status,steps,pc);
 return status[0]=='U'?2:0;
}
'''.replace('ENTRY',str(entry)).replace('CASES','\n'.join(cases))
    cmake='''cmake_minimum_required(VERSION 3.17)
project(RecompDevOfflineNativeProbe LANGUAGES CXX)
add_executable(RecompDevOfflineNativeProbe native_probe.cpp)
target_compile_features(RecompDevOfflineNativeProbe PRIVATE cxx_std_17)
if(MSVC)
 set_property(TARGET RecompDevOfflineNativeProbe PROPERTY MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
 target_compile_options(RecompDevOfflineNativeProbe PRIVATE /W4 /EHsc)
else()
 target_compile_options(RecompDevOfflineNativeProbe PRIVATE -Wall -Wextra -Wpedantic)
endif()
'''
    manifest={'schema':SCHEMA,'status':'UNQUALIFIED_NATIVE_CONTROL_FLOW_SOURCE',
              'source_sha256':sha(data),'analysis_manifest_sha256':sha(_inside_report(Path(analysis),'analysis.json').read_bytes()),
              'profile':report['profile'],'cpu':report['cpu'],'machine':report['machine'],
              'entry':entry,'lifted_instructions':len(usable),'excluded':excluded,
              'native_execution_parity':False,'gameplay_qualified':False,
              'full_cpu_semantics':False,'runtime_hardware_services':False,
              'external_game_data_embedded':False,'rights_confirmed':True}
    output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_name(output.name+'.partial-'+str(os.getpid()))
    if temp.exists():raise AnalysisFailure('PROBE_STAGING_EXISTS')
    temp.mkdir()
    try:
        (temp/'native_probe.cpp').write_text(content,encoding='utf8')
        (temp/'CMakeLists.txt').write_text(cmake,encoding='utf8')
        manifest['generated_cpp_sha256']=sha((temp/'native_probe.cpp').read_bytes())
        (temp/'native-probe.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n',encoding='utf8')
        temp.rename(output)
    except Exception:
        shutil.rmtree(temp,ignore_errors=True)
        raise
    return manifest

def main(argv=None)->int:
    p=argparse.ArgumentParser(description='Offline static candidates to minimal native control-flow probe (NOT full game recompilation)')
    p.add_argument('--rom',type=Path,required=True)
    p.add_argument('--analysis',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--rights-confirmed',action='store_true')
    a=p.parse_args(argv)
    try:
        result=prepare(a.rom,a.analysis,a.out,rights_confirmed=a.rights_confirmed)
        print('RECOMPDEV_OFFLINE_NATIVE_HANDOFF='+json.dumps(result,sort_keys=True));return 0
    except (AnalysisFailure,ValueError,OSError,KeyError) as e:
        print('RECOMPDEV_OFFLINE_NATIVE_HANDOFF_ERROR='+str(e),file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
