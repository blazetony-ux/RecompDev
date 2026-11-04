#include "rd_plugin.h"
namespace {
static uint64_t buttons(uint64_t, uint64_t configured){return configured;}
const RD_InputApi API={buttons};
const RD_Plugin PLUGIN={RD_ABI_VERSION,sizeof(RD_Plugin),RD_INPUT,sizeof(API),"Deterministic fixed-input adapter",&API};
}
extern "C" RD_EXPORT const RD_Plugin *rd_get_plugin_v1(void){return &PLUGIN;}
