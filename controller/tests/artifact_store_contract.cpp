#include "artifact_store.hpp"
#include "rd_sha256.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
namespace fs=std::filesystem;
static void check(bool b,const char*s){if(!b)throw std::runtime_error(s);}
static void write(const fs::path& p,const std::string& text){fs::create_directories(p.parent_path());std::ofstream out(p,std::ios::binary);out<<text;check(bool(out),"fixture write failed");}
static std::string digest(const std::string& s){return rdhash::sha256(reinterpret_cast<const uint8_t*>(s.data()),s.size());}
static std::string fake_analysis(const std::string&rom,const std::string&arch,const std::string&platform){
 const auto gh=std::string("{\"source-sha\":\"fixture\"}");
 return "{\"schema\":\"recompdev.analysis.providers.v1\",\"architecture\":\""+arch+"\",\"platform\":\""+platform+
  "\",\"cache_contract\":{\"source_sha256\":\""+rom+"\",\"tools\":{}},\"ghidra_export_sha256\":\""+digest(gh)+"\"}";
}
static std::string fake_report(const std::string&rom,const std::string&arch,const std::string&platform,int emitted){
 return "{\"schema\":\"recompdev.native.orchestrator.v1\",\"status\":\"MAX_RECOVERY_ROUNDS_REACHED\",\"source_sha256\":\""+rom+"\",\"analysis\":"+fake_analysis(rom,arch,platform)+",\"rounds\":[{\"frames\":89,\"emitted\":"+std::to_string(emitted)+"}]}";
}

int main(int argc,char**argv){
 if(argc==5&&std::string(argv[1])=="--promote"){
   try{
     const auto digest=rdartifact::promote(argv[4],argv[2],argv[3]);
     if(!digest){std::cerr<<"NO_PORTABLE_CAPSULE\n";return 2;}
     auto result=rdartifact::best(argv[4],argv[3]);
     if(!result||result->digest!=*digest)return 2;
     std::cout<<result->session.u8string()<<"\n";return 0;
   }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 2;}
 }
 auto temp=fs::temp_directory_path()/"recompdev-artifacts-025-contract";fs::remove_all(temp);
 try{
  const auto store=temp/"portable"/"artifact-store"/"v1";
  // The generic object ABI is not aware of CPU, console, or file format.
  auto z=rdartifact::put(store,"instruction-semantics","cpu.z80","host.x86_64","semantics.v1","CPUSPEC");
  auto m=rdartifact::put(store,"instruction-semantics","cpu.mips-r3000","host.arm64","semantics.v1","CPUSPEC");
  auto n=rdartifact::put(store,"native-object","cpu.68000","host.x86_64","win64.msvc","some ELF-independent data");
  check(z.digest==m.digest,"identical bytes did not deduplicate");
  check(rdartifact::get(store,z)=="CPUSPEC"&&rdartifact::get(store,m)=="CPUSPEC","different producers collide");
  check(rdartifact::get(store,n)=="some ELF-independent data","binary object corrupt");
  const auto sha=digest("ROM-UNIQUE"),other=digest("ROM-DIFFERENT");
  const auto original=temp/"evidence"/"jobs"/"job-a"/"sessions"/"cycle-05";
  const auto report=fake_report(sha,"mips-r3000","playstation-one",1856);
  write(original/"orchestration.json",report);
  write(original/"analysis"/"provider-manifest.json",fake_analysis(sha,"mips-r3000","playstation-one"));
  write(original/"analysis"/"ghidra-functions.json","{\"source-sha\":\"fixture\"}");
  auto hash=rdartifact::promote(store,original,sha);
  check(hash.has_value()&&hash->size()==64,"portable promotion failed");
  // A second CPU/platform and source object must coexist in one store.
  const auto second=temp/"evidence"/"jobs"/"job-b"/"sessions"/"cycle-01";
  write(second/"orchestration.json",fake_report(other,"68000","megadrive",250));
  write(second/"analysis"/"provider-manifest.json",fake_analysis(other,"68000","megadrive"));
  write(second/"analysis"/"ghidra-functions.json","{\"source-sha\":\"fixture\"}");
  check(rdartifact::promote(store,second,other).has_value(),"second architecture rejected");
  // Original reports can disappear; portable records have independent bytes.
  fs::remove_all(temp/"evidence");
  auto hit=rdartifact::best(store,sha);
  check(hit&&hit->emitted==1856&&hit->frames==89&&hit->architecture=="mips-r3000"&&hit->platform=="playstation-one","source/architecture indexed incorrectly");
  check(fs::is_regular_file(hit->session/"orchestration.json")&&fs::is_regular_file(hit->session/"analysis"/"ghidra-functions.json"),"portable materialisation missing actual payload");
  auto unrelated=rdartifact::best(store,other);
  check(unrelated&&unrelated->architecture=="68000"&&unrelated->emitted==250,"other architecture lost");
  check(!rdartifact::best(store,digest("unseen")),"foreign ROM unexpectedly hit");
  // Detect altered published material instead of silently treating it as cache.
  write(hit->session/"orchestration.json","tampered");
  bool caught=false;try{(void)rdartifact::best(store,sha);}catch(const std::exception&){caught=true;}
  check(caught,"changed materialised artifact was trusted");
  fs::remove_all(temp);
  std::cout<<"PASS: CPU/hardware-independent content-addressed artifacts, portable capsule, source isolation and tamper rejection\n";
  return 0;
 }catch(const std::exception& e){std::cerr<<"FAIL: "<<e.what()<<"\n";fs::remove_all(temp);return 1;}
}
