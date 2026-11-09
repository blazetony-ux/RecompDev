#include "rd_native_block_v1.h"
#include "probe_state.hpp"
#ifndef RD_FIXTURE_OP
# error Fixture operation must be selected by the test target
#endif
namespace {
int step(void *context,std::uint32_t physical){
 if(!context||physical!=static_cast<std::uint32_t>(RD_FIXTURE_OP))return 0;
 auto &s=*static_cast<ProbeState*>(context);
 if(s.pc!=static_cast<std::uint32_t>(RD_FIXTURE_OP))return -1;
 s.ram[s.pc]+=static_cast<std::uint8_t>(s.bank+s.input);
 s.cycles+=7;s.pc++;
 if(s.pc==2)s.frames++;
 return 1;
}
const RD_NativeBlockV1 definition={sizeof(RD_NativeBlockV1),RD_NATIVE_BLOCK_ABI_V1,
 "synthetic-cpu-v1", "semantics-1", "synthetic-bus", "probe-state-1",
 "native-fixture-v1", "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",128, &step};
}
extern "C" RD_NATIVE_BLOCK_EXPORT const RD_NativeBlockV1 *rd_native_block_get_v1(void){return &definition;}
