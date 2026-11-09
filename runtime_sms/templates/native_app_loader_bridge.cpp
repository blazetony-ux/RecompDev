#include "rd_sms_dynamic_adapter.hpp"
#include "rd_native_module_set.hpp"
#include "runtime.hpp"
#include <memory>
#include <stdexcept>
namespace {
std::unique_ptr<recomp::native::ModuleSet> active;
}
namespace recomp::sms::dynamic {
void activate(const std::filesystem::path& module,const std::string& rom_sha,std::uint64_t size){
 if(!active)active=std::make_unique<recomp::native::ModuleSet>(recomp::native::Identity{
   cpu_id,cpu_semantics,machine_id,state_abi,target_abi,rom_sha,size});
 if(active->identity().source_sha256!=rom_sha || active->identity().source_size!=size)
  throw std::runtime_error("NATIVE_MODULE_ROM_ID_CHANGED_DURING_SESSION");
 active->activate(module,recomp::native::sha256_binary(module));
}
std::size_t active_modules(){return active?active->module_count():0;}
}
bool execute_native_instruction(rd::State& s){
 if(!active){s.stopped="NATIVE_TRANSLATION_MODULE_NOT_LOADED";return false;}
 if(s.pc>=0xc000){s.stopped="NATIVE_EXECUTION_OUTSIDE_ROM";return false;}
 const int result=active->step(&s,s.rom_offset(s.pc));
 if(result==1)return true;
 s.stopped=result==0?"UNTRANSLATED_PHYSICAL_ROM_OFFSET":"NATIVE_MODULE_EXECUTION_INTEGRITY_BLOCKED";
 return false;
}
