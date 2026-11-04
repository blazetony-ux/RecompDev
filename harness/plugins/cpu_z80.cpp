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
