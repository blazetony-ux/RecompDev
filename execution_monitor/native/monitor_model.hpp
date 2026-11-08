#pragma once
// Generic read-only diagnostics projection. No CPU-specific instruction rules.
#include "rd_tiny_json.hpp"
#include <algorithm>
#include <cctype>
#include <cstdint>
#include <deque>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>

namespace rdmonitor {
constexpr const char* kSchema="recompdev.controller.diagnostics.v1";
constexpr std::size_t kMaxLine=4096;
constexpr std::size_t kHistoryLimit=2000;
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
inline std::string lower(std::string s){
 std::transform(s.begin(),s.end(),s.begin(),[](unsigned char c){return char(std::tolower(c));});return s;
}
struct Entry {
 std::uint64_t sequence=0;
 std::string text,pc,physical,opcode_class,kind;
 bool watched=false;
};
inline bool address_value(const std::string& s,std::uint64_t& out){
 if(s.empty())return false;
 try{
  std::size_t used=0;
  out=std::stoull(s,&used,s.size()>2&&s[0]=='0'&&(s[1]=='x'||s[1]=='X')?16:10);
  return used==s.size()&&out<=0xffffffffULL;
 }catch(const std::exception&){return false;}
}
inline bool address_match(const std::string& address,const std::string& search){
 auto sep=search.find(':');std::uint64_t a=0,lo=0,hi=0;
 if(sep!=std::string::npos&&address_value(address,a)&&
    address_value(search.substr(0,sep),lo)&&address_value(search.substr(sep+1),hi))
    return lo<=a&&a<=hi;
 if(address_value(address,a)&&address_value(search,lo))return a==lo;
 return lower(address).find(lower(search))!=std::string::npos;
}
inline bool matches(const Entry& e,const std::string& search,int mode){
 if(mode==5)return e.watched&&(search.empty()||lower(e.text).find(lower(search))!=std::string::npos);
 if(search.empty())return true;
 const auto q=lower(search);
 const auto contains=[&](const std::string& s){return lower(s).find(q)!=std::string::npos;};
 switch(mode){
  case 1:return address_match(e.pc,search);
  case 2:return address_match(e.physical,search);
  case 3:return contains(e.opcode_class);
  case 4:return contains(e.kind);
  default:return contains(e.text);
 }
}
struct State {
 std::string connection="Connecting to controller diagnostics v1";
 std::string cpu="CPU: -   PC: -   SP: -   Steps: -";
 std::string frame="Guest sampled frame: -   Host output: -";
 std::string status="Status: awaiting native events";
 std::deque<std::string> lines; // Compatibility with 0.4.9.21 monitor contract
 std::deque<Entry> entries;
 std::uint64_t accepted=0,rejected=0,trace_sequence=0,transport_dropped=0;
 std::string latest_cpu="-",latest_sp="?",latest_steps="?";
 void append(std::string s,std::string kind="notice",std::string pc="",std::string physical="",std::string cls="",bool watched=false){
  if(s.size()>240)s.resize(240);
  for(char&c:s)if(c=='\r'||c=='\n'||c=='\t')c=' ';
  lines.push_back(s);
  entries.push_back(Entry{++trace_sequence,std::move(s),std::move(pc),std::move(physical),std::move(cls),std::move(kind),watched});
  while(lines.size()>kHistoryLimit)lines.pop_front();
  while(entries.size()>kHistoryLimit)entries.pop_front();
 }
 bool ingest(const std::string& line){
  if(line.size()>kMaxLine){++rejected;return false;}
  try {
   const auto e=rdjson::Reader(line).parse();
   if(e.t!=rdjson::V::Object||field(e,"schema","")!=kSchema){++rejected;return false;}
   const auto kind=field(e,"type","");
   if(kind=="connected")connection="Connected to controller diagnostics v1";
   else if(kind=="instruction"){
    latest_cpu=field(e,"cpu");latest_sp=hex(e,"sp");latest_steps=number(e,"steps");
    cpu="CPU: "+latest_cpu+"   PC: "+hex(e,"pc")+"   SP: "+latest_sp+"   Steps: "+latest_steps;
    append(number(e,"guest_cycles")+"  "+hex(e,"pc")+"  opcode "+hex(e,"opcode")+"  "+field(e,"opcode_class")+
     "  -> "+hex(e,"next_pc")+(e.get("watch_hit").t==rdjson::V::Bool&&e.get("watch_hit").n!=0?" [WATCH]":""),
     "instruction",hex(e,"pc"),hex(e,"physical_offset"),field(e,"opcode_class"),
     e.get("watch_hit").t==rdjson::V::Bool&&e.get("watch_hit").n!=0);
   }else if(kind=="frame"){
    frame="Guest sampled frame: "+number(e,"frame")+"   Cycles: "+number(e,"guest_cycles")+"   Steps: "+number(e,"steps");
   }else if(kind=="input")append("INPUT mask "+hex(e,"buttons")+"  cycles "+number(e,"guest_cycles"),"input");
   else if(kind=="stop"){
    status="Guest blocked: "+field(e,"status")+" @ "+hex(e,"pc");
    append("STOP "+status,"stop",hex(e,"pc"),hex(e,"physical_offset"));
   }else if(kind=="native_result"){
    const auto s=field(e,"status");
    status=(s.find("UNTRANSLATED")!=std::string::npos||s.find("BANKED_CODE_NOT_TRANSLATED")!=std::string::npos)?
      "Guest blocked - untranslated instruction @ "+hex(e,"pc") :
      "Guest execution ended - "+s+" @ "+hex(e,"pc");
    frame="Host output frames: "+number(e,"host_frame")+"   Guest counter: "+number(e,"guest_frame")+" (different domains)";
    connection="Native run finished; last trace retained";
    // A final PC must never be mistaken for the last sampled PC. Guest SP is
    // explicitly last-sampled because native_result has no terminal SP field.
    cpu="CPU: "+latest_cpu+"   Terminal PC: "+hex(e,"pc")+"   SP(last sample): "+latest_sp+"   Steps(last sample): "+latest_steps;
    append("NATIVE RESULT "+status,"native_result",hex(e,"pc"),hex(e,"physical_offset"));
   }else if(kind=="session"||kind=="notice"){
    if(kind=="notice"&&e.get("display_dropped").t==rdjson::V::Int&&e.get("display_dropped").n>=0)
     transport_dropped=static_cast<std::uint64_t>(e.get("display_dropped").n);
    auto s=field(e,"status","");if(s.empty())s=field(e,"message");
    if(kind=="session"&&s.find("disconnected")!=std::string::npos)connection="Controller disconnected; last trace retained";
    else status="Status: "+s;
    append(kind+" "+s,kind);
   }else if(kind!="hardware"){++rejected;return false;}
   ++accepted;return true;
  }catch(const std::exception&){++rejected;return false;}
 }
 std::string trace()const{std::string s;for(const auto&line:lines){s+=line;s+="\r\n";}return s;}
};
}
