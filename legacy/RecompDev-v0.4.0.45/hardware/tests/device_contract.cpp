#include "../adapters/sms_machine.hpp"
#include "../adapters/alternate.hpp"
#include "../wav.hpp"
#include <cassert>
#include <iostream>
#include <stdexcept>
using namespace recomp::hw;
int main(int argc,char**argv){
 RateClock fast(44100,1000);assert(fast.consume(1)==44);assert(fast.consume(1)==44);
 auto fb=std::make_shared<HeadlessFrames>();auto snd=std::make_shared<HeadlessAudio>();
 sms::Machine machine; Runtime r(3579545,60,44100);
 r.bus().attach(machine.vdp());
 // A detached full SMS machine works through the same address and device rack.
 auto psg=machine.psg();auto pad=machine.controller();
 r.bus().attach(psg);r.bus().attach(pad);r.video(machine,fb);r.audio(machine,snd);r.input(machine);
 assert(r.bus().read({Space::IO,0xdc})==255);
 r.record_input(0,{0,button::Up|button::A,0,0});
 r.advance(1);assert(r.bus().read({Space::IO,0xdc})==0xee);
 r.record_input(1500,{0,button::Right|button::B,0,0});
 r.advance(1498);assert(r.bus().read({Space::IO,0xdc})==0xee);
 r.advance(1);assert(r.bus().read({Space::IO,0xdc})==0xd7);
 r.bus().write({Space::IO,0x7f},0x80);r.bus().write({Space::IO,0x7f},0x01);
 r.bus().write({Space::IO,0x7f},0x90);
 auto v=machine.vdp();v->cram[1]=3;v->regs[2]=0x0e;
 // Memory-mapped tile rendering: bit-plane 0 + tile table entry at 0x3800.
 v->vram[0]=0x80;v->vram[0x3800]=0;v->vram[0x3801]=0;
 Frame image=v->render();assert(image.width==256&&image.height==192);
 assert((image.pixels[0]&0x00ffffff)==0x00ff0000);
 const auto hash=frame_fingerprint(image);
 // Frame fingerprint must be a function of pixels/dimensions, not CPU identity.
 image.pixels[0]^=1;assert(frame_fingerprint(image)!=hash);
 assert(!r.bus().write({Space::Memory,0x4000},1));
 assert(r.bus().read({Space::Memory,0x4000})==255);
 r.advance(3579545-1500);
 assert(fb->fingerprints.size()==60);
 assert(snd->total_samples==44100);
 assert(snd->checksum!=0);
 PcmBlock block;block.sample_rate=44100;block.channels=1;
 block.samples={0,1000,-1000,32767,-32768};
 assert(argc>1&&write_pcm16_wav(argv[1],block));
 bool caught=false;
 try{r.bus().attach(std::make_shared<sms::Controller>());r.bus().read({Space::IO,0xdc});}catch(const std::runtime_error& e){caught=std::string(e.what())=="AMBIGUOUS_DEVICE_MAPPING";}
 assert(caught);
 caught=false;try{r.record_input(1,{0,0,0,0});}catch(const std::invalid_argument&){caught=true;}assert(caught);
 // Independent second platform with unrelated memory map, resolution, timing
 // and sound implementation, no code changes in shared Runtime.
 auto screen=std::make_shared<alternate::Panel>();Runtime other(2000000,50,16000);
 auto fb2=std::make_shared<HeadlessFrames>();auto snd2=std::make_shared<HeadlessAudio>();
 other.bus().attach(screen);other.video(*screen,fb2);other.audio(*screen,snd2);other.input(*screen);
 other.record_input(0,{0,button::B,0,0});other.bus().write({Space::Memory,0x4000},12);
 other.advance(2000000);
 assert(fb2->fingerprints.size()==50&&fb2->last_width==96&&fb2->last_height==64);
 assert(snd2->total_samples==16000&&other.bus().read({Space::Memory,0x4001})==button::B);
 assert(fb2->fingerprints.front()!=fb->fingerprints.front());
 // A CPU step split at any boundary must yield exact same frame/audio samples.
 auto a=std::make_shared<alternate::Panel>(),b=std::make_shared<alternate::Panel>();
 Runtime ra(2000000,50,16000),rb(2000000,50,16000);
 auto fa=std::make_shared<HeadlessFrames>();auto fb3=std::make_shared<HeadlessFrames>();
 auto sa=std::make_shared<HeadlessAudio>();auto sb=std::make_shared<HeadlessAudio>();
 ra.bus().attach(a);rb.bus().attach(b);ra.video(*a,fa);rb.video(*b,fb3);
 ra.audio(*a,sa);rb.audio(*b,sb);ra.input(*a);rb.input(*b);
 ra.record_input(12345,{0,button::A,0,0});rb.record_input(12345,{0,button::A,0,0});
 ra.advance(50000);rb.advance(5000);rb.advance(7345);rb.advance(37655);
 assert(fa->fingerprints==fb3->fingerprints);
 assert(sa->checksum==sb->checksum&&sa->total_samples==sb->total_samples);
 assert(a->render().pixels==b->render().pixels);
 std::cout<<"HARDWARE_RUNTIME_TWO_PLATFORMS_DETERMINISTIC_SYNTHETIC_PASS NOT_REFERENCE_PARITY\n";
}
