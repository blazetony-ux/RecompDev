#include "rd_sms_mode4.h"
#include <algorithm>
#include <array>
#include <cstdint>

namespace {
constexpr unsigned MASK=0x3fffu;
inline uint32_t color(uint8_t c) {
 return 0xff000000u | (uint32_t(c&3u)*85u<<16) |
    (uint32_t((c>>2)&3u)*85u<<8) | (uint32_t((c>>4)&3u)*85u);
}
inline unsigned pixel(const uint8_t* vram,unsigned pattern,unsigned px,unsigned py) {
 const unsigned off=(pattern*32u+py*4u)&MASK, bit=7u-px;
 unsigned ci=0;
 for(unsigned plane=0;plane<4;++plane)
  ci|=unsigned((vram[(off+plane)&MASK]>>bit)&1u)<<plane;
 return ci;
}
}
extern "C" RD_SMS_API uint32_t rd_sms_mode4_abi(void){return RD_SMS_MODE4_ABI;}
extern "C" RD_SMS_API int rd_sms_mode4_render(const uint8_t* vram,uint32_t vram_size,
 const uint8_t* cram,uint32_t cram_size,const uint8_t* regs,uint32_t regs_size,
 uint32_t* pixels,uint32_t pixel_count,rd_sms_mode4_stats* stats) {
 if(!vram||!cram||!regs||!pixels||vram_size!=16384u||cram_size!=32u||
    regs_size!=16u||pixel_count!=RD_SMS_MODE4_WIDTH*RD_SMS_MODE4_HEIGHT) return 0;
 rd_sms_mode4_stats result{};result.abi=RD_SMS_MODE4_ABI;
 const unsigned bgbase=(unsigned(regs[2]&0x0eu)<<10)&MASK;
 const unsigned satbase=(unsigned(regs[5]&0x7eu)<<7)&MASK;
 result.sat_base=satbase;
 unsigned sprite_count=64;
 // In 192-line mode $D0 marks the end of sprite entries, even if sprites
 // are hidden or offscreen. Sprite Y is drawn at (Y+1) modulo 256.
 for(unsigned i=0;i<64;++i){
  if(vram[(satbase+i)&MASK]==0xd0u){sprite_count=i;result.flags|=1u;break;}
 }
 result.sprites_in_sat=sprite_count;
 const unsigned tall=(regs[1]&2u)?16u:8u;
 const unsigned zoom=(regs[1]&1u)?2u:1u;
 const unsigned sprite_height=tall*zoom;
 const unsigned sprite_pattern_base=(regs[6]&4u)?256u:0u;
 // Render each scanline with fixed eight-sprite evaluation capacity; earliest
 // SAT entry wins when sprites overlap. Background priority only masks an
 // opaque tile pixel; palette index zero allows sprite pixels through.
 for(unsigned y=0;y<192;++y){
  std::array<uint8_t,256> bg_high_opaque{};
  for(unsigned x=0;x<256;++x){
   // Preserve the production v0.4.9.1 background addressing convention; its
   // scrolling/scanline accuracy is a separate, independently testable issue.
   const unsigned sx=(x+unsigned(regs[8]))&255u;
   const unsigned sy=(y+unsigned(regs[9]))%224u;
   const unsigned addr=(bgbase+(((sy/8u)*32u+sx/8u)*2u))&MASK;
   const unsigned attr=unsigned(vram[addr])|(unsigned(vram[(addr+1u)&MASK])<<8);
   const unsigned tile=attr&0x1ffu;
   const unsigned px=(attr&0x200u)?7u-(sx&7u):(sx&7u);
   const unsigned py=(attr&0x400u)?7u-(sy&7u):(sy&7u);
   const unsigned ci=pixel(vram,tile,px,py);
   bg_high_opaque[x]=((attr&0x1000u)&&ci)?1u:0u;
   pixels[y*256u+x]=color(cram[((attr&0x800u)?16u:0u)+ci]);
  }
  std::array<unsigned,8> active{};unsigned active_count=0;
  for(unsigned i=0;i<sprite_count;++i){
   const unsigned sy=(unsigned(vram[(satbase+i)&MASK])+1u)&255u;
   const unsigned line=(y+256u-sy)&255u;
   if(line>=sprite_height)continue;
   if(active_count==8){++result.scanline_sprite_overflows;break;}
   active[active_count++]=i;
  }
  if(active_count)++result.scanlines_with_sprites;
  std::array<uint8_t,256> sprite_claimed{};
  for(unsigned k=0;k<active_count;++k){
   const unsigned i=active[k];
   const unsigned xx=(satbase+0x80u+i*2u)&MASK;
   const unsigned x0=unsigned(vram[xx]);
   const int left=(regs[0]&0x08u)?int(x0)-8:int(x0);
   const unsigned sy=(unsigned(vram[(satbase+i)&MASK])+1u)&255u;
   const unsigned line=((y+256u-sy)&255u)/zoom;
   unsigned tile=unsigned(vram[(xx+1u)&MASK]);
   if(tall==16u)tile&=~1u;
   tile=sprite_pattern_base+tile+(line>>3u);
   const unsigned py=line&7u;
   for(unsigned pos=0;pos<8u*zoom;++pos){
    const int px=left+int(pos);
    if(px<0||px>=256)continue;
    const unsigned ci=pixel(vram,tile,pos/zoom,py);
    if(!ci)continue;
    if(sprite_claimed[unsigned(px)]){++result.overlapping_sprite_pixels;continue;}
    sprite_claimed[unsigned(px)]=1;
    if(bg_high_opaque[unsigned(px)]){++result.foreground_masked_pixels;continue;}
    pixels[y*256u+unsigned(px)]=color(cram[16u+ci]);
    ++result.visible_sprite_pixels;
   }
  }
 }
 if(stats)*stats=result;
 return 1;
}
