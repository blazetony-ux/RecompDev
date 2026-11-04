#pragma once
// CPU and system-independent continuous native-execution coordinator.
// Translation is provided by Cpu; its clock/cycle semantics remain the
// architecture adapter's responsibility. No ROM or platform assumptions.
#include "runtime.hpp"
#include <chrono>
#include <functional>
#include <stdexcept>
#include <string>
namespace recomp::hw {
class NativeCpu {
 public:
 virtual ~NativeCpu()=default;
 virtual bool step()=0;                // execute one generated instruction/tick
 virtual u64 cycles()const=0;          // monotonic guest cycles, after step
 virtual const std::string& blocker()const=0;
};
struct RunLimits {
 u64 max_steps=2000000,max_frames=120,max_guest_cycles=20000000;
 u64 wall_seconds=30; // not counted in deterministic output, safety only
 void validate()const {
  if(!max_steps||max_steps>20000000||!max_frames||max_frames>36000||
     !max_guest_cycles||max_guest_cycles>1000000000ull||!wall_seconds||wall_seconds>120)
    throw std::invalid_argument("INVALID_CONTINUOUS_LIMITS");
 }
};
struct RunResult {
 std::string status;u64 executed=0,cycles=0,frames=0;
 bool native_qualified=false; // never promoted on synthetic output alone
};
class ContinuousSession {
 NativeCpu& cpu_;Runtime& runtime_;
 public:
 ContinuousSession(NativeCpu& cpu,Runtime& runtime):cpu_(cpu),runtime_(runtime){}
 // Invoked before an instruction. Can pump a GUI / map controller input to
 // runtime.record_input(runtime.cycles(),...). Returning false stops cleanly.
 RunResult run(const RunLimits& limits,
   const std::function<bool(u64,u64)>& pump={}) {
  limits.validate();RunResult r;
  const u64 initial=runtime_.cycles();
  if(cpu_.cycles()!=initial)throw std::invalid_argument("CPU_HOST_CYCLE_DESYNC");
  const auto started=std::chrono::steady_clock::now();
  while(r.executed<limits.max_steps && runtime_.frames()<limits.max_frames){
   if(cpu_.cycles()-initial>=limits.max_guest_cycles){r.status="GUEST_CYCLE_LIMIT";break;}
   if((r.executed&4095)==0){
    if(std::chrono::steady_clock::now()-started>std::chrono::seconds(limits.wall_seconds)){
     r.status="WALL_TIME_LIMIT";break;
    }
    if(pump&&!pump(r.executed,runtime_.frames())){r.status="HOST_STOP";break;}
   }
   runtime_.deliver_inputs_now();
   const u64 before=cpu_.cycles();
   if(!cpu_.step()){r.status=cpu_.blocker().empty()?"NATIVE_EXECUTION_BLOCKED":cpu_.blocker();break;}
   const u64 after=cpu_.cycles();
   if(after<=before||after-before>1000000ull){r.status="INVALID_CPU_CYCLE_PROGRESS";break;}
   if(after-initial>limits.max_guest_cycles){r.status="GUEST_CYCLE_LIMIT";break;}
   runtime_.advance(after-before);
   ++r.executed;
  }
  r.cycles=runtime_.cycles()-initial;r.frames=runtime_.frames();
  if(r.status.empty())r.status=runtime_.frames()>=limits.max_frames?"FRAME_BUDGET_REACHED":"STEP_BUDGET_REACHED";
  return r;
 }
};
} // namespace recomp::hw
