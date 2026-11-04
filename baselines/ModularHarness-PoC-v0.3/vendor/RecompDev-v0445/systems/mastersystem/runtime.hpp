#pragma once
#include <array>
#include <fstream>
#include <cstdint>
#include <string>
#include <vector>
#include <utility>

namespace rd {
using u64=std::uint64_t;
enum class Op { COPY, INT_AND, INT_OR, INT_LEFT, INT_ADD, INT_EQUAL, INT_RIGHT, INT_SRIGHT,
 INT_SUB, INT_SLESS, INT_XOR, INT_NOTEQUAL, INT_ZEXT, INT_2COMP,
 INT_CARRY, INT_SCARRY, INT_LESSEQUAL, INT_SBORROW, BOOL_OR, BOOL_XOR,
 INT_LESS, BOOL_NEGATE, INT_NEGATE };
u64 mask(unsigned bytes);
u64 evaluate(Op op,u64 a,u64 b,unsigned output_bytes,unsigned a_bytes,unsigned b_bytes);
 struct State {
 struct Watch {std::uint16_t address=0;mutable u64 reads=0;u64 writes=0,nonzero_writes=0;u64 last_writer_pc=0,last_reader_pc=0;std::uint8_t value=0;};
 mutable std::vector<Watch> watches;
 void add_watch(std::uint16_t address);
 void apply_host_input(std::uint64_t buttons); // neutral button bitset, console adapter owns polarity
 std::vector<std::uint8_t> rom;
 std::array<std::uint8_t,8192> ram{};
 std::array<std::uint8_t,32768> cart_ram{};
 std::array<std::uint8_t,16384> vram{};
 std::array<std::uint8_t,32> cram{};
 std::array<std::uint8_t,16> vdp_regs{};
 std::array<std::uint8_t,256> reg{};
 std::vector<std::uint8_t> unique;
 std::array<std::uint8_t,4> mapper{{0,0,1,2}};
 std::uint16_t vdp_addr=0;
 std::uint8_t vdp_code=0, vdp_latch=0, vdp_read_buffer=0, vdp_status=0;
 std::uint8_t controller_a=0xff,controller_b=0xff;
 std::uint8_t hcounter_latch=0,io_control=0xff;
 std::uint64_t vcounter_reads=0,hcounter_reads=0,hcounter_latches=0,first_vcounter_read_step=0;

 bool vdp_pending=false,iff1=false,iff2=false,halted=false;
 bool console_pause_down=false,pending_console_nmi=false;
 unsigned ei_delay=0,last_instruction_cycles=4;
 std::uint64_t tstates=0,frames=0,vblank_events=0,maskable_interrupts=0,nmi_events=0,halt_wait_ticks=0;
 std::uint64_t first_vblank_step=0,first_irq_step=0,first_c001_nonzero_step=0;
 std::uint64_t c001_writes=0,c001_nonzero_writes=0;
 mutable std::uint64_t c001_reads=0;
 mutable std::uint16_t last_c001_reader_pc=0;
 std::uint16_t last_c001_writer_pc=0,last_irq_return_pc=0;
 std::uint8_t last_c001_value=0;
 static constexpr unsigned TSTATES_PER_SCANLINE=228,NTSC_SCANLINES=262,VBLANK_START_SCANLINE=192;
 int interrupt_mode=0;
 std::uint64_t qualified_timing_instructions=0,unqualified_timing_instructions=0;
 std::uint64_t steps=0, ram_writes=0,vram_writes=0,cram_writes=0,psg_writes=0,bank_switches=0,io_writes=0;
 std::uint64_t io_reads=0, vdp_control_reads=0, vdp_data_reads=0, vdp_control_writes=0, vdp_data_writes=0;
 std::uint64_t first_vdp_port_step=0,first_vdp_data_step=0,first_psg_step=0;
 struct TimedPsgWrite {std::uint64_t cycle;std::uint8_t value;};
 std::vector<TimedPsgWrite> psg_timeline;
 bool audio_timeline_complete=true;
 bool write_wav(const std::string& path)const; // approximate SMS PSG, not reference parity
 // Bounded, ordered *candidate* hardware effects; not an independent oracle.
 struct Event { std::uint64_t step; std::uint16_t pc; std::string kind; unsigned address, value; };
 static constexpr std::size_t EVENT_LIMIT=4096;
 std::vector<Event> events;
 std::uint64_t events_total=0;
 // Lossless candidate event stream within explicit disk limits. The inline vector
 // is only a preview. A recording failure halts execution, never silently drops.
 static constexpr std::uint64_t EVENT_STREAM_LIMIT=500000;
 static constexpr std::size_t EVENT_STREAM_BYTE_LIMIT=64u*1024u*1024u;
 static constexpr std::uint64_t EVENTS_PER_CHUNK=1024;
 std::ofstream event_stream;
 std::string event_stream_prefix;
 std::uint64_t event_stream_events=0,event_stream_bytes=0,event_stream_chunks=0;
 bool event_stream_enabled=false,event_stream_complete=true;
 void enable_event_stream(const std::string &prefix);
 void finish_event_stream();
 void record_event(const char *kind,unsigned address,unsigned value,bool after_instruction=false);
 std::array<std::uint64_t,256> port_writes{};
 std::uint16_t pc=0;
 std::string stopped;
 State();
 std::uint32_t rom_offset(std::uint16_t address)const;
 bool initial_mapping(std::uint16_t address)const;
 std::uint8_t read_byte(std::uint16_t address)const;
 void write_byte(std::uint16_t address,std::uint8_t value);
 u64 memory(std::uint16_t address,unsigned size)const;
 void write_memory(std::uint16_t address,unsigned size,u64 value);
 u64 get_register(unsigned offset,unsigned size)const;
 void set_register(unsigned offset,unsigned size,u64 value);
 u64 get_unique(unsigned offset,unsigned size)const;
 void set_unique(unsigned offset,unsigned size,u64 value);
 std::uint8_t in(std::uint16_t port);
 void out(std::uint16_t port,std::uint8_t value);
 void decimal_adjust_accumulator();
 void advance_cycles(unsigned tstates_used);
 bool service_pending_interrupt();
 void pulse_nmi();
 bool service_pending_console_nmi(); // deliver Pause/Start edge at a guest-instruction boundary
 void on_ei(){iff1=iff2=true;ei_delay=2;}
 void on_di(){iff1=iff2=false;ei_delay=0;}
 void end_instruction(){if(ei_delay>0)--ei_delay;}
 unsigned scanline()const{return unsigned((tstates/TSTATES_PER_SCANLINE)%NTSC_SCANLINES);}
 void dump_vdp(const std::string &prefix)const;
 void write_ppm(const std::string &path)const;
};
}
