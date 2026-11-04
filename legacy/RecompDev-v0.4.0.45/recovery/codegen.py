"""Strict, bounded raw P-code -> native C++ experimental whole-function compiler.

Never substitutes unknown P-code operations with no-ops. Byte-addressed register and
unique spaces preserve width/aliasing; the memory bus is explicit and checked.
"""
from __future__ import annotations
import json
from pathlib import Path

SUPPORTED = {
 'COPY','INT_ZEXT','INT_SEXT','INT_ADD','INT_SUB','INT_AND','INT_OR','INT_XOR',
 'INT_LEFT','INT_RIGHT','INT_SRIGHT','INT_MULT','INT_EQUAL','INT_NOTEQUAL',
 'INT_LESS','INT_LESSEQUAL','INT_SLESS','INT_SLESSEQUAL','INT_CARRY',
 'INT_SCARRY','INT_SBORROW','INT_NEGATE','INT_2COMP','BOOL_NEGATE',
 'BOOL_AND','BOOL_OR','BOOL_XOR','PIECE','SUBPIECE','LOAD','STORE',
 'BRANCH','CBRANCH','RETURN'
}

class Blocked(ValueError):
    pass

def vn(x):
    if not isinstance(x,dict):raise Blocked('invalid_varnode')
    s=x.get('space');offset=x.get('offset'); size=x.get('size')
    if s not in ('const','constant','register','unique','ram'):raise Blocked('unsupported_space:'+str(s))
    if type(offset)!=int or offset<0 or offset>=2**64:raise Blocked('invalid_varnode_offset')
    if type(size)!=int or size<1 or size>8:raise Blocked('unsupported_width:'+str(size))
    return x

def r(x):
    x=vn(x); s=x['space']; o=x['offset'];size=x['size']
    if s in ('const','constant'):return f'(0x{o:x}ULL & mask({size}))'
    if s in ('register','unique'):return f'rd({"regs" if s=="register" else "temps"}, {o}ULL, {size})'
    if s=='ram':return f'bus.read({o}ULL, {size})'
    raise Blocked('cannot_read_non_register_varnode')

def w(x,expr):
    x=vn(x)
    if x['space']=='ram':return f'bus.write({x["offset"]}ULL, {x["size"]}, {expr});'
    if x['space'] not in ('register','unique'):raise Blocked('cannot_write_non_register_varnode')
    s='regs' if x['space']=='register' else 'temps'
    return f'wr({s}, {x["offset"]}ULL, {x["size"]}, {expr});'

def target(v, valid):
    v=vn(v)
    if v['space'] not in ('ram','const','constant'):raise Blocked('computed_branch_not_supported')
    if v['offset'] not in valid:raise Blocked('branch_outside_function')
    return v['offset']

