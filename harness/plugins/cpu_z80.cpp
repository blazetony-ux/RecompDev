#include "rd_plugin.h"
namespace {
static int one(RD_CpuState *s,const RD_Bus *b,uint32_t *cycles){
 if(!s||!b||!cycles)return -1;
 if(s->halted){*cycles=0;return 0;}
 const auto pc=s->pc;
 const uint8_t op=b->read(b->ctx,pc);
 // This intentionally supports only the synthetic fixture's opcodes.
 // Unsupported opcodes fail closed; they are not silently treated as NOPs.
 switch(op){
 case 0x00: s->pc=uint16_t(pc+1);*cycles=4;break;
 case 0x3e:s->a=b->read(b->ctx,uint16_t(pc+1));s->pc=uint16_t(pc+2);*cycles=7;break;
 case 0xd3:{uint8_t port=b->read(b->ctx,uint16_t(pc+1));uint16_t full=uint16_t((s->a<<8)|port);b->out_port(b->ctx,full,s->a);s->pc=uint16_t(pc+2);*cycles=11;break;}
 case 0xdb:{uint8_t port=b->read(b->ctx,uint16_t(pc+1));uint16_t full=uint16_t((s->a<<8)|port);s->a=b->in_port(b->ctx,full);s->pc=uint16_t(pc+2);*cycles=11;break;}
 case 0x32:{uint16_t addr=uint16_t(b->read(b->ctx,uint16_t(pc+1)) | (b->read(b->ctx,uint16_t(pc+2))<<8));b->write(b->ctx,addr,s->a);s->pc=uint16_t(pc+3);*cycles=13;break;}
 case 0xc3:{uint16_t target=uint16_t(b->read(b->ctx,uint16_t(pc+1)) | (b->read(b->ctx,uint16_t(pc+2))<<8));s->pc=target;*cycles=10;break;}
 case 0x76:s->pc=uint16_t(pc+1);s->halted=1;*cycles=4;break;
 default:*cycles=0;return -1;
 }
 return 1;
}
const RD_CpuApi API={one};
const RD_Plugin PLUGIN={RD_ABI_VERSION,sizeof(RD_Plugin),RD_CPU,sizeof(API),"Z80 subset interpreter (synthetic fixture)",&API};
}
extern "C" RD_EXPORT const RD_Plugin *rd_get_plugin_v1(void){return &PLUGIN;}

// The original nativepilot/z80_cycles.hpp is retained untouched and reused for
// instruction timing admissibility. This decoder covers base, CB, documented
// ED and DD/FD forms, including indexed displacement and repeated prefixes.
#include "nativepilot/z80_cycles.hpp"
#include "rd_native_discovery_v1.h"
#include <algorithm>
#include <array>
// Optional production admission ABI, deliberately separate from RD_CpuApi.
// Native recovery remains owned by the authenticated legacy P-code engine.
// This gate independently checks unambiguous Z80 instruction lengths before
// a verified instruction is admitted to that engine. Unknown lengths are
// flagged for audit rather than guessed or silently executed as NOPs.
#include "rd_production_cpu_v1.h"
extern "C" RD_EXPORT int rd_z80_source_gate_v1(const uint8_t *bytes,
    uint32_t length, uint32_t physical_offset, RD_Z80SourceGateResultV1 *out) {
    if (!out || out->struct_size != sizeof(RD_Z80SourceGateResultV1) ||
        !bytes || length < 1 || length > 8 || physical_offset > 0x03ffffffu)
        return -2;
    const uint8_t op=bytes[0];
    uint32_t expected=0;
    uint32_t family=1;
    if(op==0xcb){ family=2; expected=2; }
    else if(op==0xed){
        family=3;
        if(length>=2){
            const uint8_t sub=bytes[1];
            expected = (sub==0x43||sub==0x4b||sub==0x53||sub==0x5b||
                        sub==0x63||sub==0x6b||sub==0x73||sub==0x7b) ? 4 : 2;
        }
    } else if(op==0xdd||op==0xfd){
        family=4;
        // Repeated index prefixes and IX/IY displacement rules require a
        // separate complete decoder. Never assert an unverified byte length.
    } else {
        // Complete for the unprefixed Z80 instruction length classes.
        if(op==0x01||op==0x11||op==0x21||op==0x31||
           op==0x22||op==0x2a||op==0x32||op==0x3a||
           op==0xc3||op==0xcd||
           (op&0xc7)==0xc2 || (op&0xc7)==0xc4)
            expected=3;
        else if((op&0xc7)==0x06 ||
                op==0x10||op==0x18||op==0x20||op==0x28||op==0x30||op==0x38||
                op==0xd3||op==0xdb||
                (op&0xc7)==0xc6)
            expected=2;
        else expected=1;
    }
    out->abi_version=RD_Z80_SOURCE_GATE_ABI;
    out->opcode_family=family;
    out->opcode=op;
    out->declared_length=length;
    out->expected_length=expected;
    if(expected && expected!=length) return -1;
    return expected ? 1 : 2;
}

