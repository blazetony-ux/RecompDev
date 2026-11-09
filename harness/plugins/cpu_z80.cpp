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
#include "z80_cycles.hpp"
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
extern "C" RD_EXPORT int rd_z80_source_entrypoints_v1(RD_Z80EntryPointsV1*out){
 if(!out||out->struct_size!=sizeof(*out))return -1;
 *out={};out->abi_version=RD_NATIVE_DISCOVERY_ABI;
 out->struct_size=sizeof(*out);out->count=3;
 out->pc[0]=0x0000;out->kind[0]=0;
 out->pc[1]=0x0038;out->kind[1]=1;
 out->pc[2]=0x0066;out->kind[2]=2;
 return 1;
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
  if((sub&0xc7)==0x45){r->flow=RD_FLOW_RETURN;}
  // Z80 block-repeat instructions re-execute at the same guest PC while
  // the counter/compare condition holds. Both edges are source candidates.
  else if((sub>=0xb0&&sub<=0xb3)||(sub>=0xb8&&sub<=0xbb)){
   r->flow=RD_FLOW_COND;r->conditional=1;r->target=pc;
  }
 }else if(op==0x76){r->flow=RD_FLOW_STOP;}
 else if(op==0xc9){r->flow=RD_FLOW_RETURN;}
 else if((op&0xc7)==0xc0){r->flow=RD_FLOW_RETURN;r->conditional=1;}
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

