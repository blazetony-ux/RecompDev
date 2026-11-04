#include "rd_plugin.h"
namespace {
static int execute(uint32_t physical,RD_CpuState *s,const RD_Bus *b,uint32_t *cycles){
 if(!s||!b||!cycles)return -1;
 uint8_t expected=0,imm=0;uint16_t next=0;uint32_t cost=0;
 switch(physical){
 case 0x0000: expected=0x3e;imm=0x90;next=uint16_t(s->pc+2);cost=7;break;
 case 0x0004: expected=0x3e;imm=0x01;next=uint16_t(s->pc+2);cost=7;break;
 case 0x0009: expected=0xc3;next=0x8000;cost=10;break;
 case 0x4000: if(s->pc!=0x8000)return 0;expected=0x3e;imm=0x2a;next=uint16_t(s->pc+2);cost=7;break;
 case 0x8000: if(s->pc!=0x8000)return 0;expected=0x3e;imm=0x99;next=uint16_t(s->pc+2);cost=7;break;
 default:return 0;
 }
 // Real generated blocks must be tied to SHA-pinned binary evidence.
 // POC guard: runtime bytes for this one synthetic instruction must agree.
 if(b->read(b->ctx,s->pc)!=expected)return -1;
 if(expected==0x3e){if(b->read(b->ctx,uint16_t(s->pc+1))!=imm)return -1;s->a=imm;}
 if(expected==0xc3){if(b->read(b->ctx,uint16_t(s->pc+1))!=0||b->read(b->ctx,uint16_t(s->pc+2))!=0x80)return -1;}
 s->pc=next;*cycles=cost;return 1;
}
const RD_GameApi API={execute};
const RD_Plugin PLUGIN={RD_ABI_VERSION,sizeof(RD_Plugin),RD_GAME,sizeof(API),"Synthetic bank-aware native game module",&API};
}
extern "C" RD_EXPORT const RD_Plugin *rd_get_plugin_v1(void){return &PLUGIN;}
