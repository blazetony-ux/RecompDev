#include "runtime.hpp"
#if __has_include("../hardware/input_replay.hpp")
#include "../hardware/input_replay.hpp"
#else
#include "hardware/input_replay.hpp"
#endif
#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <deque>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

bool execute_native_instruction(rd::State &s);

// Keep all reports bounded. These are observations of generated code, not
// independent Z80 reference-parity assertions.
struct Checkpoint {
 std::uint64_t step;
 std::uint16_t pc;
 std::uint64_t af, bc, de, hl, sp;
 std::array<std::uint8_t,4> mapper;
 std::uint64_t ram, vram, cram, psg, io, frames, irqs, clock;
};
static Checkpoint snapshot(const rd::State& s) {
 return {s.steps,s.pc,s.get_register(0,2),s.get_register(2,2),
         s.get_register(4,2),s.get_register(6,2),s.get_register(68,2),
         s.mapper,s.ram_writes,s.vram_writes,s.cram_writes,s.psg_writes,s.io_writes,s.frames,s.maskable_interrupts,s.tstates};
}
static void print_snapshot(const Checkpoint &p) {
 std::cout<<"{\"step\":"<<p.step<<",\"pc\":"<<p.pc
 <<",\"af\":"<<p.af<<",\"bc\":"<<p.bc<<",\"de\":"<<p.de
 <<",\"hl\":"<<p.hl<<",\"sp\":"<<p.sp<<",\"mapper\":["
 <<unsigned(p.mapper[0])<<","<<unsigned(p.mapper[1])<<","<<unsigned(p.mapper[2])
 <<","<<unsigned(p.mapper[3])<<"],\"ram_writes\":"<<p.ram
 <<",\"vram_writes\":"<<p.vram<<",\"cram_writes\":"<<p.cram
 <<",\"psg_writes\":"<<p.psg<<",\"io_writes\":"<<p.io<<",\"frames\":"<<p.frames<<",\"irqs\":"<<p.irqs<<",\"tstates\":"<<p.clock<<"}";
}
int main(int argc,char **argv){
 if(argc<2){std::cerr<<"Usage: RecompDevNativePilot <original-local-ROM> [max-steps] [snapshot.ppm]\n";return 2;}
 rd::State s;
 recomp::hw::InputTimeline input_replay;
 if(argc>8 && argv[8][0]){
  try{input_replay=recomp::hw::load_input_replay(argv[8]);}
  catch(const std::exception& e){std::cerr<<"INPUT_REPLAY_REJECTED: "<<e.what()<<"\n";return 7;}
 }
 {
  std::ifstream f(argv[1],std::ios::binary);
  if(!f){std::cerr<<"ROM_SOURCE_MISSING\n";return 3;}
  s.rom.assign(std::istreambuf_iterator<char>(f),std::istreambuf_iterator<char>());
 }
 if(s.rom.empty() || s.rom.size()>64*1024*1024){std::cerr<<"UNSUPPORTED_ROM_SIZE\n";return 4;}
 char *end=nullptr;
 const long long requested=argc>2?std::strtoll(argv[2],&end,10):50000;
 if(requested<1||requested>2000000){std::cerr<<"INVALID_STEP_BUDGET\n";return 5;}
 if(argc>5 && argv[5][0]){
   std::string spec(argv[5]);std::size_t start=0;
   while(start<spec.size()){auto endpos=spec.find(',',start);auto part=spec.substr(start,endpos==std::string::npos?endpos:endpos-start);
    char *stop=nullptr;auto val=std::strtoul(part.c_str(),&stop,0);
    if(stop==part.c_str()||*stop||val<0xc000||val>0xffff){std::cerr<<"INVALID_WATCH_ADDRESS\n";return 6;}
    s.add_watch(static_cast<std::uint16_t>(val));
    if(endpos==std::string::npos)break;start=endpos+1;}
 }
 if(argc>6 && argv[6][0])s.enable_event_stream(argv[6]);
 std::deque<std::uint16_t> last_pcs;
 std::unordered_map<std::uint32_t,std::uint64_t> hotspots;
 std::vector<Checkpoint> checkpoints;
 const std::vector<std::uint64_t> intervals{1000,10000,50000,100000,250000,500000,1000000,2000000};
 std::size_t next_checkpoint=0;
 checkpoints.push_back(snapshot(s));
 const auto begin=std::chrono::steady_clock::now();
 while(s.steps+s.halt_wait_ticks<static_cast<std::uint64_t>(requested)){
  // Native generated loops must not hang the Workbench, even with high budgets.
  if((s.steps&0xffffu)==0 && s.steps!=0 &&
    std::chrono::steady_clock::now()-begin>std::chrono::seconds(25)){
    s.stopped="NATIVE_TIME_BUDGET_REACHED";break;
  }
  try{
   input_replay.replay_until(s.tstates,[&](recomp::hw::InputState state){
    if(state.port!=0)throw std::invalid_argument("SMS_INPUT_PORT_UNSUPPORTED");
    s.apply_host_input(state.buttons);
   });
  }catch(const std::exception& e){s.stopped=std::string("INPUT_REPLAY_REJECTED: ")+e.what();break;}
  if(s.halted){++s.halt_wait_ticks;s.advance_cycles(4);s.service_pending_interrupt();if(!s.stopped.empty())break;continue;}
  if(s.pc>=0xc000){s.stopped="RAM_EXECUTION_NOT_TRANSLATED";break;}
  const auto physical=s.rom_offset(s.pc);
  hotspots[physical]++;
  last_pcs.push_back(s.pc);
  if(last_pcs.size()>24)last_pcs.pop_front();
  if(!execute_native_instruction(s)){
    if(s.stopped=="UNTRANSLATED_PHYSICAL_ROM_OFFSET")
      s.stopped=s.initial_mapping(s.pc)?"UNTRANSLATED_INITIAL_CODE":"BANKED_CODE_NOT_TRANSLATED";
    break;
  }
  ++s.steps;
  s.end_instruction();s.advance_cycles(s.last_instruction_cycles);s.service_pending_interrupt();
  if(!s.stopped.empty())break;
  if(next_checkpoint<intervals.size() && s.steps>=intervals[next_checkpoint]){
    checkpoints.push_back(snapshot(s));++next_checkpoint;
  }
 }
 s.finish_event_stream();
 if(s.stopped.empty())s.stopped=s.halted?"HALT_AWAITING_INTERRUPT":"STEP_BUDGET_REACHED";
 if(checkpoints.back().step!=s.steps || checkpoints.back().pc!=s.pc)
   checkpoints.push_back(snapshot(s));
 if(argc>3)s.write_ppm(argv[3]);
 if(argc>4)s.dump_vdp(argv[4]);
 if(argc>7 && argv[7][0])s.write_wav(argv[7]);
 std::vector<std::pair<std::uint32_t,std::uint64_t>> top(hotspots.begin(),hotspots.end());
 std::sort(top.begin(),top.end(),[](const auto& a,const auto& b){
   return a.second!=b.second?a.second>b.second:a.first<b.first;
 });
 if(top.size()>8)top.resize(8);
 const auto elapsed=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-begin).count();
 std::cout<<"PILOT_RESULT={\"status\":\""<<s.stopped
 <<"\",\"native_steps\":"<<s.steps<<",\"pc\":"<<s.pc
 <<",\"ram_writes\":"<<s.ram_writes<<",\"vram_writes\":"<<s.vram_writes
 <<",\"cram_writes\":"<<s.cram_writes<<",\"psg_writes\":"<<s.psg_writes
 <<",\"io_writes\":"<<s.io_writes<<",\"bank_switches\":"<<s.bank_switches
 <<",\"mapper\":["<<unsigned(s.mapper[0])<<","<<unsigned(s.mapper[1])<<","<<unsigned(s.mapper[2])<<","<<unsigned(s.mapper[3])
 <<"],\"physical_offset\":"<<s.rom_offset(s.pc)
 <<",\"af\":"<<s.get_register(0,2)
 <<",\"bc\":"<<s.get_register(2,2)
 <<",\"de\":"<<s.get_register(4,2)
 <<",\"hl\":"<<s.get_register(6,2)
 <<",\"sp\":"<<s.get_register(68,2)
 <<",\"last_pcs\":[";
 for(std::size_t i=0;i<last_pcs.size();i++){if(i)std::cout<<",";std::cout<<last_pcs[i];}
 std::cout<<"],\"rom_bytes\":"<<s.rom.size()<<",\"elapsed_ms\":"<<elapsed<<",\"checkpoints\":[";
 for(std::size_t i=0;i<checkpoints.size();i++){if(i)std::cout<<",";print_snapshot(checkpoints[i]);}
 std::cout<<"],\"hotspots\":[";
 for(std::size_t i=0;i<top.size();i++){
  if(i)std::cout<<",";
  std::cout<<"{\"physical_offset\":"<<top[i].first<<",\"count\":"<<top[i].second<<"}";
 }
 std::cout<<"],\"vdp_control_writes\":"<<s.vdp_control_writes
 <<",\"vdp_data_writes\":"<<s.vdp_data_writes
 <<",\"first_vdp_port_step\":"<<s.first_vdp_port_step
 <<",\"first_vdp_data_step\":"<<s.first_vdp_data_step
 <<",\"first_psg_step\":"<<s.first_psg_step
 <<",\"vdp_control_reads\":"<<s.vdp_control_reads
 <<",\"vdp_data_reads\":"<<s.vdp_data_reads
 <<",\"io_reads\":"<<s.io_reads
 <<",\"vcounter_reads\":"<<s.vcounter_reads
 <<",\"first_vcounter_read_step\":"<<s.first_vcounter_read_step
 <<",\"hcounter_reads\":"<<s.hcounter_reads
 <<",\"hcounter_latches\":"<<s.hcounter_latches
 <<",\"clock_model\":\"NTSC_SMS_APPROXIMATE_NON_PARITY\""
 <<",\"timing_qualified_steps\":"<<s.qualified_timing_instructions
 <<",\"timing_unqualified_steps\":"<<s.unqualified_timing_instructions
 <<",\"tstates\":"<<s.tstates
 <<",\"scanline\":"<<s.scanline()
 <<",\"frames\":"<<s.frames
 <<",\"vblank_events\":"<<s.vblank_events
 <<",\"first_vblank_step\":"<<s.first_vblank_step
 <<",\"maskable_interrupts\":"<<s.maskable_interrupts
 <<",\"first_irq_step\":"<<s.first_irq_step
 <<",\"irq_return_pc\":"<<s.last_irq_return_pc
 <<",\"nmi_events\":"<<s.nmi_events
 <<",\"halt_wait_ticks\":"<<s.halt_wait_ticks
 <<",\"iff1\":"<<(s.iff1?"true":"false")
 <<",\"interrupt_mode\":"<<s.interrupt_mode
 <<",\"vdp_status\":"<<unsigned(s.vdp_status)
 <<",\"vdp_registers\":[";
 for(size_t k=0;k<s.vdp_regs.size();k++){if(k)std::cout<<",";std::cout<<unsigned(s.vdp_regs[k]);}
 std::cout<<"],\"vram_nonzero_bytes\":"<<std::count_if(s.vram.begin(),s.vram.end(),[](auto b){return b!=0;})
 <<",\"cram_nonzero_bytes\":"<<std::count_if(s.cram.begin(),s.cram.end(),[](auto b){return b!=0;})
 <<",\"c001_writes\":"<<s.c001_writes
 <<",\"c001_reads\":"<<s.c001_reads
 <<",\"c001_nonzero_writes\":"<<s.c001_nonzero_writes
 <<",\"last_c001_value\":"<<unsigned(s.last_c001_value)
 <<",\"last_c001_writer_pc\":"<<s.last_c001_writer_pc
 <<",\"last_c001_reader_pc\":"<<s.last_c001_reader_pc
 <<",\"first_c001_nonzero_step\":"<<s.first_c001_nonzero_step
 <<",\"watched_memory\":[";
 for(std::size_t w=0;w<s.watches.size();++w){
   if(w)std::cout<<",";
   const auto& v=s.watches[w];
   std::cout<<"{\"address\":"<<v.address<<",\"reads\":"<<v.reads<<",\"writes\":"<<v.writes
    <<",\"nonzero_writes\":"<<v.nonzero_writes<<",\"last_writer_pc\":"<<v.last_writer_pc
    <<",\"last_reader_pc\":"<<v.last_reader_pc<<",\"value\":"<<unsigned(v.value)<<"}";
 }
 std::cout<<"],\"event_stream_complete\":"<<(s.event_stream_enabled && s.event_stream_complete && s.event_stream_events==s.events_total?"true":"false")
 <<",\"event_stream_events\":"<<s.event_stream_events
 <<",\"event_stream_chunks\":"<<s.event_stream_chunks
 <<",\"event_stream_bytes\":"<<s.event_stream_bytes
 <<",\"events_total\":"<<s.events_total
 <<",\"events_truncated\":"<<(s.events_total>s.events.size()?"true":"false")
 <<",\"events\":[";
 for(std::size_t e=0;e<s.events.size();++e){
   const auto& ev=s.events[e];if(e)std::cout<<",";
   std::cout<<"{\"step\":"<<ev.step<<",\"pc\":"<<ev.pc
    <<",\"kind\":\""<<ev.kind<<"\",\"address\":"<<ev.address<<",\"value\":"<<ev.value<<"}";
 }
 std::cout<<"],\"port_writes\":[";
 for(std::size_t p=0;p<256;p++)if(s.port_writes[p]){
   static bool first=true;
   if(!first)std::cout<<",";
   first=false;
   std::cout<<"{\"port\":"<<p<<",\"count\":"<<s.port_writes[p]<<"}";
 }
 std::cout<<"]}\n";
 return 0;
}
