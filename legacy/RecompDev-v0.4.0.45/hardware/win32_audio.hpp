#pragma once
// Optional Windows PCM16 speaker sink, isolated from CPU/device logic.
// Drop late host audio instead of blocking deterministic guest execution.
#include "core.hpp"
#include <array>
#include <vector>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <mmsystem.h>
namespace recomp::hw {
class Win32Audio {
 static constexpr std::size_t Block=2048,Slots=4;
 struct Slot {std::array<std::int16_t,Block> data{};WAVEHDR header{};bool active=false;};
 std::array<Slot,Slots> slots_{};
 std::vector<std::int16_t> pending_;
 HWAVEOUT out_=nullptr;
 public:
 bool open(u32 hz=44100){
  WAVEFORMATEX format{};format.wFormatTag=WAVE_FORMAT_PCM;format.nChannels=1;
  format.nSamplesPerSec=hz;format.wBitsPerSample=16;
  format.nBlockAlign=2;format.nAvgBytesPerSec=hz*2;
  return waveOutOpen(&out_,WAVE_MAPPER,&format,0,0,CALLBACK_NULL)==MMSYSERR_NOERROR;
 }
 void feed(const PcmBlock& b){
  b.validate();if(!out_||b.channels!=1)return;
  // Audio is best-effort presentation. Verification uses the complete
  // independently collected headless PCM stream instead.
  if(pending_.size()+b.samples.size()>Block*16){pending_.clear();return;}
  pending_.insert(pending_.end(),b.samples.begin(),b.samples.end());pump();
 }
 void pump(){
  if(!out_)return;
  for(auto& slot:slots_){
   if(slot.active){
    if(!(slot.header.dwFlags&WHDR_DONE))continue;
    waveOutUnprepareHeader(out_,&slot.header,sizeof(slot.header));slot.active=false;
   }
   if(pending_.size()<Block)continue;
   std::copy(pending_.begin(),pending_.begin()+Block,slot.data.begin());
   pending_.erase(pending_.begin(),pending_.begin()+Block);
   slot.header={};slot.header.lpData=reinterpret_cast<LPSTR>(slot.data.data());
   slot.header.dwBufferLength=DWORD(Block*sizeof(std::int16_t));
   if(waveOutPrepareHeader(out_,&slot.header,sizeof(slot.header))==MMSYSERR_NOERROR){
    if(waveOutWrite(out_,&slot.header,sizeof(slot.header))==MMSYSERR_NOERROR)slot.active=true;
    else waveOutUnprepareHeader(out_,&slot.header,sizeof(slot.header));
   }
  }
 }
 ~Win32Audio(){if(out_){waveOutReset(out_);
  for(auto& s:slots_)if(s.active)waveOutUnprepareHeader(out_,&s.header,sizeof(s.header));
  waveOutClose(out_);}}
};
}
#else
namespace recomp::hw {class Win32Audio {
 public:bool open(u32=44100){return false;}void feed(const PcmBlock&){}void pump(){}
};}
#endif
