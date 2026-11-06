#include "rd_plugin.h"
#include "rd_sha256.hpp"
#include <array>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#ifdef _WIN32
# define WIN32_LEAN_AND_MEAN
# include <windows.h>
#else
# include <dlfcn.h>
#endif
namespace fs=std::filesystem;
namespace {
#ifdef _WIN32
using Handle=HMODULE;
static Handle load(const std::string& name){return LoadLibraryA(name.c_str());}
static void *symbol(Handle h,const char* n){return reinterpret_cast<void*>(GetProcAddress(h,n));}
static void unload(Handle h){if(h)FreeLibrary(h);}
static const char* suffix=".dll";
#else
using Handle=void*;
static Handle load(const std::string& name){return dlopen(name.c_str(),RTLD_NOW|RTLD_LOCAL);}
static void *symbol(Handle h,const char* n){return dlsym(h,n);}
static void unload(Handle h){if(h)dlclose(h);}
# if defined(__APPLE__)
static const char* suffix=".dylib";
# else
static const char* suffix=".so";
# endif
#endif
struct Module {
 Handle handle=nullptr;
 const RD_Plugin* descriptor=nullptr;
 Module(const fs::path& path,int kind,size_t expected_size){
   handle=load(fs::absolute(path).string());
   if(!handle)throw std::runtime_error("PLUGIN_LOAD_FAILED "+path.string());
   auto* entry=reinterpret_cast<RD_GetPlugin>(symbol(handle,RD_PLUGIN_ENTRY));
   if(!entry){unload(handle);handle=nullptr;throw std::runtime_error("PLUGIN_ENTRY_MISSING "+path.string());}
   descriptor=entry();
   if(!descriptor||descriptor->abi_version!=RD_ABI_VERSION||descriptor->descriptor_size!=sizeof(RD_Plugin)
       ||descriptor->kind!=uint32_t(kind)||descriptor->api_size!=expected_size||!descriptor->api||!descriptor->name){
     unload(handle);handle=nullptr;throw std::runtime_error("PLUGIN_ABI_OR_KIND_REJECTED "+path.string());
   }
 }
 ~Module(){unload(handle);}
 Module(const Module&)=delete;Module& operator=(const Module&)=delete;
 template<typename T>const T& api()const{return *static_cast<const T*>(descriptor->api);}
};
static fs::path exe_directory(const char* argv0){
#ifdef _WIN32
 char p[32768]{};DWORD n=GetModuleFileNameA(nullptr,p,DWORD(sizeof(p)));if(!n||n>=sizeof(p))throw std::runtime_error("EXE_PATH_UNAVAILABLE");return fs::path(p).parent_path();
#else
 return fs::absolute(argv0).parent_path();
#endif
}
static std::vector<uint8_t> fixture(bool corrupt,bool unsupported){
 // This is author-created synthetic code. No copyrighted game ROM is embedded.
 std::vector<uint8_t> out(0xc000,0);
 auto put=[&](size_t a,std::initializer_list<uint8_t> bytes){for(auto b:bytes)out.at(a++)=b;};
 put(0x0000,{0x3e,0x90,0xd3,0x7f,0x3e,0x01,0x32,0xff,0xff,0xc3,0x00,0x80});
 put(0x4000,{0x3e,0x2a,0x32,0x00,0xc0,0x3e,0x02,0x32,0xff,0xff});
 put(0x8000,{0x3e,0x99,0x76});
 put(0x800a,{0xdb,0xdc,0x76});
 if(corrupt)out[0]=0x00;
 if(unsupported)out[2]=0xed;
 return out;
}
struct Config {
 fs::path plugindir,output="probe",rom_path;
 std::string test_case="main";
 size_t max_steps=40;
 uint16_t entry=0;
 uint64_t buttons=16;
 bool validate=false,no_fallback=false,corrupt=false,unsupported=false,list=false,probe=false;
 std::string machine="rd_machine_sms",cpu="rd_cpu_z80",game="rd_game_fixture",discovery="rd_discovery_jsonl",display="rd_display_ppm",audio="rd_audio_wav",input="rd_input_fixed";
};
static Config parse(int argc,char **argv){
 Config o; o.plugindir=exe_directory(argv[0]);
 for(int i=1;i<argc;++i){
   std::string a=argv[i];
   auto value=[&](){if(++i>=argc)throw std::runtime_error("MISSING_ARGUMENT "+a);return std::string(argv[i]);};
   if(a=="--plugin-dir")o.plugindir=value();
   else if(a=="--out")o.output=value();
   else if(a=="--case")o.test_case=value();
   else if(a=="--rom")o.rom_path=value();
   else if(a=="--entry"){auto v=std::stoul(value(),nullptr,0);if(v>65535)throw std::runtime_error("INVALID_ROM_ENTRY");o.entry=uint16_t(v);}
   else if(a=="--steps")o.max_steps=std::stoull(value());
   else if(a=="--buttons")o.buttons=std::stoull(value(),nullptr,0);
   else if(a=="--machine")o.machine=value();
   else if(a=="--cpu")o.cpu=value();
   else if(a=="--game")o.game=value();
   else if(a=="--discovery")o.discovery=value();
   else if(a=="--display")o.display=value();
   else if(a=="--audio")o.audio=value();
   else if(a=="--input")o.input=value();
   else if(a=="--validate")o.validate=true;
   else if(a=="--no-fallback")o.no_fallback=true;
   else if(a=="--probe")o.probe=true;
   else if(a=="--corrupt-fixture")o.corrupt=true;
   else if(a=="--unsupported")o.unsupported=true;
   else if(a=="--list")o.list=true;
   else if(a=="--help"){
     std::cout<<"RecompDev Modular Harness PoC v0.3 (limited Z80 runtime, NOT gameplay parity)\n"
              <<"  --plugin-dir DIR --out PREFIX --case main|bank2|rom --validate\n"
              <<"  --case rom --rom GAME_IMAGE [--entry PC] --game rd_game_recomp_v0445\n"
              <<"  --probe --case rom --rom IMAGE (untranslated exploratory probe)\n"
              <<"  --no-fallback --steps N --buttons BITSET --list\n"
              <<"  --machine NAME --cpu NAME --game NAME --discovery NAME\n"
              <<"  --display NAME --audio NAME --input NAME\n";
     std::exit(0);
   }else throw std::runtime_error("UNKNOWN_OPTION "+a);
 }
 if(o.test_case!="main"&&o.test_case!="bank2"&&o.test_case!="rom")throw std::runtime_error("UNKNOWN_TEST_CASE");
 if(o.test_case=="rom"&&o.rom_path.empty())throw std::runtime_error("ROM_PATH_REQUIRED");
 if(o.test_case!="rom"&&!o.rom_path.empty())throw std::runtime_error("ROM_REQUIRES_ROM_CASE");
 if(o.test_case=="rom"&&(o.corrupt||o.unsupported))throw std::runtime_error("FIXTURE_MUTATION_REQUIRES_FIXTURE_CASE");
 if(o.probe){
   if(o.test_case!="rom"||o.validate||o.no_fallback||o.game!="rd_game_probe")
     throw std::runtime_error("PROBE_REQUIRES_ROM_AND_RD_GAME_PROBE_WITHOUT_VALIDATION");
 }
 if(o.max_steps==0||o.max_steps>100000)throw std::runtime_error("INVALID_STEP_LIMIT");
 if(o.validate&&o.no_fallback)throw std::runtime_error("VALIDATE_REQUIRES_FALLBACK");
 for(const auto& name:{o.machine,o.cpu,o.game,o.discovery,o.display,o.audio,o.input}){
   if(name.empty()||name.size()>96||name.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")!=std::string::npos)
     throw std::runtime_error("INVALID_PLUGIN_NAME");
 }
 return o;
}
struct Plugins {
 Module machine,cpu,game,discovery,display,audio,input;
 explicit Plugins(const fs::path& dir,const Config& c):
    machine(dir/(c.machine+suffix),RD_MACHINE,sizeof(RD_MachineApi)),
    cpu(dir/(c.cpu+suffix),RD_CPU,sizeof(RD_CpuApi)),
    game(dir/(c.game+suffix),RD_GAME,sizeof(RD_GameApi)),
    discovery(dir/(c.discovery+suffix),RD_DISCOVERY,sizeof(RD_DiscoveryApi)),
    display(dir/(c.display+suffix),RD_DISPLAY,sizeof(RD_DisplayApi)),
    audio(dir/(c.audio+suffix),RD_AUDIO,sizeof(RD_AudioApi)),
    input(dir/(c.input+suffix),RD_INPUT,sizeof(RD_InputApi)){}
};
struct Outcome {
 RD_CpuState cpu{};RD_MachineStats machine{};
 uint64_t native_steps=0,fallback_steps=0,discovery_events=0;
 bool halted=false,budget=false,blocked=false;
 uint16_t blocked_pc=0;uint32_t blocked_physical=0;uint8_t blocked_opcode=0;
 std::string source_sha256;
};
static void require(bool pass,const char *why){if(!pass)throw std::runtime_error(why);}
static Outcome run(const Config& conf,const Plugins& p,bool allow_native,bool output){
 const auto& ma=p.machine.api<RD_MachineApi>();
 auto data=fixture(conf.corrupt,conf.unsupported);
 if(conf.test_case=="rom"){
  std::ifstream f(conf.rom_path,std::ios::binary|std::ios::ate);
  require(bool(f),"ROM_READ_FAILED");
  const auto bytes=static_cast<std::streamoff>(f.tellg());
  require(bytes>=0x4000 && bytes<=64*1024*1024,"INVALID_ROM_SIZE");
  data.resize(static_cast<std::size_t>(bytes));f.seekg(0);
  require(bool(f.read(reinterpret_cast<char*>(data.data()),std::streamsize(data.size()))),"ROM_READ_INCOMPLETE");
  auto sha=reinterpret_cast<const char*(*)()>(symbol(p.game.handle,"rd_game_source_sha256_v1"));
  auto size=reinterpret_cast<uint64_t(*)()>(symbol(p.game.handle,"rd_game_source_size_v1"));
  if(!conf.probe){
    require(sha && size,"GAME_SOURCE_IDENTITY_MISSING");
    require(size()==data.size(),"ROM_SIZE_MISMATCH");
    const char* expected_sha=sha();
    require(expected_sha && std::string(expected_sha)==rdhash::sha256(data.data(),data.size()),"ROM_SHA256_MISMATCH");
  }
 }
 using MachineHandle=std::unique_ptr<void,void(*)(void*)>;
 MachineHandle instance(ma.create(data.data(),data.size()),ma.destroy);
 require(bool(instance),"MACHINE_CREATE_FAILED");
 RD_Bus bus=ma.bus(instance.get());
 require(bus.ctx && bus.read && bus.write && bus.in_port && bus.out_port && bus.physical && bus.advance && bus.set_pc,"BUS_INCOMPLETE");
 RD_CpuState cpu{};cpu.sp=0xdff0;
 if(conf.test_case=="bank2")cpu.pc=0x8000;
 if(conf.test_case=="rom")cpu.pc=conf.entry;
 ma.set_input(instance.get(),p.input.api<RD_InputApi>().buttons(0,conf.buttons));
 const auto& disc=p.discovery.api<RD_DiscoveryApi>();
 struct FileDeleter{const RD_DiscoveryApi *api;void operator()(void* h)const{if(h)api->close(h);}};
 const fs::path event_file=conf.output.string()+".events.jsonl";
 std::unique_ptr<void,FileDeleter> log(nullptr,{&disc});
 if(output){
  if(!event_file.parent_path().empty())fs::create_directories(event_file.parent_path());
  log.reset(disc.open(event_file.string().c_str()));require(bool(log),"EVENT_LOG_CREATE_FAILED");
 }
 Outcome result{};
 if(conf.test_case=="rom")result.source_sha256=rdhash::sha256(data.data(),data.size());
 for(size_t iteration=0;iteration<conf.max_steps && !cpu.halted;++iteration){
  bus.set_pc(bus.ctx,cpu.pc);
  ma.set_input(instance.get(),p.input.api<RD_InputApi>().buttons(cpu.steps,conf.buttons));
  const uint16_t old_pc=cpu.pc;
  const uint32_t phy=bus.physical(bus.ctx,old_pc);
  const uint8_t op=bus.read(bus.ctx,old_pc);
  RD_MachineStats before{};ma.stats(instance.get(),&before);
  uint32_t cycles=0;bool native=false;
  if(allow_native){
   int rc=p.game.api<RD_GameApi>().execute_native(phy,&cpu,&bus,&cycles);
   require(rc>=0,"NATIVE_SOURCE_BYTES_MISMATCH");
   native=rc==1;
  }
  if(native){++result.native_steps;}
  else {
   require(!conf.no_fallback,"NATIVE_ONLY_UNRESOLVED_CODE");
   int rc=p.cpu.api<RD_CpuApi>().interpret_one(&cpu,&bus,&cycles);
   if(rc<0 && conf.probe){
      result.blocked=true;result.blocked_pc=old_pc;result.blocked_physical=phy;result.blocked_opcode=op;
      if(output){
        RD_Event ev{cpu.steps+1,old_pc,op,0,phy,before.bank3,0,"EXECUTION_BLOCKED"};
        require(disc.emit(log.get(),&ev)!=0,"DISCOVERY_IO_FAILED");++result.discovery_events;
      }
      break;
   }
   require(rc>=0,"UNSUPPORTED_Z80_OPCODE");
   if(!rc)break;
   ++result.fallback_steps;
  }
  require(cycles>0&&cycles<=1000,"BAD_INSTRUCTION_CYCLES");
  cpu.cycles+=cycles;++cpu.steps;
  bus.advance(bus.ctx,cycles);
  if(output){
    const char* kind=native?"NATIVE_EXECUTED":"FALLBACK_DISCOVERED";
    RD_Event ev{cpu.steps,old_pc,op,0,phy,before.bank3,cycles,kind};
    require(disc.emit(log.get(),&ev)!=0,"DISCOVERY_IO_FAILED");++result.discovery_events;
    RD_MachineStats after{};ma.stats(instance.get(),&after);
    if(after.bank3!=before.bank3){
     ev.kind="BANK_SWITCH";ev.bank=after.bank3;
     require(disc.emit(log.get(),&ev)!=0,"DISCOVERY_IO_FAILED");++result.discovery_events;
    }
  }
 }
 result.cpu=cpu;
 ma.stats(instance.get(),&result.machine);
 result.halted=cpu.halted!=0;
 result.budget=!result.halted && cpu.steps>=conf.max_steps;
 require(result.machine.tstates==cpu.cycles&&result.machine.steps==cpu.steps,"CPU_MACHINE_CLOCK_DIVERGENCE");
 if(output){
   std::vector<uint32_t> pixels(RD_PIXELS);
   uint32_t w=0,h=0;
   require(ma.frame_bgra(instance.get(),pixels.data(),pixels.size(),&w,&h)!=0,"FRAME_GENERATION_FAILED");
   require(p.display.api<RD_DisplayApi>().save_ppm((conf.output.string()+".ppm").c_str(),pixels.data(),w,h)!=0,"DISPLAY_SINK_FAILED");
   std::array<int16_t,RD_AUDIO_SAMPLES> pcm{};
   require(ma.audio_pcm(instance.get(),pcm.data(),pcm.size())!=0,"PCM_GENERATION_FAILED");
   require(p.audio.api<RD_AudioApi>().save_wav((conf.output.string()+".wav").c_str(),pcm.data(),uint32_t(pcm.size()),44100)!=0,"AUDIO_SINK_FAILED");
 }
 return result;
}
static void parity(const Outcome& a,const Outcome& b){
 const auto& x=a.cpu;const auto& y=b.cpu;
 require(x.pc==y.pc && x.sp==y.sp&&x.a==y.a&&x.f==y.f&&x.b==y.b&&x.c==y.c
   &&x.d==y.d&&x.e==y.e&&x.h==y.h&&x.l==y.l&&x.halted==y.halted
   &&x.cycles==y.cycles&&x.steps==y.steps,"CPU_DIFFERENTIAL_MISMATCH");
 const auto& s=a.machine;const auto& t=b.machine;
 require(s.tstates==t.tstates&&s.steps==t.steps&&s.bank2==t.bank2&&s.bank3==t.bank3
   &&s.ram_writes==t.ram_writes&&s.bank_switches==t.bank_switches&&s.psg_writes==t.psg_writes
   &&s.hardware_hash==t.hardware_hash&&s.c000==t.c000&&s.controller_a==t.controller_a,
   "MACHINE_DIFFERENTIAL_MISMATCH");
}
static void report(const Config& c,const Outcome& r,bool parity_ok){
 fs::path file=c.output.string()+".report.json";
 if(!file.parent_path().empty())fs::create_directories(file.parent_path());
 std::ofstream f(file,std::ios::binary|std::ios::trunc);require(bool(f),"REPORT_CREATE_FAILED");
 f<<"{\n  \"schema\": \"recompdev-modular-harness-poc-v1\",\n"
  <<"  \"source_release\": \"0.4.0.45\",\n"
  <<"  \"fixture\": \""<<(c.test_case=="rom"?"external or sample ROM image":"author-created synthetic Z80")<<"\",\n"
  <<"  \"case\": \""<<c.test_case<<"\",\n"
  <<"  \"game_module\": \""<<c.game<<"\",\n"
  <<"  \"native_steps\": "<<r.native_steps<<",\n"
  <<"  \"fallback_steps\": "<<r.fallback_steps<<",\n"
  <<"  \"discovery_events\": "<<r.discovery_events<<",\n"
  <<"  \"cpu_pc\": "<<r.cpu.pc<<",\n"
  <<"  \"cpu_a\": "<<unsigned(r.cpu.a)<<",\n"
  <<"  \"cycles\": "<<r.cpu.cycles<<",\n"
  <<"  \"halted\": "<<(r.halted?"true":"false")<<",\n"
  <<"  \"probe_mode\": "<<(c.probe?"true":"false")<<",\n"
  <<"  \"blocked_unsupported_opcode\": "<<(r.blocked?"true":"false")<<",\n"
  <<"  \"blocked_pc\": "<<r.blocked_pc<<",\n"
  <<"  \"blocked_physical\": "<<r.blocked_physical<<",\n"
  <<"  \"blocked_opcode\": "<<unsigned(r.blocked_opcode)<<",\n"
  <<"  \"source_sha256\": \""<<r.source_sha256<<"\",\n"
  <<"  \"step_budget_exhausted\": "<<(r.budget?"true":"false")<<",\n"
  <<"  \"bank3\": "<<r.machine.bank3<<",\n"
  <<"  \"ram_c000\": "<<unsigned(r.machine.c000)<<",\n"
  <<"  \"psg_writes\": "<<r.machine.psg_writes<<",\n"
  <<"  \"machine_hash\": \""<<std::hex<<r.machine.hardware_hash<<std::dec<<"\",\n"
  <<"  \"differential_pass\": "<<(parity_ok?"true":"false")<<",\n"
  <<"  \"runtime_rom_free\": false,\n"
  <<"  \"full_z80_coverage\": false,\n"
  <<"  \"independent_reference_parity\": false,\n"
  <<"  \"windows_binary_verified\": false\n}\n";
 require(bool(f),"REPORT_WRITE_FAILED");
}
}
int rd_harness_run(int argc,char **argv){
 try{
  auto opts=parse(argc,argv);Plugins p(opts.plugindir,opts);
  if(opts.list){
    for(auto* m:{&p.machine,&p.cpu,&p.game,&p.discovery,&p.display,&p.audio,&p.input}){
      std::cout<<m->descriptor->kind<<" "<<m->descriptor->name<<" (ABI "<<m->descriptor->abi_version<<")\n";
    }
    return 0;
  }
  const auto mixed=run(opts,p,true,true);
  bool checked=false;
  if(opts.validate){const auto reference=run(opts,p,false,false);parity(mixed,reference);checked=true;}
  report(opts,mixed,checked);
  if(opts.probe){
    std::cout<<"HARNESS_PROBE_INCOMPLETE native="<<mixed.native_steps
             <<" fallback="<<mixed.fallback_steps<<" blocked="<<mixed.blocked
             <<" pc="<<mixed.blocked_pc<<" opcode="<<unsigned(mixed.blocked_opcode)
             <<" halted="<<mixed.halted<<" budget="<<mixed.budget
             <<" UNVERIFIED_NO_GAMEPLAY_PARITY\n";
    return 0;
  }
  std::cout<<"HARNESS_POC_PASS native="<<mixed.native_steps<<" fallback="<<mixed.fallback_steps
           <<" events="<<mixed.discovery_events<<" halted="<<mixed.halted
           <<" pc="<<mixed.cpu.pc<<" a="<<unsigned(mixed.cpu.a)
           <<" c000="<<unsigned(mixed.machine.c000)<<" bank3="<<mixed.machine.bank3
           <<" psg="<<mixed.machine.psg_writes<<" cycles="<<mixed.cpu.cycles
           <<" differential="<<(checked?"PASS":"NOT_RUN")<<" NOT_GAMEPLAY_PARITY\n";
  return 0;
 }catch(const std::exception& e){std::cerr<<"HARNESS_POC_FAIL "<<e.what()<<"\n";return 4;}
}
