#pragma once
// Generic, opt-in native -> controller diagnostics v1 event producer.
// CPU adapters publish address/register metadata; neither this publisher nor
// controller knows instruction encodings. No game-specific addresses, parsing,
// gameplay changes, DLL dependencies, sockets or GUI calls.
#include <cstdint>
#include <algorithm>
#include <cstring>
#include <vector>
#include <utility>
#include <limits>
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
 std::vector<std::uint32_t> watch_pc_;
 std::vector<std::pair<std::uint32_t,std::uint32_t>> watch_range_;
 std::uint64_t watch_hits_=0;
 static bool parse_address(const std::string& value,std::uint32_t& n){
  if(value.empty()||value.size()>10)return false;
  for(char c:value)if(c<'0'||c>'9')return false;
  char* end=nullptr; const auto x=std::strtoull(value.c_str(),&end,10);
  if(!end||*end||x>std::numeric_limits<std::uint32_t>::max())return false;
  n=static_cast<std::uint32_t>(x);return true;
 }
 void parse_watch(){
  // The controller validates all supplied watches; this bounded, neutral
  // adapter treats unexpected environment values as configuration errors.
  if(const char* env=std::getenv("RECOMPDEV_MONITOR_WATCH_PC")){
   const std::string csv(env);if(csv.size()>512)throw std::runtime_error("MONITOR_PC_CONFIG_TOO_LONG");
   std::size_t start=0;
   while(start<csv.size()){
    auto end=csv.find(',',start);if(end==std::string::npos)end=csv.size();
    std::uint32_t n=0;if(!parse_address(csv.substr(start,end-start),n)||watch_pc_.size()>=16)
     throw std::runtime_error("MONITOR_PC_CONFIG_INVALID");
    watch_pc_.push_back(n);start=end+1;
   }
  }
  if(const char* env=std::getenv("RECOMPDEV_MONITOR_WATCH_PC_RANGE")){
   const std::string csv(env);if(csv.size()>512)throw std::runtime_error("MONITOR_RANGE_CONFIG_TOO_LONG");
   std::size_t start=0;
   while(start<csv.size()){
    auto end=csv.find(',',start);if(end==std::string::npos)end=csv.size();
    auto pair=csv.substr(start,end-start);auto sep=pair.find(':');
    std::uint32_t lo=0,hi=0;
    if(sep==std::string::npos||!parse_address(pair.substr(0,sep),lo)||
       !parse_address(pair.substr(sep+1),hi)||lo>hi||watch_range_.size()>=16)
     throw std::runtime_error("MONITOR_RANGE_CONFIG_INVALID");
    watch_range_.emplace_back(lo,hi);start=end+1;
   }
  }
 }
 bool hit(std::uint32_t pc)const{
  if(std::find(watch_pc_.begin(),watch_pc_.end(),pc)!=watch_pc_.end())return true;
  for(const auto& r:watch_range_)if(pc>=r.first&&pc<=r.second)return true;
  return false;
 }
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
  parse_watch();enabled_=true;
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
 // Explicitly seal the trace before a consumer reads or deletes it. This is
 // required on Windows, where an open file normally cannot be unlinked.
 // Idempotent; no further events can be published after finish().
 void finish(){
  enabled_=false;
  if(!out_.is_open())return;
  out_.flush();
  if(!out_)throw std::runtime_error("CONTROLLER_DIAGNOSTIC_TRACE_FLUSH_FAILED");
  out_.close();
  if(!out_)throw std::runtime_error("CONTROLLER_DIAGNOSTIC_TRACE_CLOSE_FAILED");
 }
 void transition(const char* cpu,std::uint64_t step,std::uint64_t cycle,std::uint64_t frame,
   std::uint32_t pc,std::uint32_t next_pc,std::uint32_t sp,std::uint32_t physical,
   std::uint32_t opcode,const char* opcode_class,const char* kind){
  if(!enabled_)return;
  const bool blocked = std::strstr(kind,"blocked")!=nullptr ||
                       std::strcmp(kind,"untranslated_code")==0;
  const bool watch_hit=hit(pc);
  if(blocked){
   if(begin()){
    out_<<"{\"type\":\"stop\",\"status\":\""<<kind
        <<"\",\"cpu\":\""<<cpu<<"\",\"pc\":"<<next_pc
        <<",\"physical_offset\":"<<physical<<",\"frame\":"<<frame
        <<",\"guest_cycles\":"<<cycle<<",\"steps\":"<<step<<"}\n";
    out_.flush();
   }
  }
  if(step % every_ != 0 && !blocked && !watch_hit)return;
  if(!begin())return;
  if(watch_hit)++watch_hits_;
  out_<<"{\"type\":\"instruction\",\"cpu\":\""<<cpu
      <<"\",\"pc\":"<<pc<<",\"next_pc\":"<<next_pc
      <<",\"sp\":"<<sp<<",\"physical_offset\":"<<physical
      <<",\"opcode\":"<<opcode<<",\"opcode_class\":\""<<opcode_class
      <<"\",\"guest_cycles\":"<<cycle<<",\"frame\":"<<frame
      <<",\"steps\":"<<step<<",\"watch_hit\":"<<(watch_hit?"true":"false")<<"}\n";
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
