#pragma once
#include "core.hpp"
#include "rd_host_loader.hpp"
namespace recomp::hw {
class Win32Audio {
 RD_Host *handle_=nullptr;
 public:
 Win32Audio()=default;
 Win32Audio(const Win32Audio&)=delete;
 Win32Audio& operator=(const Win32Audio&)=delete;
 bool open(u32 hz=44100){auto &a=host_bridge::api();return a.ready&&a.create(RD_HOST_MODE_SPEAKER,"",hz,&handle_)==0;}
 void feed(const PcmBlock&b){b.validate();auto &a=host_bridge::api();
  if(handle_&&a.pcm(handle_,b.samples.data(),b.samples.size(),b.sample_rate,b.channels)!=0)
    throw std::runtime_error("RUNTIME_HOST_AUDIO_REJECTED_PCM");
 }
 void pump(){auto&a=host_bridge::api();if(handle_)a.pump(handle_);}
 ~Win32Audio(){if(handle_)host_bridge::api().destroy(handle_);}
};
}
