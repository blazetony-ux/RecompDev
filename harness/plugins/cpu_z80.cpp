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
