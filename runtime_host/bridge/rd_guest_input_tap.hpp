#pragma once
// CPU-, console- and game-neutral capture of logical button transitions in
// guest cycle time. The run launcher alone provides the absolute evidence path.
// No ROM bytes or raw host keystrokes are recorded here.
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <stdexcept>

namespace recomp::hw {
class GuestInputTap final {
 std::ofstream output_;
 bool initialized_=false, observed_=false;
 std::uint64_t previous_=0, previous_cycle_=0;
 GuestInputTap()=default;
 public:
 GuestInputTap(const GuestInputTap&)=delete;
 GuestInputTap& operator=(const GuestInputTap&)=delete;
 static GuestInputTap& instance(){static GuestInputTap x;return x;}
 void sample(std::uint64_t guest_cycle,std::uint32_t port,std::uint64_t buttons){
  if(!initialized_){
   initialized_=true;
   const char* path=std::getenv("RECOMPDEV_GUEST_INPUT_REPLAY");
   if(path&&*path){
    output_.open(path,std::ios::out|std::ios::trunc|std::ios::binary);
    if(!output_)throw std::runtime_error("GUEST_INPUT_CAPTURE_OPEN_FAILED");
    output_<<"RECOMP_INPUT_CYCLES_V1\n";
   }
  }
  if(observed_ && guest_cycle<previous_cycle_)throw std::runtime_error("GUEST_INPUT_CYCLE_REGRESSION");
  previous_cycle_=guest_cycle;
  if(!observed_||previous_!=buttons){
   observed_=true;previous_=buttons;
   if(output_){
    output_<<guest_cycle<<","<<port<<","<<buttons<<"\n";
    output_.flush();
    if(!output_)throw std::runtime_error("GUEST_INPUT_CAPTURE_WRITE_FAILED");
   }
  }
 }
};
}