def generate(function, isa, language):
    ins=function.get('instructions',[])
    if not ins:raise Blocked('missing_function_body')
    if len(ins)>10000:raise Blocked('function_too_large')
    if isa not in ('m68k','mips'):raise Blocked('isa_without_native_adapter')
    if isa=='m68k' and not language.startswith('68000:BE:32:'):raise Blocked('language_mismatch_m68k')
    if isa=='mips' and not language.startswith('MIPS:LE:32:'):raise Blocked('language_mismatch_mips')
    endian='big' if isa=='m68k' else 'little'
    addrset={i['address'] for i in ins}
    if len(addrset)!=len(ins):raise Blocked('duplicate_instructions')
    entry=function['entry']
    if entry not in addrset:raise Blocked('missing_entry_instruction')
    ordered=sorted(ins,key=lambda i:i['address'])
    for i in ordered:
        if i.get('call'):raise Blocked('external_call_requires_dispatch')
        if i.get('delay_slots',0):raise Blocked('delay_slot_requires_isa_qualification')
        if isa=='mips' and i.get('mnemonic','').lower() in ('jr','jalr','j','jal','beq','bne','bgez','bltz','bgtz','blez'):
            raise Blocked('mips_branch_delay_slot_requires_qualification')
        if not isinstance(i.get('pcode'),list) or not i['pcode']:raise Blocked('missing_pcode')
        if i.get('length',0)<1 or i['length']>16:raise Blocked('invalid_instruction_length')
    chunks=[]; regmap={}; operations=0
    for i in ordered:
        pc=i['address']; next_pc=i.get('fallthrough')
        out=[f'case 0x{pc:x}ULL: {{']
        done=False
        for operation in i['pcode']:
            op=operation.get('op','').upper();inputs=operation.get('inputs',[]);output=operation.get('output')
            if op not in SUPPORTED:raise Blocked('unsupported_pcode:'+op)
            operations+=1
            for v in [*inputs,output]:
                if v is not None:
                    vn(v)
                    if v['space']=='register' and v.get('name'):
                        key=(v['offset'],v['size']);regmap[key]=str(v['name'])[:100]
            if op in ('RETURN','BRANCH','CBRANCH'):
                if op=='RETURN':
                    out.append('return;');done=True;break
                if op=='BRANCH':
                    if len(inputs)!=1:raise Blocked('bad_branch_arity')
                    out.append(f'pc=0x{target(inputs[0],addrset):x}ULL; break;');done=True;break
                if len(inputs)!=2:raise Blocked('bad_cbranch_arity')
                if next_pc not in addrset:raise Blocked('conditional_fallthrough_unmapped')
                out.append(f'if ({r(inputs[1])} != 0ULL) {{pc=0x{target(inputs[0],addrset):x}ULL; break;}}')
                continue
            if op in ('LOAD','STORE') and operation.get('memory_space') not in ('ram',):
                raise Blocked('memory_space_not_qualified:'+str(operation.get('memory_space')))
            if op=='STORE':
                if len(inputs)!=3:raise Blocked('bad_store_arity')
                if vn(inputs[0])['space'] not in ('const','constant'):raise Blocked('nonconstant_memory_space')
                out.append(f'bus.write({r(inputs[1])}, {inputs[2]["size"]}, {r(inputs[2])});')
                continue
            if output is None:raise Blocked('missing_pcode_output:'+op)
            size=vn(output)['size']
            if op=='LOAD':
                if len(inputs)!=2:raise Blocked('bad_load_arity')
                if vn(inputs[0])['space'] not in ('const','constant'):raise Blocked('nonconstant_memory_space')
                expr=f'bus.read({r(inputs[1])}, {size})'
            elif op in ('COPY','INT_ZEXT'):
                if len(inputs)!=1:raise Blocked('bad_unary_arity')
                expr=r(inputs[0])
            elif op=='INT_SEXT':
                if len(inputs)!=1:raise Blocked('bad_unary_arity')
                expr=f'sextend({r(inputs[0])}, {inputs[0]["size"]})'
            elif op in ('INT_NEGATE','INT_2COMP','BOOL_NEGATE'):
                if len(inputs)!=1:raise Blocked('bad_unary_arity')
                a=r(inputs[0]);expr={'INT_NEGATE':f'(~{a})','INT_2COMP':f'(0ULL-{a})','BOOL_NEGATE':f'({a}==0ULL)'}[op]
            else:
                if len(inputs)!=2:raise Blocked('bad_binary_arity:'+op)
                a,b=r(inputs[0]),r(inputs[1]);bs=inputs[1]['size']
                expressions={
                   'INT_ADD':f'({a}+{b})','INT_SUB':f'({a}-{b})',
                   'INT_MULT':f'({a}*{b})',
                   'INT_AND':f'({a}&{b})','INT_OR':f'({a}|{b})','INT_XOR':f'({a}^{b})',
                   'INT_LEFT':f'shl({a},{b})','INT_RIGHT':f'shr({a},{b})',
                   'INT_SRIGHT':f'sar({a},{inputs[0]["size"]},{b})',
                   'INT_EQUAL':f'({a}=={b})','INT_NOTEQUAL':f'({a}!={b})',
                   'INT_LESS':f'({a}<{b})','INT_LESSEQUAL':f'({a}<={b})',
                   'INT_SLESS':f'(signedv({a},{inputs[0]["size"]})<signedv({b},{inputs[1]["size"]}))',
                   'INT_SLESSEQUAL':f'(signedv({a},{inputs[0]["size"]})<=signedv({b},{inputs[1]["size"]}))',
                   'INT_CARRY':f'carry({a},{b},{inputs[0]["size"]})',
                   'INT_SCARRY':f'scarry({a},{b},{inputs[0]["size"]})',
                   'INT_SBORROW':f'sborrow({a},{b},{inputs[0]["size"]})',
                   'BOOL_AND':f'(({a}!=0ULL)&&({b}!=0ULL))',
                   'BOOL_OR':f'(({a}!=0ULL)||({b}!=0ULL))',
                   'BOOL_XOR':f'(({a}!=0ULL)!=({b}!=0ULL))',
                   'PIECE':f'piece({a},{b},{bs})',
                   'SUBPIECE':f'subpiece({a},{b})',
                }
                if op not in expressions:raise Blocked('unsupported_pcode:'+op)
                if op=='PIECE' and sum(x['size'] for x in inputs)>8:raise Blocked('piece_wider_than_64')
                expr=expressions[op]
            out.append(w(output,expr))
        if not done:
            if next_pc not in addrset:raise Blocked('fallthrough_outside_function')
            out.append(f'pc=0x{next_pc:x}ULL; break;')
        out.append('}')
        chunks.extend(out)
    if not any(any(p.get('op','').upper()=='RETURN' for p in insn['pcode']) for insn in ins):
        raise Blocked('no_return_observed')
    regs=[{'offset':k[0],'size':k[1],'name':v} for k,v in sorted(regmap.items())]
    cpp=HEADER.replace('/*ENDIAN*/', 'true' if endian=='big' else 'false').replace('/*ENTRY*/',f'0x{entry:x}ULL')
    cpp=cpp.replace('/*CASES*/','\n'.join(chunks)).replace('/*DUMP_REGS*/','\n'.join(f'  std::cout << "{x["name"]} {x["offset"]} {x["size"]} " << rd(cpu.registers,{x["offset"]}ULL,{x["size"]}) << "\\n";' for x in regs))
    return {'cpp':cpp,'registers':regs,'operations':operations,'instructions':len(ins),'entry':entry,'is_a_complete_function_claim':'analyzer_candidate_only'}

