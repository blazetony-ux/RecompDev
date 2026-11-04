"""Source-attested, bounded M68000/MIPS -> native C++17 subset.

The generated artifact contains translated operations, not a ROM interpreter.
Untranslated opcodes and unmapped control flow fail closed. Not a console runtime.
"""
import hashlib
import json
import subprocess
from collections import deque
from pathlib import Path
from adapters.formats import open_image


def signed(v,bits):return v-(1<<bits) if v&(1<<(bits-1)) else v


def _hex(v):return f'0x{v&0xffffffff:08x}u'


def instruction(image,pc):
    if not image.valid(pc):return None
    o=image.offset(pc); data=image.data
    if image.isa=='mips':
        if o+4>len(data):return None
        raw=data[o:o+4];w=int.from_bytes(raw,'little');op=w>>26;rs=(w>>21)&31;rt=(w>>16)&31;rd=(w>>11)&31;sh=(w>>6)&31;fn=w&63;imm=w&0xffff
        nextpc=pc+4; succ=[nextpc];desc='';expr='';delayed=False;terminal=False
        if w==0:desc='NOP';expr=''
        elif op==15 and rs==0:desc='LUI';expr=f'r[{rt}]={_hex(imm<<16)};'
        elif op==13:desc='ORI';expr=f'r[{rt}]=r[{rs}]|{_hex(imm)};'
        elif op==12:desc='ANDI';expr=f'r[{rt}]=r[{rs}]&{_hex(imm)};'
        elif op==14:desc='XORI';expr=f'r[{rt}]=r[{rs}]^{_hex(imm)};'
        elif op==9:desc='ADDIU';expr=f'r[{rt}]=r[{rs}]+{_hex(signed(imm,16))};'
        elif op==0 and fn in (33,35,36,37,38,39):
            desc={33:'ADDU',35:'SUBU',36:'AND',37:'OR',38:'XOR',39:'NOR'}[fn]
            ex={33:f'r[{rs}]+r[{rt}]',35:f'r[{rs}]-r[{rt}]',36:f'r[{rs}]&r[{rt}]',37:f'r[{rs}]|r[{rt}]',38:f'r[{rs}]^r[{rt}]',39:f'~(r[{rs}]|r[{rt}])'}[fn]
            expr=f'r[{rd}]={ex};'
        elif op==0 and fn in (0,2,3) and rs==0:
            desc={0:'SLL',2:'SRL',3:'SRA'}[fn]
            ex={0:f'r[{rt}]<<{sh}',2:f'r[{rt}]>>{sh}',3:f'(uint32_t)((int32_t)r[{rt}]>>{sh})'}[fn]
            expr=f'r[{rd}]={ex};'
        elif op in (4,5):
            desc='BEQ' if op==4 else 'BNE';target=pc+4+(signed(imm,16)<<2)
            cond='==' if op==4 else '!='
            expr=f'pending=true;pending_target=(r[{rs}]{cond}r[{rt}])?{_hex(target)}:{_hex(pc+8)};'
            succ=[pc+4,target,pc+8];delayed=True
        elif op in (2,3):
            desc='JAL' if op==3 else 'J';target=((pc+4)&0xf0000000)|((w&0x3ffffff)<<2)
            expr=(f'r[31]={_hex(pc+8)};' if op==3 else '')+f'pending=true;pending_target={_hex(target)};'
            succ=[pc+4,target]+([pc+8] if op==3 else []);delayed=True
        elif op==0 and fn in (8,9):
            desc='JR' if fn==8 else 'JALR';expr=f'pending=true;pending_target=r[{rs}];'+(f'r[{rd}]={_hex(pc+8)};' if fn==9 and rd else '')
            succ=[pc+4];delayed=True
        else:return {'pc':pc,'size':4,'raw':raw,'supported':False,'desc':f'MIPS_UNSUPPORTED_{w:08x}','succ':[],'terminal':True,'delay':False}
        if delayed:expr+=' if(was_pending){unsupported_delay_slot=true;}'
        return {'pc':pc,'size':4,'raw':raw,'supported':True,'desc':desc,'code':expr,'succ':succ,'terminal':terminal,'delay':delayed}
    if o+2>len(data):return None
    w=int.from_bytes(data[o:o+2],'big');size=2;desc='';code='';succ=[pc+2];terminal=False
    if w==0x4e71:desc='NOP'
    elif w==0x4e75:desc='RTS';code='if(call_stack.empty()){stop_reason="RETURNED_TO_HOST";halted=true;}else{next_pc=call_stack.back();call_stack.pop_back();}';succ=[];terminal=True
    elif (w&0xf100)==0x7000:
        reg=(w>>9)&7;imm=signed(w&255,8);desc='MOVEQ';code=f'd[{reg}]={_hex(imm)};nz(d[{reg}]);'
    elif (w&0xf1f8) in (0x5080,0x5180):
        reg=w&7;val=(w>>9)&7 or 8;sub=bool(w&0x0100);desc='SUBQ.L' if sub else 'ADDQ.L';op='-' if sub else '+'
        code=f'd[{reg}]=d[{reg}]{op}{val}u;nz(d[{reg}]);'
    elif (w&0xf000)==0x6000:
        cc=(w>>8)&15; disp=w&255
        if disp==0:
            if o+4>len(data):return None
            size=4;disp=signed(int.from_bytes(data[o+2:o+4],'big'),16)
        elif disp==255:return {'pc':pc,'size':2,'raw':data[o:o+2],'supported':False,'desc':'M68K_LONG_BRANCH_NOT_68000','succ':[],'terminal':True,'delay':False}
        else:disp=signed(disp,8)
        target=(pc+2+disp)&0xffffffff;after=pc+size
        if cc==0:desc='BRA';code=f'next_pc={_hex(target)};';succ=[target];terminal=True
        elif cc==1:desc='BSR';code=f'call_stack.push_back({_hex(after)});next_pc={_hex(target)};';succ=[target,after];terminal=True
        elif cc in (6,7):
            desc='BNE' if cc==6 else 'BEQ';cond='!z' if cc==6 else 'z'
            code=f'if({cond})next_pc={_hex(target)};';succ=[target,after]
        else:return {'pc':pc,'size':size,'raw':data[o:o+size],'supported':False,'desc':'M68K_BCC_FLAGS_UNSUPPORTED','succ':[],'terminal':True,'delay':False}
    elif (w&0xffc0) in (0x4e80,0x4ec0):
        is_call=(w&0xffc0)==0x4e80;mode=(w>>3)&7;reg=w&7
        if mode!=7 or reg not in (0,1,2):return {'pc':pc,'size':2,'raw':data[o:o+2],'supported':False,'desc':'M68K_DYNAMIC_JUMP_UNSUPPORTED','succ':[],'terminal':True,'delay':False}
        size=6 if reg==1 else 4
        if o+size>len(data):return None
        if reg==0:target=signed(int.from_bytes(data[o+2:o+4],'big'),16)&0xffffffff
        elif reg==1:target=int.from_bytes(data[o+2:o+6],'big')
        else:target=(pc+2+signed(int.from_bytes(data[o+2:o+4],'big'),16))&0xffffffff
        desc='JSR' if is_call else 'JMP';code=(f'call_stack.push_back({_hex(pc+size)});' if is_call else '')+f'next_pc={_hex(target)};'
        succ=[target]+([pc+size] if is_call else []);terminal=True
    else:return {'pc':pc,'size':2,'raw':data[o:o+2],'supported':False,'desc':f'M68K_UNSUPPORTED_{w:04x}','succ':[],'terminal':True,'delay':False}
    return {'pc':pc,'size':size,'raw':data[o:o+size],'supported':True,'desc':desc,'code':code,'succ':succ,'terminal':terminal,'delay':False}


