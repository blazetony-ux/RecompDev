// RecompDev experimental host frontend contract: framebuffer + input + audio.
// This is an author-created demonstration, NOT a Shinobi/native-game binary.
// Build on Windows: cl /EHsc /O2 StandaloneHost.cpp user32.lib gdi32.lib winmm.lib
// Non-Windows: c++ -std=c++17 StandaloneHost.cpp -o standalone-host (smoke mode only).
#include <array>
#include <cstdint>
#include <cstring>
#include <iostream>
#ifdef RECOMPDEV_GUEST_BRIDGE
#include "GuestBridge.hpp"
#endif
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <mmsystem.h>
#pragma comment(lib, "winmm.lib")
#pragma comment(lib, "gdi32.lib")
#pragma comment(lib, "user32.lib")
#endif
namespace recomp {
constexpr int width = 256, height = 192;
using Pixels = std::array<std::uint32_t, width * height>;
struct HostIO {
  Pixels pixels{};
  std::array<bool, 8> buttons{};
  std::array<std::int16_t, 735> audio_samples{}; // 44.1 kHz / 60 Hz mono
  bool render_guest() {
#ifdef RECOMPDEV_GUEST_BRIDGE
    std::uint32_t flags=0;
    for (unsigned i=0;i<buttons.size();++i) if (buttons[i]) flags|=(1u<<i);
    return recomp_guest_tick(flags,pixels.data(),pixels.size(),audio_samples.data(),audio_samples.size())==0;
#else
    return false;
#endif
  }
  void render_test_pattern(unsigned frame) {
    // Fixed synthetic pattern verifies the host window receives frame updates.
    for(int y=0;y<height;y++) for(int x=0;x<width;x++) {
      pixels[y*width+x]=0xff000000u | (((x+frame)&255u)<<16) | ((y&255u)<<8) | (frame&255u);
    }
  }
};
} // namespace recomp
#ifdef _WIN32
static recomp::HostIO state;
static WAVEHDR wave{};
static HWAVEOUT audio=nullptr;
static WAVEFORMATEX format={WAVE_FORMAT_PCM,1,44100,88200,2,16,0};
static void render_audio() {
  // Silence until a qualified guest PSG adapter produces PCM.
  if(!audio) return;
  if((wave.dwFlags&WHDR_PREPARED) && !(wave.dwFlags&WHDR_DONE))return;
  if(wave.dwFlags&WHDR_PREPARED)waveOutUnprepareHeader(audio,&wave,sizeof(wave));
  wave={};wave.lpData=(LPSTR)state.audio_samples.data();wave.dwBufferLength=sizeof(state.audio_samples);
  if(waveOutPrepareHeader(audio,&wave,sizeof(wave))==MMSYSERR_NOERROR)waveOutWrite(audio,&wave,sizeof(wave));
}
static LRESULT CALLBACK WindowProc(HWND hwnd,UINT message,WPARAM w,LPARAM l){
  switch(message){
    case WM_DESTROY:PostQuitMessage(0);return 0;
    case WM_KEYDOWN:case WM_KEYUP:{
      bool down=message==WM_KEYDOWN;
      if(w==VK_ESCAPE && down){DestroyWindow(hwnd);return 0;}
      if(w==VK_LEFT)state.buttons[0]=down;
      if(w==VK_RIGHT)state.buttons[1]=down;
      if(w==VK_UP)state.buttons[2]=down;
      if(w==VK_DOWN)state.buttons[3]=down;
      if(w=='Z')state.buttons[4]=down;
      if(w=='X')state.buttons[5]=down;
      return 0;
    }
    case WM_PAINT:{
      PAINTSTRUCT ps{};HDC dc=BeginPaint(hwnd,&ps);
      BITMAPINFO bmp{};bmp.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);
      bmp.bmiHeader.biWidth=recomp::width;bmp.bmiHeader.biHeight=-recomp::height;
      bmp.bmiHeader.biPlanes=1;bmp.bmiHeader.biBitCount=32;bmp.bmiHeader.biCompression=BI_RGB;
      RECT rect{};GetClientRect(hwnd,&rect);
      StretchDIBits(dc,0,0,rect.right,rect.bottom,0,0,recomp::width,recomp::height,
          state.pixels.data(),&bmp,DIB_RGB_COLORS,SRCCOPY);
      EndPaint(hwnd,&ps);return 0;
    }
  }
  return DefWindowProc(hwnd,message,w,l);
}
int main(){
  WNDCLASSA wc{};wc.lpfnWndProc=WindowProc;wc.hInstance=GetModuleHandle(nullptr);
  wc.lpszClassName="RecompDevHostDemo";wc.hCursor=LoadCursor(nullptr,IDC_ARROW);
  if(!RegisterClassA(&wc))return 2;
  HWND hwnd=CreateWindowExA(0,wc.lpszClassName,"RecompDev Host (synthetic demo, not a game)",
      WS_OVERLAPPEDWINDOW|WS_VISIBLE,CW_USEDEFAULT,CW_USEDEFAULT,800,625,nullptr,nullptr,wc.hInstance,nullptr);
  if(!hwnd)return 3;
  waveOutOpen(&audio,WAVE_MAPPER,&format,0,0,CALLBACK_NULL);
  MSG msg{};unsigned frame=0;
  while(true){
    while(PeekMessage(&msg,nullptr,0,0,PM_REMOVE)){
      if(msg.message==WM_QUIT)goto finished;
      TranslateMessage(&msg);DispatchMessage(&msg);
    }
#ifdef RECOMPDEV_GUEST_BRIDGE
    if (!state.render_guest()) {DestroyWindow(hwnd);break;}
#else
    state.render_test_pattern(frame++);
#endif
    render_audio();InvalidateRect(hwnd,nullptr,FALSE);Sleep(16);
  }
finished:
  if(audio){waveOutReset(audio);if(wave.dwFlags&WHDR_PREPARED)waveOutUnprepareHeader(audio,&wave,sizeof(wave));waveOutClose(audio);}
  return 0;
}
#else
int main(){
  recomp::HostIO host;
#ifdef RECOMPDEV_GUEST_BRIDGE
  if (!host.render_guest())return 2;
  std::uint32_t first=host.pixels[0];
  host.buttons[0]=true;
  if (!host.render_guest() || host.pixels[0]==first)return 3;
  std::cout<<"GUEST_BRIDGE_SYNTHETIC_PASS NO_GAMEPLAY_PARITY\n";
#else
  host.render_test_pattern(1);
  // Headless contract check, not a graphical application on this host.
  if(host.pixels[0]==0 || host.pixels.back()==0)return 1;
  std::cout<<"HOST_CONTRACT_SMOKE_ONLY NO_GAMEPLAY_PARITY\n";
#endif
  return 0;
}
#endif