HEADER=r'''// RecompDev v0.3.2.3 experimental raw P-code generated C++.
// Requires owner-provided memory map. Not hardware accurate or independently verified.
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <fstream>
#include <vector>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <limits>
using Bytes=std::unordered_map<uint64_t,uint8_t>;
static constexpr bool BIG_ENDIAN_TARGET=/*ENDIAN*/;
static uint64_t mask(int n){return n==8?UINT64_MAX:((1ULL<<(n*8))-1ULL);}
static uint64_t rd(const Bytes &b,uint64_t base,int n){
  if(n<1||n>8)throw std::runtime_error("invalid width");
  uint64_t v=0;
  for(int k=0;k<n;k++){auto it=b.find(base+(uint64_t)k);uint64_t x=(it==b.end()?0:it->second);
    if(BIG_ENDIAN_TARGET)v=(v<<8)|x;else v|=(x<<(8*k));}
  return v;
}
static void wr(Bytes &b,uint64_t base,int n,uint64_t v){
  if(n<1||n>8)throw std::runtime_error("invalid width");
  for(int k=0;k<n;k++){
    int shift=BIG_ENDIAN_TARGET?8*(n-k-1):8*k;
    b[base+(uint64_t)k]=(uint8_t)((v>>shift)&255);
  }
}
static uint64_t sextend(uint64_t v,int n){
  uint64_t m=mask(n);v&=m;uint64_t sign=1ULL<<(8*n-1);
  return (v^sign)-sign;
}
static int64_t signedv(uint64_t v,int n){
  if(n==8){int64_t x; static_assert(sizeof(x)==sizeof(v));
    // C++20 implementation does not assume signed overflow on host.
    if(v<=INT64_MAX)return (int64_t)v;
    return -(int64_t)(~v)-1;
  }
  uint64_t s=sextend(v,n);
  if(s<=INT64_MAX)return (int64_t)s;
  return -(int64_t)(~s)-1;
}
static uint64_t shl(uint64_t x,uint64_t shift){return shift>=64?0:(x<<shift);}
static uint64_t shr(uint64_t x,uint64_t shift){return shift>=64?0:(x>>shift);}
static uint64_t sar(uint64_t x,int width,uint64_t sh){
  int64_t v=signedv(x,width); if(sh>=64)return v<0?UINT64_MAX:0;
  if(sh==0)return (uint64_t)v;
  uint64_t low=((uint64_t)v)>>sh;
  if(v<0)low|=(~0ULL<<(64-sh));
  return low;
}
static uint64_t carry(uint64_t a,uint64_t b,int n){uint64_t m=mask(n);a&=m;b&=m;return a>m-b;}
static uint64_t scarry(uint64_t a,uint64_t b,int n){uint64_t m=mask(n),s=1ULL<<(8*n-1);
  a&=m;b&=m;uint64_t r=(a+b)&m;return ((~(a^b)&(a^r))&s)!=0;
}
static uint64_t sborrow(uint64_t a,uint64_t b,int n){uint64_t m=mask(n),s=1ULL<<(8*n-1);
  a&=m;b&=m;uint64_t r=(a-b)&m;return (((a^b)&(a^r))&s)!=0;
}
static uint64_t piece(uint64_t a,uint64_t b,int low){return low==8?b:((a<<(low*8))|b);}
static uint64_t subpiece(uint64_t a,uint64_t skip){return skip>=8?0:(a>>(skip*8));}
struct Bus {
  virtual uint64_t read(uint64_t address,int width)=0;
  virtual void write(uint64_t address,int width,uint64_t value)=0;
  virtual ~Bus()=default;
};
struct RecompCPUState {Bytes registers;};
static void recomp_function(RecompCPUState &state,Bus &bus) {
  Bytes &regs=state.registers;
  Bytes temps;
  uint64_t pc=/*ENTRY*/;
  for(int budget=0;budget<100000;budget++){
    switch(pc){
/*CASES*/
    default:throw std::runtime_error("control flow escaped function");
    }
  }
  throw std::runtime_error("instruction budget exhausted");
}
#ifdef RECOMP_STANDALONE_TEST
struct IOEvent {std::string kind;uint64_t address;int width;uint64_t value;};
struct SparseBus:Bus {Bytes mem; Bytes writes;std::vector<IOEvent> io_events;std::vector<uint8_t> image;uint64_t base=0;
  bool megadrive=false;
  static uint64_t addr24(uint64_t p){return p&0xffffffULL;}
  uint64_t canonical(uint64_t p)const{
    if(!megadrive)return p;
    p=addr24(p);
    // The 64KiB work RAM is mirrored throughout E00000-FFFFFF.
    return p>=0xe00000ULL ? (0xff0000ULL|(p&0xffffULL)) : p;
  }
  static std::string io_kind(uint64_t p){
    if(p>=0xc00000ULL&&p<=0xc00003ULL)return "VDP_DATA";
    if(p>=0xc00004ULL&&p<=0xc00007ULL)return "VDP_CONTROL";
    if(p==0xc00011ULL)return "PSG";
    if(p>=0xa10000ULL&&p<=0xa1001fULL)return "CONTROLLER_IO";
    if(p>=0xa11100ULL&&p<=0xa11101ULL)return "Z80_BUSREQ";
    if(p>=0xa11200ULL&&p<=0xa11201ULL)return "Z80_RESET";
    return "";
  }
  static bool qualified_io_write(uint64_t p,int width,const std::string &kind){
    if(kind=="VDP_DATA"||kind=="VDP_CONTROL")
      return (p%2==0)&&(width==2||width==4)&&p+(uint64_t)width<=((p&~3ULL)+4ULL);
    if(kind=="PSG")return p==0xc00011ULL&&width==1;
    if(kind=="CONTROLLER_IO")return width==1&&p>=0xa10001ULL&&p%2==1;
    if(kind=="Z80_BUSREQ"||kind=="Z80_RESET")
      return width==2&&p%2==0;
    return false;
  }
  std::vector<std::pair<uint64_t,uint64_t>> initialized_regions;
  void seed_ram(uint64_t addr,uint64_t len){
    if(len==0 || len>16ULL*1024ULL*1024ULL || addr>UINT64_MAX-len)
      throw std::runtime_error("invalid bounded RAM mapping");
    for(const auto &region:initialized_regions){
      if(addr<region.second && region.first<addr+len)
        throw std::runtime_error("overlapping RAM mappings");
    }
    initialized_regions.push_back({addr,addr+len});
  }
  bool in_ram(uint64_t p)const{
    for(const auto &region:initialized_regions)
      if(p>=region.first && p<region.second)return true;
    return false;
  }
  uint64_t read(uint64_t addr,int width)override {
    if(width<1||width>8)throw std::runtime_error("invalid read width");
    uint64_t v=0;
    for(int i=0;i<width;i++){
      uint64_t p=canonical(addr+(uint64_t)i);
      if(megadrive && !io_kind(p).empty())
        throw std::runtime_error("unmodelled hardware read at "+std::to_string(p));
      auto it=mem.find(p);uint8_t b=0;
      if(it!=mem.end() && (!megadrive || in_ram(p)))b=it->second;
      else if(p>=base && p-base<image.size())b=image[(size_t)(p-base)];
      else if(in_ram(p))b=0; // Explicit zero-seeded synthetic RAM only.
      else throw std::runtime_error("unmapped memory read at "+std::to_string(p));
      if(BIG_ENDIAN_TARGET)v=(v<<8)|b;else v|=((uint64_t)b<<(i*8));
    }
    return v;
  }
  void write(uint64_t addr,int width,uint64_t v)override {
    if(width<1||width>8)throw std::runtime_error("invalid write width");
    uint64_t begin=canonical(addr);
    if(megadrive){
      std::string kind=io_kind(begin);
      if(!kind.empty()){
        if(!qualified_io_write(begin,width,kind))
          throw std::runtime_error("unqualified hardware write at "+std::to_string(begin));
        io_events.push_back({kind,begin,width,v&mask(width)});
        return; // Observable side effect, NOT a device emulation.
      }
      for(int i=0;i<width;i++){
        uint64_t p=canonical(addr+(uint64_t)i);
        if(!io_kind(p).empty())throw std::runtime_error("hardware write crosses port boundary");
        if(!in_ram(p))throw std::runtime_error("unmapped or ROM memory write at "+std::to_string(p));
      }
      // RAM aliasing is resolved byte-by-byte; the bus does not allow writes to ROM.
      for(int i=0;i<width;i++){
        uint64_t p=canonical(addr+(uint64_t)i);
        int shift=BIG_ENDIAN_TARGET?8*(width-i-1):8*i;
        mem[p]=(uint8_t)((v>>shift)&255);
        writes[p]=mem[p];
      }
      return;
    }
    for(int i=0;i<width;i++){
      uint64_t p=addr+(uint64_t)i;
      if(!in_ram(p) && mem.find(p)==mem.end())
        throw std::runtime_error("unmapped memory write at "+std::to_string(p));
    }
    wr(mem,addr,width,v);
    for(int i=0;i<width;i++)writes[addr+(uint64_t)i]=mem[addr+(uint64_t)i];
  }
};
int main(int argc,char **argv){try {
  RecompCPUState cpu;SparseBus bus;
  for(int k=1;k<argc;k++){
    std::string arg=argv[k];
    if(arg=="--image"){
      if(k+4>=argc)throw std::runtime_error("--image PATH BASE OFFSET LENGTH");
      std::ifstream f(argv[++k],std::ios::binary);
      if(!f)throw std::runtime_error("image file could not be opened");
      bus.base=std::stoull(argv[++k],nullptr,0);
      uint64_t off=std::stoull(argv[++k],nullptr,0),len=std::stoull(argv[++k],nullptr,0);
      if(len>512ULL*1024ULL*1024ULL)throw std::runtime_error("image too large for verification");
      bus.image.resize((size_t)len);f.seekg((std::streamoff)off);
      f.read((char*)bus.image.data(),(std::streamsize)len);
      if((uint64_t)f.gcount()!=len)throw std::runtime_error("image short read");
      continue;
    }
    if(arg=="--megadrive-bus"){
      if(bus.megadrive)throw std::runtime_error("duplicate megadrive bus");
      bus.megadrive=true;
      bus.seed_ram(0xff0000ULL,65536ULL);
      continue;
    }
    if(arg=="--map-zero-ram"){
      if(k+2>=argc)throw std::runtime_error("--map-zero-ram BASE LENGTH");
      uint64_t addr=std::stoull(argv[++k],nullptr,0),len=std::stoull(argv[++k],nullptr,0);
      bus.seed_ram(addr,len);
      continue;
    }
    bool isMemory=arg.size()>2 && arg.substr(0,2)=="m:";
    if(isMemory)arg=arg.substr(2);
    size_t p=arg.find(':'),q=arg.find(':',p+1);
    if(p==std::string::npos||q==std::string::npos)throw std::runtime_error("expected offset:width:value");
    uint64_t off=std::stoull(arg.substr(0,p),nullptr,0),val=std::stoull(arg.substr(q+1),nullptr,0);
    int width=std::stoi(arg.substr(p+1,q-p-1));
    if(isMemory){
      uint64_t mapped=bus.canonical(off);
      if(bus.megadrive&&!bus.in_ram(mapped))
        throw std::runtime_error("fixture cannot seed non-RAM or hardware address");
      if(bus.megadrive){
        for(int i=0;i<width;i++){
          uint64_t p=bus.canonical(off+(uint64_t)i);
          if(!bus.in_ram(p))throw std::runtime_error("fixture crosses non-RAM");
          int shift=BIG_ENDIAN_TARGET?8*(width-i-1):8*i;
          bus.mem[p]=(uint8_t)((val>>shift)&255);
        }
      }else wr(bus.mem,off,width,val);
    }else wr(cpu.registers,off,width,val);
  }
  recomp_function(cpu,bus);
/*DUMP_REGS*/
  for(const auto &it:bus.writes)std::cout<<"MEM "<<it.first<<" 1 "<<(unsigned)it.second<<"\n";
  for(const auto &e:bus.io_events)std::cout<<"IO "<<e.kind<<" "<<e.address<<" "<<e.width<<" "<<e.value<<"\n";
  return 0;
} catch(const std::exception &e){std::cerr<<"RECOMP_ERROR="<<e.what()<<"\n";return 2;}}
#endif
'''
