#pragma once
// Source-byte-driven Z80 timing for translated instructions. No CPU interpreter.
// Incomplete/undocumented ED opcodes are explicitly unqualified, never called parity.
#include <array>
#include <cstdint>
namespace recomp::z80 {
struct Timing { unsigned tstates; bool known; };
inline Timing no() { return {0,false}; }
inline bool conditional_ret(unsigned op){return (op&0xc7u)==0xc0u;}
inline bool conditional_call(unsigned op){return (op&0xc7u)==0xc4u;}
inline bool conditional_jp(unsigned op){return (op&0xc7u)==0xc2u;}
inline bool is_block_repeat(unsigned op){return op==0xb0||op==0xb1||op==0xb2||op==0xb3||op==0xb8||op==0xb9||op==0xba||op==0xbb;}
template<class Read>
Timing decode(Read read, std::uint16_t pc, std::uint16_t next_pc, std::uint16_t fallthrough){
 const bool taken=next_pc!=fallthrough;
 unsigned off=0, prefixes=0; bool index=false;
 std::uint8_t op=read(pc);
 // DD/FD chain: last prefix wins; earlier prefix bytes are 4 T-states each.
 while(op==0xdd||op==0xfd){
  index=true; ++off; ++prefixes;
  if(prefixes>8)return no();
  op=read(static_cast<std::uint16_t>(pc+off));
 }
 const unsigned overhead=(prefixes?prefixes-1:0)*4;
 if(op==0xcb){
  if(index){
   auto cb=read(static_cast<std::uint16_t>(pc+off+2));
   return {overhead+((cb&0xc0)==0x40?20u:23u),true};
  }
  auto cb=read(static_cast<std::uint16_t>(pc+off+1));
  return {(cb&7)==6?((cb&0xc0)==0x40?12u:15u):8u,true};
 }
 if(op==0xed){
  const auto ed=read(static_cast<std::uint16_t>(pc+off+1));
  unsigned cost=0;
  if((ed&0xc7)==0x40 || (ed&0xc7)==0x41)cost=12; // IN/OUT r,(C)
  else if((ed&0xcf)==0x42 || (ed&0xcf)==0x4a)cost=15; // SBC/ADC HL,rr
  else if((ed&0xcf)==0x43 || (ed&0xcf)==0x4b)cost=20; // LD (nn),rr / inverse
  else if((ed&0xc7)==0x44 || (ed&0xc7)==0x45 || (ed&0xc7)==0x46)cost=(ed&0xc7)==0x44?8:((ed&0xc7)==0x45?14:8);
  else if(ed==0x47||ed==0x4f||ed==0x57||ed==0x5f)cost=9;
  else if(ed==0x67||ed==0x6f)cost=18;
  else if((ed>=0xa0&&ed<=0xa3)||(ed>=0xa8&&ed<=0xab))cost=16;
  else if(is_block_repeat(ed))cost=next_pc==pc?21:16;
  // Undefined ED opcodes have variable effects in clones: do not guess.
  return cost?Timing{cost+prefixes*4,true}:no();
 }
 static constexpr std::array<unsigned,64> first={
  4,10,7,6,4,4,7,4, 4,11,7,6,4,4,7,4,
  8,10,7,6,4,4,7,4, 12,11,7,6,4,4,7,4,
  7,10,16,6,4,4,7,4, 7,11,16,6,4,4,7,4,
  7,10,13,6,11,11,10,4, 7,11,13,6,4,4,7,4};
 unsigned cost=0;
 if(op<0x40){cost=first[op];if(op==0x10)cost=taken?13:8;
  if(op==0x20||op==0x28||op==0x30||op==0x38)cost=taken?12:7;
 }else if(op<0x80){cost=op==0x76?4:((op&7)==6||(op&0x38)==0x30?7:4);
 }else if(op<0xc0){cost=(op&7)==6?7:4;
 }else if(conditional_ret(op))cost=taken?11:5;
 else if(conditional_call(op))cost=taken?17:10;
 else if(conditional_jp(op))cost=10;
 else if((op&0xc7)==0xc7)cost=11;
 else if((op&0xcf)==0xc1)cost=10; // POP
 else if((op&0xcf)==0xc5)cost=11; // PUSH
 else if((op&0xc7)==0xc6)cost=7; // ALU immediate
 else switch(op){
  case 0xc3:case 0xca:case 0xda:case 0xea:case 0xfa: cost=10;break;
  case 0xc9:cost=10;break;
  case 0xcd:cost=17;break;
  case 0xd3:case 0xdb:cost=11;break;
  case 0xd9:case 0xeb:case 0xf3:case 0xfb:cost=4;break;
  case 0xe3:cost=19;break;
  case 0xe9:cost=4;break;
  case 0xf9:cost=6;break;
  default:return no();
 }
 if(!index)return {cost,true};
 // Index operations, where IX/IY replaces HL or (HL) with (IX/IY+d).
 if(op==0x21)return {overhead+14,true};
 if(op==0x22||op==0x2a)return {overhead+20,true};
 if(op==0x23||op==0x2b)return {overhead+10,true};
 if(op==0x34||op==0x35)return {overhead+23,true};
 if(op==0x36)return {overhead+19,true};
 if(op==0xe1)return {overhead+14,true};
 if(op==0xe3)return {overhead+23,true};
 if(op==0xe5)return {overhead+15,true};
 if(op==0xe9)return {overhead+8,true};
 if(op==0xf9)return {overhead+10,true};
 if(op>=0x40&&op<0x80&&op!=0x76){
  if((op&7)==6||(op&0x38)==0x30)return {overhead+19,true};
  return {cost+prefixes*4,true};
 }
 if(op>=0x80&&op<0xc0&&(op&7)==6)return {overhead+19,true};
 // Most other IXH/IXL byte operations cost the ordinary instruction +4.
 return {cost+prefixes*4,true};
}
} // namespace recomp::z80
