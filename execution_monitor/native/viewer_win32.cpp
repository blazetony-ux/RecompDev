// Independent native C++ Win32 subscriber to the controller's authenticated,
// localhost-only read-only event protocol. No Python/Tk, CPU plugin or ROM access.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <shellapi.h>
#include <algorithm>
#include "monitor_model.hpp"
#include <atomic>
#include <memory>
#include <string>
#include <thread>
#include <vector>
#pragma comment(lib,"Ws2_32.lib")

namespace {
constexpr UINT kEvent=WM_APP+15;
struct Ui {HWND hwnd=nullptr,fields[5]{};HFONT font=nullptr;rdmonitor::State state;std::atomic<bool> closed{false};};
Ui ui;
std::wstring wide(const std::string&s){
 if(s.empty())return {};
 int n=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,s.data(),int(s.size()),nullptr,0);
 if(n<=0)return L"[invalid UTF-8]";
 std::wstring result(size_t(n),L'\0');
 MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,s.data(),int(s.size()),result.data(),n);
 return result;
}
void post(std::string payload){
 if(ui.closed)return;
 auto *event=new std::string(std::move(payload));
 if(!PostMessageW(ui.hwnd,kEvent,0,reinterpret_cast<LPARAM>(event)))delete event;
}
void listen(int port,const std::string& token){
 WSADATA w{};
 if(WSAStartup(MAKEWORD(2,2),&w)!=0){post("ERROR: native socket initialization failed");return;}
 SOCKET sock=socket(AF_INET,SOCK_STREAM,IPPROTO_TCP);
 if(sock==INVALID_SOCKET){post("ERROR: native socket unavailable");WSACleanup();return;}
 sockaddr_in addr{};addr.sin_family=AF_INET;addr.sin_addr.s_addr=htonl(INADDR_LOOPBACK);addr.sin_port=htons(static_cast<u_short>(port));
 DWORD timeout=1000;setsockopt(sock,SOL_SOCKET,SO_RCVTIMEO,reinterpret_cast<const char*>(&timeout),sizeof(timeout));
 if(connect(sock,reinterpret_cast<sockaddr*>(&addr),sizeof(addr))!=0){post("ERROR: controller connection failed");closesocket(sock);WSACleanup();return;}
 std::string hello="{\"schema\":\"recompdev.controller.diagnostics.v1\",\"token\":"+rdjson::escape(token)+",\"role\":\"subscribe\"}\n";
 if(send(sock,hello.data(),int(hello.size()),0)!=int(hello.size())){
  post("ERROR: authentication request failed");closesocket(sock);WSACleanup();return;
 }
 std::string pending;char buf[4096];
 while(!ui.closed){
  int n=recv(sock,buf,sizeof(buf),0);
  if(n==0)break;
  if(n<0){if(WSAGetLastError()==WSAETIMEDOUT)continue;break;}
  pending.append(buf,size_t(n));
  if(pending.size()>32768){post("ERROR: oversized controller event stream");break;}
  std::size_t end=0;std::string batch;
  while((end=pending.find('\n'))!=std::string::npos){
   if(end<=rdmonitor::kMaxLine){batch.append(pending.data(),end);batch.push_back('\n');}
   pending.erase(0,end+1);
  }
  if(!batch.empty())post(std::move(batch));
 }
 closesocket(sock);WSACleanup();
 post("DISCONNECTED");
}
void refresh(){
 const auto &s=ui.state;
 const std::string fields[]={s.connection,s.cpu,s.frame,s.status,s.trace()};
 for(int i=0;i<5;++i){auto w=wide(fields[i]);SetWindowTextW(ui.fields[i],w.c_str());}
 SendMessageW(ui.fields[4],EM_SETSEL,WPARAM(-1),LPARAM(-1));
 SendMessageW(ui.fields[4],EM_SCROLLCARET,0,0);
}
void layout(int w,int h){
 const int pad=12, row=32;
 for(int i=0;i<4;++i)MoveWindow(ui.fields[i],pad,pad+i*row,std::max(50,w-2*pad),row-4,TRUE);
 MoveWindow(ui.fields[4],pad,pad+4*row,std::max(50,w-2*pad),std::max(45,h-pad*2-row*4),TRUE);
}
LRESULT CALLBACK wndproc(HWND hwnd,UINT msg,WPARAM wp,LPARAM lp){
 switch(msg){
 case WM_CREATE:{
  ui.hwnd=hwnd;
  ui.font=CreateFontW(-16,0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY,FIXED_PITCH,L"Consolas");
  for(int i=0;i<5;++i){
   const DWORD style=WS_CHILD|WS_VISIBLE|(i==4?(WS_VSCROLL|ES_MULTILINE|ES_AUTOVSCROLL|ES_READONLY):SS_LEFT);
   ui.fields[i]=CreateWindowExW(i==4?WS_EX_CLIENTEDGE:0,i==4?L"EDIT":L"STATIC",L"",style,0,0,100,25,hwnd,nullptr,GetModuleHandleW(nullptr),nullptr);
   SendMessageW(ui.fields[i],WM_SETFONT,reinterpret_cast<WPARAM>(ui.font),TRUE);
  }
  refresh();return 0;
 }
 case WM_SIZE:layout(LOWORD(lp),HIWORD(lp));return 0;
 case kEvent:{
  std::unique_ptr<std::string> event(reinterpret_cast<std::string*>(lp));
  if(*event=="DISCONNECTED"){
   ui.state.connection="Controller disconnected; last trace retained";
  }else if(event->rfind("ERROR:",0)==0){ui.state.status=*event;}
  else {
   std::size_t start=0,end=0;
   while((end=event->find('\n',start))!=std::string::npos){
    ui.state.ingest(event->substr(start,end-start));start=end+1;
   }
  }
  // Sampled instruction event stream is bounded by the producer and UI trace history.
  refresh();return 0;
 }
 case WM_CLOSE:DestroyWindow(hwnd);return 0;
 case WM_DESTROY:ui.closed=true;PostQuitMessage(0);return 0;
 }
 return DefWindowProcW(hwnd,msg,wp,lp);
}
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE,LPWSTR command,int show){
 // Shell command line parsing supports quoted argument values but never accepts
 // a remote host, a filesystem path or an executable command.
 int argc=0;LPWSTR*args=CommandLineToArgvW(GetCommandLineW(),&argc);
 if(!args)return 2;
 int port=0;std::string token;
 for(int i=1;i<argc;++i){
  std::wstring arg=args[i];
  if((arg==L"--port"||arg==L"--token")&&i+1<argc){
   std::wstring value=args[++i];
   if(arg==L"--port"){
    try{std::size_t k=0;port=std::stoi(value,&k);if(k!=value.size())port=0;}catch(...){port=0;}
   }else{
    if(value.size()==48){bool valid=true;for(wchar_t c:value)if(!((c>=L'0'&&c<=L'9')||(c>=L'a'&&c<=L'f')))valid=false;
      if(valid)token=std::string(value.begin(),value.end());}
   }
  }else{LocalFree(args);return 2;}
 }
 LocalFree(args);
 if(port<=0||port>65535||token.size()!=48)return 2;
 WNDCLASSW wc{};wc.hInstance=instance;wc.lpfnWndProc=wndproc;wc.lpszClassName=L"RecompDevNativeExecutionMonitorV1";
 wc.hCursor=LoadCursorW(nullptr,IDC_ARROW);wc.hbrBackground=reinterpret_cast<HBRUSH>(COLOR_WINDOW+1);
 if(!RegisterClassW(&wc))return 3;
 HWND window=CreateWindowExW(0,wc.lpszClassName,L"RecompDev - Native C++ Execution Monitor",WS_OVERLAPPEDWINDOW,
   CW_USEDEFAULT,CW_USEDEFAULT,1000,710,nullptr,nullptr,instance,nullptr);
 if(!window)return 3;
 ShowWindow(window,show);UpdateWindow(window);
 // Detached thread: all user-visible updates are marshalled into Win32 window messages.
 // The socket uses a timeout so closing this window cannot stall native guest execution.
 std::thread listener([port,token]{listen(port,token);});
 MSG msg{};while(GetMessageW(&msg,nullptr,0,0)>0){TranslateMessage(&msg);DispatchMessageW(&msg);}
 if(listener.joinable())listener.join();
 if(ui.font)DeleteObject(ui.font);
 return 0;
}
