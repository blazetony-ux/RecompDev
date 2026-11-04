#include "rd_plugin.h"
#include <cstdio>
namespace {
static void* open(const char *path){return path?std::fopen(path,"wb"):nullptr;}
static int emit(void *p,const RD_Event *e){
 if(!p||!e||!e->kind)return 0;
 auto* f=static_cast<std::FILE*>(p);
 return std::fprintf(f,"{\"event\":\"%s\",\"step\":%llu,\"pc\":%u,\"physical\":%u,\"bank\":%u,\"opcode\":%u,\"cycles\":%u}\n",e->kind,(unsigned long long)e->index, unsigned(e->pc),e->physical,e->bank,unsigned(e->opcode),e->cycles)>0 && std::fflush(f)==0;
}
static void close(void *p){if(p)std::fclose(static_cast<std::FILE*>(p));}
const RD_DiscoveryApi API={open,emit,close};
const RD_Plugin PLUGIN={RD_ABI_VERSION,sizeof(RD_Plugin),RD_DISCOVERY,sizeof(API),"JSONL discovery event recorder",&API};
}
extern "C" RD_EXPORT const RD_Plugin *rd_get_plugin_v1(void){return &PLUGIN;}
