#include "rd_plugin.h"
#include "systems/mastersystem/runtime.hpp"
#include "hardware/adapters/sms.hpp"
#include <algorithm>
#include <cstring>
#include <new>
#include <vector>
namespace {
struct Machine { rd::State s; };
static void* create(const uint8_t *rom,size_t size) {
 if(!rom || size==0 || size>64*1024*1024u)return nullptr;
 try{auto* m=new Machine; m->s.rom.assign(rom,rom+size); return m;}catch(...){return nullptr;}
}
static void destroy(void *p){delete static_cast<Machine*>(p);}
static uint8_t read(void *p,uint16_t a){return static_cast<Machine*>(p)->s.read_byte(a);}
static void write(void *p,uint16_t a,uint8_t b){static_cast<Machine*>(p)->s.write_byte(a,b);}
static uint8_t in(void *p,uint16_t a){return static_cast<Machine*>(p)->s.in(a);}
static void out(void *p,uint16_t a,uint8_t b){static_cast<Machine*>(p)->s.out(a,b);}
static uint32_t physical(void *p,uint16_t a){
 auto& s=static_cast<Machine*>(p)->s;
 if(a>=0xc000 || (a>=0x8000 && (s.mapper[0]&8)))return 0xffffffffu;
 return s.rom_offset(a);
}
static void set_pc(void *p,uint16_t pc){static_cast<Machine*>(p)->s.pc=pc;}
static void advance(void *p,uint32_t cycles){auto& s=static_cast<Machine*>(p)->s;s.advance_cycles(cycles);++s.steps;}
static RD_Bus bus(void *p){return {p,read,write,in,out,physical,set_pc,advance};}
static void set_input(void *p,uint64_t buttons){static_cast<Machine*>(p)->s.apply_host_input(buttons);}
static uint64_t fnv(uint64_t h,uint8_t byte){return (h^byte)*1099511628211ull;}
static void stats(void *p,RD_MachineStats *r){
 auto& s=static_cast<Machine*>(p)->s;
 *r={};r->tstates=s.tstates;r->steps=s.steps;r->ram_writes=s.ram_writes;
 r->bank_switches=s.bank_switches;r->psg_writes=s.psg_writes;
 r->vram_writes=s.vram_writes;r->cram_writes=s.cram_writes;
 r->bank2=s.mapper[2];r->bank3=s.mapper[3];r->frames=static_cast<uint32_t>(s.frames);
 r->c000=s.ram[0];r->controller_a=s.controller_a;
 uint64_t h=14695981039346656037ull;
 for(auto x:s.ram)h=fnv(h,x);
 for(auto x:s.vram)h=fnv(h,x);
 for(auto x:s.cram)h=fnv(h,x);
 for(auto x:s.mapper)h=fnv(h,x);
 for(auto e:s.psg_timeline){for(int i=0;i<8;++i)h=fnv(h,static_cast<uint8_t>(e.cycle>>(i*8)));h=fnv(h,e.value);}
 r->hardware_hash=h;
}
static int frame_bgra(void *p,uint32_t *pixels,size_t count,uint32_t *w,uint32_t *h){
 if(!pixels||count<RD_PIXELS||!w||!h)return 0;
 try{
  auto& s=static_cast<Machine*>(p)->s;
  auto frame=recomp::hw::sms::render_mode4(s.vram,s.cram,s.vdp_regs,s.tstates,s.frames);
  *w=frame.width;*h=frame.height;
  std::memcpy(pixels,frame.pixels.data(),frame.pixels.size()*sizeof(uint32_t));return 1;
 }catch(...){return 0;}
}
static int audio_pcm(void *p,int16_t *dest,size_t n){
 if(!dest||n>RD_AUDIO_SAMPLES)return 0;
 auto& s=static_cast<Machine*>(p)->s;
 recomp::hw::sms::Psg psg;
 size_t ev=0;
 for(size_t i=0;i<n;++i){
   auto cycle=uint64_t(i+1)*std::max<uint64_t>(s.tstates,1)/n;
   while(ev<s.psg_timeline.size()&&s.psg_timeline[ev].cycle<=cycle){
     psg.write({recomp::hw::Space::IO,0x7f},s.psg_timeline[ev++].value);
   }
   dest[i]=psg.sample(cycle);
 }
 return 1;
}
const RD_MachineApi API={create,destroy,bus,set_input,stats,frame_bgra,audio_pcm};
const RD_Plugin PLUGIN={RD_ABI_VERSION,sizeof(RD_Plugin),RD_MACHINE,sizeof(API),"RecompDev 0.4.0.45 SMS machine adapter",&API};
}
extern "C" RD_EXPORT const RD_Plugin *rd_get_plugin_v1(void){return &PLUGIN;}

#include "rd_native_discovery_v1.h"
// No assumed bank context: the first 1KiB reset/interrupt page is pinned to ROM
// bank 0; all other cartridge windows require mapper-state evidence.
extern "C" RD_EXPORT int rd_sms_resolve_source_v1(uint16_t guest,uint64_t size,uint64_t*physical){
 if(!physical)return -1;
 *physical=RD_NATIVE_SOURCE_UNMAPPED;
 if(guest>=0xc000)return -1;
 if(guest>=0x0400)return 0;
 if(uint64_t(guest)>=size)return -1;
 *physical=guest;return 1;
}
