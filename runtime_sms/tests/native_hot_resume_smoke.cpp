// Same-process proof using actual generated Z80 native code and an SMS machine.
// Separate modules are compiled from two independently source-attested exports;
// no reset/replay, no interpreter fallback, no game-title special cases.
#include "live_sms.hpp"
#include "rd_sms_dynamic_adapter.hpp"
#include "rd_runtime_host.h"
#include "rd_sha256.hpp"
#include <array>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <vector>
int main(int argc,char**argv){
 try{
  if(argc!=4)throw std::runtime_error("ROM_AND_TWO_MODULE_PATHS_REQUIRED");
  std::ifstream f(argv[1],std::ios::binary);
  std::vector<std::uint8_t> rom{std::istreambuf_iterator<char>(f),{}};
  if(rom.size()<0x8000)throw std::runtime_error("TEST_ROM_INVALID");
  recomp::guest::SmsNativeMachine guest;guest.load_rom(rom);
  auto& s=guest.state();
  RD_Host* host=nullptr;
  if(rd_host_create(RD_HOST_MODE_HEADLESS,"native-session",44100,&host)||!host)
   throw std::runtime_error("NATIVE_HOST_CREATE_FAILED");
  auto unchanged=host;
  const auto digest=rdhash::sha256(rom.data(),rom.size());
  recomp::sms::dynamic::activate(argv[2],digest,rom.size());
  if(!guest.step()||s.pc!=1||s.steps!=1)throw std::runtime_error("INITIAL_NATIVE_INSTRUCTION_FAILED");
  if(guest.step()||guest.blocker()!="UNTRANSLATED_INITIAL_CODE"||s.pc!=1)
   throw std::runtime_error("TRUE_CODE_GAP_WAS_NOT_OBSERVED");
  const auto steps=s.steps;const auto cycles=s.tstates;const auto mapper=s.mapper;const auto ram=s.ram;
  const auto fingerprint=guest.guest_fingerprint();
  const std::array<std::uint32_t,4> frame{0,0,0,0};
  if(rd_host_present(host,frame.data(),2,2,RD_HOST_PIXELS_BGRA8888))throw std::runtime_error("PRESENT_1_FAILED");
  recomp::sms::dynamic::activate(argv[3],digest,rom.size());
  if(guest.guest_fingerprint()!=fingerprint||s.pc!=1||s.steps!=steps||s.tstates!=cycles||s.mapper!=mapper||s.ram!=ram||host!=unchanged)
   throw std::runtime_error("STATE_MUTATED_DURING_NATIVE_MODULE_ACTIVATION");
  if(!guest.resume_after_native_activation())throw std::runtime_error("UNTRANSLATED_BLOCK_NOT_RESUMABLE");
  if(!guest.step()||s.pc!=2||s.steps!=steps+1||s.tstates<=cycles)
   throw std::runtime_error("HOT_LOADED_NATIVE_CODE_NOT_EXECUTED");
  if(rd_host_present(host,frame.data(),2,2,RD_HOST_PIXELS_BGRA8888))throw std::runtime_error("PRESENT_2_FAILED");
  RD_HostStats stats{};stats.struct_size=sizeof(stats);
  if(rd_host_stats(host,&stats)||stats.frames!=2||host!=unchanged||recomp::sms::dynamic::active_modules()!=2)
   throw std::runtime_error("PERSISTENT_HOST_OR_MODULES_BROKEN");
  rd_host_destroy(host);
  std::cout<<"RD_V27_SMS_NATIVE_HOT_RESUME=PASS initial_pc=1 resumed_pc=2 same_guest_state=1 same_host=1 modules=2\n";
  return 0;
 }catch(const std::exception& e){std::cerr<<"RD_V27_SMS_HOT_RESUME_ERROR="<<e.what()<<"\n";return 1;}
}
