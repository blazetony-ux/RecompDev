#include "native_discovery.hpp"
#include "evidence_index.hpp"
#include "rd_native_discovery_v1.h"
#include "rd_sha256.hpp"
#include "rd_tiny_json.hpp"
#include <algorithm>
#include <cctype>
#include <cstdint>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <set>
#include <unordered_map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#ifdef _WIN32
# define WIN32_LEAN_AND_MEAN
# include <windows.h>
#else
# include <dlfcn.h>
# include <unistd.h>
#endif
namespace fs=std::filesystem;
namespace {
#ifdef _WIN32
using Handle=HMODULE;
Handle load(const fs::path&p){return LoadLibraryExW(fs::absolute(p).wstring().c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);}
void* sym(Handle h,const char*n){return reinterpret_cast<void*>(GetProcAddress(h,n));}
void close(Handle h){if(h)FreeLibrary(h);}
constexpr auto SUFFIX=".dll";
#else
using Handle=void*;
Handle load(const fs::path&p){return dlopen(p.c_str(),RTLD_NOW|RTLD_LOCAL);}
void* sym(Handle h,const char*n){return dlsym(h,n);}
void close(Handle h){if(h)dlclose(h);}
# ifdef __APPLE__
constexpr auto SUFFIX=".dylib";
# else
constexpr auto SUFFIX=".so";
# endif
#endif
struct Plugin {
 fs::path path;
 Handle h{};
 const RD_Plugin* d{};
 Plugin(const fs::path&p,uint32_t kind,uint32_t api_size):path(p){
  h=load(p);if(!h)throw std::runtime_error("PLUGIN_LOAD_FAILED: "+p.string());
  auto f=reinterpret_cast<RD_GetPlugin>(sym(h,"rd_get_plugin_v1"));
  if(!f){close(h);h=nullptr;throw std::runtime_error("PLUGIN_ENTRY_MISSING: "+p.string());}
  d=f();
  if(!d||d->abi_version!=RD_ABI_VERSION||d->descriptor_size!=sizeof(RD_Plugin)||d->kind!=kind||d->api_size!=api_size||!d->api||!d->name){
   close(h);h=nullptr;throw std::runtime_error("PLUGIN_ABI_OR_KIND_REJECTED: "+p.string());
  }
 }
 ~Plugin(){close(h);}
 Plugin(const Plugin&)=delete;Plugin&operator=(const Plugin&)=delete;
 template<class T>const T* api()const{return static_cast<const T*>(d->api);}
 template<class T>T symbol(const char*n)const{auto f=reinterpret_cast<T>(sym(h,n));if(!f)throw std::runtime_error(std::string("PLUGIN_EXTENSION_MISSING: ")+n+" "+path.string());return f;}
};
std::string json(const std::string&s){std::string out="\"";for(unsigned char c:s){
 switch(c){case '\\':out+="\\\\";break;case '"':out+="\\\"";break;case '\n':out+="\\n";break;case '\r':out+="\\r";break;case '\t':out+="\\t";break;
 default:if(c<0x20){std::ostringstream ss;ss<<"\\u"<<std::hex<<std::setw(4)<<std::setfill('0')<<int(c);out+=ss.str();}else out+=char(c);}
 }return out+"\"";}
std::vector<uint8_t> bytes(const fs::path&p,size_t limit){
 auto size=fs::file_size(p);if(size>limit)throw std::runtime_error("HASH_INPUT_TOO_LARGE");
 std::vector<uint8_t> b(size);std::ifstream f(p,std::ios::binary);if(!f||(!b.empty()&&!f.read(reinterpret_cast<char*>(b.data()),b.size())))throw std::runtime_error("SOURCE_READ_FAILED: "+p.string());return b;
}
std::string filehash(const fs::path&p,size_t limit){auto b=bytes(p,limit);return rdhash::sha256(b.data(),b.size());}
struct Source {
 std::ifstream f;uint64_t size{};
 explicit Source(const fs::path&p):f(p,std::ios::binary){if(!f)throw std::runtime_error("SOURCE_OPEN_FAILED: "+p.string());size=fs::file_size(p);}
 static int read(void*ctx,uint64_t off,uint8_t*b,uint32_t n){
  auto*s=static_cast<Source*>(ctx);if(!b||off>s->size||n>s->size-off)return 0;
  s->f.clear();s->f.seekg(static_cast<std::streamoff>(off));
  return s->f.read(reinterpret_cast<char*>(b),n)?1:0;
 }
 RD_SourceV1 view(){return {RD_NATIVE_DISCOVERY_ABI,sizeof(RD_SourceV1),this,size,read};}
};

class Sha256Stream {
 std::array<uint32_t,8> h_={0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,
                             0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
 std::array<uint8_t,64> buffer_{};size_t buffered_=0;uint64_t bytes_=0;
 void compress(const uint8_t *b){
 constexpr std::uint32_t K[64]={
 0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
 0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
 0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
 0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
 0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
 0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
 0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
 0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
 uint32_t w[64]{};
 for(size_t i=0;i<16;++i){size_t j=i*4;w[i]=uint32_t(b[j])<<24|uint32_t(b[j+1])<<16|uint32_t(b[j+2])<<8|b[j+3];}
 for(size_t i=16;i<64;++i){auto x=w[i-15],y=w[i-2];w[i]=w[i-16]+(rdhash::rr(x,7)^rdhash::rr(x,18)^(x>>3))+w[i-7]+(rdhash::rr(y,17)^rdhash::rr(y,19)^(y>>10));}
 auto a=h_[0],b0=h_[1],c=h_[2],d=h_[3],e=h_[4],f=h_[5],g=h_[6],hh=h_[7];
 for(size_t i=0;i<64;++i){auto s1=rdhash::rr(e,6)^rdhash::rr(e,11)^rdhash::rr(e,25);auto ch=(e&f)^(~e&g);auto t1=hh+s1+ch+K[i]+w[i];
  auto s0=rdhash::rr(a,2)^rdhash::rr(a,13)^rdhash::rr(a,22);auto maj=(a&b0)^(a&c)^(b0&c);auto t2=s0+maj;
  hh=g;g=f;f=e;e=d+t1;d=c;c=b0;b0=a;a=t1+t2;}
 h_[0]+=a;h_[1]+=b0;h_[2]+=c;h_[3]+=d;h_[4]+=e;h_[5]+=f;h_[6]+=g;h_[7]+=hh;
 }
public:
 void update(const uint8_t*p,size_t n){bytes_+=n;
  for(size_t i=0;i<n;++i){buffer_[buffered_++]=p[i];if(buffered_==64){compress(buffer_.data());buffered_=0;}}
 }
 std::string finish(){auto bits=bytes_*8;uint8_t stop=0x80;update(&stop,1);uint8_t zero=0;
  while(buffered_!=56)update(&zero,1);
  for(int shift=56;shift>=0;shift-=8){uint8_t part=uint8_t(bits>>shift);update(&part,1);}
  const char*hex="0123456789abcdef";std::string out;out.reserve(64);for(auto x:h_)for(int shift=28;shift>=0;shift-=4)out+=hex[(x>>shift)&15];return out;
 }
};
std::string streamhash(const fs::path&p){std::ifstream f(p,std::ios::binary);if(!f)throw std::runtime_error("SOURCE_OPEN_FAILED: "+p.string());
 Sha256Stream hasher;std::array<uint8_t,65536> b{};
 while(f){f.read(reinterpret_cast<char*>(b.data()),b.size());auto n=f.gcount();if(n>0)hasher.update(b.data(),size_t(n));}
 if(!f.eof())throw std::runtime_error("SOURCE_HASH_READ_FAILED");
 return hasher.finish();
}
const char*platform(uint32_t p){switch(p){case RD_PLATFORM_SMS:return "sms";case RD_PLATFORM_MD:return "megadrive";case RD_PLATFORM_PS1:return "ps1";default:return "unknown";}}
const char*cpu(uint32_t p){switch(p){case RD_CPU_Z80_FAMILY:return "z80";case RD_CPU_M68000:return "m68000";case RD_CPU_MIPS_R3000A:return "mips-r3000a";default:return "unverified";}}
struct Block{uint16_t pc;uint64_t phys;uint32_t len,flow;uint16_t target;std::string sha;uint32_t known_banks=0;};
struct Gap{uint16_t pc;std::string reason;};
struct RuntimeSeed {
 uint16_t pc;uint64_t physical;RD_SmsSourceMapV1 mapping;
 // Optional, run-observed SP from the native pilot. Without an observed SP,
 // CALL/PUSH may write to SMS mapper registers and the CPU provider must
 // conservatively invalidate the bank map. Do not guess an initial SP.
 bool known_sp=false;uint16_t sp=0;
};
struct Discovery{
 std::vector<Block> blocks;std::vector<Gap> gaps;uint32_t edges=0;
};
Discovery walk(const RD_SourceV1*s,const Plugin&cpu_plugin,const Plugin&mapper,uint32_t max_items,
 const std::vector<RuntimeSeed>&runtime_seeds){
 auto decode=cpu_plugin.symbol<RD_Z80DecodeFnV1>("rd_z80_decode_source_v1");
 auto init=mapper.symbol<RD_SmsMapInitialFnV1>("rd_sms_map_initial_v1");
 auto map=mapper.symbol<RD_SmsMapResolveFnV1>("rd_sms_map_resolve_v1");
 auto write=mapper.symbol<RD_SmsMapWriteFnV1>("rd_sms_map_write_v1");
 auto effects=cpu_plugin.symbol<RD_Z80AbstractFnV1>("rd_z80_abstract_a_v1");
 auto effects_v2=cpu_plugin.symbol<RD_Z80AbstractFnV2>("rd_z80_abstract_effect_v2");
 struct Frame {uint16_t return_pc,expected_sp;uint8_t known_sp;};
 struct Work{uint16_t pc;RD_SmsSourceMapV1 mapping;RD_Z80AbstractV2 a;
  std::vector<Frame> calls;};
 RD_SmsSourceMapV1 initial{};initial.struct_size=sizeof(initial);
 if(init(&initial)!=1)throw std::runtime_error("SMS_INITIAL_MAPPER_FAILED");
 RD_Z80AbstractV2 initial_a{};initial_a.abi_version=RD_NATIVE_DISCOVERY_ABI;initial_a.struct_size=sizeof(initial_a);
 Discovery out;std::vector<Work> todo;
 // Ask the CPU plugin for architectural entrypoints: the controller must
 // not hardcode Z80 reset/IM1/NMI addresses or assume all are reachable.
 if(auto entries=cpu_plugin.symbol<RD_Z80EntryPointsFnV1>("rd_z80_source_entrypoints_v1")){
  RD_Z80EntryPointsV1 vectors{};vectors.struct_size=sizeof(vectors);
  if(entries(&vectors)!=1||vectors.abi_version!=RD_NATIVE_DISCOVERY_ABI||
     vectors.count<1||vectors.count>8)throw std::runtime_error("CPU_VECTOR_ABI_INVALID");
  bool reset=false;
  for(uint32_t i=0;i<vectors.count;++i){
   if(vectors.pc[i]>=0xc000)throw std::runtime_error("CPU_VECTOR_OUTSIDE_ROM");
   if(vectors.kind[i]>2)throw std::runtime_error("CPU_VECTOR_KIND_UNRECOGNISED");
   if(vectors.kind[i]==0&&vectors.pc[i]==0)reset=true;
   todo.push_back({vectors.pc[i],initial,initial_a,{}});
  }
  if(!reset)throw std::runtime_error("CPU_VECTOR_RESET_MISSING");
 }else todo.push_back({0,initial,initial_a,{}});
 // A stopped native run can contribute an observed (PC, mapper) entry.
 // It is not executable code: the CPU and mapper plugins verify every
 // instruction and ROM byte before adding it to the discovery output.
 for(const auto&seed:runtime_seeds){
  auto observed=initial_a;
  if(seed.known_sp){observed.known_sp=1;observed.sp=seed.sp;}
  todo.push_back({seed.pc,seed.mapping,observed,{}});
 }
 // Context key includes physical bank identity, not only guest PC; two distinct
 // ROM banks may map the same CPU address and must never be merged.
 std::set<std::string> seen;
 std::unordered_map<std::string,uint32_t> visits_per_mapping;
 constexpr uint32_t max_abstract_contexts_per_mapping=24;
 while(!todo.empty()&&seen.size()<max_items){
  Work w=todo.back();todo.pop_back();
  // Bounded abstract interpretation: loop counters and pointers can change
  // on every iteration. After 24 distinct states at a single ROM mapping,
  // join them conservatively into one unknown-register state instead of
  // treating thousands of iterations as independently discovered code.
  std::string mapping_key;
  mapping_key.append(reinterpret_cast<const char*>(&w.pc),sizeof(w.pc));
  mapping_key.push_back(char(w.mapping.known_mask));
  for(auto bank:w.mapping.mapper)mapping_key.push_back(char(bank));
  if(visits_per_mapping[mapping_key]>=max_abstract_contexts_per_mapping){
   w.a.known_a=0;
   w.a.known_bc=0;w.a.known_de=0;w.a.known_hl=0;
  }
  std::string key;
  key.append(reinterpret_cast<const char*>(&w.pc),sizeof(w.pc));
  key.push_back(char(w.mapping.known_mask));
  for(auto bank:w.mapping.mapper)key.push_back(char(bank));
  key.push_back(char(w.a.known_a));key.push_back(char(w.a.known_a?w.a.a:0));
  key.push_back(char(w.a.known_sp));
  if(w.a.known_sp){key.push_back(char(w.a.sp));key.push_back(char(w.a.sp>>8));}
  for(const auto pair: {std::pair<bool,uint16_t>{w.a.known_bc!=0,w.a.bc},
                         {w.a.known_de!=0,w.a.de},{w.a.known_hl!=0,w.a.hl}}){
   key.push_back(char(pair.first));
   if(pair.first){key.push_back(char(pair.second));key.push_back(char(pair.second>>8));}
  }
  // A call-return continuation is reachable only from the verified caller.
  // Keep contexts distinct for different return sites and stack depths.
  for(const auto&frame:w.calls){
   key.push_back(char(frame.return_pc));key.push_back(char(frame.return_pc>>8));
   key.push_back(char(frame.known_sp));
   if(frame.known_sp){key.push_back(char(frame.expected_sp));key.push_back(char(frame.expected_sp>>8));}
  }
  if(!seen.insert(key).second)continue;
  ++visits_per_mapping[mapping_key];
  uint64_t phys=RD_NATIVE_SOURCE_UNMAPPED;
  int mapped=map(&w.mapping,w.pc,s->byte_size,&phys);
  if(mapped!=1){out.gaps.push_back({w.pc,mapped==0?"BANK_CONTEXT_UNRESOLVED":"NO_ROM_MAPPING"});continue;}
  RD_Z80DecodeV1 decoded{};decoded.struct_size=sizeof(decoded);
  int result=decode(s,phys,w.pc,&decoded);
  if(result!=1){out.gaps.push_back({w.pc,result==2?"INSTRUCTION_LENGTH_OR_FLOW_UNVERIFIED":"INVALID_SOURCE_INSTRUCTION"});continue;}
  if(!decoded.length||decoded.length>16||decoded.pc!=w.pc){out.gaps.push_back({w.pc,"PLUGIN_DECODE_CONTRACT_FAILED"});continue;}
  std::array<uint8_t,16>b{};
  if(!s->read(s->ctx,phys,b.data(),decoded.length)){out.gaps.push_back({w.pc,"SOURCE_READ_FAILED"});continue;}
  out.blocks.push_back({w.pc,phys,decoded.length,decoded.flow,decoded.target,
   rdhash::sha256(b.data(),decoded.length),w.mapping.known_mask});
  const Work before=w;
  RD_Z80EffectV1 effect{};effect.struct_size=sizeof(effect);
  int effect_rc=0;
  if(effects_v2)effect_rc=effects_v2(b.data(),decoded.length,&w.a,&effect);
  else{
   RD_Z80AbstractV1 old{};old.abi_version=RD_NATIVE_DISCOVERY_ABI;old.struct_size=sizeof(old);
   old.known_a=w.a.known_a;old.a=w.a.a;old.known_sp=w.a.known_sp;old.sp=w.a.sp;
   effect_rc=effects(b.data(),decoded.length,&old,&effect);
   w.a.known_a=old.known_a;w.a.a=old.a;w.a.known_sp=old.known_sp;w.a.sp=old.sp;
   w.a.known_bc=w.a.known_de=w.a.known_hl=0;
  }
  if(effect_rc!=1||effect.abi_version!=RD_NATIVE_DISCOVERY_ABI){
   out.gaps.push_back({w.pc,"CPU_ABSTRACT_EFFECT_UNAVAILABLE"});continue;
  }
  if(effect.write_kind==RD_Z80_EFFECT_ABSOLUTE){
   if(write(&w.mapping,effect.absolute,effect.value,effect.value_known)!=0 &&
      effect.absolute>=0xfffc)out.gaps.push_back({w.pc,"MAPPER_WRITE_TRACKED"});
  }else if(effect.write_kind==RD_Z80_EFFECT_UNRESOLVED){
   // The Z80 plugin has not attested an exact write target. A conservative
   // mapper join is required; never claim a bank survived an unknown write.
   if(effect.absolute==0xffff){w.mapping.known_mask=0;}
   else if(effect.absolute>=0xfffb){w.mapping.known_mask &=uint8_t(~0x0f);}
  }
  const bool fall=decoded.flow==RD_FLOW_COND||
       (decoded.flow==RD_FLOW_CALL&&decoded.conditional)||
       (decoded.flow==RD_FLOW_RETURN&&decoded.conditional);
  const bool branch=decoded.flow==RD_FLOW_COND||decoded.flow==RD_FLOW_JUMP||decoded.flow==RD_FLOW_CALL;
  if(fall&&uint32_t(w.pc)+decoded.length<0x10000u){
   // Conditional CALL/RET not taken: no stack or mapper mutation occurs.
   Work after=(decoded.flow==RD_FLOW_CALL||decoded.flow==RD_FLOW_RETURN)?before:w;
   after.pc=uint16_t(w.pc+decoded.length);
   todo.push_back(after);++out.edges;
  }
  if(decoded.flow==RD_FLOW_FALL&&uint32_t(w.pc)+decoded.length<0x10000u){
   Work after=w;after.pc=uint16_t(w.pc+decoded.length);
   todo.push_back(after);++out.edges;
  }
  if(decoded.flow==RD_FLOW_RETURN){
   if(w.calls.empty())out.gaps.push_back({w.pc,"RETURN_WITHOUT_VERIFIED_CALLER"});
   else{
    const Frame frame=w.calls.back();
    if(!frame.known_sp||!w.a.known_sp||frame.expected_sp!=w.a.sp)
     out.gaps.push_back({w.pc,"RETURN_STACK_IDENTITY_UNVERIFIED"});
    else{
     w.calls.pop_back();w.pc=frame.return_pc;
     todo.push_back(w);++out.edges;
    }
   }
  }
  if(branch){
   if(decoded.flow==RD_FLOW_CALL){
    if(w.calls.size()>=16)out.gaps.push_back({w.pc,"CALL_DEPTH_LIMIT"});
    else{
     Frame frame{};frame.return_pc=uint16_t(before.pc+decoded.length);
     frame.known_sp=before.a.known_sp;
     frame.expected_sp=before.a.sp;
     w.calls.push_back(frame);w.pc=decoded.target;
     todo.push_back(w);++out.edges;
    }
   }else{w.pc=decoded.target;todo.push_back(w);++out.edges;}
  }
  if(decoded.flow==RD_FLOW_INDIRECT)
   out.gaps.push_back({w.pc,"DYNAMIC_TARGET_REQUIRES_RUNTIME_EVIDENCE"});
 }
 if(!todo.empty())out.gaps.push_back({todo.back().pc,"DISCOVERY_BUDGET_EXHAUSTED"});
 return out;
}
// Consume only a bounded, already-executed native pilot stop. The report
// cannot inject executable C++, a bank mapping, or unverified source bytes.
RuntimeSeed parse_runtime_seed(const fs::path&path,uint64_t source_size,const Plugin&mapper){
 if(!fs::is_regular_file(path)||fs::is_symlink(path)||fs::file_size(path)>8u*1024u*1024u)
  throw std::runtime_error("RUNTIME_STOP_REPORT_INVALID_FILE");
 std::ifstream in(path,std::ios::binary);
 std::string body((std::istreambuf_iterator<char>(in)),{});
 if(!in.eof()&&in.bad())throw std::runtime_error("RUNTIME_STOP_REPORT_READ_FAILED");
 // NativePilot prints one PILOT_RESULT JSON object to standard output.
 // Accept the original line or its JSON payload, but no incidental logs.
 const std::string prefix="PILOT_RESULT=";
 if(body.compare(0,prefix.size(),prefix)==0)body.erase(0,prefix.size());
 const auto d=rdjson::Reader(body).parse();
 auto integer=[&](const char*key,uint64_t max)->uint64_t{
  const auto value=d.get(key).integer();
  if(value<0||uint64_t(value)>max)throw std::runtime_error(std::string("RUNTIME_STOP_")+key+"_INVALID");
  return uint64_t(value);
 };
 const auto status=d.get("status").string();
 if(status!="UNTRANSLATED_INITIAL_CODE"&&status!="BANKED_CODE_NOT_TRANSLATED"&&
    status!="UNTRANSLATED_PHYSICAL_ROM_OFFSET")throw std::runtime_error("RUNTIME_STOP_REASON_NOT_TRANSLATION_GAP");
 if(integer("native_steps",1000000000)==0||integer("rom_bytes",1ull<<32)!=source_size)
  throw std::runtime_error("RUNTIME_STOP_SOURCE_SIZE_OR_EXECUTION_UNVERIFIED");
 auto pc=integer("pc",65535);auto physical=integer("physical_offset",source_size?source_size-1:0);
 if(pc>=0xc000)throw std::runtime_error("RUNTIME_STOP_PC_NOT_ROM");
 const auto&mapping=d.get("mapper").array();
 if(mapping.size()!=4)throw std::runtime_error("RUNTIME_STOP_MAPPER_INVALID");
 RD_SmsSourceMapV1 m{};m.struct_size=sizeof(m);m.abi_version=RD_NATIVE_DISCOVERY_ABI;
 m.known_mask=0x0f;
 for(unsigned i=0;i<4;++i){
  const auto bank=mapping[i].integer();
  if(bank<0||bank>255)throw std::runtime_error("RUNTIME_STOP_MAPPER_INVALID");
  m.mapper[i]=uint8_t(bank);
 }
 auto map=mapper.symbol<RD_SmsMapResolveFnV1>("rd_sms_map_resolve_v1");
 uint64_t checked=RD_NATIVE_SOURCE_UNMAPPED;
 if(map(&m,uint16_t(pc),source_size,&checked)!=1||checked!=physical)
  throw std::runtime_error("RUNTIME_STOP_PHYSICAL_MAPPING_MISMATCH");
 // A native pilot records SP at the *actual stopped instruction*. This is
 // machine state evidence, not an inferred initial register value. Preserve
 // compatibility with pre-SP reports by falling back to conservative analysis.
 const bool known_sp=!d.get("sp").isnull();
 const uint16_t sp=known_sp?uint16_t(integer("sp",65535)):0;
 return RuntimeSeed{uint16_t(pc),physical,m,known_sp,sp};
}
std::vector<RuntimeSeed> parse_analysis_hypotheses(const fs::path&file,
 const std::string&sha,uint64_t source_size,const Plugin&mapper){
 if(!fs::is_regular_file(file)||fs::is_symlink(file)||fs::file_size(file)>8u*1024u*1024u)
  throw std::runtime_error("ANALYSIS_CANDIDATES_INVALID_FILE");
 std::ifstream f(file,std::ios::binary);std::string body((std::istreambuf_iterator<char>(f)),{});
 auto d=rdjson::Reader(body).parse();
 if(d.get("schema").string()!="recomp-analysis-reconciliation-v1" ||
    d.get("source_sha256").string()!=sha ||
    d.get("source_size").integer()!=static_cast<int64_t>(source_size) ||
    d.get("isa").string()!="z80" || d.get("base").integer()!=0)
  throw std::runtime_error("ANALYSIS_CANDIDATES_SOURCE_OR_ISA_MISMATCH");
 const auto&rows=d.get("candidates").array();
 if(rows.size()>20000)throw std::runtime_error("ANALYSIS_CANDIDATE_COUNT_INVALID");
 RD_SmsSourceMapV1 initial{};initial.struct_size=sizeof(initial);
 if(mapper.symbol<RD_SmsMapInitialFnV1>("rd_sms_map_initial_v1")(&initial)!=1)
  throw std::runtime_error("ANALYSIS_INITIAL_MAPPER_FAILED");
 auto map=mapper.symbol<RD_SmsMapResolveFnV1>("rd_sms_map_resolve_v1");
 std::vector<RuntimeSeed>out;std::set<uint16_t>seen;
 for(const auto&entry:rows){
  auto pos=entry.get("entry").integer();
  if(pos<0||pos>=0xc000||!seen.insert(uint16_t(pos)).second)continue;
  // Function boundaries are untrusted hypotheses, never execution evidence.
  // Map them only through the documented initial mapper. CPU plugin attests
  // every resulting instruction byte before it can reach the translator.
  uint64_t physical=RD_NATIVE_SOURCE_UNMAPPED;
  if(map(&initial,uint16_t(pos),source_size,&physical)!=1||physical==RD_NATIVE_SOURCE_UNMAPPED)continue;
  out.push_back({uint16_t(pos),physical,initial,false,0});
  if(out.size()>=256)break;
 }
 return out;
}
} // namespace
int rd_native_discover(const std::vector<std::string>&args,const fs::path&exe_path){
 fs::path rom,plugindir=exe_path.parent_path(),out,analysis_candidates,gap_index;std::vector<fs::path>runtime_gap_reports;bool explicit_plugin_dir=false;
 uint32_t budget=4096;
 for(size_t i=0;i<args.size();++i){
  auto next=[&]()->std::string{if(i+1==args.size())throw std::runtime_error("MISSING_ARGUMENT "+args[i]);return args[++i];};
  if(args[i]=="--rom")rom=fs::u8path(next());
  else if(args[i]=="--stage"){if(next()!="discover")throw std::runtime_error("UNEXPECTED_STAGE");}
  else if(args[i]=="--plugin-dir"){plugindir=fs::u8path(next());explicit_plugin_dir=true;}
  else if(args[i]=="--out")out=fs::u8path(next());
  else if(args[i]=="--runtime-gap-report")runtime_gap_reports.push_back(fs::u8path(next()));
  else if(args[i]=="--runtime-gap-index")gap_index=fs::u8path(next());
  else if(args[i]=="--analysis-candidates")analysis_candidates=fs::u8path(next());
  else if(args[i]=="--budget"){auto n=std::stoull(next());if(n<1||n>100000)throw std::runtime_error("INVALID_DISCOVERY_BUDGET");budget=uint32_t(n);}
  else throw std::runtime_error("UNKNOWN_NATIVE_DISCOVERY_OPTION "+args[i]);
 }
 if(rom.empty()||!fs::is_regular_file(rom))throw std::runtime_error("SOURCE_REQUIRED_OR_NOT_FOUND");
 if(!explicit_plugin_dir){
   // The owner runtime uses <runtime>/active/ for version-locked plugins,
   // whereas CMake test builds place DLLs next to RecompDev.exe.
   auto active=exe_path.parent_path()/"active";
   if(fs::is_directory(active))plugindir=active;
 }
 rom=fs::absolute(rom);plugindir=fs::absolute(plugindir);
 if(out.empty()){
  const char*e=std::getenv("RECOMPDEV_EVIDENCE_ROOT");
  out=(e&&*e?fs::u8path(e):exe_path.parent_path()/"evidence")/"native-discovery";
 }
 if(fs::exists(out))throw std::runtime_error("EVIDENCE_EXISTS_REFUSING_OVERWRITE: "+out.string());
 const std::string source_identity_before=streamhash(rom);
 Source src(rom);auto view=src.view();
 if(src.size==0)throw std::runtime_error("EMPTY_SOURCE");
 // DLL type and API size are checked before invoking any provider callbacks.
 std::vector<std::unique_ptr<Plugin>> plugins;
 RD_FormatResultV1 accepted{};std::string chosen;
 for(const char*name:{"rd_format_sms","rd_format_md","rd_format_ps1"}){
  auto path=plugindir/(std::string(name)+SUFFIX);
  auto p=std::make_unique<Plugin>(path,RD_FORMAT_KIND,sizeof(RD_FormatApiV1));
  auto api=p->api<RD_FormatApiV1>();
  if(api->abi_version!=RD_NATIVE_DISCOVERY_ABI||api->struct_size!=sizeof(*api)||!api->inspect)throw std::runtime_error("INVALID_FORMAT_API");
  RD_FormatResultV1 r{};r.struct_size=sizeof(r);int result=api->inspect(&view,&r);
  if(result<0)throw std::runtime_error("FORMAT_INSPECTION_ERROR: "+std::string(name));
  if(result>0){if(r.abi_version!=RD_NATIVE_DISCOVERY_ABI||r.struct_size!=sizeof(r)||r.platform==0||r.status==RD_INSPECT_NO_MATCH)throw std::runtime_error("MALFORMED_FORMAT_RESULT");
   if(!chosen.empty())throw std::runtime_error("AMBIGUOUS_FORMAT_PROVIDER");
   accepted=r;chosen=name;}
  plugins.push_back(std::move(p));
 }
 if(chosen.empty())throw std::runtime_error("UNRECOGNISED_FORMAT (no native plugin qualified the source)");
 if((!runtime_gap_reports.empty()||!analysis_candidates.empty())&&accepted.platform!=RD_PLATFORM_SMS)throw std::runtime_error("RUNTIME_STOP_CPU_PLATFORM_UNSUPPORTED");
 if(!gap_index.empty()){
  auto indexed=rd_evidence_index::read(gap_index);
  runtime_gap_reports.insert(runtime_gap_reports.end(),indexed.begin(),indexed.end());
 }
 if(runtime_gap_reports.size()>512)throw std::runtime_error("RUNTIME_STOP_REPORT_COUNT_LIMIT");
 if(accepted.status!=RD_INSPECT_MATCH)throw std::runtime_error("FORMAT_FOUND_BUT_UNQUALIFIED: "+std::string(accepted.evidence));
 Discovery disc;
 std::unique_ptr<Plugin> cpu_plugin,mapper;
 if(accepted.platform==RD_PLATFORM_SMS){
  cpu_plugin=std::make_unique<Plugin>(plugindir/(std::string("rd_cpu_z80")+SUFFIX),RD_CPU,sizeof(RD_CpuApi));
  mapper=std::make_unique<Plugin>(plugindir/(std::string("rd_machine_sms")+SUFFIX),RD_MACHINE,sizeof(RD_MachineApi));
  std::vector<RuntimeSeed>seeds;
  for(const auto&runtime_gap_report:runtime_gap_reports)seeds.push_back(parse_runtime_seed(runtime_gap_report,src.size,*mapper));
  if(!analysis_candidates.empty())for(const auto&candidate:parse_analysis_hypotheses(analysis_candidates,source_identity_before,src.size,*mapper))seeds.push_back(candidate);
  disc=walk(&view,*cpu_plugin,*mapper,budget,seeds);
 }
 // Create external evidence only after source and DLL qualification.
 fs::create_directories(out);
 auto report=out/"native-discovery.json";
 std::ofstream f(report,std::ios::binary);if(!f)throw std::runtime_error("EVIDENCE_WRITE_FAILED");
 std::string srcsha=streamhash(rom);
 if(srcsha!=source_identity_before)throw std::runtime_error("SOURCE_CHANGED_DURING_DISCOVERY");
 f<<"{\n  \"schema\": \"recompdev.native.discovery.v1\",\n"
  <<"  \"workspace_release\": \"v0.4.9.11\",\n"
  <<"  \"controller_version\": \"0.4.8\",\n"
  <<"  \"source\": "<<json(rom.u8string())<<",\n"
  <<"  \"source_size\": "<<src.size<<",\n"
  <<"  \"source_sha256\": "<<json(srcsha)<<",\n"
  <<"  \"source_fully_attested\": true,\n"
  <<"  \"provider\": "<<json(chosen)<<",\n"
  <<"  \"platform\": "<<json(platform(accepted.platform))<<",\n"
  <<"  \"cpu\": "<<json(cpu(accepted.cpu))<<",\n"
  <<"  \"entry\": "<<accepted.entry<<",\n"
  <<"  \"executable_offset\": "<<accepted.executable_offset<<",\n"
  <<"  \"executable_size\": "<<accepted.executable_size<<",\n"
  <<"  \"sector_size\": "<<accepted.sector_size<<",\n"
  <<"  \"file_count\": "<<accepted.file_count<<",\n"
  <<"  \"qualification\": "<<json(accepted.evidence)<<",\n"
  <<"  \"python_spawned\": false,\n"
  <<"  \"translation_attempted\": false,\n"
  <<"  \"native_compilation_verified\": false,\n"
  <<"  \"source_length_verified_candidates\": "<<disc.blocks.size()<<",\n"
  <<"  \"execution_semantics_verified\": false,\n"
  <<"  \"control_flow_edges\": "<<disc.edges<<",\n"
  <<"  \"unresolved\": "<<disc.gaps.size()<<",\n"
  <<"  \"plugins\": [\n";
 std::vector<const Plugin*>active;for(const auto&p:plugins)active.push_back(p.get());if(cpu_plugin)active.push_back(cpu_plugin.get());if(mapper)active.push_back(mapper.get());
 for(size_t i=0;i<active.size();++i){auto&p=*active[i];f<<"    {\"name\": "<<json(p.path.filename().string())<<", \"description\": "<<json(p.d->name)<<", \"sha256\": "<<json(filehash(p.path,16*1024*1024))<<"}"<<(i+1<active.size()?",":"")<<"\n";}f<<"  ],\n  \"blocks\": [\n";
 for(size_t i=0;i<disc.blocks.size();++i){auto&b=disc.blocks[i];f<<"    {\"pc\": "<<b.pc<<", \"physical\": "<<b.phys<<", \"length\": "<<b.len<<", \"flow\": "<<b.flow<<", \"target\": "<<b.target<<", \"source_bytes_sha256\": "<<json(b.sha)<<", \"mapper_known_mask\": "<<b.known_banks<<"}"<<(i+1<disc.blocks.size()?",":"")<<"\n";}
 f<<"  ],\n  \"gaps\": [\n";
 for(size_t i=0;i<disc.gaps.size();++i){auto&b=disc.gaps[i];f<<"    {\"pc\": "<<b.pc<<", \"reason\": "<<json(b.reason)<<"}"<<(i+1<disc.gaps.size()?",":"")<<"\n";}
 f<<"  ]\n}\n";f.close();if(!f)throw std::runtime_error("EVIDENCE_WRITE_FAILED");
 std::cout<<"RECOMPDEV_NATIVE_DISCOVERY_REPORT="<<report.string()<<"\n"
          <<"RECOMPDEV_NATIVE_DISCOVERY_PLATFORM="<<platform(accepted.platform)<<"\n"
          <<"RECOMPDEV_NATIVE_DISCOVERY_CANDIDATES="<<disc.blocks.size()<<"\n";
 return 0;
}
