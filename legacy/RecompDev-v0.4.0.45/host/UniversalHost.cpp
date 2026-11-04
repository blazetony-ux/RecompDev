// v0.4.0.22 experimental universal PC host, runs an author-generated device
// demonstration; NOT an authentic native-game port or SMS parity claim.
// Win32 GDI + waveOut frontend. Same generic sink/device APIs run headlessly.
#include "../hardware/adapters/sms_machine.hpp"
#include "../hardware/adapters/alternate.hpp"
#include <cstdlib>
#include <iostream>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <mmsystem.h>
#pragma comment(lib,"user32.lib")
#pragma comment(lib,"gdi32.lib")
#pragma comment(lib,"winmm.lib")
#endif
using namespace recomp::hw;
namespace {
class LastFrame final:public FrameSink {
 public:Frame frame;void submit(const Frame& f)override{f.validate();frame=f;}
};
class BufferedSound final:public AudioSink {
 public:u32 sample_rate=0,channels=0;std::vector<std::int16_t> samples;
 void submit(const PcmBlock& b)override{b.validate();
  if(sample_rate && (sample_rate!=b.sample_rate||channels!=b.channels))
   throw std::invalid_argument("HOST_AUDIO_FORMAT_CHANGED");
  sample_rate=b.sample_rate;channels=b.channels;
  if(samples.size()+b.samples.size()>200000)throw std::length_error("HOST_AUDIO_BUFFER_LIMIT");
  samples.insert(samples.end(),b.samples.begin(),b.samples.end());}
};
struct Demo {
 std::shared_ptr<LastFrame> video=std::make_shared<LastFrame>();
 std::shared_ptr<BufferedSound> sound=std::make_shared<BufferedSound>();
 recomp::hw::sms::Machine machine;
 Runtime runtime{3579545,60,44100};
 u64 buttons=0;u64 index=0;
 Demo(){
  runtime.bus().attach(machine.vdp());runtime.bus().attach(machine.psg());runtime.bus().attach(machine.controller());
  runtime.bus().write({Space::IO,0x7f},0x80);runtime.bus().write({Space::IO,0x7f},0x01);
  runtime.bus().write({Space::IO,0x7f},0x90);
  // PSG and input are also generic, but this standalone visual demo only
  // needs the VDP route and a documented input timeline.
  runtime.video(machine,video);runtime.audio(machine,sound);runtime.input(machine);
  runtime.record_input(0,{0,0,0,0});
  auto vdp=machine.vdp();
  // Author-created tile pattern and palette; never a commercial ROM asset.
  vdp->cram[1]=0x03;vdp->cram[2]=0x0c;vdp->regs[2]=0x0e;
  vdp->vram[0x3800]=0;vdp->vram[0x3801]=0;
  for(unsigned y=0;y<8;++y)for(unsigned plane=0;plane<4;++plane)
   vdp->vram[y*4+plane]=plane==0?(y%2?0xaa:0x55):0;
 }
 void tick(){
  // Device demonstration deliberately uses different physical registers
  // from a real Z80 game. Generated game integration is a later gate.
  runtime.record_input(runtime.cycles(),{0,buttons,0,0});
  machine.vdp()->regs[8]=std::uint8_t(index++);
  runtime.advance(59660); // approximate CPU cycles/frame for visual smoke
 }
};
}
#ifdef _WIN32
static Demo* instance=nullptr;
static LRESULT CALLBACK proc(HWND h,UINT msg,WPARAM w,LPARAM l){
 switch(msg){
 case WM_DESTROY:PostQuitMessage(0);return 0;
 case WM_KEYDOWN:case WM_KEYUP:{bool down=msg==WM_KEYDOWN;
   if(w==VK_ESCAPE&&down){DestroyWindow(h);return 0;}
   u64 bit=0;switch(w){case VK_LEFT:bit=button::Left;break;case VK_RIGHT:bit=button::Right;break;
   case VK_UP:bit=button::Up;break;case VK_DOWN:bit=button::Down;break;
   case 'Z':bit=button::A;break;case 'X':bit=button::B;break;}
   if(bit&&instance){if(down)instance->buttons|=bit;else instance->buttons&=~bit;}return 0;}
 case WM_PAINT:{PAINTSTRUCT ps{};HDC dc=BeginPaint(h,&ps);
   if(instance&&!instance->video->frame.pixels.empty()){
    auto &f=instance->video->frame;BITMAPINFO bi{};
    bi.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);bi.bmiHeader.biWidth=LONG(f.width);
    bi.bmiHeader.biHeight=-LONG(f.height);bi.bmiHeader.biPlanes=1;
    bi.bmiHeader.biBitCount=32;bi.bmiHeader.biCompression=BI_RGB;
    RECT r{};GetClientRect(h,&r);
    StretchDIBits(dc,0,0,r.right,r.bottom,0,0,int(f.width),int(f.height),
      f.pixels.data(),&bi,DIB_RGB_COLORS,SRCCOPY);
   }EndPaint(h,&ps);return 0;}
 }return DefWindowProc(h,msg,w,l);
}
int main(){Demo demo;instance=&demo;demo.tick();
 WNDCLASSA wc{};wc.lpfnWndProc=proc;wc.hInstance=GetModuleHandle(nullptr);
 wc.lpszClassName="RecompDevUniversalHost";wc.hCursor=LoadCursor(nullptr,IDC_ARROW);
 if(!RegisterClassA(&wc))return 2;
 HWND h=CreateWindowExA(0,wc.lpszClassName,"RecompDev Universal Device Demo (Synthetic)",
 WS_OVERLAPPEDWINDOW|WS_VISIBLE,CW_USEDEFAULT,CW_USEDEFAULT,800,625,nullptr,nullptr,wc.hInstance,nullptr);
 if(!h)return 3;
 // Host audio output remains optional; falling back to headless audio is valid.
 demo.sound->samples.clear();
 WAVEFORMATEX fmt={WAVE_FORMAT_PCM,WORD(demo.sound->channels),DWORD(demo.sound->sample_rate),
  DWORD(demo.sound->sample_rate*demo.sound->channels*2),WORD(demo.sound->channels*2),16,0};HWAVEOUT out=nullptr;
 if(waveOutOpen(&out,WAVE_MAPPER,&fmt,0,0,CALLBACK_NULL)!=MMSYSERR_NOERROR)out=nullptr;
 WAVEHDR hdr{};std::vector<std::int16_t> wave_samples;
 MSG msg{};bool running=true;
 while(running){
  while(PeekMessage(&msg,nullptr,0,0,PM_REMOVE)){if(msg.message==WM_QUIT){running=false;break;}
   TranslateMessage(&msg);DispatchMessage(&msg);}
  if(!running)break;
  demo.tick();InvalidateRect(h,nullptr,FALSE);
  if(out&&(!hdr.lpData||(hdr.dwFlags&WHDR_DONE))){
   if(hdr.dwFlags&WHDR_PREPARED)waveOutUnprepareHeader(out,&hdr,sizeof(hdr));
   hdr={};wave_samples.swap(demo.sound->samples);
   if(!wave_samples.empty()){
    hdr.lpData=reinterpret_cast<LPSTR>(wave_samples.data());
    hdr.dwBufferLength=DWORD(wave_samples.size()*sizeof(std::int16_t));
    if(waveOutPrepareHeader(out,&hdr,sizeof(hdr))==MMSYSERR_NOERROR)waveOutWrite(out,&hdr,sizeof(hdr));
   }
  }else demo.sound->samples.clear();
  Sleep(16);
 }
 if(out){waveOutReset(out);if(hdr.dwFlags&WHDR_PREPARED)waveOutUnprepareHeader(out,&hdr,sizeof(hdr));waveOutClose(out);}
 return 0;
}
#else
int main(int argc,char**argv){
 // Two different devices, clocks and video sizes use identical sink contracts.
 Demo a;a.tick();if(a.video->frame.width!=256)return 2;
 auto src=std::make_shared<recomp::hw::alternate::Panel>();Runtime b(2000000,50,16000);
 auto frames=std::make_shared<HeadlessFrames>();auto audio=std::make_shared<HeadlessAudio>();
 b.bus().attach(src);b.video(*src,frames);b.audio(*src,audio);b.input(*src);
 b.record_input(0,{0,button::A,0,0});b.bus().write({Space::Memory,0x4000},44);
 b.advance(40000);
 if(frames->fingerprints.size()!=1||frames->last_width!=96||audio->total_samples!=320)return 3;
 std::cout<<"UNIVERSAL_HOST_TWO_DEVICE_SYNTHETIC_PASS NOT_GAMEPLAY_PARITY\n";
 return 0;
}
#endif
