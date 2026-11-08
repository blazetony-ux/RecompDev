#include "native_job.hpp"
#include "rd_sha256.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include <algorithm>
#include <functional>
#include <cstdlib>
namespace fs=std::filesystem;
static void require(bool x,const char*message){if(!x)throw std::runtime_error(message);}
static std::string read(const fs::path&p){std::ifstream in(p);return std::string(std::istreambuf_iterator<char>(in),{});}
static std::string q(const std::string&s){std::string out="\"";for(char c:s){if(c=='\\'||c=='\"')out+='\\';out+=c;}return out+'"';}
static int go(const std::vector<std::string>&a,const fs::path&source,const fs::path&exe,
   const std::function<int(const std::vector<std::string>&)>&mock){return rd_native_job(a,source,exe,mock);}
static void put(const fs::path&p,const std::string&s){std::ofstream o(p,std::ios::binary);o<<s;o.close();}
int main(int argc,char**argv){
 try{
  require(argc==3,"missing test source and binary arguments");
  auto source=fs::canonical(argv[1]);auto exe=fs::canonical(argv[2]);
  auto tmp=fs::temp_directory_path()/("recompdev-job-contract-"+std::to_string(std::hash<std::string>{}(fs::current_path().string()+std::string(argv[2]))));
  fs::remove_all(tmp);fs::create_directories(tmp);auto home=tmp/"state";
#ifdef _WIN32
  _putenv_s("RECOMPDEV_HOME",home.string().c_str());
#else
  setenv("RECOMPDEV_HOME",home.string().c_str(),1);
#endif
  auto tool_root=tmp/"tools";fs::create_directories(tool_root);
  auto gh=tool_root/"headless-tool";auto rz=tool_root/"rizin-tool";put(gh,"fake");put(rz,"fake");
  std::function<int(const std::vector<std::string>&)> unexpected=[](auto const&)->int{throw std::runtime_error("unexpected provider invocation");};
  require(go({"configure","--ghidra",gh.string(),"--rizin",rz.string(),"--workspace",(tmp/"workspace").string()},source,exe,unexpected)==0,"configure failed");
  auto cfg=read(home/"config.json");require(cfg.find("recompdev.controller.config.v1")!=std::string::npos,"missing config schema");
  auto rom=tmp/"first.sms";std::string b(32768,'\0');b[0]='\x76';b.replace(0x7ff0,8,"TMR SEGA");put(rom,b);
  std::string digest=rdhash::sha256((const uint8_t*)b.data(),b.size());
  int invocations=0;std::vector<fs::path> prior;auto bridge=[&](const std::vector<std::string>&args)->int{
     if(args.size()>1&&args[1]=="job-diagnostics")return 0;
     ++invocations;
     auto value=[&](std::string key)->std::string{for(size_t i=0;i+1<args.size();i++)if(args[i]==key)return args[i+1];return "";};
     require(value("--stage")=="native-orchestrate","wrong provider stage");
     auto out=fs::path(value("--out"));require(!out.empty(),"missing output");
     require(value("--rom")==rom.string(),"source path changed");
     if(invocations==1)require(value("--resume-from").empty(),"initial cycle had prior evidence");
     else require(value("--resume-from")==prior.back().string(),"resume history chain failed");
     prior.push_back(out);fs::create_directories(out);
     int frames=invocations==1?10:invocations==2?50:100;
     std::string result="{\"source_sha256\":"+q(digest)+",\"status\":"+q(invocations==3?"FRAME_BUDGET_REACHED_PARITY_UNVERIFIED":"MAX_RECOVERY_ROUNDS_REACHED")+
     ",\"rounds\":[{\"frames\":"+std::to_string(frames)+",\"emitted\":"+std::to_string(1000+invocations*10)+"}]}";
     put(out/"orchestration.json",result);return invocations==3?0:2;
  };
  require(go({"run","--rom",rom.string(),"--max-cycles","3","--rounds-per-cycle","2","--target-frames","100","--logging","warning"},source,exe,bridge)==0,"autonomous native scheduling failed");
  require(invocations==3,"expected three controller-scheduled calls");
  auto job_id=read(home/"last-job.txt");while(!job_id.empty()&&(job_id.back()=='\n'||job_id.back()=='\r'))job_id.pop_back();
  auto job_dir=(tmp/"workspace"/"v0.4.9.22"/"jobs")/job_id;auto job=read(job_dir/"job.json");
  require(job.find("TARGET_REACHED_PARITY_UNVERIFIED")!=std::string::npos,"not parity-unverified");
  require(job.find("\"cycle\":3")!=std::string::npos,"third cycle not committed");
  require(read(job_dir/"events.jsonl").find("AUTO_RESUME")!=std::string::npos,"missing controller automatic resume events");
  require(go({"status","--job",job_id},source,exe,unexpected)==0,"status failed");
  require(go({"inspect","--job",job_id,"--logging","debug"},source,exe,unexpected)==0,"inspect failed");
  int previews=0;
  auto preview_bridge=[&](const std::vector<std::string>&args)->int{
     ++previews;
     auto val=[&](const std::string&key)->std::string{for(size_t i=0;i+1<args.size();++i)if(args[i]==key)return args[i+1];return "";};
     require(val("--stage")=="job-preview","wrong preview provider selected");
     require(val("--job-dir")==job_dir.string(),"preview must use immutable existing job");
     require(val("--out-dir")==((tmp/"workspace"/"v0.4.9.22")/"preview").string(),"preview output outside evidence root");
     require(val("--diagnostics-dir")==((tmp/"workspace"/"v0.4.9.22")/"diagnostics").string(),"preview diagnostic root wrong");
     require(val("--sample-every")=="64","preview sampling option lost");
     require(val("--video")=="capture"&&val("--input")=="neutral","preview backend option lost");
     return 0;
  };
  require(go({"preview","--job",job_id,"--video","capture","--input","neutral","--monitor-every","64","--no-viewer"},source,exe,preview_bridge)==0,"preview dispatch failed");
  require(previews==1,"preview provider invoked wrong number of times");
  auto watch_preview=[&](const std::vector<std::string>&args)->int{
     ++previews;
     auto val=[&](const std::string&key)->std::string{for(size_t i=0;i+1<args.size();++i)if(args[i]==key)return args[i+1];return "";};
     require(val("--stage")=="job-preview","watch preview stage missing");
     require(val("--monitor-pc")=="3035","hex watch not normalized");
     require(val("--monitor-pc-range")=="3032:3044","range not normalized");
     require(std::find(args.begin(),args.end(),"--monitor-matched-only")!=args.end(),"matched-only not forwarded");
     return 0;
  };
  require(go({"preview","--job",job_id,"--no-viewer","--monitor-pc","0x0BDB",
       "--monitor-pc-range","0x0BD8:0x0BE4","--monitor-matched-only"},source,exe,watch_preview)==0,
       "controller PC/range watch dispatch failed");
  require(previews==2,"expected ordinary and watched previews");
  require(go({"preview","--job",job_id,"--monitor-pc","0x100000000"},source,exe,unexpected)==2,"oversized address accepted");
  require(go({"preview","--job",job_id,"--monitor-pc-range","0x200:0x100"},source,exe,unexpected)==2,"reversed address range accepted");
  require(go({"status","--job",job_id,"--monitor-pc","0x0BDB"},source,exe,unexpected)==2,"monitor watch leaked into status");
  require(go({"preview","--job",job_id,"--video","capture","--input","live"},source,exe,unexpected)==2,"live input without window accepted");
  require(read(job_dir/"job.json")==job,"preview mutated recovery job state");
  require(go({"resume","--job",job_id},source,exe,unexpected)==2,"complete job should reject further runs");
  require(go({"run","--rom",rom.string(),"--logging","trace"},source,exe,unexpected)==2,"unknown logging level accepted");
  require(go({"run","--rom",rom.string(),"--max-cycles","0"},source,exe,unexpected)==2,"invalid bounds accepted");
  require(go({"status","--job","../bad"},source,exe,unexpected)==2,"invalid job traversal accepted");
  auto bad_rom=tmp/"changed.sms";put(bad_rom,b);int only=0;
  auto stopped=[&](const std::vector<std::string>&args)->int{
      if(args.size()>1&&args[1]=="job-diagnostics")return 0;
      ++only;auto it=std::find(args.begin(),args.end(),"--out");require(it!=args.end()&&++it!=args.end(),"missing out");
      fs::path out=*it;fs::create_directories(out);put(out/"orchestration.json","{\"source_sha256\":"+q(digest)+",\"status\":\"MAX_RECOVERY_ROUNDS_REACHED\",\"rounds\":[{\"frames\":1,\"emitted\":1}]}");return 2;
  };
  require(go({"run","--rom",bad_rom.string(),"--max-cycles","1"},source,exe,stopped)==2,"one-cycle test should reach limit");
  auto blocked_job=read(home/"last-job.txt");while(!blocked_job.empty()&&(blocked_job.back()=='\r'||blocked_job.back()=='\n'))blocked_job.pop_back();
  put(bad_rom,b+"tampered");
  require(go({"resume","--job",blocked_job,"--max-cycles","2"},source,exe,stopped)==2,"modified ROM accepted");
  require(only==1,"provider was called after source identity changed");
  auto import_root=tmp/"attested-prior";fs::create_directories(import_root);
  put(import_root/"orchestration.json","{\"schema\":\"recompdev.native.orchestrator.v1\",\"source_sha256\":"+q(digest)+",\"rounds\":[{\"round\":1}]}");
  int imported_calls=0;
  auto import_bridge=[&](const std::vector<std::string>&args)->int{
      if(args.size()>1&&args[1]=="job-diagnostics")return 0;
      ++imported_calls;auto val=[&](const std::string&key){for(size_t i=0;i+1<args.size();++i)if(args[i]==key)return args[i+1];return std::string();};
      require(val("--resume-from")==import_root.string(),"external verified history was not passed into first cycle");
      fs::path out=val("--out");fs::create_directories(out);
      put(out/"orchestration.json","{\"source_sha256\":"+q(digest)+",\"status\":\"MAX_RECOVERY_ROUNDS_REACHED\",\"rounds\":[{\"frames\":77,\"emitted\":1200}]}");
      return 2;
  };
  require(go({"run","--rom",rom.string(),"--import-history",import_root.string(),"--max-cycles","1"},source,exe,import_bridge)==2,"import job did not stop at bounded limit");
  require(imported_calls==1,"wrong number of imported-history calls");
  put(import_root/"orchestration.json","{\"schema\":\"recompdev.native.orchestrator.v1\",\"source_sha256\":\"invalid\"}");
  require(go({"run","--rom",rom.string(),"--import-history",import_root.string()},source,exe,unexpected)==2,"wrong-source history accepted");
  int stale_calls=0;
  auto stagnant=[&](const std::vector<std::string>&args)->int{
      if(args.size()>1&&args[1]=="job-diagnostics")return 0;
      ++stale_calls;auto it=std::find(args.begin(),args.end(),"--out");require(it!=args.end()&&++it!=args.end(),"missing out");
      fs::path out=*it;fs::create_directories(out);
      int frames=stale_calls==1?100:stale_calls==2?90:95;
      int emitted=stale_calls==1?1000:stale_calls==2?900:950;
      put(out/"orchestration.json","{\"source_sha256\":"+q(digest)+",\"status\":\"MAX_RECOVERY_ROUNDS_REACHED\",\"rounds\":[{\"frames\":"+std::to_string(frames)+",\"emitted\":"+std::to_string(emitted)+"}]}");
      return 2;
  };
  require(go({"run","--rom",rom.string(),"--max-cycles","5"},source,exe,stagnant)==2,"stagnation should block");
  require(stale_calls==3,"stagnation was not measured against all-time high watermark");
  auto stagnant_id=read(home/"last-job.txt");while(!stagnant_id.empty()&&(stagnant_id.back()=='\n'||stagnant_id.back()=='\r'))stagnant_id.pop_back();
  require(read((tmp/"workspace"/"v0.4.9.22"/"jobs")/stagnant_id/"job.json").find("BLOCKED_STAGNATION")!=std::string::npos,"stagnation status not persisted");
  // v0.4.9.22: preview handoff must be explicitly requested and source-attested
  // BEFORE a recovery job is mutated; no implicit preview-to-job writes.
  int bounded=0;
  auto incomplete=[&](const std::vector<std::string>&args)->int{
      if(args.size()>1&&args[1]=="job-diagnostics")return 0;
      ++bounded;auto it=std::find(args.begin(),args.end(),"--out");require(it!=args.end()&&++it!=args.end(),"missing output");
      fs::path out=*it;fs::create_directories(out);
      put(out/"orchestration.json","{\"source_sha256\":"+q(digest)+",\"status\":\"MAX_RECOVERY_ROUNDS_REACHED\",\"rounds\":[{\"frames\":18,\"emitted\":1800}]}");
      return 2;
  };
  require(go({"run","--rom",rom.string(),"--max-cycles","1"},source,exe,incomplete)==2,"preview handoff fixture not bounded");
  auto preview_job=read(home/"last-job.txt");while(!preview_job.empty()&&(preview_job.back()=='\n'||preview_job.back()=='\r'))preview_job.pop_back();
  auto preview_jdir=(tmp/"workspace"/"v0.4.9.22"/"jobs")/preview_job;
  auto unchanged=read(preview_jdir/"job.json");
  auto zip=tmp/"preview-check.zip";put(zip,"fake archived fixture");
  int probes=0,scheduled=0;
  auto preview_verified=[&](const std::vector<std::string>&args)->int{
      auto val=[&](const std::string&key){for(size_t i=0;i+1<args.size();++i)if(args[i]==key)return args[i+1];return std::string();};
      if(val("--stage")=="preview-verify"){
         ++probes;require(val("--job-id")==preview_job,"preview provenance job not forwarded");
         require(val("--resume-from")==((preview_jdir/"sessions")/"cycle-01").string(),"preview source cycle changed");
         return probes==1?2:0;
      }
      if(val("--stage")=="job-diagnostics")return 0;
      require(val("--stage")=="native-orchestrate","wrong resume provider");
      ++scheduled;require(val("--preview-stop")==zip.string(),"missing explicitly verified preview seed");
      require(val("--preview-job-id")==preview_job,"preview job identity not forwarded to analyzer");
      fs::path out=val("--out");fs::create_directories(out);
      put(out/"orchestration.json","{\"source_sha256\":"+q(digest)+",\"status\":\"MAX_RECOVERY_ROUNDS_REACHED\",\"rounds\":[{\"frames\":19,\"emitted\":1801}]}");
      return 2;
  };
  require(go({"resume","--job",preview_job,"--max-cycles","2","--preview-stop",zip.string()},source,exe,preview_verified)==2,
          "invalid preview did not fail closed");
  require(read(preview_jdir/"job.json")==unchanged,"rejected preview changed recovery job");
  require(scheduled==0,"unverified preview reached native translator");
  require(go({"resume","--job",preview_job,"--max-cycles","2","--preview-stop",zip.string()},source,exe,preview_verified)==2,
          "valid preflight dispatch did not reach bounded recovery");
  require(probes==2&&scheduled==1,"preview was executed without attestation");
  require(go({"preview","--job",preview_job,"--preview-stop",zip.string()},source,exe,unexpected)==2,
          "preview-stop unexpectedly accepted by non-resume command");
  // v0.4.9.22: actual compiled scheduler must cross cycle 16 and create
  // a source-checked cycle-20 path without switching plugin directories.
  int extended_calls=0;
  auto extended=[&](const std::vector<std::string>&args)->int{
      if(args.size()>1&&args[1]=="job-diagnostics")return 0;
      ++extended_calls;
      auto val=[&](const std::string&key){for(size_t k=0;k+1<args.size();++k)if(args[k]==key)return args[k+1];return std::string();};
      fs::path out=val("--out");require(!out.empty(),"extended session missing output");fs::create_directories(out);
      put(out/"orchestration.json","{\"source_sha256\":"+q(digest)+",\"status\":\"MAX_RECOVERY_ROUNDS_REACHED\",\"rounds\":[{\"frames\":"+std::to_string(extended_calls)+",\"emitted\":"+std::to_string(2000+extended_calls)+"}]}");
      return 2;
  };
  require(go({"run","--rom",rom.string(),"--max-cycles","20","--rounds-per-cycle","1"},source,exe,extended)==2,
          "new controller could not extend beyond sixteen automatic cycles");
  require(extended_calls==20,"new controller interrupted before cycle 20");
  auto long_id=read(home/"last-job.txt");while(!long_id.empty()&&(long_id.back()=='\n'||long_id.back()=='\r'))long_id.pop_back();
  auto long_dir=tmp/"workspace"/"v0.4.9.22"/"jobs"/long_id;
  require(fs::is_regular_file(long_dir/"sessions"/"cycle-20"/"orchestration.json"),"cycle 20 evidence missing");
  require(read(long_dir/"job.json").find("\"cycle\":20")!=std::string::npos,"cycle 20 ledger entry missing");
  fs::remove_all(tmp);
  std::cout<<"PASS: compiled controller job scheduling, logging, immutable sessions and identity gates\n";
  return 0;
 }catch(const std::exception&e){std::cerr<<"FAIL: "<<e.what()<<"\n";return 1;}
}
