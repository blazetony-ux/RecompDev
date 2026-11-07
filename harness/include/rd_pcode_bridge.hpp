#pragma once
// ABI adapter for v0.4.0.45 nativepilot.generator.emit_instruction output.
// Guest state belongs to the generic harness, *not* to the game DLL.
// P-code ALU evaluator is derived from RecompDev v0.4.0.45
// systems/mastersystem/runtime.cpp (rd::evaluate), with no machine dependency.
#include "rd_plugin.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <stdexcept>
#include <unordered_map>
namespace rd {
using u64=std::uint64_t;
enum class Op { COPY, INT_AND, INT_OR, INT_LEFT, INT_ADD, INT_EQUAL, INT_RIGHT, INT_SRIGHT,
 INT_SUB, INT_SLESS, INT_XOR, INT_NOTEQUAL, INT_ZEXT, INT_2COMP,
 INT_CARRY, INT_SCARRY, INT_LESSEQUAL, INT_SBORROW, BOOL_OR, BOOL_XOR,
 INT_LESS, BOOL_NEGATE, INT_NEGATE };
inline u64 mask(unsigned n){return n>=8?~u64(0):((u64(1)<<(n*8))-1);}
inline std::int64_t signed_value(u64 x,unsigned n){u64 m=mask(n);x &=m;u64 sign=u64(1)<<(n*8-1);return (x&sign)?std::int64_t(x|~m):std::int64_t(x);}
inline u64 evaluate(Op op,u64 a,u64 b,unsigned size,unsigned as,unsigned bs){
 const u64 m=mask(size),am=mask(as),bm=mask(bs),operand_mask=mask(std::max(as,bs));a&=am;b&=bm;
 switch(op){
 case Op::COPY:case Op::INT_ZEXT:return a&m;
 case Op::INT_AND:return (a&b)&m;
 case Op::INT_OR:return (a|b)&m;
 case Op::INT_XOR:return (a^b)&m;
 case Op::INT_LEFT:return b>=64?0:(a<<b)&m;
 case Op::INT_RIGHT:return b>=64?0:(a>>b)&m;
 case Op::INT_SRIGHT:{const unsigned bits=as*8;const bool negative=(a & (u64(1)<<(bits-1)))!=0;
  if(b>=bits)return negative?m:0;
  const unsigned n=static_cast<unsigned>(b);
  if(n==0)return a&m;
  const u64 fill=negative?(am^(am>>n)):0;
  return ((a>>n)|fill)&m;}
 case Op::INT_ADD:return (a+b)&m;
 case Op::INT_SUB:return (a-b)&m;
 case Op::INT_EQUAL:return a==b;
 case Op::INT_NOTEQUAL:return a!=b;
 case Op::INT_LESS:return a<b;
 case Op::INT_LESSEQUAL:return a<=b;
 case Op::INT_SLESS:return signed_value(a,as)<signed_value(b,bs);
 case Op::INT_2COMP:return (u64(0)-a)&m;
 case Op::INT_NEGATE:return (~a)&m;
 case Op::INT_CARRY:return a>operand_mask-b;
 case Op::INT_SCARRY:{u64 sign=u64(1)<<(std::max(as,bs)*8-1),r=(a+b)&operand_mask;return ((~(a^b)&(a^r)&sign)!=0);}
 case Op::INT_SBORROW:{u64 sign=u64(1)<<(std::max(as,bs)*8-1),r=(a-b)&operand_mask;return (((a^b)&(a^r)&sign)!=0);}
 case Op::BOOL_OR:return (a!=0)||(b!=0);
 case Op::BOOL_XOR:return (a!=0)!=(b!=0);
 case Op::BOOL_NEGATE:return a==0;
 }
 return 0;
}
class BridgeState {
 RD_CpuState& cpu;const RD_Bus& bus;
 std::array<std::uint8_t,72> reg{};
 std::unordered_map<unsigned,std::uint8_t> unique;
 static u64 load(const std::uint8_t* p,unsigned offset,unsigned size){u64 v=0;for(unsigned i=0;i<size;++i)v|=u64(p[offset+i])<<(8*i);return v;}
 static void save(std::uint8_t* p,unsigned offset,unsigned size,u64 v){for(unsigned i=0;i<size;++i)p[offset+i]=std::uint8_t(v>>(8*i));}
 static void check_reg(unsigned offset,unsigned size){if(size<1||size>8||!((offset+size<=8)||(offset>=68&&offset+size<=70)))throw std::out_of_range("unsupported Z80 register offset");}
 static void check_unique(unsigned offset,unsigned size){if(size<1||size>8||offset>1024u*1024u-size)throw std::out_of_range("unsupported unique offset");}
public:
 bool halted=false;int interrupt_mode=0;
 explicit BridgeState(RD_CpuState& s,const RD_Bus& b):cpu(s),bus(b){
  reg[0]=s.f;reg[1]=s.a;reg[2]=s.c;reg[3]=s.b;reg[4]=s.e;reg[5]=s.d;reg[6]=s.l;reg[7]=s.h;
  reg[68]=std::uint8_t(s.sp);reg[69]=std::uint8_t(s.sp>>8);
 }
 u64 get_register(unsigned o,unsigned n)const{check_reg(o,n);return load(reg.data(),o,n);}
 void set_register(unsigned o,unsigned n,u64 v){check_reg(o,n);save(reg.data(),o,n,v);}
 u64 get_unique(unsigned o,unsigned n)const{check_unique(o,n);u64 result=0;
  for(unsigned i=0;i<n;++i){auto it=unique.find(o+i);if(it!=unique.end())result|=u64(it->second)<<(i*8);}
  return result;}
 void set_unique(unsigned o,unsigned n,u64 v){check_unique(o,n);
  for(unsigned i=0;i<n;++i)unique[o+i]=std::uint8_t(v>>(i*8));}
 u64 memory(std::uint16_t address,unsigned n)const{
  if(n<1||n>8)throw std::out_of_range("memory width");
  u64 v=0;for(unsigned i=0;i<n;++i)v|=u64(bus.read(bus.ctx,std::uint16_t(address+i)))<<(8*i);return v;
 }
 void write_memory(std::uint16_t address,unsigned n,u64 v){
  if(n<1||n>8)throw std::out_of_range("memory width");
  for(unsigned i=0;i<n;++i)bus.write(bus.ctx,std::uint16_t(address+i),std::uint8_t(v>>(8*i)));
 }
 std::uint8_t in(std::uint16_t p)const{return bus.in_port(bus.ctx,p);}
 void out(std::uint16_t p,std::uint8_t v){bus.out_port(bus.ctx,p,v);}
 void commit(){cpu.f=reg[0];cpu.a=reg[1];cpu.c=reg[2];cpu.b=reg[3];cpu.e=reg[4];cpu.d=reg[5];cpu.l=reg[6];cpu.h=reg[7];cpu.sp=std::uint16_t(reg[68]|(reg[69]<<8));cpu.halted=halted?1:cpu.halted;}
};
} // namespace rd
