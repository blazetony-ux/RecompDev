#include "native_discovery.hpp"
#include "rd_native_discovery_v1.h"
#include "rd_sha256.hpp"
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
Handle load(const fs::path&p){return LoadLibraryW(p.wstring().c_str());}
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
struct Discovery{
 std::vector<Block> blocks;std::vector<Gap> gaps;uint32_t edges=0;
};
Discovery walk(const RD_SourceV1*s,const Plugin&cpu_plugin,const Plugin&mapper,uint32_t max_items){
 auto decode=cpu_plugin.symbol<RD_Z80DecodeFnV1>("rd_z80_decode_source_v1");
 auto init=mapper.symbol<RD_SmsMapInitialFnV1>("rd_sms_map_initial_v1");
 auto map=mapper.symbol<RD_SmsMapResolveFnV1>("rd_sms_map_resolve_v1");
 auto write=mapper.symbol<RD_SmsMapWriteFnV1>("rd_sms_map_write_v1");
 auto effects=cpu_plugin.symbol<RD_Z80AbstractFnV1>("rd_z80_abstract_a_v1");
 struct Work{uint16_t pc;RD_SmsSourceMapV1 mapping;RD_Z80AbstractV1 a;};
 RD_SmsSourceMapV1 initial{};initial.struct_size=sizeof(initial);
 if(init(&initial)!=1)throw std::runtime_error("SMS_INITIAL_MAPPER_FAILED");
 RD_Z80AbstractV1 initial_a{};initial_a.abi_version=RD_NATIVE_DISCOVERY_ABI;initial_a.struct_size=sizeof(initial_a);
 Discovery out;std::vector<Work> todo{{0,initial,initial_a}};
 // Context key includes physical bank identity, not only guest PC; two distinct
 // ROM banks may map the same CPU address and must never be merged.
 std::set<std::string> seen;
 while(!todo.empty()&&seen.size()<max_items){
  Work w=todo.back();todo.pop_back();
  std::string key;
  key.append(reinterpret_cast<const char*>(&w.pc),sizeof(w.pc));
  key.push_back(char(w.mapping.known_mask));
  for(auto bank:w.mapping.mapper)key.push_back(char(bank));
  key.push_back(char(w.a.known_a));key.push_back(char(w.a.known_a?w.a.a:0));
  key.push_back(char(w.a.known_sp));
  if(w.a.known_sp){key.push_back(char(w.a.sp));key.push_back(char(w.a.sp>>8));}
  if(!seen.insert(key).second)continue;
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
  RD_Z80EffectV1 effect{};effect.struct_size=sizeof(effect);
  if(effects(b.data(),decoded.length,&w.a,&effect)!=1||
     effect.abi_version!=RD_NATIVE_DISCOVERY_ABI){
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
  const bool fall=decoded.flow==RD_FLOW_FALL||decoded.flow==RD_FLOW_COND||
                 decoded.flow==RD_FLOW_CALL||
                 (decoded.flow==RD_FLOW_INDIRECT&&decoded.conditional);
  const bool branch=decoded.flow==RD_FLOW_COND||decoded.flow==RD_FLOW_JUMP||decoded.flow==RD_FLOW_CALL;
  if(fall&&uint32_t(w.pc)+decoded.length<0x10000u){
   Work after=w;after.pc=uint16_t(w.pc+decoded.length);
   if(decoded.flow==RD_FLOW_CALL){
    // A return-site is only a potential CFG successor; the call may modify
    // any bank or A, so future mapping is deliberately unknown.
    after.mapping.known_mask=0;after.a.known_a=0;after.a.known_sp=0;
   }
   todo.push_back(after);++out.edges;
  }
  if(branch){w.pc=decoded.target;todo.push_back(w);++out.edges;}
  if(decoded.flow==RD_FLOW_INDIRECT)
   out.gaps.push_back({w.pc,"DYNAMIC_TARGET_REQUIRES_RUNTIME_EVIDENCE"});
 }
 if(!todo.empty())out.gaps.push_back({todo.back().pc,"DISCOVERY_BUDGET_EXHAUSTED"});
 return out;
}
} // namespace
int rd_native_discover(const std::vector<std::string>&args,const fs::path&exe_path){
 fs::path rom,plugindir=exe_path.parent_path(),out;bool explicit_plugin_dir=false;
 uint32_t budget=4096;
 for(size_t i=0;i<args.size();++i){
  auto next=[&]()->std::string{if(i+1==args.size())throw std::runtime_error("MISSING_ARGUMENT "+args[i]);return args[++i];};
  if(args[i]=="--rom")rom=fs::u8path(next());
  else if(args[i]=="--stage"){if(next()!="discover")throw std::runtime_error("UNEXPECTED_STAGE");}
  else if(args[i]=="--plugin-dir"){plugindir=fs::u8path(next());explicit_plugin_dir=true;}
  else if(args[i]=="--out")out=fs::u8path(next());
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
 if(accepted.status!=RD_INSPECT_MATCH)throw std::runtime_error("FORMAT_FOUND_BUT_UNQUALIFIED: "+std::string(accepted.evidence));
 Discovery disc;
 std::unique_ptr<Plugin> cpu_plugin,mapper;
 if(accepted.platform==RD_PLATFORM_SMS){
  cpu_plugin=std::make_unique<Plugin>(plugindir/(std::string("rd_cpu_z80")+SUFFIX),RD_CPU,sizeof(RD_CpuApi));
  mapper=std::make_unique<Plugin>(plugindir/(std::string("rd_machine_sms")+SUFFIX),RD_MACHINE,sizeof(RD_MachineApi));
  disc=walk(&view,*cpu_plugin,*mapper,budget);
 }
 // Create external evidence only after source and DLL qualification.
 fs::create_directories(out);
 auto report=out/"native-discovery.json";
 std::ofstream f(report,std::ios::binary);if(!f)throw std::runtime_error("EVIDENCE_WRITE_FAILED");
 std::string srcsha=streamhash(rom);
 if(srcsha!=source_identity_before)throw std::runtime_error("SOURCE_CHANGED_DURING_DISCOVERY");
 f<<"{\n  \"schema\": \"recompdev.native.discovery.v1\",\n"
  <<"  \"workspace_release\": \"v0.4.9.9\",\n"
  <<"  \"controller_version\": \"0.4.6\",\n"
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
