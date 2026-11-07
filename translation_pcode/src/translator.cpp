#include "rd_translation_v1.h"
#include "rd_tiny_json.hpp"
#include "rd_sha256.hpp"
#include "rd_z80_native_codegen_v1.h"
#include "rd_native_discovery_v1.h"
#include <algorithm>
#include <cstring>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#else
#include <dlfcn.h>
#endif
namespace fs=std::filesystem;
using J=rdjson::V;
namespace {
struct Instruction {int pc=0,phys=0,length=0,fall=0;std::string name,hash,pcode_signature,source_code;J pcode;};
std::string read_file(const fs::path&p,size_t limit){
 if(!fs::is_regular_file(p)||fs::file_size(p)>limit)throw std::runtime_error("INPUT_MISSING_OR_TOO_LARGE: "+p.string());
 std::ifstream f(p,std::ios::binary);if(!f)throw std::runtime_error("INPUT_UNREADABLE");
 return std::string(std::istreambuf_iterator<char>(f),{});
}
std::string hash(const std::string&s){return rdhash::sha256(reinterpret_cast<const uint8_t*>(s.data()),s.size());}
uint64_t number(const J&v,const std::string&name,uint64_t maximum=0x100000000ull){
 auto n=v.get(name).integer();
 if(n<0||uint64_t(n)>maximum)throw std::runtime_error("INVALID_INTEGER_"+name);
 return uint64_t(n);
}
int num(const J&v,const std::string&name){return int(number(v,name,0x7fffffffu));}
std::string str(const J&v,const std::string&name){return v.get(name).string();}
std::string qhex(unsigned n,unsigned width=0){std::ostringstream o;o<<"0x"<<std::hex<<std::setfill('0')<<std::setw(int(width))<<n<<"u";return o.str();}
std::string qint(int n){return std::to_string(n)+"u";}
std::string qwide(uint64_t n){return std::to_string(n)+"ull";}
std::string var_read(const J&v,bool full){
 const std::string space=str(v,"space");const uint64_t off=number(v,"offset");int size=num(v,"size");
 if(size<1||size>8)throw std::runtime_error("VARNODE_WIDTH_UNSUPPORTED");
 if(space=="const")return qwide(off);
 if(space=="register"){
  if(!(full ? (off+size<=256) : ((off+size<=8)||(off>=68&&off+size<=70))))
   throw std::runtime_error("CPU_REGISTER_NOT_SUPPORTED_BY_SELECTED_BACKEND");
  return "s.get_register("+qwide(off)+","+qint(size)+")";
 }
 if(space=="unique"){
  if(off>uint64_t(1024u*1024u-size))throw std::runtime_error("UNIQUE_TEMPORARY_OOB");
  return "s.get_unique("+qwide(off)+","+qint(size)+")";
 }
 if(space=="ram")return "s.memory("+qwide(off)+","+qint(size)+")";
 throw std::runtime_error("UNMODELLED_VARNODE_READ: "+space);
}
std::string var_write(const J&v,const std::string&e,bool full){
 const std::string space=str(v,"space");const uint64_t off=number(v,"offset");int sz=num(v,"size");
 if(sz<1||sz>8)throw std::runtime_error("VARNODE_WIDTH_UNSUPPORTED");
 if(space=="register"){
  if(!(full ? (off+sz<=256) : ((off+sz<=8)||(off>=68&&off+sz<=70))))
   throw std::runtime_error("CPU_REGISTER_NOT_SUPPORTED_BY_SELECTED_BACKEND");
  return "s.set_register("+qwide(off)+","+qint(sz)+","+e+");";
 }
 if(space=="unique"){
  if(off>1024u*1024u-sz)throw std::runtime_error("UNIQUE_TEMPORARY_OOB");
  return "s.set_unique("+qwide(off)+","+qint(sz)+","+e+");";
 }
 if(space=="ram")return "s.write_memory("+qwide(off)+","+qint(sz)+","+e+");";
 throw std::runtime_error("UNMODELLED_VARNODE_WRITE: "+space);
}
std::string alu(const std::string&op){
 static const std::set<std::string> names={"COPY","INT_AND","INT_OR","INT_LEFT","INT_ADD","INT_EQUAL","INT_RIGHT","INT_SRIGHT",
 "INT_SUB","INT_SLESS","INT_XOR","INT_NOTEQUAL","INT_ZEXT","INT_2COMP","INT_CARRY","INT_SCARRY","INT_LESSEQUAL",
 "INT_SBORROW","BOOL_OR","BOOL_XOR","INT_LESS","BOOL_NEGATE","INT_NEGATE"};
 return names.count(op)?op:std::string();
}
std::vector<std::string> lower(const Instruction&i,bool full){
 if(i.name=="DAA"){if(!full)throw std::runtime_error("DAA_REQUIRES_FULL_CPU_STATE");return {"s.decimal_adjust_accumulator();"};}
 const auto&ops=i.pcode.array();if(ops.size()>500)throw std::runtime_error("UNBOUNDED_PCODE");
 bool guard=false;int branch_pos=-1;
 if(i.name=="CALL"||i.name=="RET"){
  for(size_t k=0;k<ops.size();++k)if(str(ops[k],"op")=="CBRANCH"){
   if(branch_pos!=-1)throw std::runtime_error("MULTIPLE_INTERNAL_BRANCHES");
   branch_pos=int(k);
  }
  if(branch_pos>=0){
   const auto&b=ops[size_t(branch_pos)].get("inputs").array();
   const std::string expected=i.name=="CALL"?"CALL":"RETURN";
   if(b.size()!=2||str(b[0],"space")!="ram"||num(b[0],"offset")!=i.fall||ops.empty()||str(ops.back(),"op")!=expected)
     throw std::runtime_error("UNVERIFIED_CONDITIONAL_CALL_RET_CFG");
   guard=true;
  }
 }
 std::vector<std::string> out;
 for(size_t k=0;k<ops.size();++k){
  const auto&p=ops[k];const auto op=str(p,"op");const auto&args=p.get("inputs").array();const auto&res=p.get("output");
  if(!alu(op).empty()){
   if(args.empty()||res.isnull())throw std::runtime_error("MISSING_ALU_INPUT_OUTPUT");
   auto a=var_read(args[0],full);auto b=args.size()>1?var_read(args[1],full):"0u";
   auto expression="rd::evaluate(rd::Op::"+op+","+a+","+b+","+qint(num(res,"size"))+","+
     qint(num(args[0],"size"))+","+qint(args.size()>1?num(args[1],"size"):1)+")";
   out.push_back(var_write(res,expression,full));
  }else if(op=="LOAD"){
   if(args.size()<2||res.isnull())throw std::runtime_error("INVALID_PCODE_LOAD");
   auto addr=var_read(args[1],full);std::string space=str(p,"memory_space");
   std::string expression;
   if(space=="ram")expression="s.memory(static_cast<std::uint16_t>("+addr+"),"+qint(num(res,"size"))+")";
   else if(space=="io")expression="s.in(static_cast<std::uint16_t>("+addr+"))";
   else throw std::runtime_error("UNSUPPORTED_LOAD_SPACE");
   out.push_back(var_write(res,expression,full));
  }else if(op=="STORE"){
   if(args.size()<3)throw std::runtime_error("INVALID_PCODE_STORE");
   auto addr=var_read(args[1],full),val=var_read(args[2],full);const auto space=str(p,"memory_space");
   if(space=="ram")out.push_back("s.write_memory(static_cast<std::uint16_t>("+addr+"),"+qint(num(args[2],"size"))+","+val+");");
   else if(space=="io")out.push_back("s.out(static_cast<std::uint16_t>("+addr+"),static_cast<std::uint8_t>("+val+"));");
   else throw std::runtime_error("UNSUPPORTED_STORE_SPACE");
  }else if(op=="BRANCH"||op=="CALL"||op=="CBRANCH"||op=="BRANCHIND"||op=="RETURN"){
   if(args.empty())throw std::runtime_error("MISSING_BRANCH_TARGET");
   if(str(args[0],"space")=="const")throw std::runtime_error("INSTRUCTION_LOCAL_BRANCH_UNSUPPORTED");
   auto target=(str(args[0],"space")=="ram"&&op!="RETURN")?qwide(number(args[0],"offset")):var_read(args[0],full);
   if(op=="CBRANCH"){
    if(args.size()!=2)throw std::runtime_error("INVALID_CONDITIONAL_BRANCH");
    if(guard)out.push_back("if(!( "+var_read(args[1],full)+" )){");
    else out.push_back("if("+var_read(args[1],full)+")next=static_cast<std::uint16_t>("+target+");");
   }else out.push_back("next=static_cast<std::uint16_t>("+target+");");
  }else if(op=="CALLOTHER"){
   if(args.empty()||str(args[0],"space")!="const")throw std::runtime_error("UNMODELLED_CALLOTHER");
   auto selector=num(args[0],"offset");
   if(i.name=="HALT"&&selector==9)out.push_back("s.halted=true;");
   else if(i.name=="DI"&&selector==4)out.push_back("s.on_di();");
   else if(i.name=="EI"&&selector==5)out.push_back("s.on_ei();");
   else if(i.name=="IM"&&selector==6&&args.size()>1&&str(args[1],"space")=="const")
      out.push_back("s.interrupt_mode="+qwide(number(args[1],"offset"))+";");
   else throw std::runtime_error("UNMODELLED_CPU_CALLOTHER");
  }else throw std::runtime_error("UNSUPPORTED_PCODE_OPERATION: "+op);
 }
 if(guard)out.push_back("}");
 return out;
}
unsigned timing(const std::string&n){
 if(n=="LDIR"||n=="LDDR"||n=="OTIR"||n=="OTDR"||n=="CPIR"||n=="CPDR")return 21;
 if(n=="LDI"||n=="LDD"||n=="OUTI"||n=="OUTD"||n=="CPI"||n=="CPD")return 16;
 if(n=="CALL"||n=="RST")return 17;
 if(n=="RET"||n=="RETI"||n=="RETN")return 10;
 if(n=="JR"||n=="DJNZ")return 12;
 if(n=="OUT"||n=="IN"||n=="PUSH"||n=="POP")return 11;
 if(n=="JP"||n=="JP_RESET_SOURCE_ATTESTED")return 10;
 if(n=="HALT"||n=="DI"||n=="EI"||n=="NOP"||n=="INC"||n=="DEC")return 4;
 if(n=="IM")return 8;return 7;
}
std::string canonical(const J&v){
 switch(v.t){
 case J::Null:return "null";
 case J::Bool:return v.n?"true":"false";
 case J::Int:return std::to_string(v.n);
 case J::String:return rdjson::escape(v.s);
 case J::Array:{std::string a="[";for(const auto&e:v.a){if(a.size()>1)a+=",";a+=canonical(e);}return a+"]";}
 case J::Object:{std::string a="{";for(const auto&e:v.o){if(a.size()>1)a+=",";a+=rdjson::escape(e.first)+":"+canonical(e.second);}return a+"}";}
 }return "null";
}
void verify_document(const J&doc,const std::string&source,const std::string&sha,bool require_ghidra,
 std::map<int,Instruction>&instructions,unsigned&attested){
 if(str(doc,"schema")!="recomp-function-pcode-v1"||str(doc,"language")!="z80:LE:16:default"||
    str(doc,"source_sha256")!=sha||str(doc,"target_id").empty())throw std::runtime_error("PCODE_DOCUMENT_IDENTITY_MISMATCH");
 if(require_ghidra&&str(doc,"analyzer")!="ghidra-raw-pcode")throw std::runtime_error("GHIDRA_PROVENANCE_REQUIRED");
 int slot=-1,bank=-1;
 if(!doc.get("bank_context").isnull()){
  const auto&m=doc.get("bank_context");slot=num(m,"slot");bank=num(m,"bank");
  if(slot<0||slot>2||bank<0||bank>255||num(m,"base")!=slot*16384||num(m,"physical_start")!=bank*16384)
   throw std::runtime_error("BANK_PROVENANCE_INVALID");
 }
 const auto&funcs=doc.get("functions").array();if(funcs.size()>2000)throw std::runtime_error("FUNCTIONS_LIMIT_EXCEEDED");
 for(const auto&func:funcs){
  const auto&list=func.get("instructions").array();if(list.size()>12000)throw std::runtime_error("FUNCTION_SIZE_LIMIT_EXCEEDED");
  for(const auto&i:list){
   Instruction inst;inst.pc=num(i,"address");inst.length=num(i,"length");inst.name=str(i,"mnemonic");inst.hash=str(i,"bytes_sha256");
   if(inst.pc>=0xc000||inst.length<1||inst.length>8||inst.pc+inst.length>0xc000)throw std::runtime_error("ROM_INSTRUCTION_WINDOW_INVALID");
   int physical=inst.pc;
   if(slot>=0){int base=slot*0x4000;if(inst.pc<base||inst.pc+inst.length>base+0x4000)throw std::runtime_error("BANK_WINDOW_CROSSING");
    physical=slot==0&&inst.pc<0x400?inst.pc:bank*0x4000+(inst.pc-base);
   }
   if(physical<0||size_t(physical)+size_t(inst.length)>source.size())throw std::runtime_error("PHYSICAL_ROM_RANGE_INVALID");
   if(hash(source.substr(size_t(physical),size_t(inst.length)))!=inst.hash)throw std::runtime_error("INSTRUCTION_SOURCE_HASH_MISMATCH");
   inst.phys=physical;inst.fall=i.get("fallthrough").isnull()?(inst.pc+inst.length)&0xffff:num(i,"fallthrough");
   if(inst.fall>=65536)throw std::runtime_error("INVALID_FALLTHROUGH");
   inst.pcode=i.get("pcode");if(inst.pcode.t!=J::Array||inst.pcode.a.size()>500)throw std::runtime_error("PCODE_VECTOR_INVALID");
   inst.pcode_signature=hash(canonical(inst.pcode));
   auto it=instructions.find(physical);
   if(it!=instructions.end()){
    const auto&prev=it->second;
    if(prev.pc!=inst.pc||prev.length!=inst.length||prev.hash!=inst.hash||prev.name!=inst.name||prev.pcode_signature!=inst.pcode_signature)
      throw std::runtime_error("CONFLICTING_SOURCE_INSTRUCTION");
   }else{instructions.emplace(physical,std::move(inst));++attested;}
  }
 }
}
// The discovery report is optional and never supplies executable strings.
// It can nominate source bytes for a CPU-owned, narrowly scoped native lift.
// All identity, bank/guest, source hash and opcode checks are repeated here.
struct CpuCodegen {
#ifdef _WIN32
 HMODULE module=nullptr;
#else
 void* module=nullptr;
#endif
 RD_Z80NativeCodeFnV1 emit=nullptr;
 explicit CpuCodegen(const fs::path&p){
  if(!fs::is_regular_file(p)||fs::is_symlink(p))throw std::runtime_error("CPU_SOURCE_PLUGIN_MISSING");
#ifdef _WIN32
  module=LoadLibraryExW(fs::absolute(p).wstring().c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
  if(module)emit=reinterpret_cast<RD_Z80NativeCodeFnV1>(GetProcAddress(module,"rd_z80_emit_native_full_v1"));
#else
  module=dlopen(p.c_str(),RTLD_NOW|RTLD_LOCAL);
  if(module)emit=reinterpret_cast<RD_Z80NativeCodeFnV1>(dlsym(module,"rd_z80_emit_native_full_v1"));
#endif
  if(!module||!emit)throw std::runtime_error("CPU_NATIVE_SOURCE_CODEGEN_ABI_MISSING");
 }
 ~CpuCodegen(){
#ifdef _WIN32
  if(module)FreeLibrary(module);
#else
  if(module)dlclose(module);
#endif
 }
};
unsigned recover_discovered(const fs::path&report,const fs::path&cpu,const std::string&source,
 const std::string&source_hash,std::map<int,Instruction>&ins,unsigned&attested){
 if(!fs::is_regular_file(report)||fs::is_symlink(report))throw std::runtime_error("DISCOVERY_REPORT_NOT_REGULAR");
 const auto doc=rdjson::Reader(read_file(report,64u*1024u*1024u)).parse();
 if(str(doc,"schema")!="recompdev.native.discovery.v1"||str(doc,"source_sha256")!=source_hash||
    str(doc,"cpu")!="z80"||str(doc,"platform")!="sms"||(doc.get("source_fully_attested").t!=J::Bool||!doc.get("source_fully_attested").n)||
    number(doc,"source_size",source.size())!=source.size())
    throw std::runtime_error("DISCOVERY_REPORT_SOURCE_OR_PLATFORM_MISMATCH");
 const auto&blocks=doc.get("blocks").array();if(blocks.size()>100000)throw std::runtime_error("DISCOVERY_ITEM_LIMIT");
 CpuCodegen plugin(cpu);unsigned recovered=0;
 for(const auto&block:blocks){
  const auto pc=num(block,"pc"),phys=num(block,"physical"),length=num(block,"length");
  if(pc>=0xc000||length<1||length>16||pc+length>0xc000||
     size_t(phys)+size_t(length)>source.size()||
     unsigned(pc&0x3fff)+unsigned(length)>0x4000||
     (phys&0x3fff)!=(pc&0x3fff))throw std::runtime_error("DISCOVERY_BLOCK_ADDRESS_INVALID");
  const auto slot=pc<0x400?0:(pc<0x4000?1:(pc<0x8000?2:3));
  if(pc<0x400 && phys!=pc)throw std::runtime_error("PINNED_RESET_PAGE_MISMATCH");
  if(pc>=0x400&&!(number(block,"mapper_known_mask",15)&(1u<<slot)))
     throw std::runtime_error("DISCOVERY_BLOCK_UNKNOWN_BANK");
  const auto bytes=source.substr(size_t(phys),size_t(length));
  if(hash(bytes)!=str(block,"source_bytes_sha256"))
     throw std::runtime_error("DISCOVERY_INSTRUCTION_SOURCE_HASH_MISMATCH");
  if(ins.count(phys))continue;
  // Direct branches, calls and returns are source-verified in the CPU plugin.
  // RETURN is admitted only when the DLL provides a native stack-pop lowering;
  // the discovery controller must have established a matching caller context.
  // Truly indirect jumps still lack a verified target and remain unresolved.
  const auto flow=num(block,"flow");
  if(flow==RD_FLOW_INDIRECT)continue;
  RD_Z80NativeCodeV1 emitted{};emitted.struct_size=sizeof(emitted);
  auto status=plugin.emit(reinterpret_cast<const uint8_t*>(bytes.data()),uint32_t(length),&emitted);
  if(status<0||emitted.abi_version!=RD_Z80_NATIVE_CODEGEN_ABI_V1||
     emitted.struct_size!=sizeof(emitted))throw std::runtime_error("CPU_SOURCE_CODEGEN_CONTRACT_FAILURE");
  if(!status)continue;
  if(emitted.supported!=1||!std::memchr(emitted.cpp_body,0,sizeof(emitted.cpp_body)))
     throw std::runtime_error("CPU_SOURCE_CODEGEN_OUTPUT_INVALID");
  Instruction i;i.pc=pc;i.phys=phys;i.length=length;i.fall=pc+length;
  i.name="CPU_SOURCE_LIFT";i.hash=hash(bytes);i.source_code=emitted.cpp_body;
  ins.emplace(phys,std::move(i));++attested;++recovered;
 }
 return recovered;
}

std::string raw(const fs::path&p){return read_file(p,64u*1024u*1024u);}
void publish(const fs::path&p,const std::string&s){std::ofstream f(p,std::ios::binary);if(!f)throw std::runtime_error("OUTPUT_WRITE_FAILED");f<<s;if(!f)throw std::runtime_error("OUTPUT_WRITE_FAILED");}
void result_status(RD_TranslationResultV1*r,const std::string&s){std::strncpy(r->status,s.c_str(),sizeof(r->status)-1);r->status[sizeof(r->status)-1]='\0';}
int run(const RD_TranslationRequestV1*r,RD_TranslationResultV1*out,
 const char*discovery_report=nullptr,const char*cpu_plugin=nullptr){
 if(!r||!out||r->abi_version!=RD_TRANSLATION_ABI_V1||r->struct_size!=sizeof(*r)||out->struct_size!=sizeof(*out)||
   !r->rom_path||!r->base_export||!r->output_directory||r->bank_count>64||(r->bank_count&&!r->bank_exports))return -1;
 *out={};out->abi_version=RD_TRANSLATION_ABI_V1;out->struct_size=sizeof(*out);
 try{
  const bool full=r->full_runtime_project!=0;
  if(full&&!r->source_root)throw std::runtime_error("PRESERVED_RUNTIME_SOURCE_ROOT_REQUIRED");
  const fs::path source_path=fs::u8path(r->rom_path),export_path=fs::u8path(r->base_export),destination=fs::u8path(r->output_directory);
  if(fs::exists(destination))throw std::runtime_error("OUTPUT_EXISTS_REFUSING_OVERWRITE");
  if(!fs::is_regular_file(source_path)||fs::is_symlink(source_path)||!fs::is_regular_file(export_path)||fs::is_symlink(export_path))throw std::runtime_error("SOURCE_OR_EXPORT_NOT_REGULAR");
  std::string source=raw(source_path);if(source.size()<0x4000)throw std::runtime_error("CARTRIDGE_TOO_SMALL");
  const auto source_hash=hash(source);
  std::map<int,Instruction> ins;unsigned attested=0;
  const auto base_json=read_file(export_path,64u*1024u*1024u);
  auto base=rdjson::Reader(base_json).parse();
  if(!base.get("bank_context").isnull())throw std::runtime_error("BASE_EXPORT_HAS_BANK_CONTEXT");
  verify_document(base,source,source_hash,r->require_ghidra!=0,ins,attested);
  for(unsigned k=0;k<r->bank_count;++k){
   if(!r->bank_exports[k])throw std::runtime_error("BANK_EXPORT_NULL");
   fs::path f=fs::u8path(r->bank_exports[k]);if(!fs::is_regular_file(f)||fs::is_symlink(f))throw std::runtime_error("BANK_EXPORT_NOT_REGULAR");
   const auto bank_json=read_file(f,64u*1024u*1024u);
   auto doc=rdjson::Reader(bank_json).parse();
   if(str(doc,"target_id")!=str(base,"target_id")||doc.get("bank_context").isnull())throw std::runtime_error("BANK_EXPORT_IDENTITY_MISMATCH");
   verify_document(doc,source,source_hash,r->require_ghidra!=0,ins,attested);
  }
  unsigned source_recovered=0;
  if(discovery_report){
   if(!full||!cpu_plugin)throw std::runtime_error("DISCOVERY_LIFT_REQUIRES_FULL_BACKEND_AND_CPU_PLUGIN");
   source_recovered=recover_discovered(fs::u8path(discovery_report),fs::u8path(cpu_plugin),source,source_hash,ins,attested);
  }
  // Source-verified reset vector is an explicit fixed rule from the preserved
  // nativepilot.generator. It is not inferred from a title or ROM fingerprint.
  if(!ins.count(0)&&source.size()>=3&&uint8_t(source[0])==0xc3){
   Instruction init;init.pc=init.phys=0;init.length=3;init.fall=3;init.name="JP_RESET_SOURCE_ATTESTED";
   init.hash=hash(source.substr(0,3));init.pcode.t=J::Array;
   J operation;operation.t=J::Object;
   J name;name.t=J::String;name.s="BRANCH";operation.o.emplace("op",name);
   J arg;arg.t=J::Object;J sp;sp.t=J::String;sp.s="ram";arg.o.emplace("space",sp);
   J target;target.t=J::Int;target.n=uint8_t(source[1])|(uint8_t(source[2])<<8);arg.o.emplace("offset",target);
   J sz;sz.t=J::Int;sz.n=1;arg.o.emplace("size",sz);
   J args;args.t=J::Array;args.a.push_back(arg);operation.o.emplace("inputs",args);init.pcode.a.push_back(operation);
   ins.emplace(0,std::move(init));++attested;
  }
  std::ostringstream code,accepted,reject;
  if(full){
   code<<"// Native P-code translation: RecompDev v0.4.9.10, preserved full guest runtime.\n"
       <<"#include \"runtime.hpp\"\n#include \"z80_cycles.hpp\"\n#include \"rd_sha256.hpp\"\n"
       <<"#include <array>\n#include <cstdint>\n#include <string>\n"
       <<"bool execute_native_instruction(rd::State&s){\n"
       <<" if(s.steps==0){if(s.rom.empty()||rdhash::sha256(s.rom.data(),s.rom.size())!=\""<<source_hash<<"\"){s.stopped=\"ROM_SHA256_MISMATCH\";return false;}}\n"
       <<" const auto physical=s.rom_offset(s.pc);\n switch(physical){\n";
  }else{
  code<<"// Native RecompDev v0.4.9.10 source-attested P-code translation DLL.\n"
      <<"#include \"rd_pcode_bridge.hpp\"\n#include \"z80_cycles.hpp\"\n#include <cstdint>\n"
      <<"namespace {\nint execute(uint32_t physical,RD_CpuState*cpu,const RD_Bus*bus,uint32_t*cycles){\n"
      <<" if(!cpu||!bus||!cycles||!bus->read||!bus->write||!bus->in_port||!bus->out_port)return -1;\n switch(physical){\n";
  }
  unsigned emitted=0,rejected=0;
  accepted<<"[";reject<<"[";
  for(const auto&kv:ins){const auto&i=kv.second;
   try{
    const auto lowered=i.source_code.empty()?lower(i,full):std::vector<std::string>{i.source_code};
    if(lowered.empty()&&i.name!="NOP")throw std::runtime_error("EMPTY_SEMANTICS_UNVERIFIED");
    if(full){
     code<<" case "<<qhex(unsigned(i.phys))<<":{\n"
         <<"  std::uint16_t next="<<qhex(unsigned(i.fall))<<";s.last_instruction_cycles="<<timing(i.name)<<";\n"
         <<"  std::array<std::uint8_t,8> source_bytes{};\n"
         <<"  for(unsigned j=0;j<"<<i.length<<"u;++j)source_bytes[j]=s.read_byte(std::uint16_t("<<qhex(unsigned(i.pc))<<"+j));\n";
     for(int j=0;j<i.length;++j)code<<"  if(source_bytes["<<j<<"]!="<<qhex(uint8_t(source[size_t(i.phys+j)]))<<"){s.stopped=\"SOURCE_INSTRUCTION_BYTE_MISMATCH\";return false;}\n";
     for(const auto&line:lowered)code<<"  "<<line<<"\n";
     if(i.name=="RETN")code<<"  s.iff1=s.iff2;\n";
     code<<"  const auto timing=recomp::z80::decode([&](std::uint16_t a){return source_bytes[std::uint16_t(a-"<<qhex(unsigned(i.pc))<<")&7];},"
         <<"std::uint16_t("<<qhex(unsigned(i.pc))<<"),next,std::uint16_t("<<qhex(unsigned(i.fall))<<"));\n"
         <<"  if(timing.known){s.last_instruction_cycles=timing.tstates;++s.qualified_timing_instructions;}else{++s.unqualified_timing_instructions;}\n"
         <<"  s.pc=next;return true;\n }\n";
    }else{
     code<<" case "<<qhex(unsigned(i.phys))<<":{\n"
       <<"  if(cpu->pc!="<<qhex(unsigned(i.pc))<<")return 0;\n";
     for(int j=0;j<i.length;++j)code<<"  if(bus->read(bus->ctx,uint16_t(cpu->pc+"<<j<<"u))!="<<qhex(uint8_t(source[size_t(i.phys+j)]))<<")return -1;\n";
     code<<"  std::uint16_t next="<<qhex(unsigned(i.fall))<<";\n  rd::BridgeState s(*cpu,*bus);\n";
     for(const auto&line:lowered)code<<"  "<<line<<"\n";
     code<<"  const auto timing=recomp::z80::decode([&](std::uint16_t a){return bus->read(bus->ctx,a);},cpu->pc,next,uint16_t("<<qhex(unsigned(i.fall))<<"));\n"
       <<"  if(!timing.known)return -1;\n  s.commit();cpu->pc=next;*cycles=timing.tstates;return 1;\n }\n";
    }
    if(emitted++)accepted<<",";accepted<<"{\"physical\":"<<i.phys<<",\"pc\":"<<i.pc<<",\"length\":"<<i.length<<"}";
   }catch(const std::exception&e){if(rejected++)reject<<",";reject<<"{\"physical\":"<<i.phys<<",\"reason\":"<<rdjson::escape(e.what())<<"}";}
  }
  accepted<<"]";reject<<"]";
  if(!emitted)throw std::runtime_error("NO_SAFE_ATTESTED_INSTRUCTIONS_FOR_NATIVE_GENERATION");
  if(full){
   code<<" default:s.stopped=\"UNTRANSLATED_PHYSICAL_ROM_OFFSET\";return false;\n }\n}\n";
  }else{
  code<<" default:return 0;\n }\n}\nconst RD_GameApi API={execute};\n"
      <<"const RD_Plugin PLUGIN={RD_ABI_VERSION,sizeof(RD_Plugin),RD_GAME,sizeof(API),\"P-code generated game module (native translator)\",&API};\n}\n"
      <<"extern \"C\" RD_EXPORT const RD_Plugin*rd_get_plugin_v1(void){return &PLUGIN;}\n"
      <<"extern \"C\" RD_EXPORT const char*rd_game_source_sha256_v1(void){return \""<<source_hash<<"\";}\n"
      <<"extern \"C\" RD_EXPORT uint64_t rd_game_source_size_v1(void){return "<<source.size()<<"ull;}\n";
  }
  // No partial output: all hashes and export validations completed first.
  fs::create_directories(destination);
  if(full){
   const bool partition=emitted>512;
   std::vector<std::string> parts;
   if(!partition)publish(destination/"translated.cpp",code.str());
   else{
    // Avoid compiling the same enormous switch twice. Source-attested cases
    // are independent by physical ROM offset and can be compiled as separate
    // object files into one shared static translation library.
    const std::string full_code=code.str();
    const auto begin=full_code.find("\n case ");
    const auto stop=full_code.rfind("\n default:");
    if(begin==std::string::npos||stop==std::string::npos||begin>=stop)
     throw std::runtime_error("GENERATED_TRANSLATION_PARTITION_INVALID");
    std::vector<std::string> cases;
    for(size_t a=begin+1;a<stop;){
     const auto b=full_code.find("\n case ",a);
     const auto next=(b==std::string::npos||b>=stop)?stop:b+1;
     std::string instruction=full_code.substr(a,next-a);
     size_t pos=0;
     while((pos=instruction.find("return true;",pos))!=std::string::npos){
      instruction.replace(pos,12,"return 1;");pos+=9;
     }
     pos=0;
     while((pos=instruction.find("return false;",pos))!=std::string::npos){
      instruction.replace(pos,13,"return 2;");pos+=9;
     }
     // A new last instruction must not change the whitespace of the
     // previously last case, which may live in a different partition.
     while(!instruction.empty() && (instruction.back()=='\n'||instruction.back()=='\r'||instruction.back()==' '||instruction.back()=='\t'))instruction.pop_back();
     instruction.push_back('\n');
     cases.push_back(std::move(instruction));a=next;
    }
    constexpr size_t PART_COUNT=24;
    std::vector<std::ostringstream> output(PART_COUNT);
    // Stable physical-address partitioning: recovering a new source-verified
    // instruction must not reshuffle thousands of unrelated generated cases.
    // This allows incremental native compilation to rebuild only affected
    // object files instead of recompiling the complete game each recovery.
    for(const auto &item:cases){
     const auto at=item.find("case 0x");
     if(at==std::string::npos)throw std::runtime_error("TRANSLATION_CASE_ADDRESS_MISSING");
     const auto colon=item.find(':',at+7);
     if(colon==std::string::npos)throw std::runtime_error("TRANSLATION_CASE_ADDRESS_INVALID");
     const auto physical=uint32_t(std::stoul(item.substr(at+7,colon-at-7),nullptr,16));
     const auto partition=(((physical*2654435761u)>>24)%PART_COUNT);
     output[partition]<<item;
    }
    std::ostringstream dispatch;
    dispatch<<"#include \"runtime.hpp\"\n#include \"rd_sha256.hpp\"\n#include <cstdint>\n";
    for(size_t j=0;j<PART_COUNT;++j){
     std::string filename="native_part_"+std::to_string(j)+".cpp";parts.push_back(filename);
     std::ostringstream part;
     part<<"#include \"runtime.hpp\"\n#include \"z80_cycles.hpp\"\n#include <array>\n#include <cstdint>\n"
         <<"int rd_native_part_"<<j<<"(rd::State&s,std::uint32_t physical){switch(physical){\n"
         <<output[j].str()<<"\n default:return 0;\n}}\n";
     publish(destination/filename,part.str());
     dispatch<<"int rd_native_part_"<<j<<"(rd::State&,std::uint32_t);\n";
    }
    dispatch<<"bool execute_native_instruction(rd::State&s){\n"
            <<" if(s.steps==0){if(s.rom.empty()||rdhash::sha256(s.rom.data(),s.rom.size())!=\""<<source_hash
            <<"\"){s.stopped=\"ROM_SHA256_MISMATCH\";return false;}}\n"
            <<" const auto physical=s.rom_offset(s.pc);\n int outcome=0;\n";
    for(size_t j=0;j<PART_COUNT;++j)
     dispatch<<" outcome=rd_native_part_"<<j<<"(s,physical);if(outcome)return outcome==1;\n";
    dispatch<<" s.stopped=\"UNTRANSLATED_PHYSICAL_ROM_OFFSET\";return false;\n}\n";
    publish(destination/"translated.cpp",dispatch.str());
   }
   const fs::path port=fs::weakly_canonical(fs::u8path(r->source_root))/"runtime_sms";
   if(!fs::is_regular_file(port/"templates"/"main.cpp")||
      !fs::is_regular_file(port/"include"/"runtime.hpp"))
      throw std::runtime_error("ACTIVE_SMS_RUNTIME_SOURCE_MISSING");
   auto from=[&](const fs::path&src,const fs::path&dst){
    if(!fs::is_regular_file(src)||fs::is_symlink(src))throw std::runtime_error("PORT_TEMPLATE_NOT_REGULAR");
    fs::create_directories((destination/dst).parent_path());
    fs::copy_file(src,destination/dst,fs::copy_options::overwrite_existing);
   };
   for(const auto*n:{"main.cpp","interactive.cpp","live_sms.hpp","z80_cycles.hpp","CMakeLists.txt"})
    from(port/"templates"/n,n);
   from(fs::u8path(r->source_root)/"harness"/"include"/"rd_sha256.hpp","rd_sha256.hpp");
   if(partition){
    std::string cmake=read_file(destination/"CMakeLists.txt",128u*1024u);
    cmake+="\nadd_library(rd_generated_translation STATIC translated.cpp";
    for(const auto&name:parts)cmake+=" "+name;
    cmake+=")\ntarget_compile_features(rd_generated_translation PRIVATE cxx_std_17)\n"
     "target_include_directories(rd_generated_translation PRIVATE \"${RECOMPDEV_SOURCE_ROOT}/runtime_sms/include\" \"${RECOMPDEV_SOURCE_ROOT}/runtime_sms/templates\")\n"
     "target_link_libraries(RecompDevNativePilot PRIVATE rd_generated_translation)\n"
     "target_link_libraries(RecompDevNativeApp PRIVATE rd_generated_translation)\n"
     "if(MSVC)\n target_compile_options(rd_generated_translation PRIVATE /O1 /bigobj)\n"
     "elseif(CMAKE_CXX_COMPILER_ID MATCHES \"GNU|Clang\")\n target_compile_options(rd_generated_translation PRIVATE -O1)\nendif()\n";
    publish(destination/"CMakeLists.txt",cmake);
   }
  }else publish(destination/"rd_game_pcode.cpp",code.str());
  std::ostringstream manifest;manifest<<"{\n \"schema\":\"recompdev.native.pcode.generated.v1\",\n"
    <<" \"workspace_release\":\"v0.4.9.10\",\n \"source_sha256\":\""<<source_hash<<"\",\n"
    <<" \"source_size\":"<<source.size()<<",\n \"attested\":"<<attested<<",\n \"emitted\":"<<emitted<<",\n"
    <<" \"rejected\":"<<rejected<<",\n \"source_decoder_recovered\":"<<source_recovered<<",\n \"backend\":\""<<(full?"dll_sms_native_runtime":"limited_harness_game_dll")<<"\",\n \"accepted_instructions\":"<<accepted.str()<<",\n \"rejections\":"<<reject.str()<<",\n"
    <<" \"full_CPU_state_port\":"<<(full?"true":"false")<<",\n \"full_recovery_port\":false\n}\n";
  publish(destination/"translation-manifest.json",manifest.str());
  std::strncpy(out->source_sha256,source_hash.c_str(),64);out->attested=attested;out->emitted=emitted;out->rejected=rejected;
  result_status(out,"SOURCE_ATTESTED_NATIVE_CPP_EMITTED");return 1;
 }catch(const std::exception&e){result_status(out,e.what());return -1;}
}
int run_v1(const RD_TranslationRequestV1*r,RD_TranslationResultV1*out){return run(r,out);}
const RD_TranslationApiV1 API={RD_TRANSLATION_ABI_V1,sizeof(RD_TranslationApiV1),run_v1};
const RD_Plugin PLUGIN={RD_ABI_VERSION,sizeof(RD_Plugin),RD_TRANSLATOR_KIND,sizeof(API),
 "Native P-code C++ lowering (preserved full runtime + limited game-DLL adapter)",&API};
} // namespace
extern "C" RD_EXPORT const RD_Plugin*rd_get_plugin_v1(void){return &PLUGIN;}

extern "C" RD_EXPORT int rd_translation_recover_source_v1(
 const RD_TranslationRecoveryRequestV1*r,RD_TranslationResultV1*out){
 if(!r||r->abi_version!=RD_TRANSLATION_ABI_V1||r->struct_size!=sizeof(*r)||
    !r->source_discovery_json||!r->cpu_plugin_path)return -1;
 return run(&r->base,out,r->source_discovery_json,r->cpu_plugin_path);
}
