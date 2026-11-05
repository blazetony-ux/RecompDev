#pragma once
#include "core.hpp"
#include "rd_host_loader.hpp"
namespace recomp::hw {
// Match the existing portable native-app interface, change only presentation.
class Win32Window {
 RD_Host *handle_=nullptr;
 public:
 Win32Window()=default;
 Win32Window(const Win32Window&)=delete;
 Win32Window& operator=(const Win32Window&)=delete;
 bool open(const char*title){auto &a=host_bridge::api();
  return a.ready&&a.create(RD_HOST_MODE_WINDOW,title,44100,&handle_)==0;
 }
 bool pump(){auto &a=host_bridge::api();return handle_&&a.pump(handle_)>0;}
 u64 buttons()const{auto &a=host_bridge::api();return handle_?a.buttons(handle_):0;}
 void present(const Frame&f){f.validate();auto &a=host_bridge::api();
  if(handle_&&a.present(handle_,f.pixels.data(),f.width,f.height,RD_HOST_PIXELS_BGRA8888)!=0)
   throw std::runtime_error("RUNTIME_HOST_VIDEO_REJECTED_FRAME");
 }
 void title(const char*t){auto &a=host_bridge::api();if(handle_)a.title(handle_,t);}
 ~Win32Window(){if(handle_)host_bridge::api().destroy(handle_);}
};
}
