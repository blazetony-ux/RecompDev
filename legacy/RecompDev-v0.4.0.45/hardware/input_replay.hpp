#pragma once
#include "core.hpp"
#include <fstream>
#include <sstream>
namespace recomp::hw {
// Portable, bounded, explicitly versioned deterministic input fixture.
// The owner controls this CSV. Clock units are the guest CPU's clock cycles.
inline InputTimeline load_input_replay(const std::string& path){
 std::ifstream f(path,std::ios::binary|std::ios::ate);
 if(!f||f.tellg()<0||f.tellg()>1048576)throw std::invalid_argument("INVALID_INPUT_REPLAY_FILE");
 f.seekg(0);std::string line;
 if(!std::getline(f,line))throw std::invalid_argument("UNSUPPORTED_INPUT_REPLAY_SCHEMA");
 if(!line.empty()&&line.back()=='\r')line.pop_back();
 if(line!="RECOMP_INPUT_CYCLES_V1")
  throw std::invalid_argument("UNSUPPORTED_INPUT_REPLAY_SCHEMA");
 InputTimeline result;std::size_t rows=0;
 auto parse=[](const std::string& s)->u64{
  if(s.empty()||s.size()>19||s.find_first_not_of("0123456789")!=std::string::npos)
   throw std::invalid_argument("INVALID_INPUT_NUMBER");
  std::size_t end=0;u64 number=0;
  try{number=std::stoull(s,&end,10);}catch(const std::exception&){throw std::invalid_argument("INVALID_INPUT_NUMBER");}
  if(end!=s.size())throw std::invalid_argument("INVALID_INPUT_NUMBER");return number;
 };
 while(std::getline(f,line)){
  if(!line.empty()&&line.back()=='\r')line.pop_back();
  if(line.empty())continue;
  if(++rows>10000||line.size()>80)throw std::length_error("INPUT_REPLAY_EVENT_LIMIT");
  const auto x=line.find(','),y=line.find(',',x==std::string::npos?0:x+1);
  if(x==std::string::npos||y==std::string::npos||line.find(',',y+1)!=std::string::npos)
   throw std::invalid_argument("INVALID_INPUT_REPLAY_ROW");
  const u64 cycle=parse(line.substr(0,x)),port=parse(line.substr(x+1,y-x-1)),buttons=parse(line.substr(y+1));
  if(port>15)throw std::invalid_argument("INVALID_INPUT_PORT");
  result.append(cycle,{u32(port),buttons,0,0});
 }
 return result;
}
} // namespace recomp::hw
