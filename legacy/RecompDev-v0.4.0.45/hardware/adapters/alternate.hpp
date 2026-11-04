#pragma once
// Tiny *fictional* device used to prove that shared contracts are not SMS-/Z80-
// specific: different IO map, geometry, clock and controller conventions.
#include "../runtime.hpp"
namespace recomp::hw::alternate {
class Panel final:public Device,public VideoSource,public AudioSource,public InputTarget {
 u8 colour_=0;u64 ticks_=0,keys_=0;
 public:
 const char* name()const override{return "alternate-test-panel";}
 bool maps(IoAddress a)const override{return a.space==Space::Memory&&a.address>=0x4000&&a.address<0x4002;}
 u8 read(IoAddress a)override{return a.address==0x4000?colour_:u8(keys_);}
 void write(IoAddress a,u8 v)override{if(a.address==0x4000)colour_=v;}
 void advance(u64 cycles)override{ticks_+=cycles;}
 Frame render()const override{Frame f;f.width=96;f.height=64;f.source_cycle=ticks_;
  f.pixels.assign(96*64,0xff000000u|(u32(colour_)<<16)|(u32(keys_&255)<<8));return f;}
 std::int16_t sample(u64 c)override{return (c/200)%2?320:-320;}
 void set_input(InputState v)override{keys_=v.buttons;}
};
}
