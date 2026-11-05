#pragma once
/* Console-specific, dynamically loadable VDP renderer. The generic host has no
 * knowledge of Sega, Z80, SAT or palette layouts. Staged projects only. */
#include "rd_sms_mode4.h"
#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include <string>
#ifdef _WIN32
# ifndef NOMINMAX
#  define NOMINMAX 1
# endif
# ifndef WIN32_LEAN_AND_MEAN
#  define WIN32_LEAN_AND_MEAN 1
# endif
# include <windows.h>
#else
# include <dlfcn.h>
#endif
namespace rd_sms_mode4_bridge {
using render_fn=int (*)(const uint8_t*,uint32_t,const uint8_t*,uint32_t,
                          const uint8_t*,uint32_t,uint32_t*,uint32_t,rd_sms_mode4_stats*);
using version_fn=uint32_t (*)();
struct Loaded {
 render_fn render=nullptr;
 Loaded(){
  const char* path=std::getenv("RECOMPDEV_SMS_MODE4_DLL");
  if(!path||!*path)throw std::runtime_error("SMS_VIDEO_PLUGIN_MISSING: RECOMPDEV_SMS_MODE4_DLL not specified");
#ifdef _WIN32
  HMODULE h=LoadLibraryA(path);
  if(!h)throw std::runtime_error("SMS_VIDEO_PLUGIN_LOAD_FAILED: "+std::string(path));
  const auto version=reinterpret_cast<version_fn>(GetProcAddress(h,"rd_sms_mode4_abi"));
  render=reinterpret_cast<render_fn>(GetProcAddress(h,"rd_sms_mode4_render"));
#else
  void* h=dlopen(path,RTLD_NOW|RTLD_LOCAL);
  if(!h)throw std::runtime_error("SMS_VIDEO_PLUGIN_LOAD_FAILED: "+std::string(dlerror()));
  const auto version=reinterpret_cast<version_fn>(dlsym(h,"rd_sms_mode4_abi"));
  render=reinterpret_cast<render_fn>(dlsym(h,"rd_sms_mode4_render"));
#endif
  if(!version||!render||version()!=RD_SMS_MODE4_ABI)
   throw std::runtime_error("SMS_VIDEO_PLUGIN_ABI_MISMATCH");
 }
};
inline void render(const uint8_t* vram,const uint8_t* cram,const uint8_t* regs,
                   uint32_t* pixels,uint64_t ordinal) {
 static Loaded plugin;
 rd_sms_mode4_stats stats{};
 if(!plugin.render(vram,16384,cram,32,regs,16,pixels,256*192,&stats))
  throw std::runtime_error("SMS_VIDEO_PLUGIN_RENDER_FAILED");
 const char* file=std::getenv("RECOMPDEV_SMS_VIDEO_STATS");
 if(file&&*file){
  std::FILE* f=std::fopen(file,"ab+");
  if(f){
   std::fseek(f,0,SEEK_END);
   if(std::ftell(f)==0)
    std::fputs("frame,sat_base,sat_entries,scanline_overflows,sprite_overlaps,visible_sprite_pixels,foreground_masked_pixels,scanlines_with_sprites,terminator_found\n",f);
   std::fprintf(f,"%llu,%u,%u,%u,%u,%u,%u,%u,%u\n",
    static_cast<unsigned long long>(ordinal),stats.sat_base,stats.sprites_in_sat,
    stats.scanline_sprite_overflows,stats.overlapping_sprite_pixels,
    stats.visible_sprite_pixels,stats.foreground_masked_pixels,
    stats.scanlines_with_sprites,stats.flags&1u);
   std::fclose(f);
  }
 }
}
}
