#include "counters.hpp"
#include "hardware/adapters/sms.hpp"
#include "rd_sms_mode4.h"
#include "runtime.hpp"
#include "hardware/wav.hpp"
#include <algorithm>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
extern "C" RD_SMS_NATIVE_API unsigned rd_sms_native_runtime_abi(void){return 0x00010000u;}
namespace rd {
u64 mask(unsigned n){return n>=8?~u64(0):((u64(1)<<(n*8))-1);}
static std::int64_t signed_value(u64 x,unsigned n){u64 m=mask(n);x &=m;u64 sign=u64(1)<<(n*8-1);return (x&sign)?std::int64_t(x|~m):std::int64_t(x);}
u64 evaluate(Op op,u64 a,u64 b,unsigned size,unsigned as,unsigned bs){
 const u64 m=mask(size),am=mask(as),bm=mask(bs),operand_mask=mask(std::max(as,bs));a&=am;b&=bm;
 switch(op){
 case Op::COPY:case Op::INT_ZEXT:return a&m;
 case Op::INT_AND:return (a&b)&m;
 case Op::INT_OR:return (a|b)&m;
 case Op::INT_XOR:return (a^b)&m;
 case Op::INT_LEFT:return b>=64?0:(a<<b)&m;
 case Op::INT_RIGHT:return b>=64?0:(a>>b)&m;
 // Arithmetic right shift: preserve source-width sign, including oversized
 // shifts, without implementation-defined negative signed shifts or shifts by 64.
 case Op::INT_SRIGHT:{
  const unsigned bits=as*8;
  const bool negative=(a & (u64(1)<<(bits-1)))!=0;
  if(b>=bits)return negative?m:0;
  const unsigned n=static_cast<unsigned>(b);
  if(n==0)return a&m;
  const u64 fill=negative?(am^(am>>n)):0;
  return ((a>>n)|fill)&m;
 }
 case Op::INT_ADD:return (a+b)&m;
 case Op::INT_SUB:return (a-b)&m;
 case Op::INT_EQUAL:return a==b;
 case Op::INT_NOTEQUAL:return a!=b;
 case Op::INT_LESS:return a<b;
 case Op::INT_LESSEQUAL:return a<=b;
 case Op::INT_SLESS:return signed_value(a,as)<signed_value(b,bs);
 case Op::INT_2COMP:return (u64(0)-a)&m;
 case Op::INT_NEGATE:return (~a)&m;
 case Op::INT_CARRY:return a>operand_mask-b;
 case Op::INT_SCARRY:{u64 sign=u64(1)<<(std::max(as,bs)*8-1),r=(a+b)&operand_mask;return ((~(a^b)&(a^r)&sign)!=0);}
 case Op::INT_SBORROW:{u64 sign=u64(1)<<(std::max(as,bs)*8-1),r=(a-b)&operand_mask;return (((a^b)&(a^r)&sign)!=0);}
 case Op::BOOL_OR:return (a!=0)||(b!=0);
 case Op::BOOL_XOR:return (a!=0)!=(b!=0);
 case Op::BOOL_NEGATE:return a==0;
 }
 return 0;
}
State::State():unique(1024*1024,0){}
void State::enable_event_stream(const std::string &prefix){
 event_stream_enabled=true;event_stream_prefix=prefix;
 event_stream_complete=true;event_stream_events=event_stream_bytes=event_stream_chunks=0;
}
void State::finish_event_stream(){
 if(event_stream.is_open()){
  event_stream.flush();
  if(!event_stream.good()){event_stream_complete=false;stopped="EVENT_STREAM_IO_ERROR";}
  event_stream.close();
  if(event_stream.fail()){event_stream_complete=false;stopped="EVENT_STREAM_IO_ERROR";}
 }
}
void State::record_event(const char *kind,unsigned address,unsigned value,bool after_instruction){
 ++events_total;
 const Event ev{steps+(after_instruction?0:1),pc,kind,address,value};
 if(events.size()<EVENT_LIMIT)events.push_back(ev);
 if(!event_stream_enabled)return;
 if(!event_stream_complete)return;
 const std::string line="{\"step\":"+std::to_string(ev.step)+",\"pc\":"+std::to_string(ev.pc)
  +",\"kind\":\""+ev.kind+"\",\"address\":"+std::to_string(ev.address)
  +",\"value\":"+std::to_string(ev.value)+"}\n";
 if(event_stream_events>=EVENT_STREAM_LIMIT || event_stream_bytes+line.size()>EVENT_STREAM_BYTE_LIMIT){
  event_stream_complete=false;stopped="EVENT_STREAM_LIMIT_REACHED";return;
 }
 if(event_stream_events%EVENTS_PER_CHUNK==0){
  if(event_stream.is_open()){
   event_stream.flush();
   if(!event_stream.good()){event_stream_complete=false;stopped="EVENT_STREAM_IO_ERROR";return;}
   event_stream.close();
   if(event_stream.fail()){event_stream_complete=false;stopped="EVENT_STREAM_IO_ERROR";return;}
  }
  std::ostringstream name;
  name<<event_stream_prefix<<"-"<<std::setw(6)<<std::setfill('0')<<event_stream_chunks<<".jsonl";
  event_stream.open(name.str(),std::ios::binary|std::ios::trunc);
  if(!event_stream.is_open()){event_stream_complete=false;stopped="EVENT_STREAM_IO_ERROR";return;}
  ++event_stream_chunks;
 }
 event_stream.write(line.data(),std::streamsize(line.size()));
 if(!event_stream.good()){event_stream_complete=false;stopped="EVENT_STREAM_IO_ERROR";return;}
 ++event_stream_events;event_stream_bytes+=line.size();
}
void State::apply_host_input(std::uint64_t buttons){
 // On the Sega Master System, the console Pause/Start switch asserts NMI,
 // not an ordinary bit on controller port DC/DD. Queue a single rising edge
 // and deliver it at the next native guest instruction boundary. This avoids
 // reentrant CPU state changes in the host's cycle-scheduled input callback.
 const bool pressed=(buttons&recomp::hw::button::Start)!=0;
 if(pressed&&!console_pause_down)pending_console_nmi=true;
 console_pause_down=pressed;
 recomp::hw::sms::Controller pad;
 pad.set_input({0,buttons,0,0});
 controller_a=pad.read({recomp::hw::Space::IO,0xdc});
 controller_b=pad.read({recomp::hw::Space::IO,0xdd});
}
void State::add_watch(std::uint16_t addr){
 if(addr<0xc000||watches.size()>=8)return;
 for(const auto &w:watches)if(w.address==addr)return;
 Watch w;w.address=addr;watches.push_back(w);
}
std::uint32_t State::rom_offset(std::uint16_t a)const{
 if(a<0x400)return a;
 unsigned slot=a<0x4000?1:(a<0x8000?2:3);
 unsigned bank=mapper[slot];
 if(rom.empty())return 0xffffffffu;
 unsigned count=unsigned((rom.size()+0x3fff)/0x4000);
 return ((bank%count)*0x4000)+(a&0x3fff);
}
bool State::initial_mapping(std::uint16_t a)const{
 if(a>=0xc000)return false;
 return rom_offset(a)==a;
}
std::uint8_t State::read_byte(std::uint16_t a)const{
 if(a>=0xc000){for(auto &w:watches)if((a&0x1fff)==(w.address&0x1fff)){++w.reads;w.last_reader_pc=pc;}if((a&0x1fff)==1){++c001_reads;last_c001_reader_pc=pc;}return ram[a&0x1fff];}
 if(a>=0x8000 && (mapper[0]&0x08))return cart_ram[((mapper[0]&0x04)?0x4000:0)+(a&0x3fff)];
 auto off=rom_offset(a);
 return off<rom.size()?rom[off]:0xff;
}
void State::write_byte(std::uint16_t a,std::uint8_t value){
 if(a>=0xc000){ram[a&0x1fff]=value;ram_writes++;
 for(auto &w:watches)if((a&0x1fff)==(w.address&0x1fff)){++w.writes;if(value)++w.nonzero_writes;w.value=value;w.last_writer_pc=pc;record_event("RAM_WATCH_WRITE",a,value);}
 if((a&0x1fff)==1){++c001_writes;last_c001_value=value;last_c001_writer_pc=pc;
   if(value){++c001_nonzero_writes;if(!first_c001_nonzero_step)first_c001_nonzero_step=steps+1;}}
 if(a>=0xfffc){unsigned idx=a-0xfffc;if(mapper[idx]!=value){record_event("MAPPER_WRITE",a,value);mapper[idx]=value;bank_switches++;}}return;}
 if(a>=0x8000 && (mapper[0]&0x08))cart_ram[((mapper[0]&0x04)?0x4000:0)+(a&0x3fff)]=value;
}
u64 State::memory(std::uint16_t a,unsigned sz)const{
 u64 value=0;for(unsigned i=0;i<sz&&i<8;i++)value|=u64(read_byte(std::uint16_t(a+i)))<<(i*8);return value;
}
void State::write_memory(std::uint16_t a,unsigned sz,u64 value){for(unsigned i=0;i<sz&&i<8;i++)write_byte(std::uint16_t(a+i),std::uint8_t(value>>(i*8)));}
u64 State::get_register(unsigned offset,unsigned size)const{u64 v=0;for(unsigned i=0;i<size&&i<8;i++)if(offset+i<reg.size())v|=u64(reg[offset+i])<<(8*i);return v;}
void State::set_register(unsigned offset,unsigned size,u64 v){for(unsigned i=0;i<size&&i<8;i++)if(offset+i<reg.size())reg[offset+i]=std::uint8_t(v>>(8*i));}
u64 State::get_unique(unsigned offset,unsigned size)const{u64 v=0;for(unsigned i=0;i<size&&i<8;i++)if(offset+i<unique.size())v|=u64(unique[offset+i])<<(8*i);return v;}
void State::set_unique(unsigned offset,unsigned size,u64 v){for(unsigned i=0;i<size&&i<8;i++)if(offset+i<unique.size())unique[offset+i]=std::uint8_t(v>>(8*i));}
std::uint8_t State::in(std::uint16_t port){
 unsigned p=port&0xff;
 io_reads++;
 if((p&0xc1)==0x80){vdp_data_reads++;vdp_pending=false;auto b=vdp_read_buffer;record_event("VDP_DATA_READ",p,b);vdp_read_buffer=vram[vdp_addr&0x3fff];vdp_addr=(vdp_addr+1)&0x3fff;return b;}
 if((p&0xc1)==0x81){vdp_control_reads++;vdp_pending=false;auto status=vdp_status;record_event("VDP_STATUS_READ",p,status);vdp_status&=0x1f;return status;}
 if((p&0xc0)==0x40){
  if(!(p&1)){
   ++vcounter_reads;if(!first_vcounter_read_step)first_vcounter_read_step=steps+1;
   auto value=recomp::sms::vcounter_ntsc_192(scanline());
   record_event("VDP_VCOUNTER_READ",p,value);
   return value;
  }
  ++hcounter_reads;record_event("VDP_HCOUNTER_READ",p,hcounter_latch);
  return hcounter_latch;
 }
 if(p==0xdc){record_event("INPUT_READ",p,controller_a);return controller_a;}
 if(p==0xdd){
  // SMS output TH pins read back on controller port DD (bits 6 and 7).
  // Port 3F selects line direction and output level; retain other input bits.
  std::uint8_t value=controller_b;
  if(!(io_control&0x02)){if(io_control&0x20)value|=0x40;else value&=std::uint8_t(~0x40u);}
  if(!(io_control&0x08)){if(io_control&0x80)value|=0x80;else value&=std::uint8_t(~0x80u);}
  record_event("INPUT_READ",p,value);return value;
 }
 return 0xff;
}
void State::out(std::uint16_t port,std::uint8_t value){
 io_writes++;unsigned p=port&0xff;port_writes[p]++;
 if(p==0x3f){
  // Only an externally driven TH rising edge latches the counter.
  const bool rise_a=(io_control&0x20)==0 && (value&0x20)!=0 && (value&0x02)!=0;
  const bool rise_b=(io_control&0x80)==0 && (value&0x80)!=0 && (value&0x08)!=0;
  if(rise_a||rise_b){hcounter_latch=recomp::sms::approximate_latched_hcounter(tstates);++hcounter_latches;}
  io_control=value;record_event("IO_CONTROL_WRITE",p,value);return;
 }
 if((p&0xc1)==0x81){
   record_event("VDP_CONTROL_WRITE",p,value);
   vdp_control_writes++;if(!first_vdp_port_step)first_vdp_port_step=steps+1;
   if(!vdp_pending){vdp_latch=value;vdp_pending=true;}
   else{vdp_pending=false;vdp_addr=((value&0x3f)<<8)|vdp_latch;vdp_code=value>>6;
     if(vdp_code==2){unsigned idx=value&0x0f;if(idx<vdp_regs.size())vdp_regs[idx]=vdp_latch;}
     if(vdp_code==0){vdp_read_buffer=vram[vdp_addr&0x3fff];vdp_addr=(vdp_addr+1)&0x3fff;}
   }return;
 }
 if((p&0xc1)==0x80){vdp_data_writes++;if(!first_vdp_data_step)first_vdp_data_step=steps+1;vdp_pending=false;
   if(vdp_code==3){record_event("CRAM_WRITE",vdp_addr&0x1f,value);cram[vdp_addr&0x1f]=value;cram_writes++;}
   else{record_event("VRAM_WRITE",vdp_addr&0x3fff,value);vram[vdp_addr&0x3fff]=value;vdp_read_buffer=value;vram_writes++;}
   vdp_addr=(vdp_addr+1)&0x3fff;return;
 }
 if((p&0xc0)==0x40){
  if(psg_timeline.size()<250000)psg_timeline.push_back({tstates,value});
  else audio_timeline_complete=false;
  record_event("PSG_WRITE",p,value);psg_writes++;if(!first_psg_step)first_psg_step=steps+1;return;}
}
void State::advance_cycles(unsigned ticks){
 const auto old=tstates/TSTATES_PER_SCANLINE;tstates+=ticks;
 const auto now=tstates/TSTATES_PER_SCANLINE;
 for(auto line=old+1;line<=now;++line){
  if(line%NTSC_SCANLINES==VBLANK_START_SCANLINE){vdp_status|=0x80;++vblank_events;if(!first_vblank_step)first_vblank_step=steps+1;}
  if(line%NTSC_SCANLINES==0)++frames;
 }
}
bool State::service_pending_interrupt(){
 if(!(vdp_status&0x80)||!(vdp_regs[1]&0x20)||!iff1||ei_delay)return false;
 if(interrupt_mode==2){stopped="IM2_INTERRUPT_VECTOR_NOT_MODELLED";return false;}
 if(interrupt_mode!=0&&interrupt_mode!=1){stopped="UNSUPPORTED_INTERRUPT_MODE";return false;}
 // IM0 assumes external device supplies RST 38h; this is NOT reference verified.
 iff1=iff2=false;halted=false;last_irq_return_pc=pc;
 auto sp=std::uint16_t(get_register(68,2)-2);set_register(68,2,sp);write_memory(sp,2,pc);
 record_event("IRQ",0x0038,interrupt_mode,true);pc=0x0038;++maskable_interrupts;if(!first_irq_step)first_irq_step=steps+1;
 advance_cycles(13);return true;
}
bool State::service_pending_console_nmi(){
 if(!pending_console_nmi)return false;
 pending_console_nmi=false;
 pulse_nmi();
 return true;
}
void State::pulse_nmi(){
 auto sp=std::uint16_t(get_register(68,2)-2);set_register(68,2,sp);write_memory(sp,2,pc);
 iff2=iff1;iff1=false;halted=false;record_event("NMI",0x0066,0,true);pc=0x0066;++nmi_events;advance_cycles(11);
}
void State::dump_vdp(const std::string &prefix)const{
 std::ofstream v(prefix+"-vram.bin",std::ios::binary);if(v)v.write(reinterpret_cast<const char*>(vram.data()),vram.size());
 std::ofstream c(prefix+"-cram.bin",std::ios::binary);if(c)c.write(reinterpret_cast<const char*>(cram.data()),cram.size());
 std::ofstream regs(prefix+"-vdp-registers.bin",std::ios::binary);if(regs)regs.write(reinterpret_cast<const char*>(vdp_regs.data()),vdp_regs.size());
}
void State::decimal_adjust_accumulator(){
 // Z80 DAA flags: S,Z,Y,H,X,P/V,N,C; Ghidra exposes DAA as CALLOTHER(1).
 const unsigned before=reg[1],f=reg[0];
 const bool n=(f&0x02)!=0,h=(f&0x10)!=0,c=(f&0x01)!=0;
 unsigned adjust=0;bool carry=c;
 if(h||(!n&&(before&0x0f)>9))adjust|=0x06;
 if(c||(!n&&before>0x99)){adjust|=0x60;carry=true;}
 const unsigned after=n?((before-adjust)&0xff):((before+adjust)&0xff);
 unsigned nf=(f&0x02)|(after&0xa8)|(after==0?0x40:0)|(carry?0x01:0);
 if(((before^after)&0x10)!=0)nf|=0x10;
 unsigned parity=0;for(unsigned x=after;x;x>>=1)parity^=(x&1u);
 if(parity==0)nf|=0x04;
 reg[1]=std::uint8_t(after);reg[0]=std::uint8_t(nf);
}
bool State::write_wav(const std::string& path)const{
 if(psg_timeline.empty()||!audio_timeline_complete||tstates>100000000ull)return false;
 recomp::hw::PcmBlock samples;samples.sample_rate=44100;samples.channels=1;
 const std::uint64_t cpu_hz=3579545u;
 const std::uint64_t count=(tstates*44100u)/cpu_hz;
 samples.samples.reserve(std::size_t(count));
 recomp::hw::sms::Psg chip;
 std::size_t index=0;
 for(std::uint64_t i=0;i<count;++i){
  const std::uint64_t cycle=((i+1)*cpu_hz+44099u)/44100u;
  while(index<psg_timeline.size() && psg_timeline[index].cycle<=cycle){
   chip.write({recomp::hw::Space::IO,0x7f},psg_timeline[index].value);++index;
  }
  samples.samples.push_back(chip.sample(cycle));
 }
 return recomp::hw::write_pcm16_wav(path,samples);
}
void State::write_ppm(const std::string &path)const{
 if(!vram_writes)return;
 std::array<std::uint32_t,256*192> pixels{};
 if(!rd_sms_mode4_render(vram.data(),uint32_t(vram.size()),cram.data(),uint32_t(cram.size()),
      vdp_regs.data(),uint32_t(vdp_regs.size()),pixels.data(),uint32_t(pixels.size()),nullptr))
  throw std::runtime_error("SMS_VIDEO_PLUGIN_RENDER_FAILED");
 std::ofstream out(path,std::ios::binary);
 if(!out)return;
 out<<"P6\n256 192\n255\n";
 for(auto px:pixels){
  const unsigned char rgb[3]={static_cast<unsigned char>((px>>16)&255),
   static_cast<unsigned char>((px>>8)&255),static_cast<unsigned char>(px&255)};
  out.write(reinterpret_cast<const char*>(rgb),3);
 }
}
} // namespace rd
