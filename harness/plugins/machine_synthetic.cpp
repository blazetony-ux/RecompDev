#include "rd_plugin.h"
#include <algorithm>
#include <array>
#include <cstring>
#include <new>
#include <vector>
namespace {
// A second, fully independent test machine. It is NOT a console model.
// Its purpose is to prove the host can replace the machine DLL without a rebuild.
struct Machine {
 std::vector<uint8_t> rom;
 std::array<uint8_t,8192> ram{};
 std::array<uint8_t,4> mapper{{0,0,1,2}};
 uint64_t cycles=0,steps=0,ram_writes=0,bank_switches=0,psg_writes=0;
 uint8_t input=0xff;
 std::vector<std::pair<uint64_t,uint8_t>> sound;
};
static void *create(const uint8_t *data,size_t n){
 if(!data||n<0xc000||n>64*1024*1024u)return nullptr;
 try{auto m=new Machine;m->rom.assign(data,data+n);return m;}catch(...){return nullptr;}
}
static void destroy(void *p){delete static_cast<Machine*>(p);}
static uint32_t physical(void *p,uint16_t addr){
 auto& m=*static_cast<Machine*>(p);
 if(addr>=0xc000)return 0xffffffffu;
 if(addr<0x400)return addr;
 const size_t bank=m.mapper[addr<0x4000?1:addr<0x8000?2:3]%(m.rom.size()/0x4000);
 return uint32_t(bank*0x4000+(addr&0x3fff));
}
static uint8_t read(void *p,uint16_t a){
 auto& m=*static_cast<Machine*>(p);
 if(a>=0xc000)return m.ram[a&0x1fff];
 uint32_t off=physical(p,a);return off<m.rom.size()?m.rom[off]:0xff;
}
static void write(void *p,uint16_t a,uint8_t value){
 auto& m=*static_cast<Machine*>(p);
 if(a<0xc000)return;
 m.ram[a&0x1fff]=value;++m.ram_writes;
 if(a>=0xfffc){uint8_t& slot=m.mapper[a-0xfffc];if(slot!=value){slot=value;++m.bank_switches;}}
}
static uint8_t in(void *p,uint16_t port){return (port&255)==0xdc?static_cast<Machine*>(p)->input:0xff;}
static void out(void *p,uint16_t port,uint8_t value){
 auto& m=*static_cast<Machine*>(p);
 if((port&0xc0)==0x40){++m.psg_writes;m.sound.push_back({m.cycles,value});}
}
static void set_pc(void*,uint16_t){}
static void advance(void *p,uint32_t n){auto& m=*static_cast<Machine*>(p);m.cycles+=n;++m.steps;}
static RD_Bus bus(void *p){return {p,read,write,in,out,physical,set_pc,advance};}
static void set_input(void *p,uint64_t keys){static_cast<Machine*>(p)->input=uint8_t(0xff & (~(keys&(1ull<<4)?0x10:0ull)));}
static uint64_t hash(uint64_t h,uint8_t c){return (h^c)*1099511628211ull;}
static void stats(void *p,RD_MachineStats *r){
 auto& m=*static_cast<Machine*>(p);*r={};
 r->tstates=m.cycles;r->steps=m.steps;r->ram_writes=m.ram_writes;
 r->bank_switches=m.bank_switches;r->psg_writes=m.psg_writes;
 r->bank2=m.mapper[2];r->bank3=m.mapper[3];r->c000=m.ram[0];r->controller_a=m.input;
 uint64_t h=14695981039346656037ull;
 for(auto x:m.ram)h=hash(h,x);
 for(auto x:m.mapper)h=hash(h,x);
 for(auto e:m.sound){for(unsigned i=0;i<8;++i)h=hash(h,uint8_t(e.first>>(i*8)));h=hash(h,e.second);}
 r->hardware_hash=h;
}
static int frame(void *p,uint32_t *dst,size_t count,uint32_t *w,uint32_t *h){
 if(!p||!dst||count<RD_PIXELS||!w||!h)return 0;
 *w=256;*h=192;
 const auto value=static_cast<Machine*>(p)->ram[0];
 for(uint32_t y=0;y<192;++y)for(uint32_t x=0;x<256;++x)dst[y*256+x]=0xff000000u|(((x/16+y/16+value)&3u)*0x00555555u);
 return 1;
}
static int audio(void*,int16_t *dst,size_t n){if(!dst||n>RD_AUDIO_SAMPLES)return 0;std::fill(dst,dst+n,0);return 1;}
const RD_MachineApi API={create,destroy,bus,set_input,stats,frame,audio};
const RD_Plugin PLUGIN={RD_ABI_VERSION,sizeof(RD_Plugin),RD_MACHINE,sizeof(API),"Synthetic alternate machine (not SMS)",&API};
}
extern "C" RD_EXPORT const RD_Plugin *rd_get_plugin_v1(void){return &PLUGIN;}
