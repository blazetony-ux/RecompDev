#include "rd_runtime_host.h"
#include "hardware/core.hpp"
#include "hardware/win32_window.hpp"
#include "hardware/win32_audio.hpp"
#include <cstring>
#include <fstream>
#include <chrono>
#include <cstdlib>
#include <memory>
#include <new>
#include <vector>
#include <limits>
#include <cstdint>
#include <string>

namespace hw = recomp::hw;
struct RD_Host {
 uint32_t mode=0, rate=44100; bool running=true;
 uint64_t frames=0, samples=0, frame_hash=0, audio_hash=14695981039346656037ull;
 uint32_t width=0,height=0;
 uint64_t previously_sampled_buttons=0;
 std::chrono::steady_clock::time_point opened=std::chrono::steady_clock::now();
 std::ofstream input_log;
 hw::Win32Window window;
 hw::Win32Audio audio;
};
extern "C" {
uint32_t rd_host_abi_version(void){return RD_HOST_ABI_VERSION;}
int rd_host_create(uint32_t mode,const char *title,uint32_t rate,RD_Host **out){
 if(!out)return -1;
 *out=nullptr;
 if(mode>RD_HOST_MODE_SPEAKER||rate<8000||rate>192000)return -2;
 try{
  auto host=std::unique_ptr<RD_Host>(new RD_Host());host->mode=mode;host->rate=rate;
  if(mode==RD_HOST_MODE_WINDOW){
   if(!host->window.open(title?title:"RecompDev Native Host"))return -3;
   // Caller owns the evidence path; no guest ROM, keystrokes or arbitrary
   // device state is saved, only abstract sampled button masks.
   if(const char* path=std::getenv("RECOMPDEV_RUNTIME_HOST_INPUT_EVENTS")){
    if(*path)host->input_log.open(path,std::ios::out|std::ios::trunc);
   }
  }
  if(mode==RD_HOST_MODE_SPEAKER && !host->audio.open(rate))return -4;
  *out=host.release();return 0;
 }catch(...){return -5;}
}
void rd_host_destroy(RD_Host *p){delete p;}
int rd_host_present(RD_Host *p,const uint32_t *pixels,uint32_t w,uint32_t h,uint32_t fmt){
 if(!p||p->mode==RD_HOST_MODE_SPEAKER||!pixels||!w||!h||w>4096||h>4096||fmt!=RD_HOST_PIXELS_BGRA8888)return -1;
 try{
  hw::Frame frame;frame.width=w;frame.height=h;frame.format=hw::PixelFormat::BGRA8888;
  frame.pixels.assign(pixels,pixels+static_cast<size_t>(w)*h);
  p->frame_hash=hw::frame_fingerprint(frame);p->frames++;p->width=w;p->height=h;
  if(p->mode==RD_HOST_MODE_WINDOW)p->window.present(frame);
  return 0;
 }catch(...){return -2;}
}
int rd_host_pcm(RD_Host *p,const int16_t *data,size_t count,uint32_t rate,uint32_t ch){
 if(!p||p->mode==RD_HOST_MODE_WINDOW||(!data&&count)||rate!=p->rate||ch<1||ch>8||count%ch||count>1048576||p->samples>60000000-count)return -1;
 try{
  for(size_t i=0;i<count;++i){auto v=static_cast<uint16_t>(data[i]);
   p->audio_hash=(p->audio_hash^static_cast<uint8_t>(v))*1099511628211ull;
   p->audio_hash=(p->audio_hash^static_cast<uint8_t>(v>>8))*1099511628211ull;
  }
  p->samples+=count;
  if(p->mode==RD_HOST_MODE_SPEAKER && count){
    // The frozen Win32 speaker handles mono PCM; downmix any source channel
    // count without changing original guest audio/hardware state.
    hw::PcmBlock block;block.channels=1;block.sample_rate=rate;
    block.samples.reserve(count/ch);
    for(size_t i=0;i<count;i+=ch){int32_t sum=0;
      for(uint32_t channel=0;channel<ch;++channel)sum+=data[i+channel];
      block.samples.push_back(static_cast<int16_t>(sum/static_cast<int32_t>(ch)));
    }
    p->audio.feed(block);
  }
  return 0;
 }catch(...){return -2;}
}
int rd_host_pump(RD_Host *p){
 if(!p)return -1;
 if(p->mode==RD_HOST_MODE_WINDOW){
  p->running=p->window.pump();
  const auto value=p->window.buttons();
  if(value!=p->previously_sampled_buttons){
   const auto elapsed=std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now()-p->opened).count();
   if(p->input_log.is_open()){
    p->input_log<<"{\"elapsed_ms\":"<<elapsed<<",\"buttons\":"<<value<<"}\n";
    p->input_log.flush();
   }
   p->previously_sampled_buttons=value;
  }
 }
 if(p->mode==RD_HOST_MODE_SPEAKER)p->audio.pump();
 return p->running?1:0;
}
uint64_t rd_host_buttons(RD_Host *p){return p&&p->mode==RD_HOST_MODE_WINDOW?p->window.buttons():0;}
int rd_host_title(RD_Host *p,const char *title){
 if(!p||!title)return -1;
 if(p->mode==RD_HOST_MODE_WINDOW)p->window.title(title);
 return 0;
}
int rd_host_stats(RD_Host *p,RD_HostStats *out){
 if(!p||!out||out->struct_size<sizeof(RD_HostStats))return -1;
 RD_HostStats s{};s.struct_size=sizeof(s);s.abi_version=RD_HOST_ABI_VERSION;s.running=p->running?1:0;
 s.width=p->width;s.height=p->height;s.frames=p->frames;s.audio_samples=p->samples;
 s.frame_fingerprint=p->frame_hash;s.audio_fingerprint=p->audio_hash;s.buttons=rd_host_buttons(p);
 std::memcpy(out,&s,sizeof(s));return 0;
}
}