def trace(image,max_ins=160):
    if not 1<=max_ins<=4096:raise ValueError('maximum decoded instruction bound is 1..4096')
    q=deque([image.entry]);seen={};pending=set()
    while q and len(seen)<max_ins:
        pc=q.popleft()
        if pc in seen:continue
        ins=instruction(image,pc)
        if ins is None:continue
        seen[pc]=ins
        if image.isa=='mips' and ins['delay']:
            slot=instruction(image,pc+4)
            if slot is None or not slot['supported'] or slot['delay']:
                raise ValueError(f'MIPS delay slot unsupported at {pc+4:#x}')
            pending.add(pc+4)
        if ins['supported']:
            for dst in ins['succ']:
                if image.valid(dst) and dst not in seen:q.append(dst)
    return seen, bool(q)


def generate(source,out,fmt='auto',isa=None,endian=None,base=None,entry=None,
             max_instructions=160,expected_sha256=None,require_supported=False):
    source=Path(source).resolve(strict=True);data=source.read_bytes();sha=hashlib.sha256(data).hexdigest()
    if expected_sha256 is not None and sha!=expected_sha256.lower():raise ValueError('source SHA-256 mismatch')
    image=open_image(data,fmt,isa,endian,base,entry)
    graph,bounded=trace(image,max_instructions)
    unsupported=[{'pc':pc,'reason':ins['desc']} for pc,ins in sorted(graph.items()) if not ins['supported']]
    if not graph:raise ValueError('no mapped instructions to compile')
    if require_supported and (unsupported or bounded):raise ValueError('strict compilation: unsupported or bounded instruction found: '+str(unsupported[:3]))
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    cases=[]
    for pc,ins in sorted(graph.items()):
        if ins['supported']:
            action=ins['code']
        else:
            action='stop_reason="UNSUPPORTED_TRANSLATION";halted=true;'
        cases.append(f'case {_hex(pc)}:{{ /* {ins["desc"]} */ {action} break;}}')
    prelude='''#include <cstdint>\n#include <iostream>\n#include <string>\n#include <vector>\n#include <cstdlib>\n'''
    if image.isa=='mips':
        body='''uint32_t r[32]={0};bool pending=false;uint32_t pending_target=0;bool unsupported_delay_slot=false;'''
        logic='''bool was_pending=pending;uint32_t prior_target=pending_target;pending=false;'''
        post='''r[0]=0;if(unsupported_delay_slot){stop_reason="INVALID_DELAY_SLOT";halted=true;}if(!halted)pc=was_pending?prior_target:pc+4;'''
        signature='''for(int i=0;i<32;i++)fingerprint=(fingerprint^r[i])*1099511628211ULL;
 std::cout<<",\\"registers\\":[";for(int i=0;i<32;i++){if(i)std::cout<<",";std::cout<<r[i];}std::cout<<"]";'''
    else:
        body='''uint32_t d[8]={0};bool z=false,n=false;std::vector<uint32_t>call_stack;auto nz=[&](uint32_t v){z=v==0;n=bool(v&0x80000000u);};'''
        logic='''uint32_t next_pc=pc+2;'''
        post='''if(!halted)pc=next_pc;'''
        signature='''for(int i=0;i<8;i++)fingerprint=(fingerprint^d[i])*1099511628211ULL;fingerprint=(fingerprint^(z?1:0))*1099511628211ULL;
 std::cout<<",\\"registers\\":[";for(int i=0;i<8;i++){if(i)std::cout<<",";std::cout<<d[i];}std::cout<<"],\\"z\\":"<<(z?"true":"false");'''
    signature,state_fields=signature.split('\n std::cout',1)
    state_fields='std::cout'+state_fields
    # For M68K, overwrite next_pc with actual decoded sequential length per case.
    if image.isa=='m68k':
        for i,(pc,ins) in enumerate(sorted(graph.items())):
            cases[i]=cases[i].replace('*/ ',f'*/ next_pc={_hex(pc+ins["size"])}; ',1)
    code=prelude+'''int main(int argc,char**argv){
 uint64_t limit=100000;if(argc>1){char*e=nullptr;limit=std::strtoull(argv[1],&e,10);if(!e||*e||limit==0||limit>10000000){std::cerr<<"invalid step budget\\n";return 2;}}
 uint32_t pc='''+_hex(image.entry)+''';uint64_t steps=0;bool halted=false;std::string stop_reason="STEP_BUDGET_REACHED";
 '''+body+'''
 while(!halted&&steps<limit){
 '''+logic+'''
 switch(pc){
 '''+'\n'.join(cases)+'''
 default:{stop_reason="UNMAPPED_TRANSLATED_PC";halted=true;break;}
 }
 ++steps;
 '''+post+'''
 }
 uint64_t fingerprint=1469598103934665603ULL;
 '''+signature+'''
 std::cout<<"{\\"schema\\":\\"recomp-source-native-subset-v0432\\",\\"isa\\":\\"'''+image.isa+'''\\",\\"steps\\":"<<steps<<",\\"pc\\":"<<pc<<",\\"fingerprint\\":"<<fingerprint<<",\\"stop\\":\\""<<stop_reason<<"\\"";
 '''+state_fields+'''
 std::cout<<"}"<<std::endl;
 return stop_reason=="UNSUPPORTED_TRANSLATION"||stop_reason=="INVALID_DELAY_SLOT"?3:0;
}
'''
    (out/'translated.cpp').write_bytes(code.encode('utf-8'))
    (out/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.16)\nproject(RecompNativeSubset LANGUAGES CXX)\nadd_executable(RecompNativeSubset translated.cpp)\ntarget_compile_features(RecompNativeSubset PRIVATE cxx_std_17)\nif(MSVC)\n target_compile_options(RecompNativeSubset PRIVATE /W3 /EHsc)\nelse()\n target_compile_options(RecompNativeSubset PRIVATE -Wall -Wextra)\nendif()\n',encoding='utf-8')
    report={'schema':'recomp-multisa-native-build-v0432','source_sha256':sha,'container':image.container,'isa':image.isa,'entry':image.entry,
        'translated_instructions':sum(x['supported'] for x in graph.values()),'unsupported_boundaries':unsupported,
        'bounded':bounded,'native_qualified':False,'independent_parity':'NOT_ESTABLISHED',
        'instruction_proofs':[{'pc':pc,'sha256':hashlib.sha256(i['raw']).hexdigest(),'supported':i['supported'],'mnemonic':i['desc']} for pc,i in sorted(graph.items())],
        'output':str(out),'generated_cpp_sha256':hashlib.sha256(code.encode('utf-8')).hexdigest(),'qualification':'RESTRICTED_COMPILED_SOURCE_INSTRUCTIONS_NOT_GAMEPLAY'}
    (out/'build-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


def compile_project(project):
    project=Path(project).resolve(strict=True)
    report=json.loads((project/'build-report.json').read_text())
    if hashlib.sha256((project/'translated.cpp').read_bytes()).hexdigest()!=report['generated_cpp_sha256']:
        raise ValueError('generated translation changed after source-attested emission')
    for cmd in (['cmake','-S',str(project),'-B',str(project/'build')],['cmake','--build',str(project/'build'),'--config','Release']):
        p=subprocess.run(cmd,text=True,capture_output=True,timeout=180)
        if p.returncode:raise RuntimeError('native compiler failed: '+p.stdout[-3000:]+p.stderr[-3000:])
    candidates=list((project/'build').rglob('RecompNativeSubset.exe' if __import__('os').name=='nt' else 'RecompNativeSubset'))
    candidates=[p for p in candidates if p.is_file()]
    if len(candidates)!=1:raise ValueError('native executable not uniquely identified')
    return candidates[0]
