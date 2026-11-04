// Placeholder: overridden by build_pcode_plugin.py after source verification.
#include "rd_plugin.h"
namespace {
int execute(uint32_t,RD_CpuState*,const RD_Bus*,uint32_t*){return 0;}
const RD_GameApi API={execute};
const RD_Plugin PLUGIN={RD_ABI_VERSION,sizeof(RD_Plugin),RD_GAME,sizeof(API),"No owner Ghidra export imported",&API};
}
extern "C" RD_EXPORT const RD_Plugin *rd_get_plugin_v1(void){return &PLUGIN;}
extern "C" RD_EXPORT const char* rd_game_source_sha256_v1(void){return "";}
extern "C" RD_EXPORT uint64_t rd_game_source_size_v1(void){return 0;}
