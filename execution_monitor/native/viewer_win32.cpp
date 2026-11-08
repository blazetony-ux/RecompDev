// Standalone CPU-neutral native Windows diagnostics subscriber. v0.4.9.22.
// Socket ingestion is bounded and NEVER updates a Win32 control. All GUI work
// runs on a timer at 10 Hz, in short batches, independent of native execution.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <shellapi.h>
#include <algorithm>
#include <atomic>
#include <cwctype>
#include <string>
#include <thread>
#include <vector>
#include "monitor_model.hpp"
#include "event_queue.hpp"
#pragma comment(lib,"Ws2_32.lib")
namespace {
constexpr UINT_PTR kRefreshTimer=1;
constexpr int kSearch=101,kMode=102,kMatch=103,kFollow=104,kPrev=105,kNext=106;
struct Ui {
 HWND hwnd=nullptr,labels[5]{},trace=nullptr,search=nullptr,mode=nullptr,matched=nullptr,follow=nullptr,prev=nullptr,next=nullptr;
 HFONT font=nullptr;
 rdmonitor::State state;
 rdmonitor::EventQueue queue;
 std::atomic<bool> closed{false};
 std::uint64_t rendered=0;
 int displayed_lines=0;
 bool dirty=true, follow_enabled=true, matched_only=false;
 std::string initial_search;
 bool initial_matched=false;
};
Ui ui;
std::wstring wide(const std::string& s){
 if(s.empty())return {};
 const int n=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,s.data(),int(s.size()),nullptr,0);
 if(n<=0)return L"[invalid UTF-8]";
 std::wstring result(size_t(n),L'\0');
 MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,s.data(),int(s.size()),result.data(),n);
 return result;
}
std::string utf8(const std::wstring& s){
 if(s.empty())return {};
 int n=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,s.data(),int(s.size()),nullptr,0,nullptr,nullptr);
 if(n<=0)return {};
 std::string out(size_t(n),'\0');
 WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,s.data(),int(s.size()),out.data(),n,nullptr,nullptr);
 return out;
}
std::wstring getText(HWND h,int cap=512){
 int n=GetWindowTextLengthW(h);
 if(n<0||n>cap)return {};
 std::wstring out(size_t(n+1),L'\0');
 GetWindowTextW(h,out.data(),n+1);out.resize(size_t(n));return out;
}
void listen(int port,const std::string& token){
 WSADATA w{};
 if(WSAStartup(MAKEWORD(2,2),&w)!=0){ui.queue.offer("ERROR: Socket initialization failed");return;}
 SOCKET sock=socket(AF_INET,SOCK_STREAM,IPPROTO_TCP);
 if(sock==INVALID_SOCKET){ui.queue.offer("ERROR: Socket unavailable");WSACleanup();return;}
 sockaddr_in addr{};addr.sin_family=AF_INET;addr.sin_addr.s_addr=htonl(INADDR_LOOPBACK);addr.sin_port=htons(static_cast<u_short>(port));
 DWORD timeout=1000;setsockopt(sock,SOL_SOCKET,SO_RCVTIMEO,reinterpret_cast<const char*>(&timeout),sizeof(timeout));
 if(connect(sock,reinterpret_cast<sockaddr*>(&addr),sizeof(addr))!=0){
  ui.queue.offer("ERROR: Controller connection failed");closesocket(sock);WSACleanup();return;
 }
 std::string hello="{\"schema\":\"recompdev.controller.diagnostics.v1\",\"token\":"+rdjson::escape(token)+",\"role\":\"subscribe\"}\n";
 if(send(sock,hello.data(),int(hello.size()),0)!=int(hello.size())){
  ui.queue.offer("ERROR: Authentication failed");closesocket(sock);WSACleanup();return;
 }
 std::string pending;char buf[4096];
 while(!ui.closed){
  int n=recv(sock,buf,sizeof(buf),0);
  if(n==0)break;
  if(n<0){if(WSAGetLastError()==WSAETIMEDOUT)continue;break;}
  pending.append(buf,size_t(n));
  if(pending.size()>65536){ui.queue.offer("ERROR: Oversized controller event stream");break;}
  std::size_t end=0;
  while((end=pending.find('\n'))!=std::string::npos){
   if(end<=rdmonitor::kMaxLine)ui.queue.offer(pending.substr(0,end));
   pending.erase(0,end+1);
  }
 }
 closesocket(sock);WSACleanup();ui.queue.offer("DISCONNECTED");
}
void setIfChanged(HWND h,const std::string& s){
 auto value=wide(s);if(getText(h)!=value)SetWindowTextW(h,value.c_str());
}
void drawLabels(){
 const auto& s=ui.state;
 const std::string dropped="Display queue dropped "+std::to_string(ui.queue.dropped())+
  " events; "+std::to_string(ui.queue.waiting())+" pending; "+std::to_string(s.transport_dropped)+" transport drops; "+std::to_string(s.rejected)+" rejected";
 const std::string v[]={s.connection,s.cpu,s.frame,s.status,dropped};
 for(int i=0;i<5;++i)setIfChanged(ui.labels[i],v[i]);
}
std::string query(){return utf8(getText(ui.search));}
int mode(){return int(SendMessageW(ui.mode,CB_GETCURSEL,0,0));}
void appendText(const std::wstring& value,bool clear){
 if(value.empty()&&!clear)return;
 if(clear){SetWindowTextW(ui.trace,value.c_str());ui.displayed_lines=0;for(wchar_t c:value)if(c==L'\n')++ui.displayed_lines;}
 else{
  const int old_first=int(SendMessageW(ui.trace,EM_GETFIRSTVISIBLELINE,0,0));
  SendMessageW(ui.trace,EM_SETSEL,WPARAM(-1),LPARAM(-1));
  SendMessageW(ui.trace,EM_REPLACESEL,FALSE,reinterpret_cast<LPARAM>(value.c_str()));
  for(wchar_t c:value)if(c==L'\n')++ui.displayed_lines;
  if(!ui.follow_enabled){
   const int new_first=int(SendMessageW(ui.trace,EM_GETFIRSTVISIBLELINE,0,0));
   SendMessageW(ui.trace,EM_LINESCROLL,0,old_first-new_first);
  }
 }
 // Bound the EDIT control independently from the native producer and queue.
 if(ui.displayed_lines>2300){
  const int remove=ui.displayed_lines-1800;
  const LRESULT index=SendMessageW(ui.trace,EM_LINEINDEX,remove,0);
  if(index>0){SendMessageW(ui.trace,EM_SETSEL,0,index);SendMessageW(ui.trace,EM_REPLACESEL,FALSE,reinterpret_cast<LPARAM>(L""));ui.displayed_lines-=remove;}
 }
 if(ui.follow_enabled){SendMessageW(ui.trace,EM_SETSEL,WPARAM(-1),LPARAM(-1));SendMessageW(ui.trace,EM_SCROLLCARET,0,0);}
}
void updateTrace(){
 std::wstring addition;
 const std::string q=query();const int m=mode();
 const bool rebuild=ui.dirty;
 if(rebuild)ui.rendered=0;
 for(const auto&e:ui.state.entries){
  if(e.sequence<=ui.rendered)continue;
  if(!ui.matched_only||rdmonitor::matches(e,q,m)){
   addition+=wide(e.text);addition+=L"\r\n";
  }
 }
 ui.rendered=ui.state.trace_sequence;
 appendText(addition,rebuild);
 ui.dirty=false;
}
void navigate(bool forward){
 const auto term=getText(ui.search);if(term.empty())return;
 const auto content=getText(ui.trace,1000000);if(content.empty())return;
 auto a=content,b=term;
 std::transform(a.begin(),a.end(),a.begin(),[](wchar_t c){return towlower(c);});
 std::transform(b.begin(),b.end(),b.begin(),[](wchar_t c){return towlower(c);});
 DWORD lo=0,hi=0;SendMessageW(ui.trace,EM_GETSEL,reinterpret_cast<WPARAM>(&lo),reinterpret_cast<LPARAM>(&hi));
 std::size_t at=std::wstring::npos;
 if(forward){at=a.find(b,size_t(hi));if(at==std::wstring::npos)at=a.find(b);}
 else{at=a.rfind(b,lo?size_t(lo-1):0);if(at==std::wstring::npos)at=a.rfind(b);}
 if(at!=std::wstring::npos){ui.follow_enabled=false;SendMessageW(ui.follow,BM_SETCHECK,BST_UNCHECKED,0);
  SendMessageW(ui.trace,EM_SETSEL,at,at+b.size());SendMessageW(ui.trace,EM_SCROLLCARET,0,0);SetFocus(ui.trace);}
}
void layout(int w,int h){
 const int pad=12,row=30;const int usable=std::max(80,w-pad*2);
 for(int i=0;i<5;++i)MoveWindow(ui.labels[i],pad,pad+i*row,usable,row-4,TRUE);
 const int y=pad+5*row;
 const int combo=135,button=72,check=125;
 const int searchWidth=std::max(90,usable-combo-2*button-2*check-26);
 int x=pad;
 MoveWindow(ui.search,x,y,searchWidth,26,TRUE);x+=searchWidth+5;
 MoveWindow(ui.mode,x,y,combo,240,TRUE);x+=combo+5;
 MoveWindow(ui.matched,x,y,check,26,TRUE);x+=check+3;
 MoveWindow(ui.follow,x,y,check,26,TRUE);x+=check+3;
 MoveWindow(ui.prev,x,y,button-8,26,TRUE);x+=button-6;
 MoveWindow(ui.next,x,y,button-8,26,TRUE);
 MoveWindow(ui.trace,pad,y+35,usable,std::max(45,h-y-35-pad),TRUE);
}
LRESULT CALLBACK wndproc(HWND hwnd,UINT msg,WPARAM wp,LPARAM lp){
 switch(msg){
 case WM_CREATE:{
  ui.hwnd=hwnd;
  ui.font=CreateFontW(-16,0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY,FIXED_PITCH,L"Consolas");
  for(int i=0;i<5;++i)ui.labels[i]=CreateWindowExW(0,L"STATIC",L"",WS_CHILD|WS_VISIBLE|SS_LEFT,0,0,100,25,hwnd,nullptr,GetModuleHandleW(nullptr),nullptr);
  ui.search=CreateWindowExW(WS_EX_CLIENTEDGE,L"EDIT",wide(ui.initial_search).c_str(),WS_CHILD|WS_VISIBLE|WS_TABSTOP|ES_AUTOHSCROLL,0,0,100,25,hwnd,(HMENU)kSearch,GetModuleHandleW(nullptr),nullptr);
  ui.mode=CreateWindowExW(0,L"COMBOBOX",L"",WS_CHILD|WS_VISIBLE|WS_TABSTOP|CBS_DROPDOWNLIST|WS_VSCROLL,0,0,100,100,hwnd,(HMENU)kMode,GetModuleHandleW(nullptr),nullptr);
  for(auto s:{L"All text",L"PC address",L"Physical offset",L"Opcode class",L"Event type",L"Watch hits"})SendMessageW(ui.mode,CB_ADDSTRING,0,reinterpret_cast<LPARAM>(s));
  SendMessageW(ui.mode,CB_SETCURSEL,ui.initial_matched?5:(ui.initial_search.rfind("0x",0)==0?1:0),0);
  ui.matched=CreateWindowExW(0,L"BUTTON",L"Matches only",WS_CHILD|WS_VISIBLE|WS_TABSTOP|BS_AUTOCHECKBOX,0,0,100,25,hwnd,(HMENU)kMatch,GetModuleHandleW(nullptr),nullptr);
  ui.follow=CreateWindowExW(0,L"BUTTON",L"Follow latest",WS_CHILD|WS_VISIBLE|WS_TABSTOP|BS_AUTOCHECKBOX,0,0,100,25,hwnd,(HMENU)kFollow,GetModuleHandleW(nullptr),nullptr);
  ui.prev=CreateWindowExW(0,L"BUTTON",L"Previous",WS_CHILD|WS_VISIBLE|WS_TABSTOP,0,0,70,25,hwnd,(HMENU)kPrev,GetModuleHandleW(nullptr),nullptr);
  ui.next=CreateWindowExW(0,L"BUTTON",L"Next",WS_CHILD|WS_VISIBLE|WS_TABSTOP,0,0,70,25,hwnd,(HMENU)kNext,GetModuleHandleW(nullptr),nullptr);
  ui.trace=CreateWindowExW(WS_EX_CLIENTEDGE,L"EDIT",L"",WS_CHILD|WS_VISIBLE|WS_TABSTOP|WS_VSCROLL|WS_HSCROLL|ES_MULTILINE|ES_AUTOVSCROLL|ES_AUTOHSCROLL|ES_READONLY,0,0,100,100,hwnd,nullptr,GetModuleHandleW(nullptr),nullptr);
  SendMessageW(ui.trace,EM_SETLIMITTEXT,1024*1024,0);
  for(auto h:{ui.labels[0],ui.labels[1],ui.labels[2],ui.labels[3],ui.labels[4],ui.search,ui.mode,ui.matched,ui.follow,ui.prev,ui.next,ui.trace})
   SendMessageW(h,WM_SETFONT,reinterpret_cast<WPARAM>(ui.font),TRUE);
  ui.matched_only=ui.initial_matched;
  SendMessageW(ui.matched,BM_SETCHECK,ui.matched_only?BST_CHECKED:BST_UNCHECKED,0);
  SendMessageW(ui.follow,BM_SETCHECK,BST_CHECKED,0);
  SetTimer(hwnd,kRefreshTimer,100,nullptr);
  drawLabels();return 0;
 }
 case WM_SIZE:layout(LOWORD(lp),HIWORD(lp));return 0;
 case WM_TIMER:
  if(wp==kRefreshTimer){
   // At most 768 JSON parses per 100-ms tick: bounded Win32 message latency.
   auto batch=ui.queue.take(768);
   for(const auto&line:batch){
    if(line=="DISCONNECTED")ui.state.connection="Controller disconnected; last trace retained";
    else if(line.rfind("ERROR:",0)==0)ui.state.status=line;
    else ui.state.ingest(line);
   }
   drawLabels();if(!batch.empty()||ui.dirty)updateTrace();return 0;
  }break;
 case WM_COMMAND:{
  const int id=LOWORD(wp),note=HIWORD(wp);
  if((id==kSearch&&note==EN_CHANGE)||(id==kMode&&note==CBN_SELCHANGE)){
   ui.dirty=true;return 0;
  }
  if(id==kMatch&&note==BN_CLICKED){ui.matched_only=SendMessageW(ui.matched,BM_GETCHECK,0,0)==BST_CHECKED;ui.dirty=true;return 0;}
  if(id==kFollow&&note==BN_CLICKED){ui.follow_enabled=SendMessageW(ui.follow,BM_GETCHECK,0,0)==BST_CHECKED;return 0;}
  if(id==kPrev&&note==BN_CLICKED){navigate(false);return 0;}
  if(id==kNext&&note==BN_CLICKED){navigate(true);return 0;}
  if(HWND(lp)==ui.trace&&note==EN_VSCROLL){ui.follow_enabled=false;SendMessageW(ui.follow,BM_SETCHECK,BST_UNCHECKED,0);return 0;}
  break;
 }
 case WM_CLOSE:DestroyWindow(hwnd);return 0;
 case WM_DESTROY:ui.closed=true;KillTimer(hwnd,kRefreshTimer);PostQuitMessage(0);return 0;
 }
 return DefWindowProcW(hwnd,msg,wp,lp);
}
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE,LPWSTR,int show){
 int argc=0;LPWSTR*args=CommandLineToArgvW(GetCommandLineW(),&argc);
 if(!args)return 2;
 int port=0;std::string token,search;bool matched=false;
 for(int i=1;i<argc;++i){
  const std::wstring arg=args[i];
  if((arg==L"--port"||arg==L"--token"||arg==L"--search")&&i+1<argc){
   const std::wstring value=args[++i];
   if(arg==L"--port"){
    try{std::size_t k=0;port=std::stoi(value,&k);if(k!=value.size())port=0;}catch(...){port=0;}
   }else if(arg==L"--token"){
    if(value.size()==48){bool valid=true;for(wchar_t c:value)if(!((c>=L'0'&&c<=L'9')||(c>=L'a'&&c<=L'f')))valid=false;
     if(valid)token=utf8(value);}
   }else if(value.size()<=96)search=utf8(value);
  }else if(arg==L"--matched-only")matched=true;
  else{LocalFree(args);return 2;}
 }
 LocalFree(args);
 if(port<=0||port>65535||token.size()!=48)return 2;
 ui.initial_search=search;ui.initial_matched=matched;
 WNDCLASSW wc{};wc.hInstance=instance;wc.lpfnWndProc=wndproc;wc.lpszClassName=L"RecompDevNativeExecutionMonitorV2";
 wc.hCursor=LoadCursorW(nullptr,IDC_ARROW);wc.hbrBackground=reinterpret_cast<HBRUSH>(COLOR_WINDOW+1);
 if(!RegisterClassW(&wc))return 3;
 HWND window=CreateWindowExW(0,wc.lpszClassName,L"RecompDev - Native C++ Execution Monitor",WS_OVERLAPPEDWINDOW,
  CW_USEDEFAULT,CW_USEDEFAULT,1170,750,nullptr,nullptr,instance,nullptr);
 if(!window)return 3;
 ShowWindow(window,show);UpdateWindow(window);
 std::thread listener([port,token]{listen(port,token);});
 MSG msg{};while(GetMessageW(&msg,nullptr,0,0)>0){TranslateMessage(&msg);DispatchMessageW(&msg);}
 if(listener.joinable())listener.join();
 if(ui.font)DeleteObject(ui.font);
 return 0;
}
