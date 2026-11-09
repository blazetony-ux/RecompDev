#pragma once
// Transitional Master System bridge: native translated Z80 instructions use
// the existing rd::State hardware bus; frame/audio/input are carried through
// the universal host contracts. This is NOT a qualified SMS timing model.
#include "runtime.hpp"
#include "hardware/continuous.hpp"
#include "hardware/adapters/sms.hpp"
#include "rd_sms_mode4.h"
#include <limits>
#include <array>
#include <algorithm>
#include <ostream>
#include <stdexcept>
#include <string>

bool execute_native_instruction(rd::State&);
namespace recomp::guest {
class SmsNativeMachine final: public recomp::hw::NativeCpu,
 public recomp::hw::VideoSource,public recomp::hw::AudioSource,public recomp::hw::InputTarget {
 rd::State state_;
 recomp::hw::sms::Psg psg_;
 std::size_t audio_cursor_=0;
 std::string blocker_;
 // Last 256 *executed* transitions. Evidence only, not an interpreter or oracle.
 // Stores stack and interrupt context before and after each translated instruction.
 struct Transition {
  std::uint64_t step,cycles,irqs,vdp,psg,cram;
  std::uint16_t before,after,sp_before,sp_after,stack_word;
  std::uint32_t physical;
  std::array<std::uint8_t,4> mapper;
  bool iff1,iff2;
  const char* kind;const char* opcode_class;
 };
 struct FrameHardware {std::uint64_t frame,cycles,steps,irqs,vdp,psg,cram;
                       std::uint16_t pc,sp;unsigned palette_bytes;};
 mutable std::vector<FrameHardware> frame_hardware_;
 std::array<Transition,256> history_{};
 std::size_t written_=0;
 std::uint16_t stack_peek(std::uint16_t sp)const {
  if(sp<0xc000)return 0; // never read a bus port as a diagnostic side effect
  const auto off=std::size_t(sp&0x1fff);
  return std::uint16_t(state_.ram[off])|std::uint16_t(state_.ram[(off+1)&0x1fff])<<8;
 }
 Transition begin_transition()const {
  const auto pc=state_.pc;
  const auto sp=std::uint16_t(state_.get_register(68,2));
  const auto off=pc<0xc000?state_.rom_offset(pc):0;
  const auto opcode=off<state_.rom.size()?state_.rom[off]:0;
  const char* cls="OTHER_OR_LINEAR";
  if(opcode==0xc9||opcode==0xd9)cls="RETURN";
  else if(opcode==0xcd)cls="CALL";
  else if(opcode==0xc3||opcode==0xe9)cls="JUMP";
  else if(opcode==0x18||opcode==0x10||opcode==0x20||opcode==0x28||opcode==0x30||opcode==0x38)cls="RELATIVE_BRANCH";
  else if((opcode&0xc7)==0xc7)cls="RST";
  else if((opcode&0xc7)==0xc0)cls="CONDITIONAL_RETURN";
  else if((opcode&0xc7)==0xc4)cls="CONDITIONAL_CALL";
  else if((opcode&0xc7)==0xc2)cls="CONDITIONAL_JUMP";
  else if(opcode==0xed)cls="EXTENDED_OPCODE";
  return {state_.steps,state_.tstates,state_.maskable_interrupts,
   state_.vdp_control_writes+state_.vdp_data_writes,state_.psg_writes,state_.cram_writes,
   pc,pc,sp,sp,stack_peek(sp),pc<0xc000?state_.rom_offset(pc):0,
   state_.mapper,state_.iff1,state_.iff2,"instruction",cls};
 }
 void end_transition(Transition t,const char* kind){
  t.after=state_.pc;t.sp_after=std::uint16_t(state_.get_register(68,2));t.kind=kind;
  history_[written_%history_.size()]=t;++written_;
 }
 public:
 void write_frame_hardware_json(std::ostream& o)const {
  o<<"[";
  for(std::size_t i=0;i<frame_hardware_.size();++i){
   const auto& t=frame_hardware_[i];if(i)o<<",";
   o<<"{\"frame\":"<<t.frame<<",\"guest_cycles\":"<<t.cycles
    <<",\"steps\":"<<t.steps<<",\"pc\":"<<t.pc<<",\"sp\":"<<t.sp
    <<",\"irqs\":"<<t.irqs<<",\"vdp_writes\":"<<t.vdp
    <<",\"psg_writes\":"<<t.psg<<",\"cram_writes\":"<<t.cram
    <<",\"palette_nonzero_bytes\":"<<t.palette_bytes<<"}";
  }
  o<<"]";
 }
 void write_trace_json(std::ostream& o)const {
  const auto count=std::min(written_,history_.size());
  o<<"[";
  for(std::size_t i=0;i<count;++i){
   const auto& t=history_[(written_-count+i)%history_.size()];
   if(i)o<<",";
   o<<"{\"step\":"<<t.step<<",\"cycles\":"<<t.cycles
    <<",\"pc_before\":"<<t.before<<",\"pc_after\":"<<t.after
    <<",\"physical_offset\":"<<t.physical
    <<",\"physical_offset_valid\":"<<(t.before<0xc000?"true":"false")
    <<",\"sp_before\":"<<t.sp_before<<",\"sp_after\":"<<t.sp_after
    <<",\"stack_word_before\":"<<t.stack_word
    <<",\"stack_word_in_ram\":"<<(t.sp_before>=0xc000?"true":"false")
    <<",\"iff1_before\":"<<(t.iff1?"true":"false")
    <<",\"iff2_before\":"<<(t.iff2?"true":"false")
    <<",\"interrupt_count_before\":"<<t.irqs
    <<",\"mapper_before\":[";
   for(unsigned j=0;j<4;++j){if(j)o<<",";o<<unsigned(t.mapper[j]);}
   o<<"],\"vdp_writes_before\":"<<t.vdp
    <<",\"psg_writes_before\":"<<t.psg
    <<",\"cram_writes_before\":"<<t.cram
    <<",\"interrupt_count_after\":"<<state_irqs_for(i,count)
    <<",\"opcode_class\":\""<<t.opcode_class<<"\""
    <<",\"kind\":\""<<t.kind<<"\"}";
  }
  o<<"]";
 }
 std::uint64_t state_irqs_for(std::size_t i,std::size_t count)const{
  if(i+1<count)return history_[(written_-count+i+1)%history_.size()].irqs;
  return state_.maskable_interrupts;
 }

 void load_rom(const std::vector<std::uint8_t>& rom){
  if(rom.empty()||rom.size()>64*1024*1024)throw std::invalid_argument("INVALID_ROM_SIZE");
  state_.rom=rom;
 }
 rd::State& state(){return state_;}
 bool step()override {
  if(!blocker_.empty())return false;
  // Deliver the SMS Pause/Start edge as its own 11-cycle hardware step.
  // The host scheduler can then account for those cycles even if the new
  // guest vector 0x0066 is not translated and the following step blocks.
  // This is a guest interrupt, NOT an interpreter instruction.
  auto before=begin_transition();
  if(state_.service_pending_console_nmi()){
   end_transition(before,"console_nmi");
   return true;
  }
  if(state_.halted){
   // HALT continues to advance hardware time while awaiting a source-driven IRQ.
   state_.advance_cycles(4);++state_.halt_wait_ticks;
   state_.service_pending_interrupt();
   if(state_.halted && !state_.iff1 && !state_.iff2){blocker_="HALT_WITHOUT_ENABLED_IRQ";end_transition(before,"halt_blocked");return false;}
  }else{
   if(state_.pc>=0xc000){blocker_="RAM_EXECUTION_NOT_TRANSLATED";end_transition(before,"ram_execution_blocked");return false;}
   if(!execute_native_instruction(state_)){
    blocker_=state_.stopped.empty()?"UNTRANSLATED_CODE":state_.stopped;
    if(blocker_=="UNTRANSLATED_PHYSICAL_ROM_OFFSET")
     blocker_=state_.initial_mapping(state_.pc)?"UNTRANSLATED_INITIAL_CODE":"BANKED_CODE_NOT_TRANSLATED";
    end_transition(before,"untranslated_code");return false;
   }
   ++state_.steps;state_.end_instruction();
   state_.advance_cycles(state_.last_instruction_cycles);
   state_.service_pending_interrupt();
  }
  if(!state_.stopped.empty()){blocker_=state_.stopped;end_transition(before,"hardware_blocked");return false;}
  end_transition(before,state_.maskable_interrupts>before.irqs?"irq_accepted":(state_.halted?"halt":"instruction"));
  return true;
 }
 recomp::hw::u64 cycles()const override{return state_.tstates;}
 const std::string& blocker()const override{return blocker_;}
 // Only the exact untranslated-code stop is resumable at its original PC.
 // Other failures (source mismatch, hardware, interrupts) are terminal.
 bool resume_after_native_activation(){
  if(blocker_!="UNTRANSLATED_INITIAL_CODE"&&blocker_!="BANKED_CODE_NOT_TRANSLATED")return false;
  if(state_.stopped!="UNTRANSLATED_PHYSICAL_ROM_OFFSET")return false;
  state_.stopped.clear();blocker_.clear();return true;
 }

 // Host-presentation-independent FNV fingerprint of bounded guest state.
 // Diagnostic comparison only; not an independent reference oracle.
 recomp::hw::u64 guest_fingerprint()const{
  recomp::hw::u64 h=14695981039346656037ull;
  auto byte=[&](std::uint8_t v){h=(h^v)*1099511628211ull;};
  auto word=[&](std::uint64_t v){for(unsigned i=0;i<8;++i)byte(std::uint8_t(v>>(i*8)));};
  for(auto v:state_.ram)byte(v);
  for(auto v:state_.cart_ram)byte(v);
  for(auto v:state_.vram)byte(v);
  for(auto v:state_.cram)byte(v);
  for(auto v:state_.vdp_regs)byte(v);
  for(auto v:state_.reg)byte(v);
  for(auto v:state_.mapper)byte(v);
  word(state_.pc);word(state_.tstates);word(state_.steps);
  word(state_.frames);word(state_.vblank_events);word(state_.maskable_interrupts);
  word(state_.ram_writes);word(state_.vram_writes);word(state_.cram_writes);
  word(state_.psg_writes);word(state_.bank_switches);word(state_.io_writes);word(state_.io_reads);
  byte(state_.vdp_status);byte(state_.vdp_code);word(state_.vdp_addr);
  byte(state_.controller_a);byte(state_.controller_b);
  byte(state_.iff1);byte(state_.iff2);byte(state_.halted);
  return h;
 }
 recomp::hw::Frame render()const override{
  if(frame_hardware_.size()<36000){
   const auto nonzero=std::count_if(state_.cram.begin(),state_.cram.end(),[](auto v){return v!=0;});
   frame_hardware_.push_back({frame_hardware_.size()+1,state_.tstates,state_.steps,
    state_.maskable_interrupts,state_.vdp_control_writes+state_.vdp_data_writes,
    state_.psg_writes,state_.cram_writes,state_.pc,
    std::uint16_t(state_.get_register(68,2)),unsigned(nonzero)});
  }
  recomp::hw::Frame output;
  output.width=RD_SMS_MODE4_WIDTH;output.height=RD_SMS_MODE4_HEIGHT;
  output.source_cycle=state_.tstates;output.ordinal=state_.frames;
  output.pixels.resize(size_t(output.width)*output.height);
  if(!rd_sms_mode4_render(state_.vram.data(),uint32_t(state_.vram.size()),
        state_.cram.data(),uint32_t(state_.cram.size()),
        state_.vdp_regs.data(),uint32_t(state_.vdp_regs.size()),
        output.pixels.data(),uint32_t(output.pixels.size()),nullptr))
   throw std::runtime_error("SMS_VIDEO_PLUGIN_RENDER_FAILED");
  return output;
 }
 std::int16_t sample(recomp::hw::u64 cycle)override{
  // Only writes observed through the translated CPU path are played back.
  // Ordering within a single native instruction is unqualified, and the
  // historical native runtime provides only approximate PSG timing.
  while(audio_cursor_<state_.psg_timeline.size()&&state_.psg_timeline[audio_cursor_].cycle<=cycle){
   psg_.write({recomp::hw::Space::IO,0x7f},state_.psg_timeline[audio_cursor_].value);
   ++audio_cursor_;
  }
  return psg_.sample(cycle);
 }
 void set_input(recomp::hw::InputState in)override{
  if(in.port!=0)throw std::invalid_argument("SMS_INPUT_PORT_UNSUPPORTED");
  state_.apply_host_input(in.buttons);
 }
};
} // namespace recomp::guest