// Conservative independent *source* decoder, not an executing CPU/translator.
// Never invent index-prefix lengths, dynamic branch destinations or bank state.
namespace {
static uint32_t base_length(uint8_t op){
 if(op==0x01||op==0x11||op==0x21||op==0x31||op==0x22||op==0x2a||op==0x32||op==0x3a||
    op==0xc3||op==0xcd||(op&0xc7)==0xc2||(op&0xc7)==0xc4)return 3;
 if((op&0xc7)==0x06||op==0x10||op==0x18||op==0x20||op==0x28||op==0x30||op==0x38||
    op==0xd3||op==0xdb||(op&0xc7)==0xc6)return 2;
 return 1;
}
static bool index_displacement(uint8_t op){
 if(op==0x34||op==0x35||op==0x36)return true;
 if(op>=0x40&&op<=0x7f&&op!=0x76)return ((op&7)==6)||((op&0x38)==0x30);
 return op>=0x80&&op<0xc0&&(op&7)==6;
}
static bool ed_documented(uint8_t op){
 // Match exactly the preserved timing engine's documented ED groups.
 if((op&0xc7)==0x40||(op&0xc7)==0x41||(op&0xcf)==0x42||(op&0xcf)==0x4a||
    (op&0xcf)==0x43||(op&0xcf)==0x4b||(op&0xc7)==0x44||
    (op&0xc7)==0x45||(op&0xc7)==0x46)return true;
 if(op==0x47||op==0x4f||op==0x57||op==0x5f||op==0x67||op==0x6f)return true;
 return (op>=0xa0&&op<=0xa3)||(op>=0xa8&&op<=0xab)||
        (op>=0xb0&&op<=0xb3)||(op>=0xb8&&op<=0xbb);
}
}
extern "C" RD_EXPORT int rd_z80_decode_source_v1(const RD_SourceV1*s,
 uint64_t physical,uint16_t pc,RD_Z80DecodeV1*r){
 if(!s||!r||s->abi_version!=RD_NATIVE_DISCOVERY_ABI||s->struct_size!=sizeof(*s)||!s->read||r->struct_size!=sizeof(*r))return -2;
 *r={};r->abi_version=RD_NATIVE_DISCOVERY_ABI;r->struct_size=sizeof(*r);r->pc=pc;
 constexpr uint32_t cap=16;
 std::array<uint8_t,cap> data{};
 uint32_t got=0;
 auto fetch=[&](uint32_t off)->bool{
  while(got<=off){if(got>=cap||physical+got>=s->byte_size||unsigned(pc)+got>=0x10000u||
    !s->read(s->ctx,physical+got,&data[got],1))return false;
   ++got;}
  return true;
 };
 if(!fetch(0))return -1;
 uint8_t op=data[0];r->opcode=op;
 uint32_t prefixes=0;
 while(op==0xdd||op==0xfd){
  if(++prefixes>8||!fetch(prefixes))return 2;
  op=data[prefixes];
 }
 uint32_t length=0;uint32_t arg=prefixes;
 if(op==0xcb){length=prefixes?prefixes+3:2;}
 else if(op==0xed){
  if(!fetch(prefixes+1))return -1;
  auto sub=data[prefixes+1];
  if(!ed_documented(sub))return 2;
  length=prefixes+((sub&0xcf)==0x43||(sub&0xcf)==0x4b?4u:2u);
 }else{
  length=prefixes+base_length(op);
  if(prefixes&&index_displacement(op))++length;
 }
 if(!length||length>cap||!fetch(length-1))return -1;
 // Prevent source-byte reads that cross a mapper window without independently
 // verifying the mapping for the second side of the instruction.
 if((unsigned(pc)&0x3fff)+length>0x4000)return 2;
 // The native timing engine from the frozen v0.4.0.45 implementation must
 // recognise the decoded instruction; unknown ED aliases fail closed.
 if(op==0xed){
  auto get=[&](uint16_t where)->uint8_t{return data[uint16_t(where-pc)];};
  if(!recomp::z80::decode(get,pc,uint16_t(pc+length),uint16_t(pc+length)).known)return 2;
 }
 r->length=length;r->flow=RD_FLOW_FALL;
 if(op==0xed){
  auto sub=data[prefixes+1];
  if((sub&0xc7)==0x45){r->flow=RD_FLOW_INDIRECT;}
 }else if(op==0x76){r->flow=RD_FLOW_STOP;}
 else if(op==0xc9){r->flow=RD_FLOW_RETURN;}
 else if((op&0xc7)==0xc0){r->flow=RD_FLOW_INDIRECT;r->conditional=1;}
 else if(op==0xe9){r->flow=RD_FLOW_INDIRECT;}
 else if(op==0xc3||op==0xcd||(op&0xc7)==0xc2||(op&0xc7)==0xc4){
  r->target=uint16_t(data[arg+1]|(uint16_t(data[arg+2])<<8));
  r->conditional=(op!=0xc3&&op!=0xcd);
  r->flow=op==0xcd||(op&0xc7)==0xc4?RD_FLOW_CALL:r->conditional?RD_FLOW_COND:RD_FLOW_JUMP;
 }else if(op==0x10||op==0x18||op==0x20||op==0x28||op==0x30||op==0x38){
  r->target=uint16_t(pc+length+int8_t(data[arg+1]));
  r->conditional=op!=0x18;r->flow=r->conditional?RD_FLOW_COND:RD_FLOW_JUMP;
 }else if((op&0xc7)==0xc7){r->target=uint16_t(op&0x38);r->flow=RD_FLOW_CALL;}
 r->status=1;return 1;
}
// Conservative Z80 register constant/absolute-write effects; mapper state is
// owned by the machine DLL. We never infer effects of undocumented opcodes.
extern "C" RD_EXPORT int rd_z80_abstract_a_v1(const uint8_t*b,uint32_t n,
 RD_Z80AbstractV1*a,RD_Z80EffectV1*effect){
 if(!b||!a||!effect||a->abi_version!=RD_NATIVE_DISCOVERY_ABI||
   a->struct_size!=sizeof(*a)||effect->struct_size!=sizeof(*effect)||n==0||n>16)return -1;
 *effect={};effect->abi_version=RD_NATIVE_DISCOVERY_ABI;effect->struct_size=sizeof(*effect);
 const uint8_t op=b[0];
 if(op==0x32&&n==3){effect->write_kind=RD_Z80_EFFECT_ABSOLUTE;
  effect->absolute=uint16_t(b[1]|(uint16_t(b[2])<<8));
  effect->value_known=a->known_a;effect->value=a->a;}
 else if(op==0x22&&n==3){ // two-byte write may overlap mapper bytes
  effect->write_kind=RD_Z80_EFFECT_UNRESOLVED;
  effect->absolute=uint16_t(b[1]|(uint16_t(b[2])<<8));
 }else if(op==0x34||op==0x35||op==0x36||op==0x77||op==0x70||op==0x71||op==0x72||
          op==0x73||op==0x74||op==0x75||op==0xe3||op==0xc5||op==0xd5||op==0xe5||op==0xf5){
  effect->write_kind=RD_Z80_EFFECT_UNRESOLVED;effect->absolute=0xffff;
 }
 if(op==0x31&&n==3){a->known_sp=1;a->sp=uint16_t(b[1]|uint16_t(b[2])<<8);}
 if(op==0xcd||(op&0xc7)==0xc4||(op&0xc7)==0xc7){
  // Only preserve mapper state across the branch if the explicit stack write
  // cannot hit the mapper register range (FFFC-FFFF).
  if(!a->known_sp||uint16_t(a->sp-1)>=0xfffc||uint16_t(a->sp-2)>=0xfffc){
   effect->write_kind=RD_Z80_EFFECT_UNRESOLVED;effect->absolute=0xffff;
  }
  if(a->known_sp)a->sp=uint16_t(a->sp-2);
 }
 if(op==0x3e&&n==2){a->known_a=1;a->a=b[1];return 1;}
 if(op==0xaf&&n==1){a->known_a=1;a->a=0;return 1;}
 // Recognised instructions not changing A. Others invalidate constant A.
 if(op==0xc3||op==0xcd||op==0xc9||op==0xf3||op==0xfb||op==0x32||op==0x76||
    op==0x01||op==0x11||op==0x21||op==0x31||op==0x22||op==0x18||
    (op==0xed&&n>=2&&(b[1]&0xc7)==0x46))return 1;
 a->known_a=0;return 1;
}
