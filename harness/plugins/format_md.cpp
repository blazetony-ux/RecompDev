#include "rd_native_discovery_v1.h"
#include <cstring>
namespace {
uint32_t be32(const uint8_t*p){return uint32_t(p[0])<<24|uint32_t(p[1])<<16|uint32_t(p[2])<<8|p[3];}
int inspect(const RD_SourceV1*s,RD_FormatResultV1*r){
 if(!s||!r||s->struct_size!=sizeof(*s)||s->abi_version!=RD_NATIVE_DISCOVERY_ABI||!s->read||r->struct_size!=sizeof(*r))return -1;
 *r={};r->abi_version=RD_NATIVE_DISCOVERY_ABI;r->struct_size=sizeof(*r);
 if(s->byte_size<0x200||s->byte_size>64ull*1024*1024)return 0;
 uint8_t h[0x110]{};if(!s->read(s->ctx,0,h,sizeof(h)))return -1;
 if(std::memcmp(h+0x100,"SEGA",4))return 0;
 uint32_t sp=be32(h),pc=be32(h+4);
 r->platform=RD_PLATFORM_MD;r->cpu=RD_CPU_M68000;r->entry=pc;
 r->executable_offset=0;r->executable_size=s->byte_size;
 // A cartridge header alone does not prove the entry is executable.
 if((pc&1)||pc>=s->byte_size || pc<0x200||sp==0){r->status=RD_INSPECT_BLOCKED;
   std::strncpy(r->evidence,"SEGA header, but reset vectors not qualified",sizeof(r->evidence)-1);
 }else {r->status=RD_INSPECT_MATCH;std::strncpy(r->evidence,"SEGA header and bounded even-aligned 68000 reset PC; no code semantics verified",sizeof(r->evidence)-1);}
 return 1;
}
const RD_FormatApiV1 API={RD_NATIVE_DISCOVERY_ABI,sizeof(RD_FormatApiV1),inspect};
const RD_Plugin PLUGIN={RD_ABI_VERSION,sizeof(RD_Plugin),RD_FORMAT_KIND,sizeof(API),"Mega Drive cartridge structure",&API};
}
extern "C" RD_EXPORT const RD_Plugin*rd_get_plugin_v1(void){return &PLUGIN;}
