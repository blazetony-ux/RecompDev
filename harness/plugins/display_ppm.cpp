#include "rd_plugin.h"
#include <cstdio>
namespace {
static int save(const char *path,const uint32_t *pixels,uint32_t w,uint32_t h){
 if(!path||!pixels||!w||!h||w>4096||h>4096)return 0;
 auto* f=std::fopen(path,"wb");if(!f)return 0;
 int ok=std::fprintf(f,"P6\n%u %u\n255\n",w,h)>0;
 for(size_t i=0;ok&&i<size_t(w)*h;++i){
  const uint32_t p=pixels[i];const uint8_t rgb[3]={uint8_t(p>>16),uint8_t(p>>8),uint8_t(p)};
  ok=std::fwrite(rgb,1,3,f)==3;
 }
 return std::fclose(f)==0&&ok;
}
const RD_DisplayApi API={save};
const RD_Plugin PLUGIN={RD_ABI_VERSION,sizeof(RD_Plugin),RD_DISPLAY,sizeof(API),"Headless PPM display sink",&API};
}
extern "C" RD_EXPORT const RD_Plugin *rd_get_plugin_v1(void){return &PLUGIN;}
