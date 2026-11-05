#pragma once
// Small generated-project adapter. The shared library owns every OS-specific
// window/audio implementation. Neither this bridge nor the public ABI knows
// any machine, CPU, framebuffer resolution or game title.
#include "rd_runtime_host.h"
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <string>
#ifdef _WIN32
# define WIN32_LEAN_AND_MEAN
# include <windows.h>
#else
# include <dlfcn.h>
#endif
namespace recomp::host_bridge {
struct Api {
 using Create=int (*)(uint32_t,const char*,uint32_t,RD_Host**);
 using Destroy=void (*)(RD_Host*);
 using Present=int (*)(RD_Host*,const uint32_t*,uint32_t,uint32_t,uint32_t);
 using Pcm=int (*)(RD_Host*,const int16_t*,size_t,uint32_t,uint32_t);
 using Pump=int (*)(RD_Host*);
 using Buttons=uint64_t (*)(RD_Host*);
 using Title=int (*)(RD_Host*,const char*);
 using Version=uint32_t (*)(void);
 Create create=nullptr;Destroy destroy=nullptr;Present present=nullptr;Pcm pcm=nullptr;
 Pump pump=nullptr;Buttons buttons=nullptr;Title title=nullptr;Version version=nullptr;
 bool ready=false;
 Api(){
  const char* loc=std::getenv("RECOMPDEV_RUNTIME_HOST_DLL");
  if(!loc||!*loc)return;
#ifdef _WIN32
  auto lib=LoadLibraryA(loc);if(!lib)return;
  auto sym=[&](const char*n){return reinterpret_cast<void*>(GetProcAddress(lib,n));};
#else
  auto lib=dlopen(loc,RTLD_NOW|RTLD_LOCAL);if(!lib)return;
  auto sym=[&](const char*n){return dlsym(lib,n);};
#endif
  create=reinterpret_cast<Create>(sym("rd_host_create"));
  destroy=reinterpret_cast<Destroy>(sym("rd_host_destroy"));
  present=reinterpret_cast<Present>(sym("rd_host_present"));
  pcm=reinterpret_cast<Pcm>(sym("rd_host_pcm"));
  pump=reinterpret_cast<Pump>(sym("rd_host_pump"));
  buttons=reinterpret_cast<Buttons>(sym("rd_host_buttons"));
  title=reinterpret_cast<Title>(sym("rd_host_title"));
  version=reinterpret_cast<Version>(sym("rd_host_abi_version"));
  ready=create&&destroy&&present&&pcm&&pump&&buttons&&title&&version&&version()==RD_HOST_ABI_VERSION;
 }
};
inline Api& api(){static Api a;return a;}
}
