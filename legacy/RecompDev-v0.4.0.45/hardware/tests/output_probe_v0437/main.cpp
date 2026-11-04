// Deterministic, source-owned hardware fixture, NOT an emulated or translated game.
// Uses the exact SMS mode-4 renderer, PSG implementation, PPM and WAV serializers
// used in the generated native application's hardware presentation layer.
#include "hardware/adapters/sms.hpp"
#include "hardware/image_io.hpp"
#include "hardware/wav.hpp"
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>

int main(int argc,char**argv){
 if(argc!=2){std::cerr<<"Usage: RecompDevNativeOutputProbe <output-prefix>\n";return 2;}
 try {
  using namespace recomp::hw;
  sms::Vdp vdp;
  // Two visible tiles: left red (palette entry 1), right blue (entry 4).
  // This deliberate input is independent of ROM/Ghidra/CPU execution.
  vdp.regs[2]=14;
  for(unsigned row=0;row<8;++row){
   vdp.vram[row*4]=0xff;            // tile 0, bit plane 0 => palette 1
   vdp.vram[32+row*4+2]=0xff;       // tile 1, plane 2 => palette 4
  }
  for(unsigned y=0;y<24;++y)for(unsigned x=0;x<32;++x){
   unsigned a=0x3800+(y*32+x)*2;
   vdp.vram[a]=std::uint8_t(x>=16?1:0);
   vdp.vram[a+1]=0;
  }
  // Exercise actual device CRAM port logic, not just direct palette assignment.
  vdp.write({Space::IO,0x81},1);vdp.write({Space::IO,0x81},0xc0);
  vdp.write({Space::IO,0x80},3); // CRAM index 1, #FF0000
  vdp.write({Space::IO,0x81},4);vdp.write({Space::IO,0x81},0xc0);
  vdp.write({Space::IO,0x80},0x30); // CRAM index 4, #0000FF
  auto frame=vdp.render();frame.validate();
  if(frame.width!=256||frame.height!=192||frame.pixels.size()!=49152)
   throw std::runtime_error("FRAME_DIMENSIONS_INVALID");
  if(!write_rgb_ppm(std::string(argv[1])+".ppm",frame))throw std::runtime_error("PPM_WRITE_FAILED");
  sms::Psg psg;
  // SN76489 tone 0 period 16, full volume. Other channels remain muted.
  psg.write({Space::IO,0x7f},0x80);
  psg.write({Space::IO,0x7f},0x01);
  psg.write({Space::IO,0x7f},0x90);
  PcmBlock block;block.sample_rate=44100;block.channels=1;
  for(std::uint64_t n=0;n<4410;++n){
   const std::uint64_t cycle=n*3579545ull/44100ull;
   block.samples.push_back(psg.sample(cycle));
  }
  if(!write_pcm16_wav(std::string(argv[1])+".wav",block))throw std::runtime_error("WAV_WRITE_FAILED");
  std::cout<<"NATIVE_OUTPUT_PROBE=CREATED\n";
  return 0;
 }catch(const std::exception& e){std::cerr<<"NATIVE_OUTPUT_ERROR="<<e.what()<<"\n";return 3;}
}
