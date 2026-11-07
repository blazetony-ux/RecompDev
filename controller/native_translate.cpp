#include "native_translate.hpp"
#include "native_discovery.hpp"
#include "rd_translation_v1.h"
#include "rd_sha256.hpp"
#include "rd_tiny_json.hpp"
#include <chrono>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#include <cstdlib>
#include <iterator>
#include <cstring>
#include <regex>
#include <algorithm>
#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#else
#include <unistd.h>
#include <sys/wait.h>
#include <cerrno>
#include <dlfcn.h>
#endif
namespace fs=std::filesystem;
namespace {
#ifdef _WIN32
std::wstring quote(const std::wstring&v){std::wstring o=L"\"";size_t bs=0;for(wchar_t c:v){if(c==L'\\'){++bs;continue;}if(c==L'"'){o.append(bs*2+1,L'\\');o+=c;bs=0;continue;}o.append(bs,L'\\');bs=0;o+=c;}o.append(bs*2,L'\\');return o+L'"';}
int process(const std::vector<fs::path>&v){
 std::wstring cmd;for(auto&p:v){if(!cmd.empty())cmd+=L' ';cmd+=quote(p.wstring());}
 std::vector<wchar_t>b(cmd.begin(),cmd.end());b.push_back(0);
 STARTUPINFOW si{};si.cb=sizeof(si);PROCESS_INFORMATION pi{};
 if(!CreateProcessW(nullptr,b.data(),nullptr,nullptr,FALSE,0,nullptr,nullptr,&si,&pi))return 127;
 WaitForSingleObject(pi.hProcess,INFINITE);DWORD exit=127;GetExitCodeProcess(pi.hProcess,&exit);CloseHandle(pi.hThread);CloseHandle(pi.hProcess);return int(exit);
}
using Handle=HMODULE;
Handle open(const fs::path&p){return LoadLibraryExW(fs::absolute(p).wstring().c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);}
void* symbol(Handle h,const char*n){return reinterpret_cast<void*>(GetProcAddress(h,n));}
void close(Handle h){FreeLibrary(h);}
constexpr const char* EXT=".dll";
#else
int process(const std::vector<fs::path>&v){pid_t pid=fork();if(pid<0)return 127;if(pid==0){
 std::vector<std::string>args;for(const auto&p:v)args.push_back(p.string());std::vector<char*>av;for(auto&s:args)av.push_back(s.data());av.push_back(nullptr);execvp(av[0],av.data());_exit(127);
 }int status;while(waitpid(pid,&status,0)<0){if(errno!=EINTR)return 127;}return WIFEXITED(status)?WEXITSTATUS(status):127;}
using Handle=void*;
Handle open(const fs::path&p){return dlopen(p.c_str(),RTLD_NOW|RTLD_LOCAL);}
void* symbol(Handle h,const char*n){return dlsym(h,n);}
void close(Handle h){dlclose(h);}
constexpr const char* EXT=".so";
#endif
std::string sha(const fs::path&p){std::ifstream f(p,std::ios::binary);if(!f)throw std::runtime_error("ROM_UNREADABLE");
 std::string s((std::istreambuf_iterator<char>(f)),{});
 return rdhash::sha256(reinterpret_cast<const uint8_t*>(s.data()),s.size());}
void require(bool yes,const std::string&reason){if(!yes)throw std::runtime_error(reason);}
}
int rd_native_translate(const std::vector<std::string>&args,const fs::path&exe){
 fs::path rom,base,out,plugin_dir=exe.parent_path(),source_root,discovery_report,analysis_candidates;std::vector<fs::path>runtime_gap_reports;
 bool discover_source=false;
 if(fs::is_directory(plugin_dir/"active"))plugin_dir/="active";
 std::vector<std::string>banks;std::vector<fs::path>history_roots;bool require_ghidra=true,compile=true,full=true;
 for(size_t i=0;i<args.size();++i){
  auto next=[&](){require(i+1<args.size(),"MISSING_ARGUMENT "+args[i]);return args[++i];};
  const auto&a=args[i];
  if(a=="--stage"){require(next()=="native-translate","UNEXPECTED_STAGE");}
  else if(a=="--rom")rom=fs::u8path(next());
  else if(a=="--export")base=fs::u8path(next());
  else if(a=="--bank-export")banks.push_back(next());
  else if(a=="--history-root")history_roots.push_back(fs::u8path(next()));
  else if(a=="--plugin-dir")plugin_dir=fs::u8path(next());
  else if(a=="--source-root")source_root=fs::u8path(next());
  else if(a=="--out")out=fs::u8path(next());
  else if(a=="--discovery-report")discovery_report=fs::u8path(next());
  else if(a=="--analysis-candidates"){analysis_candidates=fs::u8path(next());discover_source=true;}
  else if(a=="--runtime-gap-report"){runtime_gap_reports.push_back(fs::u8path(next()));discover_source=true;}
  else if(a=="--discover-source")discover_source=true;
  else if(a=="--allow-synthetic-export")require_ghidra=false;
  else if(a=="--no-compile")compile=false;
  else if(a=="--backend"){auto b=next();require(b=="full"||b=="game-dll","UNSUPPORTED_TRANSLATION_BACKEND");full=(b=="full");}
  else throw std::runtime_error("UNKNOWN_NATIVE_TRANSLATE_OPTION "+a);
 }
 require(!rom.empty()&&!base.empty(),"ROM_AND_GHIDRA_EXPORT_REQUIRED");
 require(runtime_gap_reports.empty()||discovery_report.empty(),"SELECT_EXPLICIT_OR_RUNTIME_GAP_DISCOVERY");
 require(runtime_gap_reports.size()<=64,"RUNTIME_STOP_REPORT_COUNT_LIMIT");
 require(fs::is_regular_file(rom)&&fs::is_regular_file(base),"ROM_OR_EXPORT_MISSING");
 if(source_root.empty()){
  auto pointer=exe.parent_path()/"source-root.txt";
  if(fs::is_regular_file(pointer)){std::ifstream f(pointer);std::string s;std::getline(f,s);source_root=fs::u8path(s);}
  else if(const char*e=std::getenv("RECOMPDEV_SOURCE_ROOT"))source_root=fs::u8path(e);
  // A normal installed controller lives in the runtime sibling directory,
  // while its Git-managed source checkout lives beside it. Find it by source
  // structure rather than depending on an installer-created per-release file.
  if(source_root.empty()){
   const auto siblings=exe.parent_path().parent_path();
   std::error_code ec;
   if(fs::is_directory(siblings,ec)){
    size_t checked=0;
    for(fs::directory_iterator it(siblings,fs::directory_options::skip_permission_denied,ec),end;
        it!=end&&!ec&&checked<64;it.increment(ec),++checked){
     if(!it->is_directory(ec)||it->is_symlink(ec))continue;
     const auto candidate=it->path();
     if(fs::is_regular_file(candidate/"RELEASE_ID.txt")&&
        fs::is_regular_file(candidate/"harness"/"include"/"rd_pcode_bridge.hpp")&&
        fs::is_regular_file(candidate/"docs"/"project"/"DEVELOPMENT-CONTRACT.md")){
      require(source_root.empty(),"MULTIPLE_SOURCE_ROOTS_REQUIRE_EXPLICIT_SELECTION");
      source_root=candidate;
     }
    }
   }
  }
 }
 require(!source_root.empty()&&fs::is_regular_file(source_root/"harness"/"include"/"rd_pcode_bridge.hpp"),"SOURCE_ROOT_REQUIRED_FOR_COMPILE");
 rom=fs::weakly_canonical(rom);base=fs::weakly_canonical(base);source_root=fs::weakly_canonical(source_root);
 if(out.empty()){
  const char*e=std::getenv("RECOMPDEV_EVIDENCE_ROOT");
  auto parent=(e&&*e)?fs::u8path(e):(source_root.parent_path()/"RecompDev-Evidence");
  auto stamp=std::chrono::duration_cast<std::chrono::microseconds>(
    std::chrono::system_clock::now().time_since_epoch()).count();
  out=parent/"v0.4.9.11"/"native-translate"/(std::to_string(stamp));
 }
 out=fs::absolute(out).lexically_normal();
 // Reuse existing Ghidra bank-recovery evidence from prior runs, without
 // requiring each recovered document to be specified by hand. Read only;
 // the translator DLL still verifies every instruction against this ROM.
 if(!history_roots.empty()){
  std::string expected=sha(rom);
  std::ifstream initial(base,std::ios::binary);
  if(!initial)throw std::runtime_error("BASE_EXPORT_UNREADABLE");
  std::string base_json((std::istreambuf_iterator<char>(initial)),{});
  const auto initial_doc=rdjson::Reader(base_json).parse();
  const auto target=initial_doc.get("target_id").string();
  require(initial_doc.get("source_sha256").string()==expected,"BASE_ROM_MISMATCH");
  std::vector<fs::path>found;
  size_t inspected=0;
  for(const auto&root:history_roots){
   require(fs::is_directory(root),"HISTORY_DIRECTORY_MISSING");
   std::error_code ec;
   fs::recursive_directory_iterator it(root,fs::directory_options::skip_permission_denied,ec),end;
   for(;it!=end;it.increment(ec)){
    if(ec)throw std::runtime_error("HISTORY_ENUMERATION_FAILED");
    if(++inspected>50000)throw std::runtime_error("HISTORY_ENTRY_LIMIT_EXCEEDED");
    const auto&p=it->path();
    if(it->is_symlink()){
     if(it->is_directory())it.disable_recursion_pending();
     continue;
    }
    if(!it->is_regular_file()||p.filename()!="bank-functions.json")continue;
    if(it->file_size()>64u*1024u*1024u)continue;
    std::ifstream file(p,std::ios::binary);
    std::string body((std::istreambuf_iterator<char>(file)),{});
    const auto obj=rdjson::Reader(body).parse();
    if(obj.get("schema").t!=rdjson::V::String||obj.get("schema").s!="recomp-function-pcode-v1")continue;
    if(obj.get("source_sha256").t!=rdjson::V::String||obj.get("source_sha256").s!=expected)continue;
    if(obj.get("target_id").t!=rdjson::V::String||obj.get("target_id").s!=target)continue;
    if(obj.get("bank_context").isnull())continue;
    found.push_back(fs::weakly_canonical(p));
   }
  }
  std::sort(found.begin(),found.end());
  found.erase(std::unique(found.begin(),found.end()),found.end());
  require(found.size()+banks.size()<=64,"BANK_EXPORT_COUNT_LIMIT");
  for(const auto&p:found)banks.push_back(p.u8string());
  std::cout<<"RECOMPDEV_HISTORY_BANK_EXPORTS="<<found.size()<<"\n";
 }
 if(discover_source){
  require(discovery_report.empty(),"SELECT_EXPLICIT_OR_AUTOMATIC_DISCOVERY");
  auto discovery_out=out;
  discovery_out+= "-source-discovery";
  std::vector<std::string> discovery_args={"--stage","discover","--rom",rom.u8string(),
    "--plugin-dir",plugin_dir.u8string(),"--out",discovery_out.u8string(),"--budget","10000"};
  if(!analysis_candidates.empty()){discovery_args.push_back("--analysis-candidates");discovery_args.push_back(analysis_candidates.u8string());}
  for(const auto&runtime_gap_report:runtime_gap_reports){discovery_args.push_back("--runtime-gap-report");discovery_args.push_back(runtime_gap_report.u8string());}
  require(rd_native_discover(discovery_args,exe)==0,"SOURCE_DISCOVERY_FAILED");
  discovery_report=discovery_out/"native-discovery.json";
 }
 require(!fs::exists(out),"EVIDENCE_EXISTS_REFUSING_OVERWRITE");
 bool beneath=false;auto a=source_root.begin(),b=out.begin();
 for(;a!=source_root.end()&&b!=out.end()&&*a==*b;++a,++b){}
 beneath=(a==source_root.end());
 require(!beneath,"EVIDENCE_MUST_BE_OUTSIDE_SOURCE");
 require(out!=rom.parent_path(),"OUTPUT_ROM_DIRECTORY_REFUSED");
 fs::path p=fs::absolute(plugin_dir)/(std::string("rd_translation_pcode")+EXT);
 require(fs::is_regular_file(p),"TRANSLATION_DLL_MISSING");
 Handle h=open(p);require(h!=nullptr,"TRANSLATION_DLL_LOAD_FAILED");
 try{
  auto get=reinterpret_cast<RD_GetPlugin>(symbol(h,RD_PLUGIN_ENTRY));
  require(get!=nullptr,"TRANSLATION_PLUGIN_ENTRY_MISSING");
  const RD_Plugin*plugin=get();
  require(plugin&&plugin->abi_version==RD_ABI_VERSION&&plugin->descriptor_size==sizeof(RD_Plugin)&&
    plugin->kind==RD_TRANSLATOR_KIND&&plugin->api_size==sizeof(RD_TranslationApiV1),"TRANSLATION_PLUGIN_ABI_MISMATCH");
  const auto*api=static_cast<const RD_TranslationApiV1*>(plugin->api);
  require(api&&api->abi_version==RD_TRANSLATION_ABI_V1&&api->struct_size==sizeof(*api)&&api->translate,"TRANSLATION_API_INVALID");
  std::vector<const char*>bank_pointers;for(const auto&b:banks)bank_pointers.push_back(b.c_str());
  RD_TranslationRequestV1 request{};request.abi_version=RD_TRANSLATION_ABI_V1;request.struct_size=sizeof(request);
  auto r=rom.u8string(),e=base.u8string(),o=out.u8string();
  request.rom_path=r.c_str();request.base_export=e.c_str();request.output_directory=o.c_str();
  request.bank_exports=bank_pointers.data();request.bank_count=uint32_t(banks.size());request.require_ghidra=require_ghidra?1:0;
  auto source_root_utf8=source_root.u8string();request.source_root=source_root_utf8.c_str();request.full_runtime_project=full?1:0;
  RD_TranslationResultV1 result{};result.struct_size=sizeof(result);
  int rc=0;
  if(!discovery_report.empty()){
   auto extension=reinterpret_cast<RD_TranslationRecoveryFnV1>(symbol(h,"rd_translation_recover_source_v1"));
   require(extension!=nullptr,"TRANSLATION_DISCOVERY_ABI_UNAVAILABLE");
   RD_TranslationRecoveryRequestV1 extended{};
   extended.abi_version=RD_TRANSLATION_ABI_V1;extended.struct_size=sizeof(extended);
   extended.base=request;
   auto report_path=fs::weakly_canonical(discovery_report).u8string();
   const auto cpu_path=fs::absolute(plugin_dir/(std::string("rd_cpu_z80")+EXT)).u8string();
   extended.source_discovery_json=report_path.c_str();extended.cpu_plugin_path=cpu_path.c_str();
   rc=extension(&extended,&result);
  }else rc=api->translate(&request,&result);
  require(rc==1&&result.abi_version==RD_TRANSLATION_ABI_V1&&result.emitted>0,
          "NATIVE_TRANSLATION_REJECTED: "+std::string(result.status));
  require(result.source_sha256==sha(rom),"ROM_CHANGED_DURING_TRANSLATION");
  std::cout<<"RECOMPDEV_NATIVE_TRANSLATION_EMITTED="<<result.emitted<<"\n"
   <<"RECOMPDEV_NATIVE_TRANSLATION_REJECTED="<<result.rejected<<"\n"
   <<"RECOMPDEV_NATIVE_TRANSLATION_MANIFEST="<<(out/"translation-manifest.json").string()<<"\n";
  if(compile&&!full){
   // Write a narrowly scoped CMake project outside Git. All native lowering
   // happened in the DLL; CMake only compiles the generated translation unit.
   std::ofstream cmake(out/"CMakeLists.txt",std::ios::binary);
   cmake<<"cmake_minimum_required(VERSION 3.17)\nproject(RecompDevNativePcode LANGUAGES CXX)\n"
     <<"set(CMAKE_CXX_STANDARD 17)\nadd_library(rd_game_pcode SHARED rd_game_pcode.cpp)\n"
     <<"target_include_directories(rd_game_pcode PRIVATE \"${RECOMPDEV_SOURCE_ROOT}/harness/include\" \"${RECOMPDEV_SOURCE_ROOT}/runtime_sms/templates\")\n"
     <<"set_target_properties(rd_game_pcode PROPERTIES PREFIX \"\" LIBRARY_OUTPUT_DIRECTORY \"${CMAKE_BINARY_DIR}/bin\" RUNTIME_OUTPUT_DIRECTORY \"${CMAKE_BINARY_DIR}/bin\")\n";
   cmake.close();
   auto build=out/"build";
   int conf=process({"cmake","-S",out,"-B",build,"-DRECOMPDEV_SOURCE_ROOT="+source_root.string(),"-DCMAKE_BUILD_TYPE=Release"});
   require(conf==0,"NATIVE_GAME_CMAKE_CONFIGURATION_FAILED");
   int rcbuild=process({"cmake","--build",build,"--config","Release","--parallel","2"});
   require(rcbuild==0,"NATIVE_GAME_COMPILATION_FAILED");
   fs::path artifact;
   for(auto candidate:{build/"bin"/"Release"/(std::string("rd_game_pcode")+EXT),
                       build/"bin"/(std::string("rd_game_pcode")+EXT)})if(fs::is_regular_file(candidate)){artifact=candidate;break;}
   require(!artifact.empty(),"COMPILED_NATIVE_GAME_DLL_MISSING");
   fs::create_directories(out/"runtime");
   fs::copy_file(artifact,out/"runtime"/artifact.filename());
   // Source-selected shared plugins are copied to a separate test layout;
   // never overwrite an owner's active DLLs. No ROM bytes are copied.
   for(const auto& name:{"rd_cpu_z80","rd_machine_sms","rd_discovery_jsonl","rd_display_ppm","rd_audio_wav","rd_input_fixed"}){
    auto f=plugin_dir/(std::string(name)+EXT);require(fs::is_regular_file(f),"REQUIRED_RUNTIME_PLUGIN_MISSING "+std::string(name));
    fs::copy_file(f,out/"runtime"/f.filename());
   }
   std::cout<<"RECOMPDEV_NATIVE_GAME_DLL="<<artifact.string()<<"\n"
    <<"RECOMPDEV_ISOLATED_RUNTIME="<<(out/"runtime").string()<<"\n";
  }
  if(compile&&full){
   auto build=out/"build";
   int conf=process({"cmake","-S",out,"-B",build,"-DCMAKE_BUILD_TYPE=Release",
       "-DRECOMPDEV_SOURCE_ROOT="+source_root.string()});
   require(conf==0,"PRESERVED_FULL_CMAKE_CONFIGURATION_FAILED");
   int built=process({"cmake","--build",build,"--config","Release","--parallel","2"});
   require(built==0,"PRESERVED_FULL_NATIVE_COMPILATION_FAILED");
   auto locate=[&](const std::string&name){
    for(auto candidate:{build/"Release"/(name+".exe"),build/(name+".exe"),build/"Release"/name,build/name})
     if(fs::is_regular_file(candidate))return candidate;
    throw std::runtime_error("FULL_NATIVE_BINARY_MISSING: "+name);
   };
   const auto pilot=locate("RecompDevNativePilot"),application=locate("RecompDevNativeApp");
   std::cout<<"RECOMPDEV_PRESERVED_NATIVE_PILOT="<<pilot.string()<<"\n"
     <<"RECOMPDEV_PRESERVED_NATIVE_APP="<<application.string()<<"\n";
  }
  close(h);return 0;
 }catch(...){close(h);throw;}
}
