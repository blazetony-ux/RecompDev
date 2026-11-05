#pragma once
// Source-only, host-neutral diagnostics contract. SMS-specific input/VDP
// inspection is selected by the external staging adapter, NOT by the host.
// No game memory addresses, ROM data or inferred player identity are recorded.
// Writes only when RECOMPDEV_MOVEMENT_TRACE_DIR is set by the launcher.
#include <array>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <stdexcept>
#include <string>

namespace rd_movement_trace {
class Recorder final {
 std::ofstream controller_,ports_,frames_,sprites_;
 bool enabled_=false;
 std::uint64_t last_buttons_=~std::uint64_t(0), frame_seq_=0;
 std::uint64_t port_count_=0, sprite_count_=0;
 static void open(std::ofstream& f,const std::string& filename,const char* header){
  f.open(filename,std::ios::out|std::ios::trunc|std::ios::binary);
  if(!f)throw std::runtime_error("MOVEMENT_TRACE_OPEN_FAILED: "+filename);
  f<<header<<'\n';if(!f)throw std::runtime_error("MOVEMENT_TRACE_HEADER_WRITE_FAILED");
 }
 Recorder(){
  const char* dir=std::getenv("RECOMPDEV_MOVEMENT_TRACE_DIR");
  if(!dir||!*dir)return;
  const std::string prefix=std::string(dir)+"/";
  open(controller_,prefix+"movement-controller.csv","guest_cycle,logical_buttons,controller_dc,controller_dd");
  open(ports_,prefix+"movement-port-reads.csv","guest_cycle,pc,port,value");
  open(frames_,prefix+"movement-frames.csv","render_seq,guest_frame,guest_cycle,scroll_h_reg8,scroll_v_reg9,reg0,reg1,sat_base,sat_entries");
  open(sprites_,prefix+"movement-sprites.csv","render_seq,guest_cycle,sat_index,x_raw,y_raw,pattern,screen_x,screen_y");
  enabled_=true;
 }
 public:
 Recorder(const Recorder&)=delete;Recorder& operator=(const Recorder&)=delete;
 static Recorder& instance(){static Recorder x;return x;}
 void controller(std::uint64_t cycle,std::uint64_t buttons,std::uint8_t dc,std::uint8_t dd){
  if(!enabled_||buttons==last_buttons_)return;
  last_buttons_=buttons;
  controller_<<cycle<<','<<buttons<<','<<unsigned(dc)<<','<<unsigned(dd)<<'\n';
  if(!controller_)throw std::runtime_error("MOVEMENT_CONTROLLER_TRACE_WRITE_FAILED");
 }
 void port(std::uint64_t cycle,std::uint16_t pc,unsigned port,std::uint8_t value){
  if(!enabled_)return;
  if(++port_count_>250000)throw std::runtime_error("MOVEMENT_PORT_TRACE_LIMIT");
  ports_<<cycle<<','<<unsigned(pc)<<','<<port<<','<<unsigned(value)<<'\n';
  if(!ports_)throw std::runtime_error("MOVEMENT_PORT_TRACE_WRITE_FAILED");
 }
 void frame(std::uint64_t cycle,std::uint64_t guest_frame,
   const std::array<std::uint8_t,16384>& vram,const std::array<std::uint8_t,16>& regs){
  if(!enabled_)return;
  if(frame_seq_>=36000)throw std::runtime_error("MOVEMENT_FRAME_TRACE_LIMIT");
  const std::uint64_t seq=frame_seq_++;
  const unsigned sat=(unsigned(regs[5]&0x7e)<<7)&0x3fff;
  unsigned count=0;
  for(;count<64;++count)if(vram[(sat+count)&0x3fff]==0xd0)break;
  frames_<<seq<<','<<guest_frame<<','<<cycle<<','<<unsigned(regs[8])<<','<<unsigned(regs[9])
    <<','<<unsigned(regs[0])<<','<<unsigned(regs[1])<<','<<sat<<','<<count<<'\n';
  if(!frames_)throw std::runtime_error("MOVEMENT_FRAME_TRACE_WRITE_FAILED");
  for(unsigned i=0;i<count;++i){
   if(++sprite_count_>1500000)throw std::runtime_error("MOVEMENT_SPRITE_TRACE_LIMIT");
   const unsigned x=vram[(sat+0x80+i*2)&0x3fff];
   const unsigned y=vram[(sat+i)&0x3fff];
   const unsigned patt=vram[(sat+0x81+i*2)&0x3fff];
   const int screen_x=int(x)-((regs[0]&8)?8:0);
   const unsigned screen_y=(y+1)&255;
   sprites_<<seq<<','<<cycle<<','<<i<<','<<x<<','<<y<<','<<patt<<','<<screen_x<<','<<screen_y<<'\n';
  }
  if(!sprites_)throw std::runtime_error("MOVEMENT_SPRITE_TRACE_WRITE_FAILED");
 }
};
inline void controller(std::uint64_t c,std::uint64_t b,std::uint8_t a,std::uint8_t d){Recorder::instance().controller(c,b,a,d);}
inline void port(std::uint64_t c,std::uint16_t pc,unsigned p,std::uint8_t value){Recorder::instance().port(c,pc,p,value);}
inline void frame(std::uint64_t c,std::uint64_t f,const std::array<std::uint8_t,16384>& vram,
 const std::array<std::uint8_t,16>& regs){Recorder::instance().frame(c,f,vram,regs);}
} // namespace rd_movement_trace
