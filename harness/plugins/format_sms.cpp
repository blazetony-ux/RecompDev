#include "rd_native_discovery_v1.h"
#include <cstring>
#include <initializer_list>
namespace {
int inspect(const RD_SourceV1*s,RD_FormatResultV1*r){
 if(!s||!r||s->abi_version!=RD_NATIVE_DISCOVERY_ABI||s->struct_size!=sizeof(*s)||!s->read||r->struct_size!=sizeof(*r))return -1;
 *r={};r->struct_size=sizeof(*r);r->abi_version=RD_NATIVE_DISCOVERY_ABI;
 if(s->byte_size<0x4000 || s->byte_size>8ull*1024*1024)return 0;
 // SMS cartridge headers occur at ROM-relative 0x1ff0 / 0x3ff0 / 0x7ff0.
 bool header=false;for(uint64_t off:{0x1ff0ull,0x3ff0ull,0x7ff0ull}){
  uint8_t b[8]{};if(off+8<=s->byte_size&&s->read(s->ctx,off,b,8)&&!std::memcmp(b,"TMR SEGA",8)){header=true;break;}
 }
 if(!header)return 0;
 r->platform=RD_PLATFORM_SMS;r->cpu=RD_CPU_Z80_FAMILY;r->status=RD_INSPECT_MATCH;
 r->entry=0;r->executable_offset=0;r->executable_size=s->byte_size;
 std::strncpy(r->evidence,"TMR SEGA cartridge header; reset address is a candidate, not verified code",sizeof(r->evidence)-1);
 return 1;
}
const RD_FormatApiV1 API={RD_NATIVE_DISCOVERY_ABI,sizeof(RD_FormatApiV1),inspect};
const RD_Plugin PLUGIN={RD_ABI_VERSION,sizeof(RD_Plugin),RD_FORMAT_KIND,sizeof(API),"SMS cartridge structure",&API};
}
extern "C" RD_EXPORT const RD_Plugin*rd_get_plugin_v1(void){return &PLUGIN;}
