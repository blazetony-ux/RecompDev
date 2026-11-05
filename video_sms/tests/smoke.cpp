#include "rd_sms_mode4.h"
#include "hardware/adapters/sms.hpp"
#include <array>
#include <cstdlib>
#include <cstdint>
#include <iostream>
// Release builds define NDEBUG: checks must not use disabled assert macros.
#define CHECK(expr) do { if(!(expr)) {std::cerr<<"VIDEO_TEST_FAIL "<<__LINE__<<" "<<#expr<<"\n";std::exit(2);} } while(false)
using u8=std::uint8_t;
using u32=std::uint32_t;
struct Rig {
 std::array<u8,16384> vram{};std::array<u8,32> cram{};std::array<u8,16> regs{};
 std::array<u32,256*192> pixels{};rd_sms_mode4_stats stats{};
 Rig(){regs[2]=0x0e;regs[5]=0x7e;regs[6]=0;regs[1]=0x40;
  vram[0x3f00]=0xd0;cram[1]=0x03;cram[17]=0x0c;cram[18]=0x30;
  for(unsigned row=0;row<8;++row){vram[32u+row*4u]=0xff;vram[64u+row*4u+1u]=0xff;}}
 void sprite(unsigned n,u8 y,u8 x,u8 tile){vram[0x3f00+n]=y;vram[0x3f80+n*2]=x;vram[0x3f81+n*2]=tile;vram[0x3f00+n+1]=0xd0;}
 bool render(){return rd_sms_mode4_render(vram.data(),16384,cram.data(),32,regs.data(),16,pixels.data(),256*192,&stats)==1;}
};
int main(){
 CHECK(rd_sms_mode4_abi()==RD_SMS_MODE4_ABI);
 Rig r;CHECK(r.render());CHECK(r.pixels[30*256+20]!=0xffff0000u);CHECK(r.stats.visible_sprite_pixels==0);
 // Background-only video must be byte-for-byte identical to the frozen renderer.
 {const auto before=recomp::hw::sms::render_mode4(r.vram,r.cram,r.regs);
  CHECK(std::equal(before.pixels.begin(),before.pixels.end(),r.pixels.begin()));}
 r.sprite(0,19,20,1);CHECK(r.render());CHECK(r.pixels[20*256+20]==0xff00ff00u);
 CHECK(r.stats.visible_sprite_pixels==64);CHECK(r.stats.scanlines_with_sprites==8);
 // Transparent color zero reveals background.
 r.vram[32]=0x7f;CHECK(r.render());CHECK(r.pixels[20*256+20]!=0xff00ff00u);
 // Priority background tile masks sprites only where BG pixel is not zero.
 r.vram[32]=0xff;r.vram[0x3884]=2;r.vram[0x3885]=0x10; // tile 2, high priority
 CHECK(r.render());CHECK(r.pixels[20*256+20]!=0xff00ff00u);
 r.vram[0x3885]=0;CHECK(r.render());CHECK(r.pixels[20*256+20]==0xff00ff00u);
 // Sprite bank selection, early clock and 8x16 sprite pair.
 r.regs[0]=8;r.sprite(0,19,20,1);CHECK(r.render());CHECK(r.pixels[20*256+12]==0xff00ff00u);
 r.regs[0]=0;r.regs[6]=4;
 for(unsigned line=0;line<8;++line)r.vram[0x2000+32+line*4+1]=0xff;
 CHECK(r.render());CHECK(r.pixels[20*256+20]==0xff0000ffu);
 r.regs[6]=0;r.regs[1]|=2; // 8x16 uses aligned pattern even/odd
 r.sprite(0,19,20,1);CHECK(r.render());CHECK(r.stats.scanlines_with_sprites==16);
 // Magnification duplicates both axes in the SMS2/idealized model.
 r.regs[1]|=1;CHECK(r.render());CHECK(r.stats.scanlines_with_sprites==32);
 // Lowest SAT index wins, two entries on same scanline overlap.
 r.regs[1]=0x40;r.sprite(0,19,20,1);r.sprite(1,19,20,2);
 CHECK(r.render());CHECK(r.pixels[20*256+20]==0xff00ff00u);CHECK(r.stats.overlapping_sprite_pixels>0);
 // Nine sprites on one scanline exceed evaluation capacity.
 for(unsigned i=0;i<9;++i)r.sprite(i,19,static_cast<u8>(i*8),1);
 CHECK(r.render());CHECK(r.stats.scanline_sprite_overflows==8);
 CHECK(rd_sms_mode4_render(nullptr,0,r.cram.data(),32,r.regs.data(),16,r.pixels.data(),256*192,&r.stats)==0);
 std::cout<<"RD_SMS_MODE4_SPRITES_PASS abi=1.0 transparent priority bank magnify earlyclock tall overflow collision\n";
}
