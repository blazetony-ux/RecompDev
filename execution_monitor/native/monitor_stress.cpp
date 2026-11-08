#include "event_queue.hpp"
#include "monitor_model.hpp"
#include "rd_execution_events.hpp"
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
static void ok(bool b){if(!b)throw std::runtime_error("V22_MONITOR_STRESS_FAILURE");}
static void env(const char* key,const char* value){
#ifdef _WIN32
 if(_putenv_s(key,value))throw std::runtime_error("SETENV_FAILED");
#else
 if(setenv(key,value,1))throw std::runtime_error("SETENV_FAILED");
#endif
}
static int exercise_monitor(){
 rdmonitor::EventQueue queue;
 for(int i=0;i<50000;++i)queue.offer("event-"+std::to_string(i));
 ok(queue.waiting()==rdmonitor::EventQueue::limit);
 ok(queue.dropped()==50000-rdmonitor::EventQueue::limit);
 auto partial=queue.take(768);ok(partial.size()==768&&partial[0]=="event-41808");
 rdmonitor::State model;
 auto t0=std::chrono::steady_clock::now();
 for(int i=0;i<40000;++i){
  auto event="{\"schema\":\"recompdev.controller.diagnostics.v1\",\"type\":\"instruction\",\"cpu\":\"mips\",\"pc\":"+
   std::to_string(i%256)+",\"sp\":123,\"steps\":"+std::to_string(i)+
   ",\"guest_cycles\":555,\"opcode\":5,\"opcode_class\":\"LOAD\",\"next_pc\":128}";
  ok(model.ingest(event));
 }
 ok(model.lines.size()==rdmonitor::kHistoryLimit);
 ok(model.entries.size()==rdmonitor::kHistoryLimit);
 ok(rdmonitor::matches(model.entries.back(),"load",3));
 ok(rdmonitor::matches(model.entries.back(),"instruction",4));
 ok(!rdmonitor::matches(model.entries.back(),"",5));
 ok(rdmonitor::address_match("0xBDB","0x0BDB"));
 ok(rdmonitor::address_match("0xBDB","0x0BD8:0x0BE4"));
 ok(!rdmonitor::address_match("0x4F9E","0x0BD8:0x0BE4"));
 ok(!rdmonitor::matches(model.entries.back(),"RETURN",3));
 ok(model.ingest(R"({"schema":"recompdev.controller.diagnostics.v1","type":"native_result","status":"FRAME_BUDGET_REACHED","pc":300,"host_frame":1800,"guest_frame":1799})"));
 ok(model.cpu.find("Terminal PC: 0x12C")!=std::string::npos);
 ok(model.cpu.find("SP(last sample)")!=std::string::npos);
 // Captures all hits on explicitly watched addresses regardless of the
 // configured sampling stride; never references machine instruction encoding.
 auto path=std::filesystem::temp_directory_path()/("rd22-monitor-"+std::to_string(std::chrono::steady_clock::now().time_since_epoch().count())+".jsonl");
 env("RECOMPDEV_CONTROLLER_DIAGNOSTIC_EVENTS",path.string().c_str());
 env("RECOMPDEV_MONITOR_SAMPLE_EVERY","128");
 env("RECOMPDEV_MONITOR_WATCH_PC","5,17");
 env("RECOMPDEV_MONITOR_WATCH_PC_RANGE","70:72");
 for(std::uint64_t i=1;i<=256;++i){
  const unsigned pc=(i%100);
  rd_execution_events::transition("generic",i,i*4,0,pc,pc+1,400,pc,0,"BRANCH","normal");
 }
 // The static publisher otherwise holds the log open until process exit.
 // Linux allows unlinking an open file; Windows rejects it, so finalize first.
 rd_execution_events::Publisher::instance().finish();
 rd_execution_events::Publisher::instance().finish(); // idempotency contract
 std::ifstream file(path);ok(bool(file));
 int instructions=0,watched=0,sampled=0;
 std::string line;
 while(std::getline(file,line)){
  if(line.find("\"type\":\"instruction\"")==std::string::npos)continue;
  ++instructions;
  if(line.find("\"watch_hit\":true")!=std::string::npos)++watched;
  else ++sampled;
 }
 file.close();ok(std::filesystem::remove(path));
 // 2 sampled (128,256), plus 2-3 repeated watch hits per address/range.
 ok(watched>=12&&sampled==2&&instructions>sampled);
 auto elapsed=std::chrono::duration_cast<std::chrono::seconds>(std::chrono::steady_clock::now()-t0).count();
 ok(elapsed<20);
 std::cout<<"PASS: 50k-event bounded queue; 40k native-model ingestion; exact PC watch overrides sampling; terminal state\n";
 return 0;
}
int main(){
 try{return exercise_monitor();}
 catch(const std::exception& e){std::cerr<<"V22_MONITOR_STRESS_EXCEPTION: "<<e.what()<<"\n";return 2;}
 catch(...){std::cerr<<"V22_MONITOR_STRESS_UNKNOWN_EXCEPTION\n";return 3;}
}
