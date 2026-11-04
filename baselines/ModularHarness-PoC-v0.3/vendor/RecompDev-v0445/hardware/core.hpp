#pragma once
// RecompDev v0.4.0.22 universal device contracts. No CPU, game, console,
// resolution, operating-system or frontend assumptions in this file.
#include <algorithm>
#include <cstdint>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
namespace recomp::hw {
using u8=std::uint8_t;using u32=std::uint32_t;using u64=std::uint64_t;
constexpr u32 ContractVersion=1;
enum class Space : u8 { Memory=0, IO=1 };
struct IoAddress { Space space;u32 address; };
enum class PixelFormat : u8 { BGRA8888=1 };
struct Frame {
 u32 width=0,height=0;PixelFormat format=PixelFormat::BGRA8888;
 u64 source_cycle=0,ordinal=0;std::vector<u32> pixels;
 void validate()const{
  if(!width||!height||width>4096||height>4096||u64(width)*height!=pixels.size())
   throw std::invalid_argument("INVALID_FRAME_CONTRACT");
 }
};
// Portable deterministic content hash, for testing only; not a cryptographic attestation.
inline u64 frame_fingerprint(const Frame& f){
 f.validate();u64 h=14695981039346656037ull;
 auto add=[&](u8 b){h=(h^b)*1099511628211ull;};
 for(unsigned i=0;i<4;++i){add(u8(f.width>>(8*i)));add(u8(f.height>>(8*i)));}
 for(auto px:f.pixels)for(unsigned i=0;i<4;++i)add(u8(px>>(8*i)));
 return h;
}
struct PcmBlock {
 u32 sample_rate=0,channels=0;u64 first_cycle=0;
 std::vector<std::int16_t> samples; // interleaved signed PCM
 void validate()const{
  if(sample_rate<8000||sample_rate>192000||!channels||channels>8||samples.size()%channels)
   throw std::invalid_argument("INVALID_PCM_CONTRACT");
 }
};
struct InputState { u32 port=0;u64 buttons=0;std::int16_t axis_x=0,axis_y=0; };
namespace button {
 constexpr u64 Up=1ull<<0,Down=1ull<<1,Left=1ull<<2,Right=1ull<<3;
 constexpr u64 A=1ull<<4,B=1ull<<5,C=1ull<<6,Start=1ull<<7,Select=1ull<<8;
}
class FrameSink {public:virtual ~FrameSink()=default;virtual void submit(const Frame& f)=0;};
class AudioSink {public:virtual ~AudioSink()=default;virtual void submit(const PcmBlock& b)=0;};
class HeadlessFrames final: public FrameSink {
 public:std::vector<u64> fingerprints;u32 last_width=0,last_height=0;
 void submit(const Frame& f)override{if(fingerprints.size()>=200000)throw std::length_error("HEADLESS_FRAME_LIMIT");fingerprints.push_back(frame_fingerprint(f));last_width=f.width;last_height=f.height;}
};
class HeadlessAudio final: public AudioSink {
 public:u64 total_samples=0;u64 checksum=14695981039346656037ull;
 void submit(const PcmBlock& b)override{
  b.validate();total_samples+=b.samples.size();
  for(auto x:b.samples){auto v=std::uint16_t(x);checksum=(checksum^u8(v))*1099511628211ull;checksum=(checksum^u8(v>>8))*1099511628211ull;}
 }
};
// Every device advertises its actual mapped address space/range. No catch-all
// machine-specific map is baked into the bus. Ambiguous overlaps fail closed.
class Device {
 public:virtual ~Device()=default;
 virtual const char* name()const=0;
 virtual bool maps(IoAddress a)const=0;
 virtual u8 read(IoAddress a)=0;
 virtual void write(IoAddress a,u8 value)=0;
 virtual void advance(u64 cpu_cycles)=0;
};
class Rack {
 std::vector<std::shared_ptr<Device>> devices_;
 u64 cycle_=0;
 public:
 u64 cycle()const{return cycle_;}
 void attach(std::shared_ptr<Device> d){if(!d)throw std::invalid_argument("NULL_DEVICE");
  if(devices_.size()>=64)throw std::length_error("DEVICE_RACK_LIMIT");
  for(auto &old:devices_)if(old.get()==d.get())throw std::invalid_argument("DUPLICATE_DEVICE");
  devices_.push_back(std::move(d));}
 Device* find(IoAddress a)const{
  Device* found=nullptr;
  for(auto &d:devices_)if(d->maps(a)){
   if(found)throw std::runtime_error("AMBIGUOUS_DEVICE_MAPPING");
   found=d.get();
  }
  return found;
 }
 u8 read(IoAddress a){auto *d=find(a);return d?d->read(a):0xff;}
 bool write(IoAddress a,u8 v){auto *d=find(a);if(!d)return false;d->write(a,v);return true;}
 void advance(u64 cycles){
  if(cycles>std::numeric_limits<u64>::max()-cycle_)throw std::overflow_error("CYCLE_OVERFLOW");
  // No scheduler-owned timing approximation: device is explicitly told guest CPU cycles.
  for(auto &d:devices_)d->advance(cycles);
  cycle_+=cycles;
 }
};
// Exact integer-ratio accumulation: no floating-point timing drift.
class RateClock {
 u64 units_=0,rate_,clock_;
 public:
 RateClock(u64 events_per_second,u64 cpu_clocks_per_second):rate_(events_per_second),clock_(cpu_clocks_per_second){
  if(!rate_||!clock_)throw std::invalid_argument("BAD_CLOCK_RATIO");}
 u64 until_next()const{const u64 remaining=clock_-units_;return remaining/rate_+(remaining%rate_?1:0);}
 u64 consume(u64 cycles){
  if(cycles>(std::numeric_limits<u64>::max()-units_)/rate_)throw std::overflow_error("RATE_ACCUMULATOR_OVERFLOW");
  units_+=cycles*rate_;auto n=units_/clock_;units_%=clock_;return n;
 }
};
// Input timeline injects host events at deterministic guest-cycle boundaries.
class InputTimeline {
 struct Timed {u64 cycle;InputState state;};
 std::vector<Timed> entries_;std::size_t cursor_=0;u64 last_cycle_=0;
 public:
 void append(u64 cycle,InputState state){
  if(cycle<last_cycle_)throw std::invalid_argument("INPUT_EVENT_IN_PAST");
  if(!entries_.empty()&&cycle<entries_.back().cycle)throw std::invalid_argument("INPUT_NOT_MONOTONIC");
  if(entries_.size()>=100000)throw std::length_error("INPUT_EVENT_LIMIT");
  entries_.push_back({cycle,state});
 }
 u64 next_cycle()const{return cursor_<entries_.size()?entries_[cursor_].cycle:std::numeric_limits<u64>::max();}
 template<class Fn>void visit(Fn&& fn)const{for(const auto& e:entries_)fn(e.cycle,e.state);}
 template<class Fn>void replay_until(u64 cycle,Fn&& fn){
  if(cycle<last_cycle_)throw std::invalid_argument("INPUT_TIME_REWIND");
  while(cursor_<entries_.size()&&entries_[cursor_].cycle<=cycle){auto &e=entries_[cursor_++];fn(e.state);}last_cycle_=cycle;
 }
};
} // namespace recomp::hw
