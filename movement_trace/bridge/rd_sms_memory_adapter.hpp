#pragma once
// Master System-only provider adapter. No SMS knowledge leaks into the generic
// rd_state_observer recorder or offline correlation engine.
#include "rd_state_observer.hpp"
#include <cstdint>
#include <type_traits>

namespace rd_sms_memory_adapter {
template<class State>
inline void sample(std::uint64_t guest_cycle,std::uint64_t guest_frame,const State& state){
 // 0xc000..0xdfff is the physical 8 KiB Z80 work-RAM window; 0xe000..0xffff
 // aliases it. Publish one physical region to avoid mirrored false positives.
 const rd_state_observer::MemoryRegionView regions[] = {{
   "system_wram","machine_sms","cpu_z80",0xc000u,
   state.ram.data(),state.ram.size(),"little","z80_tstates"
 }};
 rd_state_observer::sample_memory(guest_cycle,guest_frame,regions,1);
}
} // namespace rd_sms_memory_adapter
