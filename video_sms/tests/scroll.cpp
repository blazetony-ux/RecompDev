#include "rd_sms_mode4.h"
#include <array>
#include <cstdlib>
#include <cstdint>
#include <iostream>
#define CHECK(x) do {if(!(x)){std::cerr<<"SCROLL_TEST_FAIL line "<<__LINE__<<": "<<#x<<"\n";std::exit(2);}} while(0)
using u8=std::uint8_t; using u32=std::uint32_t;
int main(){
 std::array<u8,16384> v{}; std::array<u8,32> c{};std::array<u8,16> r{};
 std::array<u32,256*192> p{};
 r[1]=0x40;r[2]=0x0e;r[5]=0x7e;
 v[0x3f00]=0xd0; // empty sprite table
 // Three solid colours: tile 1=red, 2=green, 3=blue.
 for(unsigned row=0;row<8;++row){v[32+row*4]=0xff;v[64+row*4+1]=0xff;v[96+row*4+2]=0xff;}
 c[1]=3;c[2]=12;c[4]=48;c[18]=0x3f;
 for(unsigned y=0;y<28;++y){
  v[0x3800+y*64+0]=1; // first column of every tilemap row
  v[0x3800+y*64+31*2]=2; // last column
 }
 // Row 1 has a different first tile for testing vertical scroll.
 v[0x3800+64]=3;
 auto render=[&]{CHECK(rd_sms_mode4_render(v.data(),u32(v.size()),c.data(),u32(c.size()),
  r.data(),u32(r.size()),p.data(),u32(p.size()),nullptr)==1);};
 const u32 red=0xffff0000u, green=0xff00ff00u, blue=0xff0000ffu, white=0xffffffffu;
 render();CHECK(p[0]==red);
 r[8]=8;render();
 CHECK(p[8]==red);CHECK(p[0]==green); // positive R8 moves BG right
 r[0]=0x40;render(); // top 16 scanlines are unscrolled
 CHECK(p[0]==red);CHECK(p[8]==0xff000000u); // col 1 has tile 0
 CHECK(p[16*256]==green);CHECK(p[16*256+8]==red);
 r[0]=0;r[7]=2;r[8]=3;render();
 CHECK(p[0]==white);CHECK(p[2]==white); // fine-scroll backdrop
 CHECK(p[3]==red);
 r[8]=0;r[9]=8;render();
 CHECK(p[0]==blue); // vertical scroll by one tile
 r[0]=0x80;render();
 CHECK(p[0]==blue); // ordinary scroll region
 CHECK(p[192]==0xff000000u); // last eight columns ignore vertical R9
 r[0]=0x20;r[7]=2;render();
 CHECK(p[0]==white);CHECK(p[7]==white);CHECK(p[8]!=white); // left mask
 std::cout<<"RD_SMS_MODE4_SCROLL_REGISTERS_PASS direction top-right-lock fine-scroll backdrop left-mask\n";
}