// ABI v2: source-only, explicit register-pair abstract state. This does NOT
// execute code. It allows safe bank tracking through PUSH, LDI and known
// absolute/indirect writes without assuming unknown data or register values.
extern "C" RD_EXPORT int rd_z80_abstract_effect_v2(const uint8_t*b,uint32_t n,
 RD_Z80AbstractV2*a,RD_Z80EffectV1*e){
 if(!b||!a||!e||n<1||n>16||a->abi_version!=RD_NATIVE_DISCOVERY_ABI||
    a->struct_size!=sizeof(*a)||e->struct_size!=sizeof(*e))return -1;
 *e={};e->abi_version=RD_NATIVE_DISCOVERY_ABI;e->struct_size=sizeof(*e);
 const auto op=b[0];
 const auto word=[&](){return uint16_t(b[1]|(uint16_t(b[2])<<8));};
 const auto uncertain=[&](){e->write_kind=RD_Z80_EFFECT_UNRESOLVED;e->absolute=0xffff;};
 const auto writes=[&](bool known,uint16_t addr,unsigned count){
  if(!known){uncertain();return;}
  // Wrapped writes must be checked byte-by-byte. Nothing below FFFC is
  // allowed to silently cover a mapper register via address wrap.
  for(unsigned k=0;k<count;++k)if(uint16_t(addr+k)>=0xfffc){
   uncertain();return;
  }
 };
 const auto normal_a=[&](){a->known_a=0;};
 if(op==0x31&&n==3){a->known_sp=1;a->sp=word();return 1;}
 if(op==0x01&&n==3){a->known_bc=1;a->bc=word();return 1;}
 if(op==0x11&&n==3){a->known_de=1;a->de=word();return 1;}
 if(op==0x21&&n==3){a->known_hl=1;a->hl=word();return 1;}
 if(n==2&&(op&0xc7)==0x06 && op!=0x36){
  if(op==0x3e){a->known_a=1;a->a=b[1];}
  else if(op==0x06&&a->known_bc)a->bc=uint16_t((a->bc&0x00ff)|(unsigned(b[1])<<8));
  else if(op==0x0e&&a->known_bc)a->bc=uint16_t((a->bc&0xff00)|unsigned(b[1]));
  else if(op==0x16&&a->known_de)a->de=uint16_t((a->de&0x00ff)|(unsigned(b[1])<<8));
  else if(op==0x1e&&a->known_de)a->de=uint16_t((a->de&0xff00)|unsigned(b[1]));
  else if(op==0x26&&a->known_hl)a->hl=uint16_t((a->hl&0x00ff)|(unsigned(b[1])<<8));
  else if(op==0x2e&&a->known_hl)a->hl=uint16_t((a->hl&0xff00)|unsigned(b[1]));
  return 1;
 }
 if(op==0xaf&&n==1){a->known_a=1;a->a=0;return 1;}
 // INC/DEC r never write to mapped RAM (the (HL) cases are handled below).
 // Preserve the bank mapping while propagating any known 8-bit register.
 if(n==1&&((op&0xc7)==0x04||(op&0xc7)==0x05)){
  const unsigned reg=(op>>3)&7;
  if(reg!=6){
   const int delta=(op&1)?-1:1;
   auto adjust=[&](uint16_t&pair,bool known,bool high){
    if(!known)return;
    const unsigned shift=high?8:0;
    const unsigned val=((pair>>shift)+delta)&0xffu;
    pair=uint16_t((pair&~(0xffu<<shift))|(val<<shift));
   };
   switch(reg){
    case 0:adjust(a->bc,a->known_bc, true);break;
    case 1:adjust(a->bc,a->known_bc,false);break;
    case 2:adjust(a->de,a->known_de, true);break;
    case 3:adjust(a->de,a->known_de,false);break;
    case 4:adjust(a->hl,a->known_hl, true);break;
    case 5:adjust(a->hl,a->known_hl,false);break;
    case 7:if(a->known_a)a->a=uint8_t(a->a+delta);break;
   }
   return 1;
  }
 }
 // CB BIT is a pure read (including BIT b,(HL)); it never writes mapper
 // registers. RES/SET and shifts update their register or (HL) operand.
 // Do not erase a known ROM bank merely because flags are updated.
 if(op==0xcb&&n==2){
  const unsigned sub=b[1],kind=sub>>6,reg=sub&7u;
  if(kind==1)return 1; // BIT b,r: flags only
  if(reg==6)writes(a->known_hl,a->hl,1);
  else if(reg<=1)a->known_bc=0;
  else if(reg<=3)a->known_de=0;
  else if(reg<=5)a->known_hl=0;
  else normal_a();
  return 1;
 }
 if(op==0x19){if(a->known_hl&&a->known_de)a->hl=uint16_t(a->hl+a->de);
                  else a->known_hl=0;return 1;}
 if(op==0x10&&n==2){if(a->known_bc)a->bc=uint16_t((a->bc&0x00ff)|(((a->bc>>8)-1u)&0xffu)<<8);
                  return 1;}
 if(op==0x03||op==0x0b){if(a->known_bc)a->bc=uint16_t(a->bc+(op==0x03?1:-1));return 1;}
 if(op==0x13||op==0x1b){if(a->known_de)a->de=uint16_t(a->de+(op==0x13?1:-1));return 1;}
 if(op==0x23||op==0x2b){if(a->known_hl)a->hl=uint16_t(a->hl+(op==0x23?1:-1));return 1;}
 if(op==0x32&&n==3){e->write_kind=RD_Z80_EFFECT_ABSOLUTE;e->absolute=word();
  e->value_known=a->known_a;e->value=a->a;return 1;}
 if(op==0x22&&n==3){writes(true,word(),2);return 1;}
 if(op==0x02||op==0x0a||op==0x12||op==0x1a){
  if(op==0x02)writes(a->known_bc,a->bc,1);
  if(op==0x12)writes(a->known_de,a->de,1);
  if(op==0x0a||op==0x1a)normal_a();
  return 1;
 }
 if(op==0x34||op==0x35||op==0x36||op==0x70||op==0x71||op==0x72||
    op==0x73||op==0x74||op==0x75||op==0x77){
  writes(a->known_hl,a->hl,1);return 1;
 }
 if(op==0xe3){writes(a->known_sp,a->sp,2);a->known_hl=0;return 1;}
 if(op==0xc5||op==0xd5||op==0xe5||op==0xf5){
  const auto new_sp=uint16_t(a->sp-2);
  writes(a->known_sp,new_sp,2);
  if(a->known_sp)a->sp=new_sp;
  return 1;
 }
 if(op==0xc1||op==0xd1||op==0xe1||op==0xf1){
  if(a->known_sp)a->sp=uint16_t(a->sp+2);
  if(op==0xc1)a->known_bc=0;
  if(op==0xd1)a->known_de=0;
  if(op==0xe1)a->known_hl=0;
  if(op==0xf1)normal_a();
  return 1;
 }
 if(op==0xcd||((op&0xc7)==0xc4)||(op&0xc7)==0xc7){
  auto new_sp=uint16_t(a->sp-2);writes(a->known_sp,new_sp,2);
  if(a->known_sp)a->sp=new_sp;return 1;
 }
 if(op==0xed&&n>=2){
  const auto sub=b[1];
  if(sub==0xa0||sub==0xa8||sub==0xb0||sub==0xb8){
   writes(a->known_de,a->de,1);
   const auto delta=(sub==0xa0||sub==0xb0)?1:-1;
   if(a->known_hl)a->hl=uint16_t(a->hl+delta);
   if(a->known_de)a->de=uint16_t(a->de+delta);
   if(a->known_bc)a->bc=uint16_t(a->bc-1);
   // Repeating forms branch to themselves until BC reaches zero. Without
   // a verified iteration count the post-loop values are not constants.
   if(sub==0xb0||sub==0xb8)a->known_bc=a->known_de=a->known_hl=0;
   return 1;
  }
  if(sub==0xa1||sub==0xa9||sub==0xb1||sub==0xb9){
   if(a->known_hl)a->hl=uint16_t(a->hl+((sub==0xa1||sub==0xb1)?1:-1));
   if(a->known_bc)a->bc=uint16_t(a->bc-1);
   if(sub==0xb1||sub==0xb9)a->known_bc=a->known_hl=0;
   return 1;
  }
  // Input/output Z80 ED instructions affect *ports*, not SMS mapper memory
  // registers (FFFC-FFFF). Preserve known bank state. ED block input forms
  // also write to (HL), which must be range-checked independently.
  if(sub==0xa2||sub==0xaa||sub==0xb2||sub==0xba||
     sub==0xa3||sub==0xab||sub==0xb3||sub==0xbb){
   const bool is_input=(sub&3)==2;
   const bool backwards=(sub&8)!=0;
   const bool repeat=(sub&0x10)!=0;
   if(is_input)writes(a->known_hl,a->hl,1);
   if(a->known_hl)a->hl=uint16_t(a->hl+(backwards?-1:1));
   if(a->known_bc)a->bc=uint16_t((a->bc&0xff)|((((a->bc>>8)-1u)&0xffu)<<8));
   if(repeat){a->known_bc=0;a->known_hl=0;}
   return 1;
  }
  if((sub&0xc7)==0x40){ // IN r,(C): changes the destination register only
   switch((sub>>3)&7){
    case 0:case 1:a->known_bc=0;break;
    case 2:case 3:a->known_de=0;break;
    case 4:case 5:a->known_hl=0;break;
    case 7:normal_a();break;
   }
   return 1;
  }
  if((sub&0xc7)==0x41)return 1; // OUT (C),r: port, not mapped RAM
  if((sub&0xc7)==0x45){if(a->known_sp)a->sp=uint16_t(a->sp+2);return 1;}
  if((sub&0xc7)==0x46||sub==0x47||sub==0x4f)return 1;
 }
 if(op==0xc9||(op&0xc7)==0xc0){
  if(a->known_sp)a->sp=uint16_t(a->sp+2);return 1;
 }
 if(op==0xd3&&n==2)return 1; // OUT (n),A uses the I/O bus
 // Register-to-register LD and ALU r are memory-read-only except
 // LD (HL),r, handled earlier. They cannot modify mapper registers.
 if(op>=0x40&&op<=0xbf){
  if(op>=0x40&&op<=0x7f){
   const unsigned dest=(op>>3)&7;
   const unsigned src=op&7;
   const bool source_known=src==7?a->known_a:
      (src<=1?a->known_bc:(src<=3?a->known_de:(src<=5?a->known_hl:false)));
   if(dest==7){a->known_a=0;}
   else if(dest<=1){a->known_bc=0;}
   else if(dest<=3){a->known_de=0;}
   else if(dest<=5){a->known_hl=0;}
   (void)source_known;
  }else normal_a();
  return 1;
 }
 // Immediate arithmetic changes A and flags only.
 if(n==2&&(op&0xc7)==0xc6){normal_a();return 1;}
 // Control flow and flag-only operations do not write memory, hence
 // cannot invalidate an otherwise known mapper context. The controller
 // still tracks taken/fallthrough paths, call stacks and physical banks.
 const bool relative_branch=(op==0x18||op==0x20||op==0x28||op==0x30||op==0x38);
 const bool absolute_branch=(op==0xc3||(op&0xc7)==0xc2);
 if(op==0xf3||op==0xfb||op==0x00||op==0x76||op==0xe9||
    op==0x37||op==0x3f||relative_branch||absolute_branch||
    op==0x08||op==0xd9){
  if(op==0x08||op==0xd9){a->known_bc=a->known_de=a->known_hl=0;normal_a();}
  return 1;
 }
 // A-only arithmetic and port reads do not touch SMS bank registers.
 if(op==0x2f||op==0x27||op==0x07||op==0x0f||op==0x17||op==0x1f||
    (op==0xdb&&n==2)){normal_a();return 1;}
 // Any opcode not modelled in the abstract state must not invent constants.
 a->known_bc=a->known_de=a->known_hl=0;normal_a();
 // A decoded unknown instruction may have an indirect mapper write.
 uncertain();return 1;
}

