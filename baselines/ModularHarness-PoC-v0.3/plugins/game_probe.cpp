#include "rd_plugin.h"
// No native blocks, no ROM identity waiver outside explicit --probe mode.
namespace {
int execute(uint32_t,RD_CpuState*,const RD_Bus*,uint32_t*){return 0;}
const RD_GameApi API={execute};
const RD_Plugin PLUGIN={RD_ABI_VERSION,sizeof(RD_Plugin),RD_GAME,sizeof(API),
  "Development-only ROM probe: no translated instructions",&API};
}
extern "C" RD_EXPORT const RD_Plugin *rd_get_plugin_v1(void){return &PLUGIN;}
