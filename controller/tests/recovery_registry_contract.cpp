#include "recovery_registry.hpp"
#include "rd_sha256.hpp"
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string>
#include <iostream>
namespace fs=std::filesystem;
static void require(bool pass,const char*what){if(!pass)throw std::runtime_error(what);}
static void put(const fs::path& p,const std::string&v){fs::create_directories(p.parent_path());std::ofstream f(p,std::ios::binary);f<<v;}
static std::string digest(const std::string&v){return rdhash::sha256((const uint8_t*)v.data(),v.size());}
static std::string report(const std::string&sha,int emitted,int frames){
 return "{\"schema\":\"recompdev.native.orchestrator.v1\",\"source_sha256\":\""+sha+"\",\"status\":\"MAX_RECOVERY_ROUNDS_REACHED\",\"rounds\":[{\"emitted\":"+std::to_string(emitted)+",\"frames\":"+std::to_string(frames)+"}]}";
}
int main(){
 try{
  auto root=fs::temp_directory_path()/"recompdev-registry-contract-024";fs::remove_all(root);fs::create_directories(root);
  auto sha=digest("ROM-A"),other=digest("ROM-B");
  auto s1=root/"v0.4.9.23"/"jobs"/"job-a"/"sessions"/"cycle-01";
  auto s2=root/"v0.4.9.23"/"jobs"/"job-a"/"sessions"/"cycle-02";
  put(s1/"orchestration.json",report(sha,1300,66));put(s2/"orchestration.json",report(sha,1500,89));
  put(s1.parent_path().parent_path()/"job.json","{\"schema\":\"recompdev.controller.job.v1\",\"rom_sha256\":\""+sha+"\"}");
  require(!rdregistry::find(root,other).has_value(),"source isolation failed");
  auto old=rdregistry::find(root,sha);
  require(old&&old->session==fs::canonical(s2)&&old->emitted==1500,"v23 automatic discovery failed");
  rdregistry::remember(root,sha,s2,"job-auto-v23",2);
  require(fs::is_regular_file(root/"translation-registry"/"v1"/sha/"job-auto-v23-cycle-2.json"),"no immutable index");
  auto hit=rdregistry::find(root,sha);require(hit&&hit->session==old->session,"indexed lookup differed");
  // An attacker or disk corruption must invalidate the index rather than
  // silently dispatch a different native translation.
  put(s2/"orchestration.json",report(sha,1501,89));bool refused=false;
  try{(void)rdregistry::find(root,sha);}catch(const std::exception&){refused=true;}
  require(refused,"corrupt report re-used without detecting altered SHA");
  bool wrong=false;try{rdregistry::remember(root,other,s1,"job-other",1);}catch(const std::exception&){wrong=true;}
  require(wrong,"cross-ROM index entry accepted");
  fs::remove_all(root);
  std::cout<<"PASS: CPU-neutral immutable cross-version recovery registry and tamper detection\n";
  return 0;
 }catch(const std::exception&e){std::cerr<<"FAIL: "<<e.what()<<"\n";return 1;}
}