// Native C++ code generation for a deliberately bounded, fully decoded subset.
// This is source lifting, not an interpreter fallback. The caller checks the
// source's full SHA-256, individual instruction SHA-256 and runtime bytes.
#include "rd_z80_native_codegen_v1.h"
#include <cstring>
#include <string>
extern "C" RD_EXPORT int rd_z80_emit_native_full_v1(const uint8_t *bytes,uint32_t length,
 RD_Z80NativeCodeV1 *out){
 if(!bytes||!out||out->struct_size!=sizeof(*out)||length<1||length>16)return -1;
 *out={};out->abi_version=RD_Z80_NATIVE_CODEGEN_ABI_V1;out->struct_size=sizeof(*out);
 // A separate Z80 op is supported only after independent length validation.
 // Preserve the frozen Ghidra P-code's F behaviour: H,N cleared, P/V reflects
 // updated BC; all other bits retained. No undocumented bit-3/5 claims.
 const char *body=nullptr;
 bool block_repeat=false;
 if(length==2&&bytes[0]==0xed&&(bytes[1]==0xa0||bytes[1]==0xa8||
                                    bytes[1]==0xb0||bytes[1]==0xb8)){
  const bool decrement=(bytes[1]==0xa8||bytes[1]==0xb8);
  block_repeat=(bytes[1]==0xb0||bytes[1]==0xb8);
  if(!decrement)body=R"CPP(
   const auto rd_hl=std::uint16_t(s.get_register(6u,2u));
   const auto rd_de=std::uint16_t(s.get_register(4u,2u));
   const auto rd_bc=std::uint16_t(s.get_register(2u,2u)-1u);
   const auto rd_value=std::uint8_t(s.read_byte(rd_hl));
   s.write_byte(rd_de,rd_value);
   s.set_register(6u,2u,std::uint16_t(rd_hl+1u));
   s.set_register(4u,2u,std::uint16_t(rd_de+1u));
   s.set_register(2u,2u,rd_bc);
   const auto rd_a=std::uint8_t(s.get_register(1u,1u));
   const auto rd_n=std::uint8_t(rd_a+rd_value);
   s.set_register(0u,1u,(s.get_register(0u,1u)&0xc1u)|(rd_n&0x08u)|((rd_n&0x02u)<<4)|(rd_bc?0x04u:0u));
  )CPP";
  else body=R"CPP(
   const auto rd_hl=std::uint16_t(s.get_register(6u,2u));
   const auto rd_de=std::uint16_t(s.get_register(4u,2u));
   const auto rd_bc=std::uint16_t(s.get_register(2u,2u)-1u);
   const auto rd_value=std::uint8_t(s.read_byte(rd_hl));
   s.write_byte(rd_de,rd_value);
   s.set_register(6u,2u,std::uint16_t(rd_hl-1u));
   s.set_register(4u,2u,std::uint16_t(rd_de-1u));
   s.set_register(2u,2u,rd_bc);
   const auto rd_a=std::uint8_t(s.get_register(1u,1u));
   const auto rd_n=std::uint8_t(rd_a+rd_value);
   s.set_register(0u,1u,(s.get_register(0u,1u)&0xc1u)|(rd_n&0x08u)|((rd_n&0x02u)<<4)|(rd_bc?0x04u:0u));
  )CPP";
 }
 std::string cpp=body?body:"";
 // LDIR/LDDR are native repeated LDI/LDD micro-operations.  Re-execute
 // the same source-attested instruction while the 16-bit BC count is nonzero.
 // The source-driven timing model distinguishes 21-T repeat from 16-T exit.
 if(block_repeat)cpp+="if(rd_bc!=0u)next=s.pc;";
 // Extend fully source-verified native lifting to the Z80 block I/O forms.
 // The output's memory/port behaviour and *undocumented* flags follow the
 // native Z80 specification; the external runtime remains CPU-agnostic.
 // In particular, OUTI/OTIR place the old BC on the 16-bit port address bus,
 // whereas INI/INIR use BC after B has been decremented.
 if(cpp.empty()&&length==2&&bytes[0]==0xed){
  const unsigned sub=bytes[1];
  if(sub==0xa2||sub==0xaa||sub==0xb2||sub==0xba||
     sub==0xa3||sub==0xab||sub==0xb3||sub==0xbb){
   const bool input=(sub&3)==2,backwards=(sub&8)!=0,repeat=(sub&0x10)!=0;
   const std::string delta=backwards?"-1u":"+1u";
   cpp=R"CPP(
    { const auto rd_bc=std::uint16_t(s.get_register(2u,2u));
      const auto rd_hl=std::uint16_t(s.get_register(6u,2u));
      const auto rd_b=std::uint8_t((rd_bc>>8)-1u);
      const auto rd_bc_new=std::uint16_t((std::uint16_t(rd_b)<<8)|(rd_bc&0xffu));
      const auto rd_hl_new=std::uint16_t(rd_hl RD_DELTA);
      std::uint8_t rd_value=0;
      RD_TRANSFER
      s.set_register(2u,2u,rd_bc_new);
      s.set_register(6u,2u,rd_hl_new);
      // Y/X/S from B, Z from B==0, N from transferred bit 7.
      const auto rd_extra=std::uint32_t(rd_value)+std::uint32_t(RD_PORT_SUM);
      auto rd_parity=std::uint8_t((rd_extra&7u)^rd_b);
      rd_parity^=std::uint8_t(rd_parity>>4);
      rd_parity^=std::uint8_t(rd_parity>>2);
      rd_parity^=std::uint8_t(rd_parity>>1);
      const std::uint8_t rd_flags=std::uint8_t((rd_b&0xa8u)|
       (rd_b==0?0x40u:0u)|(rd_value&0x80u?0x02u:0u)|
       (rd_extra>255u?0x11u:0u)|((rd_parity&1u)?0u:0x04u));
      s.set_register(0u,1u,rd_flags);
      RD_REPEAT
    }
   )CPP";
   auto replace_all=[&](const std::string&key,const std::string&replacement){
    size_t at=0;while((at=cpp.find(key,at))!=std::string::npos){cpp.replace(at,key.size(),replacement);at+=replacement.size();}
   };
   replace_all("RD_DELTA",delta);
   replace_all("RD_TRANSFER",input?
    "rd_value=s.in(rd_bc_new);s.write_byte(rd_hl,rd_value);":
    "rd_value=s.read_byte(rd_hl);s.out(rd_bc,rd_value);");
   replace_all("RD_PORT_SUM",input?
    (backwards?"std::uint8_t((rd_bc&0xffu)-1u)":"std::uint8_t((rd_bc&0xffu)+1u)"):
    "std::uint8_t(rd_hl_new&0xffu)");
   replace_all("RD_REPEAT",repeat?"if(rd_b!=0u)next=s.pc;":"");
  }else if((sub&0xc7)==0x41){
   // ED 41/49/.../79: OUT (C),r. ED 71 drives a zero data byte.
   const unsigned reg=(sub>>3)&7;
   constexpr unsigned offs[8]={3,2,5,4,7,6,0,1};
   cpp="s.out(std::uint16_t(s.get_register(2u,2u)),"+
     (reg==6?std::string("0u"):"std::uint8_t(s.get_register("+
      std::to_string(offs[reg])+"u,1u))")+");";
  }
 }
 // Source-lift CB BIT, RES and SET, including memory operands. The CPU
 // plugin owns flags and register semantics; the controller sees only a
 // verified source-instruction body. Rotates/shifts remain unsupported here.
 if(cpp.empty()&&length==2&&bytes[0]==0xcb){
  const unsigned sub=bytes[1],group=sub>>6,bit=(sub>>3)&7u,reg=sub&7u;
  if(group>=1){
   constexpr unsigned offs[8]={3,2,5,4,7,6,0,1};
   std::string address="std::uint16_t(s.get_register(6u,2u))";
   std::string value=reg==6?"std::uint8_t(s.read_byte("+address+"))":
     "std::uint8_t(s.get_register("+std::to_string(offs[reg])+"u,1u))";
   if(group==1){
    // BIT sets H, clears N, preserves C. S is meaningful only for bit 7.
    // The undocumented X/Y bits on memory BIT come from the effective
    // address high byte rather than the operand's value.
    const std::string bits=reg==6?
      "std::uint8_t("+address+">>8)":"rd_val";
    cpp="{const auto rd_val="+value+";"
      "const bool rd_set=((rd_val>>"+std::to_string(bit)+"u)&1u)!=0u;"
      "const auto rd_xy="+bits+";"
      "auto rd_f=std::uint8_t((s.get_register(0u,1u)&1u)|0x10u|(rd_xy&0x28u)|"
      "(rd_set?0u:0x44u)|"+std::string(bit==7?"(rd_set?0x80u:0u)":"0u")+");s.set_register(0u,1u,rd_f);}";
   }else{
    const std::string modified="std::uint8_t(rd_val"+
      std::string(group==2?"&~":"|")+"(1u<<"+std::to_string(bit)+"u))";
    cpp="{const auto rd_val="+value+";const auto rd_new="+modified+";"+
      (reg==6?"s.write_byte("+address+",rd_new);":
       "s.set_register("+std::to_string(offs[reg])+"u,1u,rd_new);")+"}";
   }
  }
 }
 // The additional source-byte-verified forms have direct Z80 semantics and
 // no conditional flags (except DI/XOR A). They do not inspect ROM titles.
 const auto op=bytes[0];
 const auto imm16=(length==3)?unsigned(bytes[1]|(unsigned(bytes[2])<<8)):0u;
 if(cpp.empty()&&length==3){
  if(op==0x01||op==0x11||op==0x21||op==0x31){
   const unsigned reg=op==0x01?2:(op==0x11?4:(op==0x21?6:68));
   cpp="s.set_register("+std::to_string(reg)+"u,2u,"+std::to_string(imm16)+"u);";
  }else if(op==0x32){
   cpp="s.write_byte("+std::to_string(imm16)+"u,static_cast<std::uint8_t>(s.get_register(1u,1u)));";
  }else if(op==0xc3){cpp="next="+std::to_string(imm16)+"u;";}
  else if(op==0xcd){
   cpp="{auto sp=std::uint16_t(s.get_register(68u,2u)-2u);"
       "s.write_memory(sp,2u,std::uint16_t(s.pc+3u));s.set_register(68u,2u,sp);"
       "next="+std::to_string(imm16)+"u;}";
  }
 }
 if(cpp.empty()&&length==2){
  // Relative branches are recompiled directly from verified source bytes;
  // their conditions use Z80 F flags, never ROM- or game-specific addresses.
  if(op==0x18||op==0x20||op==0x28||op==0x30||op==0x38){
   const auto displacement=int(int8_t(bytes[1]));
   const std::string destination="std::uint16_t(s.pc+2u+("+
     std::to_string(displacement)+"))";
   if(op==0x18)cpp="next="+destination+";";
   else{
    const unsigned mask=(op==0x20||op==0x28)?0x40u:0x01u;
    const bool if_set=(op==0x28||op==0x38);
    cpp="if((s.get_register(0u,1u)&"+std::to_string(mask)+"u)"+
      std::string(if_set?"!=0u":"==0u")+")next="+destination+";";
   }
  }
  else if((op&0xc7)==0x06&&op!=0x36){
   const unsigned r=(op>>3)&7;
   // Source register order B,C,D,E,H,L,(HL),A maps to Ghidra F,A,C,B,E,D,L,H.
   constexpr unsigned offsets[8]={3,2,5,4,7,6,0,1};
   cpp="s.set_register("+std::to_string(offsets[r])+"u,1u,"+
       std::to_string(unsigned(bytes[1]))+"u);";
  }
  else if(op==0x36)cpp="s.write_byte(std::uint16_t(s.get_register(6u,2u)),"+
     std::to_string(unsigned(bytes[1]))+"u);";
  else if(op==0xd3)cpp="s.out(std::uint16_t((s.get_register(1u,1u)<<8)|"+
    std::to_string(unsigned(bytes[1]))+"u),std::uint8_t(s.get_register(1u,1u)));";
  else if(op==0xdb)cpp="s.set_register(1u,1u,s.in(std::uint16_t((s.get_register(1u,1u)<<8)|"+
    std::to_string(unsigned(bytes[1]))+"u)));";
  else if(op==0xed&&bytes[1]==0x56)cpp="s.interrupt_mode=1;";
  else if(op==0x10){
   const auto displacement=int(int8_t(bytes[1]));
   cpp="{const auto b=std::uint8_t(s.get_register(3u,1u)-1u);"
       "s.set_register(3u,1u,b);if(b)next=std::uint16_t(s.pc+2u+("+
       std::to_string(displacement)+"));}";
  }
 }
 if(cpp.empty()&&length==1){
  if(op==0x00)cpp="/* NOP */";
  else if(op==0xf3)cpp="s.on_di();";
  else if(op==0xfb)cpp="s.on_ei();";
  else if(op==0x76)cpp="s.halted=true;";
  // The Z80 CPU owns the *semantic* of this indirect branch; its target is
  // read from the live register at execution time, not guessed by discovery.
  else if(op==0xe9)cpp="next=std::uint16_t(s.get_register(6u,2u));";
  else if(op==0x77)cpp="s.write_byte(std::uint16_t(s.get_register(6u,2u)),static_cast<std::uint8_t>(s.get_register(1u,1u)));";
  else if((op&0xc7)==0x04||(op&0xc7)==0x05){
   const unsigned reg=(op>>3)&7;
   constexpr unsigned offs[8]={3,2,5,4,7,6,0,1};
   if(reg!=6){
    const bool dec=(op&1)!=0;
    const auto off=std::to_string(offs[reg]);
    cpp="{const auto v=std::uint8_t(s.get_register("+off+"u,1u));"
      "const auto r=std::uint8_t(v"+std::string(dec?"-1u":"+1u")+");"
      "const auto oldf=std::uint8_t(s.get_register(0u,1u));"
      "const auto f=std::uint8_t((oldf&1u)|(r&0xa8u)|(r==0?0x40u:0u)|"+
      std::string(dec?"0x02u":"0u")+"|"+
      (dec?"((v&15u)==0u?0x10u:0u)|((v==0x80u)?0x04u:0u)":"((v&15u)==15u?0x10u:0u)|((v==0x7fu)?0x04u:0u)")+
      ");s.set_register("+off+"u,1u,r);s.set_register(0u,1u,f);}";
   }
  }
  else if(op==0xaf)cpp="s.set_register(1u,1u,0u);s.set_register(0u,1u,0x44u);";
  else if((op&0xc7)==0xc0){
   // Conditional RET NZ/Z/NC/C/PO/PE/P/M: check the CPU flags and
   // consume the stack only when the condition is true.
   constexpr unsigned mask[8]={0x40u,0x40u,0x01u,0x01u,0x04u,0x04u,0x80u,0x80u};
   const unsigned cc=(op>>3)&7u;
   const std::string condition="(s.get_register(0u,1u)&"+std::to_string(mask[cc])+"u)"+
      std::string((cc&1u)?"!=0u":"==0u");
   cpp="if("+condition+"){const auto rd_sp=std::uint16_t(s.get_register(68u,2u));"
      "next=std::uint16_t(s.memory(rd_sp,2u));s.set_register(68u,2u,std::uint16_t(rd_sp+2u));}";
  }
  else if(op==0xc9)cpp="{auto sp=std::uint16_t(s.get_register(68u,2u));"
    "next=std::uint16_t(s.memory(sp,2u));s.set_register(68u,2u,std::uint16_t(sp+2u));}";
  else if(op==0x19)cpp=R"CPP(
   {const auto hl=std::uint16_t(s.get_register(6u,2u));
    const auto de=std::uint16_t(s.get_register(4u,2u));
    const auto sum=std::uint32_t(hl)+std::uint32_t(de);
    const auto result=std::uint16_t(sum);
    const auto flags=(s.get_register(0u,1u)&0xc4u)|((result>>8)&0x28u)|
        (((hl^de^sum)&0x1000u)?0x10u:0u)|((sum>>16)&1u);
    s.set_register(6u,2u,result);s.set_register(0u,1u,flags);}
   )CPP";
  else if(op==0x03||op==0x0b||op==0x13||op==0x1b||op==0x23||op==0x2b){
   const unsigned r=op==0x03||op==0x0b?2:(op==0x13||op==0x1b?4:6);
   const bool increment=op==0x03||op==0x13||op==0x23;
   cpp="s.set_register("+std::to_string(r)+"u,2u,std::uint16_t(s.get_register("+
     std::to_string(r)+"u,2u)"+(increment?"+1u":"-1u")+"));";
  }else if(op==0xc5||op==0xd5||op==0xe5||op==0xf5){
   const unsigned r=op==0xc5?2:(op==0xd5?4:(op==0xe5?6:0));
   cpp="{auto sp=std::uint16_t(s.get_register(68u,2u)-2u);"
     "s.write_memory(sp,2u,s.get_register("+std::to_string(r)+"u,2u));"
     "s.set_register(68u,2u,sp);}";
  }else if(op==0xc1||op==0xd1||op==0xe1||op==0xf1){
   const unsigned r=op==0xc1?2:(op==0xd1?4:(op==0xe1?6:0));
   cpp="{auto sp=std::uint16_t(s.get_register(68u,2u));"
      "s.set_register("+std::to_string(r)+"u,2u,s.memory(sp,2u));"
      "s.set_register(68u,2u,std::uint16_t(sp+2u));}";
  }
 }
 if(cpp.empty())return 0;
 if(cpp.size()>=sizeof(out->cpp_body))return -1;
 std::memcpy(out->cpp_body,cpp.c_str(),cpp.size()+1);
 out->supported=1;return 1;
}
