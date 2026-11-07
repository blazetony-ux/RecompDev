#pragma once
// Master System-specific devices built on the CPU-independent hardware contracts.
// Approximate MODE4/PSG foundation, NOT verified SMS VDP/PSG/IRQ parity.
#include "../core.hpp"
#include <array>
#include <cmath>
namespace recomp::hw::sms {
// Screenshot renderer for an existing Z80 execution state. Used by the native
// pilot AND by the detachable VDP device, avoiding separate rendering algorithms.
inline Frame render_mode4(const std::array<u8,16384>& vram,
 const std::array<u8,32>& cram,const std::array<u8,16>& regs,u64 cycle=0,u64 ordinal=0){
 Frame out;out.width=256;out.height=192;out.source_cycle=cycle;out.ordinal=ordinal;
 out.pixels.resize(std::size_t(out.width)*out.height);
 const u32 base=(u32(regs[2]&0x0e)<<10)&0x3fff;
 const u32 hscroll=(regs[8]);const u32 vscroll=regs[9];
 for(u32 y=0;y<out.height;++y){
  for(u32 x=0;x<out.width;++x){
   // Mode 4 background and palette priority; per-column scroll and sprite
   // collision/overflow require additional independent qualification.
   u32 sx=(x+hscroll)&255,sy=(y+vscroll)%224;
   u32 a=(base+(((sy/8)*32+sx/8)*2))&0x3fff;
   u32 attr=u32(vram[a])|(u32(vram[(a+1)&0x3fff])<<8);
   u32 tile=attr&0x1ff, px=(attr&0x200)?7-(sx&7):(sx&7),py=(attr&0x400)?7-(sy&7):(sy&7);
   u32 patt=(tile*32+py*4)&0x3fff,bit=7-px,ci=0;
   for(u32 plane=0;plane<4;++plane)ci|=u32((vram[(patt+plane)&0x3fff]>>bit)&1)<<plane;
   const u8 c=cram[((attr&0x800)?16:0)+ci];
   const u32 r=u32(c&3)*85,g=u32((c>>2)&3)*85,b=u32((c>>4)&3)*85;
   out.pixels[std::size_t(y)*out.width+x]=0xff000000u|(r<<16)|(g<<8)|b;
  }
 }
 return out;
}
class Vdp final:public Device {
 public:std::array<u8,16384> vram{};std::array<u8,32> cram{};std::array<u8,16> regs{};
 u8 status=0,read_buffer=0,latch=0,code=0;u32 address=0;bool pending=false;
 u64 cycles=0;u64 ordinal=0;
 const char* name()const override{return "sms-vdp";}
 bool maps(IoAddress a)const override{return a.space==Space::IO&&((a.address&0xc0)==0x80);}
 u8 read(IoAddress a)override{
  if((a.address&1)==0){pending=false;u8 v=read_buffer;read_buffer=vram[address&0x3fff];address=(address+1)&0x3fff;return v;}
  pending=false;u8 v=status;status&=0x1f;return v;
 }
 void write(IoAddress a,u8 v)override{
  if((a.address&1)==1){
   if(!pending){latch=v;pending=true;}else{pending=false;address=((u32(v)&63)<<8)|latch;code=v>>6;
    if(code==2&&((v&0xf)<regs.size()))regs[v&0xf]=latch;
    if(code==0){read_buffer=vram[address&0x3fff];address=(address+1)&0x3fff;}}
  }else{
   pending=false;if(code==3)cram[address&31]=v;else{vram[address&0x3fff]=v;read_buffer=v;}
   address=(address+1)&0x3fff;
  }
 }
 void advance(u64 ticks)override{cycles+=ticks;
  // Nominal NTSC SMS timing, explicitly unqualified.
  if(cycles/(228*262)>ordinal)ordinal=cycles/(228*262);
  if((cycles/228)%262>=192)status|=0x80;
 }
 Frame render()const{return render_mode4(vram,cram,regs,cycles,ordinal);}
};
class Psg final:public Device {
 using u16=std::uint16_t;
 std::array<u16,3> tone_{{1,1,1}};
 std::array<u8,4> vol_{{15,15,15,15}};
 u8 selected_=0,noise_=0;
 u16 noise_lfsr_=0x8000;
 u64 noise_cycle_=0;
 bool noise_epoch_pending_=true;
 void set_noise(u8 data){
  noise_=data&7;
  noise_lfsr_=0x8000;  // SMS 16-bit LFSR, reset by every noise-register write.
  noise_epoch_pending_=true;
 }
 public:
 const char* name()const override{return "sms-psg";}
 bool maps(IoAddress a)const override{return a.space==Space::IO&&((a.address&0xc0)==0x40)&&((a.address&1)!=0);}
 u8 read(IoAddress)override{return 0xff;}
 void write(IoAddress,u8 v)override{
  if(v&0x80){
   selected_=(v>>4)&7;
   unsigned ch=selected_>>1;
   if(selected_&1)vol_[ch]=v&15;
   else if(ch==3)set_noise(v);
   else tone_[ch]=u16((tone_[ch]&0x3f0)|(v&15));
  }else if(selected_&1){
   // A data byte can change the currently latched volume register.
   vol_[selected_>>1]=v&15;
  }else if(selected_==6){
   // Likewise, unlatch-bit-clear data writes can update noise mode/rate.
   set_noise(v);
  }else{
   unsigned ch=selected_>>1;
   tone_[ch]=u16((tone_[ch]&15)|((v&63)<<4));
  }
 }
 void advance(u64)override{}
 // Source-cycle sampled SMS-compatible tone and 16-bit noise approximation.
 // Internal PSG clock is input_clock/16. White noise has taps 0,3 -> bit15.
 // Amplitudes, analogue filtering and phase-exact reference parity remain open.
 std::int16_t sample(u64 source_cycle){
  int mix=0;
  for(unsigned c=0;c<3;++c){
   u32 halfperiod=std::max<u32>(tone_[c],1u)*16u;
   int sign=((source_cycle/halfperiod)&1)?-1:1;
   mix+=sign*(15-vol_[c])*100;
  }
  if(noise_epoch_pending_||source_cycle<noise_cycle_){
   noise_cycle_=source_cycle;noise_epoch_pending_=false;
  }
  const unsigned rate=noise_&3u;
  const u32 div=(rate==3?std::max<u32>(tone_[2],1u):(16u<<rate));
  const u64 shift_period=u64(div)*32u;
  while(source_cycle-noise_cycle_>=shift_period){
   noise_cycle_+=shift_period;
   const unsigned lo=noise_lfsr_&1u;
   const unsigned hi=(noise_&4u)?(lo^((noise_lfsr_>>3)&1u)):lo;
   noise_lfsr_=u16((noise_lfsr_>>1)|(hi<<15));
  }
  if(vol_[3]!=15){
   const int level=(noise_lfsr_&1u)?1:-1;
   mix+=level*(15-vol_[3])*100;
  }
  return std::int16_t(std::clamp(mix,-32768,32767));
 }
};
class Controller final:public Device {
 std::array<InputState,2> ports_{};
 public:
 const char* name()const override{return "sms-controller";}
 bool maps(IoAddress a)const override{return a.space==Space::IO&&((a.address&255)==0xdc||(a.address&255)==0xdd);}
 u8 read(IoAddress a)override{
  u8 v=0xff;
  const u64 mask=ports_[0].buttons;
  if((a.address&255)==0xdc){
   if(mask&button::Up)v&=~u8(1<<0);
   if(mask&button::Down)v&=~u8(1<<1);
   if(mask&button::Left)v&=~u8(1<<2);
   if(mask&button::Right)v&=~u8(1<<3);
   if(mask&button::A)v&=~u8(1<<4);
   if(mask&button::B)v&=~u8(1<<5);
  }
  return v;
 }
 void write(IoAddress,u8)override{}
 void advance(u64)override{}
 void set_input(InputState in){if(in.port>=ports_.size())throw std::invalid_argument("INPUT_PORT_OUT_OF_RANGE");ports_[in.port]=in;}
};
} // namespace recomp::hw::sms
