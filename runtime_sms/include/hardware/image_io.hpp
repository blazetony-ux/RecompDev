#pragma once
// Shared PPM encoder for native host and compiled video qualification probe.
#include "core.hpp"
#include <fstream>
namespace recomp::hw {
inline bool write_rgb_ppm(const std::string& path,const Frame& f){
 if(f.pixels.empty())return false;
 f.validate();
 std::ofstream o(path,std::ios::binary|std::ios::trunc);
 if(!o)return false;
 o<<"P6\n"<<f.width<<" "<<f.height<<"\n255\n";
 for(auto px:f.pixels){
  const char rgb[]={char((px>>16)&255),char((px>>8)&255),char(px&255)};
  o.write(rgb,3);
 }
 o.flush();return o.good();
}
}
