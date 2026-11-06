#include "rd_native_discovery_v1.h"
#include <cstring>
#include <initializer_list>
namespace {
uint32_t le32(const uint8_t*p){return uint32_t(p[0])|uint32_t(p[1])<<8|uint32_t(p[2])<<16|uint32_t(p[3])<<24;}
int read_user(const RD_SourceV1*s,uint32_t sector,uint32_t user_off,uint64_t pos,uint8_t*b,uint32_t n){
 uint64_t lba=pos/2048,rest=pos%2048;
 while(n){if(lba>UINT64_MAX/sector)return 0;
  uint64_t at=lba*sector+user_off+rest;
  uint32_t take=uint32_t((2048-rest)<n?2048-rest:n);
  if(at>s->byte_size||take>s->byte_size-at||!s->read(s->ctx,at,b,take))return 0;
  b+=take;n-=take;rest=0;++lba;
 }return 1;
}
int exe(const uint8_t*header,uint64_t available,RD_FormatResultV1*r,uint64_t at){
 if(available<0x800||std::memcmp(header,"PS-X EXE",8))return 0;
 uint32_t pc=le32(header+0x10),addr=le32(header+0x18),len=le32(header+0x1c);
 if(!len||len>available-0x800||pc==0||addr==0)return 0;
 r->platform=RD_PLATFORM_PS1;r->cpu=RD_CPU_MIPS_R3000A;r->status=RD_INSPECT_MATCH;
 r->entry=pc;r->executable_offset=at;r->executable_size=uint64_t(len)+0x800;
 std::strncpy(r->evidence,"PS-X EXE header and bounded load section; MIPS code unverified",sizeof(r->evidence)-1);
 return 1;
}
int inspect(const RD_SourceV1*s,RD_FormatResultV1*r){
 if(!s||!r||s->struct_size!=sizeof(*s)||s->abi_version!=RD_NATIVE_DISCOVERY_ABI||!s->read||r->struct_size!=sizeof(*r))return -1;
 *r={};r->abi_version=RD_NATIVE_DISCOVERY_ABI;r->struct_size=sizeof(*r);
 uint8_t h[0x800]{};
 if(s->byte_size>=0x800 && s->read(s->ctx,0,h,sizeof(h)) && exe(h,s->byte_size,r,0))return 1;
 // ISO9660 primary volume descriptor (2048 sector data or raw CD Mode 2/Form 1 2352 sector).
 for(uint32_t sector:{2048u,2352u}){
  uint32_t user_off=0;
  if(sector==2352){
   uint8_t header[16]{};
   if(!s->read(s->ctx,16ull*2352,header,16))continue;
   // Raw CD sectors must have the standard sync pattern and Mode 1/2 byte.
   if(header[0]!=0 || header[11]!=0 || header[12]!=0 || header[13]!=0 || header[14]!=2)continue;
   bool sync=true;for(int j=1;j<11;++j)if(header[j]!=0xff)sync=false;
   if(!sync||(header[15]!=1&&header[15]!=2))continue;
   user_off=header[15]==1?16:24;
  }
  uint8_t pvd[2048]{};
  if(!read_user(s,sector,user_off,16ull*2048,pvd,sizeof(pvd))||pvd[0]!=1||std::memcmp(pvd+1,"CD001",5)||pvd[6]!=1)continue;
  r->platform=RD_PLATFORM_PS1;r->cpu=RD_CPU_UNKNOWN;r->status=RD_INSPECT_BLOCKED;r->sector_size=sector;
  std::strncpy(r->evidence,"ISO9660 volume verified; no verified PS-X EXE within bounded root inventory",sizeof(r->evidence)-1);
  const uint8_t*dir=pvd+156;
  uint32_t extent=le32(dir+2),size=le32(dir+10);
  if(dir[0]<34||!extent||!size||size>16u*1024*1024)return 1;
  // Bounded root directory walk; no indefinite raw scan / no payload export.
  uint32_t at=0;uint32_t files=0;
  while(at<size && files<1024){
   uint8_t n=0;if(!read_user(s,sector,user_off,uint64_t(extent)*2048+at,&n,1))break;
   if(!n){at+=2048-(at%2048);continue;}
   if(n<34||at+n>size)break;
   uint8_t rec[256]{};if(!read_user(s,sector,user_off,uint64_t(extent)*2048+at,rec,n))break;
   const uint8_t namelen=rec[32];
   if(namelen<=n-33 && !(rec[25]&2) && namelen>1){
    ++files;
    uint32_t start=le32(rec+2),bytes=le32(rec+10);
    if(bytes>=0x800&&bytes<32u*1024*1024){
     uint8_t eh[0x800]{};
     if(read_user(s,sector,user_off,uint64_t(start)*2048,eh,sizeof(eh))&&exe(eh,bytes,r,uint64_t(start)*sector+user_off))break;
    }
   }
   at+=n;
  }
  r->file_count=files;return 1;
 }
 return 0;
}
const RD_FormatApiV1 API={RD_NATIVE_DISCOVERY_ABI,sizeof(RD_FormatApiV1),inspect};
const RD_Plugin PLUGIN={RD_ABI_VERSION,sizeof(RD_Plugin),RD_FORMAT_KIND,sizeof(API),"PS1 PS-X EXE and ISO9660 sectors",&API};
}
extern "C" RD_EXPORT const RD_Plugin*rd_get_plugin_v1(void){return &PLUGIN;}
