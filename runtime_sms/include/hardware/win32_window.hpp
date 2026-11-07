#pragma once
// Optional host display; the guest CPU and machine runtime never depend on Win32.
#include "core.hpp"
#include <chrono>
#include <thread>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
namespace recomp::hw {
class Win32Window {
 HWND hwnd_=nullptr;Frame last_;
 u64 buttons_=0;bool running_=true;
 static LRESULT CALLBACK proc(HWND h,UINT msg,WPARAM w,LPARAM l){
  auto* self=reinterpret_cast<Win32Window*>(GetWindowLongPtrA(h,GWLP_USERDATA));
  if(msg==WM_NCCREATE){auto* cs=reinterpret_cast<CREATESTRUCTA*>(l);SetWindowLongPtrA(h,GWLP_USERDATA,reinterpret_cast<LONG_PTR>(cs->lpCreateParams));return TRUE;}
  if(self){
   if(msg==WM_CLOSE){self->running_=false;DestroyWindow(h);return 0;}
   if(msg==WM_DESTROY){self->running_=false;return 0;}
   if(msg==WM_KEYDOWN||msg==WM_KEYUP){const bool down=msg==WM_KEYDOWN;u64 bit=0;
    switch(w){case VK_UP:bit=button::Up;break;case VK_DOWN:bit=button::Down;break;
      case VK_LEFT:bit=button::Left;break;case VK_RIGHT:bit=button::Right;break;
      case 'Z':bit=button::A;break;case 'X':bit=button::B;break;case VK_RETURN:bit=button::Start;break;}
    if(w==VK_ESCAPE&&down){self->running_=false;DestroyWindow(h);return 0;}
    if(bit){if(down)self->buttons_|=bit;else self->buttons_&=~bit;}return 0;
   }
   if(msg==WM_PAINT){PAINTSTRUCT ps{};auto dc=BeginPaint(h,&ps);
    if(!self->last_.pixels.empty()){
     BITMAPINFO bi{};bi.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);
     bi.bmiHeader.biWidth=LONG(self->last_.width);bi.bmiHeader.biHeight=-LONG(self->last_.height);
     bi.bmiHeader.biPlanes=1;bi.bmiHeader.biBitCount=32;bi.bmiHeader.biCompression=BI_RGB;
     RECT rc{};GetClientRect(h,&rc);
     StretchDIBits(dc,0,0,rc.right,rc.bottom,0,0,int(self->last_.width),int(self->last_.height),
       self->last_.pixels.data(),&bi,DIB_RGB_COLORS,SRCCOPY);
    }EndPaint(h,&ps);return 0;
   }
  }
  return DefWindowProcA(h,msg,w,l);
 }
 public:
 bool open(const char* title){
  HINSTANCE inst=GetModuleHandleA(nullptr);WNDCLASSA wc{};wc.lpfnWndProc=&proc;
  wc.hInstance=inst;wc.lpszClassName="RecompDevNativeGeneratedWindow";
  wc.hCursor=LoadCursorA(nullptr,IDC_ARROW);
  if(!RegisterClassA(&wc)&&GetLastError()!=ERROR_CLASS_ALREADY_EXISTS)return false;
  hwnd_=CreateWindowExA(0,wc.lpszClassName,title,WS_OVERLAPPEDWINDOW|WS_VISIBLE,
   CW_USEDEFAULT,CW_USEDEFAULT,800,600,nullptr,nullptr,inst,this);
  return hwnd_!=nullptr;
 }
 bool pump(){MSG m{};while(PeekMessageA(&m,nullptr,0,0,PM_REMOVE)){
   if(m.message==WM_QUIT){running_=false;break;}TranslateMessage(&m);DispatchMessageA(&m);
  }return running_;}
 u64 buttons()const{return buttons_;}
 void present(const Frame& f){f.validate();last_=f;if(hwnd_)InvalidateRect(hwnd_,nullptr,FALSE);}
 void title(const char* text){if(hwnd_)SetWindowTextA(hwnd_,text);}
};
}
#else
namespace recomp::hw {
class Win32Window {
 public:bool open(const char*){return false;}bool pump(){return false;}
 u64 buttons()const{return 0;}void present(const Frame&){}void title(const char*){}
};
}
#endif
