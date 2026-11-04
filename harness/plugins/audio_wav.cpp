#include "rd_plugin.h"
#include <cstdio>
namespace {
static void w16(FILE *f,uint16_t x){std::fputc(x&255,f);std::fputc(x>>8,f);}
static void w32(FILE *f,uint32_t x){w16(f,uint16_t(x));w16(f,uint16_t(x>>16));}
static int save(const char *path,const int16_t *sample,uint32_t n,uint32_t rate){
 if(!path||!sample||n>441000||rate<8000||rate>192000)return 0;
 FILE *f=std::fopen(path,"wb");if(!f)return 0;
 std::fwrite("RIFF",1,4,f);w32(f,36+2*n);std::fwrite("WAVEfmt ",1,8,f);
 w32(f,16);w16(f,1);w16(f,1);w32(f,rate);w32(f,rate*2);w16(f,2);w16(f,16);
 std::fwrite("data",1,4,f);w32(f,2*n);
 for(uint32_t i=0;i<n;++i)w16(f,uint16_t(sample[i]));
 int ok=!std::ferror(f);return std::fclose(f)==0&&ok;
}
const RD_AudioApi API={save};
const RD_Plugin PLUGIN={RD_ABI_VERSION,sizeof(RD_Plugin),RD_AUDIO,sizeof(API),"Headless WAV audio sink",&API};
}
extern "C" RD_EXPORT const RD_Plugin *rd_get_plugin_v1(void){return &PLUGIN;}
