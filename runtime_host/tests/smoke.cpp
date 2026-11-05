#include "rd_runtime_host.h"
#include <stdexcept>
#define assert(x) do { if(!(x)) throw std::runtime_error("assertion failed: " #x); } while(false)
#include <cstdint>
#include <vector>
#include <utility>
#include <iostream>
int main(){
 assert(rd_host_abi_version()==RD_HOST_ABI_VERSION);
 RD_Host *video=nullptr,*audio=nullptr;
 assert(rd_host_create(RD_HOST_MODE_HEADLESS,"generic test",44100,&video)==0);
 for(auto d: {std::pair<uint32_t,uint32_t>{256,192},{320,240},{640,480}}){
  std::vector<uint32_t> frame(size_t(d.first)*d.second,0xffa01435);
  assert(rd_host_present(video,frame.data(),d.first,d.second,RD_HOST_PIXELS_BGRA8888)==0);
 }
 assert(rd_host_present(video,nullptr,256,192,RD_HOST_PIXELS_BGRA8888)!=0);
 RD_HostStats stat{};stat.struct_size=sizeof(stat);
 assert(rd_host_stats(video,&stat)==0 && stat.frames==3 && stat.width==640 && stat.height==480);
 assert(rd_host_buttons(video)==0 && rd_host_pump(video)==1);
 assert(rd_host_create(RD_HOST_MODE_HEADLESS,"audio",44100,&audio)==0);
 std::vector<int16_t> pcm(2048,150);assert(rd_host_pcm(audio,pcm.data(),pcm.size(),44100,1)==0);
 assert(rd_host_pcm(audio,pcm.data(),pcm.size(),44100,2)==0);
 assert(rd_host_pcm(audio,pcm.data(),pcm.size(),44100,8)==0);
 assert(rd_host_pcm(audio,pcm.data(),pcm.size(),44100,9)!=0);
 assert(rd_host_pcm(audio,pcm.data(),pcm.size(),32000,1)!=0);
 stat.struct_size=sizeof(stat);assert(rd_host_stats(audio,&stat)==0 && stat.audio_samples==6144);
 rd_host_destroy(audio);rd_host_destroy(video);
 std::cout<<"HOST_ABI_PASS; frames=3; resolutions=256x192,320x240,640x480; pcm=6144\n";
}
