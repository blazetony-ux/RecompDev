#include "rd_native_module_set.hpp"
#include "rd_runtime_host.h"
#include "probe_state.hpp"
#include <cassert>
#include <filesystem>
#include <functional>
#include <iostream>
#include <stdexcept>
#include <string>
namespace fs=std::filesystem;
using recomp::native::Identity;
using recomp::native::ModuleSet;
void expect_fail(const std::function<void()>& f,const std::string& code){
 try{f();throw std::runtime_error("EXPECTED_REJECTION_MISSING: "+code);}
 catch(const std::runtime_error& e){if(std::string(e.what()).find(code)==std::string::npos)throw;}
}
static Identity identity(){return {"synthetic-cpu-v1","semantics-1","synthetic-bus","probe-state-1",
 "native-fixture-v1","0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",128};}
int main(int argc,char**argv){
 try{
  if(argc!=3)throw std::runtime_error("FIXTURE_MODULES_REQUIRED");
  const fs::path a=argv[1],b=argv[2];
  ModuleSet modules(identity());
  RD_Host* host=nullptr;
  if(rd_host_create(RD_HOST_MODE_HEADLESS,"synthetic-continuous-session",44100,&host)!=0||!host)
   throw std::runtime_error("HOST_INITIALISATION_FAILED");
  const auto initial_host=host;
  const std::uint32_t frame[4]={0,1,2,3};
  ProbeState s{};s.bank=3;s.input=2;
  auto expected=s;
  auto oracle=[](ProbeState& x){x.ram[x.pc]+=static_cast<std::uint8_t>(x.bank+x.input);x.cycles+=7;x.pc++;if(x.pc==2)x.frames++;};
  if(modules.step(&s,s.pc)!=0)throw std::runtime_error("UNTRANSLATED_WAS_NOT_REPORTED");
  auto frozen=s;
  expect_fail([&]{modules.activate(a,"0000000000000000000000000000000000000000000000000000000000000000");},"BINARY_SHA256_MISMATCH");
  if(modules.module_count()||s.pc!=frozen.pc||s.cycles!=frozen.cycles)throw std::runtime_error("UNSAFE_FAILED_ACTIVATION");
  auto incompatible=identity();incompatible.cpu_semantics_version="semantics-2";
  ModuleSet wrong_cpu(incompatible);
  expect_fail([&]{wrong_cpu.activate(a,recomp::native::sha256_binary(a));},"SOURCE_OR_CONTEXT_MISMATCH");
  auto wrong_machine=identity();wrong_machine.machine_state_abi="probe-state-2";
  ModuleSet wrong_bus(wrong_machine);
  expect_fail([&]{wrong_bus.activate(a,recomp::native::sha256_binary(a));},"SOURCE_OR_CONTEXT_MISMATCH");
  modules.activate(a,recomp::native::sha256_binary(a));
  if(modules.step(&s,s.pc)!=1)throw std::runtime_error("FIRST_MODULE_DID_NOT_RUN");
  oracle(expected);
  if(s.pc!=expected.pc||s.cycles!=expected.cycles||s.ram[0]!=expected.ram[0])throw std::runtime_error("STATE_PARITY_FIRST_BLOCK");
  if(rd_host_present(host,frame,2,2,RD_HOST_PIXELS_BGRA8888)!=0)throw std::runtime_error("FIRST_FRAME_PRESENT_FAILED");
  if(modules.step(&s,s.pc)!=0)throw std::runtime_error("SECOND_GAP_NOT_DETECTED");
  frozen=s;
  if(rd_host_pump(host)!=1||host!=initial_host)throw std::runtime_error("HOST_IDENTITY_CHANGED");
  modules.activate(b,recomp::native::sha256_binary(b));
  if(s.pc!=frozen.pc||s.cycles!=frozen.cycles||s.bank!=frozen.bank||s.input!=frozen.input||s.ram[0]!=frozen.ram[0])
   throw std::runtime_error("STATE_MODIFIED_DURING_MODULE_ACTIVATION");
  if(modules.step(&s,s.pc)!=1)throw std::runtime_error("HOT_LOADED_MODULE_DID_NOT_RUN");
  oracle(expected);
  if(s.pc!=expected.pc||s.cycles!=expected.cycles||s.frames!=expected.frames||s.ram[1]!=expected.ram[1])
   throw std::runtime_error("STATE_PARITY_AFTER_HOT_ACTIVATION");
  if(rd_host_present(host,frame,2,2,RD_HOST_PIXELS_BGRA8888)!=0)throw std::runtime_error("SECOND_FRAME_PRESENT_FAILED");
  RD_HostStats stats{};stats.struct_size=sizeof(stats);
  if(rd_host_stats(host,&stats)!=0||stats.frames!=2||host!=initial_host)throw std::runtime_error("HOST_NOT_PERSISTENT");
  if(modules.module_count()!=2||modules.step(&s,s.pc)!=0)throw std::runtime_error("MODULE_DISPATCH_INCORRECT");
  expect_fail([&]{modules.activate(a,recomp::native::sha256_binary(a));},"ALREADY_ACTIVE");
  // CPU semantics shared with another synthetic machine instance. Bus state,
  // mapper and input differ, while the same compiled modules are unchanged.
  ProbeState second{};second.bank=9;second.input=4;
  ProbeState second_ref=second;
  if(modules.step(&second,0)!=1||modules.step(&second,1)!=1)throw std::runtime_error("OTHER_MACHINE_NO_REUSE");
  oracle(second_ref);oracle(second_ref);
  if(second.cycles!=second_ref.cycles||second.ram[0]!=second_ref.ram[0]||second.ram[1]!=second_ref.ram[1])
   throw std::runtime_error("OTHER_MACHINE_PARITY");
  rd_host_destroy(host);
  std::cout<<"RD_V27_NATIVE_MODULE_RESULT=HOT_SWAP_STATE_CONTINUITY_VERIFIED modules=2 frames=2 cpu_variants_rejected=1 machine_abis_rejected=1\n";
  return 0;
 }catch(const std::exception&e){std::cerr<<"RD_V27_NATIVE_MODULE_ERROR="<<e.what()<<"\n";return 1;}
}
