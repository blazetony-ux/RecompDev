#pragma once
// Generic, opt-in native -> controller diagnostics v1 event producer.
// CPU adapters publish address/register metadata; neither this publisher nor
// controller knows instruction encodings. No game-specific addresses, parsing,
// gameplay changes, DLL dependencies, sockets or GUI calls.
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <string>
#include <stdexcept>

namespace rd_execution_events {
class Publisher final {
 std::ofstream out_;
 std::uint64_t emitted_=0, every_=256;
 std::uint64_t last_buttons_=~std::uint64_t{0};
 bool enabled_=false, limit_reported_=false;
 Publisher(){
  const char* path=std::getenv("RECOMPDEV_CONTROLLER_DIAGNOSTIC_EVENTS");
  if(!path || !*path) return;
  const char* interval=std::getenv("RECOMPDEV_MONITOR_SAMPLE_EVERY");
  if(interval && *interval){
   char* end=nullptr;
   const auto n=std::strtoull(interval,&end,10);
   if(end && !*end && n>=1 && n<=65536) every_=n;
  }
  out_.open(path,std::ios::binary|std::ios::trunc);
  if(!out_)throw std::runtime_error("CONTROLLER_DIAGNOSTIC_TRACE_OPEN_FAILED");
  enabled_=true;
 }
 bool begin(){
  if(!enabled_ || limit_reported_)return false;
  if(emitted_>=200000){
   limit_reported_=true;
   out_<<"{\"type\":\"notice\",\"message\":\"Controller telemetry event limit reached\"}\n";
   out_.flush();return false;
  }
  ++emitted_;return true;
 }
 public:
 Publisher(const Publisher&)=delete;
 Publisher& operator=(const Publisher&)=delete;
 static Publisher& instance(){static Publisher p;return p;}
 void transition(const char* cpu,std::uint64_t step,std::uint64_t cycle,std::uint64_t frame,
   std::uint32_t pc,std::uint32_t next_pc,std::uint32_t sp,std::uint32_t physical,
   std::uint32_t opcode,const char* opcode_class,const char* kind){
  if(!enabled_)return;
  const bool blocked = std::string(kind).find("blocked")!=std::string::npos ||
                       std::string(kind)=="untranslated_code";
  if(blocked){
   if(begin()){
    out_<<"{\"type\":\"stop\",\"status\":\""<<kind
        <<"\",\"cpu\":\""<<cpu<<"\",\"pc\":"<<next_pc
        <<",\"physical_offset\":"<<physical<<",\"frame\":"<<frame
        <<",\"guest_cycles\":"<<cycle<<",\"steps\":"<<step<<"}\n";
    out_.flush();
   }
  }
  if(step % every_ != 0 && !blocked)return;
  if(!begin())return;
  out_<<"{\"type\":\"instruction\",\"cpu\":\""<<cpu
      <<"\",\"pc\":"<<pc<<",\"next_pc\":"<<next_pc
      <<",\"sp\":"<<sp<<",\"physical_offset\":"<<physical
      <<",\"opcode\":"<<opcode<<",\"opcode_class\":\""<<opcode_class
      <<"\",\"guest_cycles\":"<<cycle<<",\"frame\":"<<frame
      <<",\"steps\":"<<step<<"}\n";
  out_.flush();
  if(!out_)throw std::runtime_error("CONTROLLER_DIAGNOSTIC_TRACE_WRITE_FAILED");
 }
 void frame(std::uint64_t frame,std::uint64_t cycle,std::uint64_t steps){
  if(!begin())return;
  out_<<"{\"type\":\"frame\",\"frame\":"<<frame
      <<",\"guest_cycles\":"<<cycle<<",\"steps\":"<<steps<<"}\n";
  out_.flush();
 }
 void input(std::uint64_t cycle,std::uint64_t buttons){
  if(!enabled_ || buttons==last_buttons_)return;
  last_buttons_=buttons;
  if(!begin())return;
  out_<<"{\"type\":\"input\",\"guest_cycles\":"<<cycle
      <<",\"buttons\":"<<buttons<<"}\n";
  out_.flush();
 }
};
inline void transition(const char* cpu,std::uint64_t step,std::uint64_t cycle,std::uint64_t frame,
 std::uint32_t pc,std::uint32_t next_pc,std::uint32_t sp,std::uint32_t physical,
 std::uint32_t opcode,const char* opcode_class,const char* kind){
 Publisher::instance().transition(cpu,step,cycle,frame,pc,next_pc,sp,physical,opcode,opcode_class,kind);
}
inline void frame(std::uint64_t f,std::uint64_t c,std::uint64_t s){Publisher::instance().frame(f,c,s);}
inline void input(std::uint64_t c,std::uint64_t b){Publisher::instance().input(c,b);}
}
