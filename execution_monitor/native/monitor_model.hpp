#pragma once
// CPU/machine-neutral, read-only diagnostics event projection, shared by
// a native Win32 subscriber and cross-platform contract tests.
#include "rd_tiny_json.hpp"
#include <cstdint>
#include <deque>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>

namespace rdmonitor {
constexpr const char* kSchema="recompdev.controller.diagnostics.v1";
constexpr std::size_t kMaxLine=4096;
inline std::string field(const rdjson::V& e,const char* key,const char* fallback="?"){
 const auto& x=e.get(key);return x.t==rdjson::V::String?x.s:fallback;
}
inline std::string number(const rdjson::V& e,const char* key){
 const auto&x=e.get(key);return x.t==rdjson::V::Int?std::to_string(x.n):"?";
}
inline std::string hex(const rdjson::V& e,const char* key){
 const auto&x=e.get(key);if(x.t!=rdjson::V::Int||x.n<0)return "?";
 std::ostringstream ss;ss<<"0x"<<std::uppercase<<std::hex<<x.n;return ss.str();
}
struct State {
 std::string connection="Connecting to controller diagnostics v1";
 std::string cpu="CPU: -   PC: -   SP: -   Steps: -";
 std::string frame="Guest sampled frame: -   Host output: -";
 std::string status="Status: awaiting native events";
 std::deque<std::string> lines;
 std::uint64_t accepted=0,rejected=0;
 void append(std::string s){
  // Text never controls the native process; limit GUI content and event history.
  if(s.size()>240)s.resize(240);
  for(char&c:s)if(c=='\r'||c=='\n'||c=='\t')c=' ';
  lines.push_back(std::move(s));if(lines.size()>300)lines.pop_front();
 }
 bool ingest(const std::string& line){
  if(line.size()>kMaxLine){++rejected;return false;}
  try {
   const auto e=rdjson::Reader(line).parse();
   if(e.t!=rdjson::V::Object||field(e,"schema","")!=kSchema){++rejected;return false;}
   const auto kind=field(e,"type","");
   if(kind=="connected")connection="Connected to controller diagnostics v1";
   else if(kind=="instruction"){
    cpu="CPU: "+field(e,"cpu")+"   PC: "+hex(e,"pc")+"   SP: "+hex(e,"sp")+"   Steps: "+number(e,"steps");
    append(number(e,"guest_cycles")+"  "+hex(e,"pc")+"  opcode "+hex(e,"opcode")+"  "+field(e,"opcode_class")+"  -> "+hex(e,"next_pc"));
   }else if(kind=="frame"){
    frame="Guest sampled frame: "+number(e,"frame")+"   Cycles: "+number(e,"guest_cycles")+"   Steps: "+number(e,"steps");
   }else if(kind=="input")append("INPUT mask "+hex(e,"buttons")+"  cycles "+number(e,"guest_cycles"));
   else if(kind=="stop"){
    status="Guest blocked: "+field(e,"status")+" @ "+hex(e,"pc");
    append("STOP "+status);
   }else if(kind=="native_result"){
    auto s=field(e,"status");
    status=(s.find("UNTRANSLATED")!=std::string::npos||s.find("BANKED_CODE_NOT_TRANSLATED")!=std::string::npos)?
      "Guest blocked - untranslated instruction @ "+hex(e,"pc") :
      "Guest execution ended - "+s+" @ "+hex(e,"pc");
    frame="Host output frames: "+number(e,"host_frame")+"   Guest counter: "+number(e,"guest_frame")+" (different domains)";
    connection="Native run finished; last trace retained";
    append("NATIVE RESULT "+status);
   }else if(kind=="session"||kind=="notice"){
    auto s=field(e,"status","");if(s.empty())s=field(e,"message");
    if(kind=="session"&&s.find("disconnected")!=std::string::npos)connection="Controller disconnected; last trace retained";
    else status="Status: "+s;
    append(kind+" "+s);
   }else if(kind!="hardware") {++rejected;return false;}
   ++accepted;return true;
  }catch(const std::exception&){++rejected;return false;}
 }
 std::string trace()const{std::string s;for(const auto&line:lines){s+=line;s+='\r';s+='\n';}return s;}
};
}
