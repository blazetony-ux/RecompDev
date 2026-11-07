#pragma once
#include "core.hpp"
namespace recomp::hw {
// The host owns the sink; machine adapters own the video, audio and controller
// devices. The CPU-architecture-agnostic runtime only transports time and data.
class VideoSource {public:virtual ~VideoSource()=default;virtual Frame render()const=0;};
class AudioSource {public:virtual ~AudioSource()=default;virtual std::int16_t sample(u64 source_cycle)=0;};
class InputTarget {public:virtual ~InputTarget()=default;virtual void set_input(InputState)=0;};
class Runtime {
 Rack bus_;
 std::shared_ptr<FrameSink> frames_;
 std::shared_ptr<AudioSink> audio_;
 VideoSource* video_=nullptr;AudioSource* sound_=nullptr;InputTarget* input_=nullptr;
 u64 clock_hz_,cpu_cycle_=0,frames_total_=0;
 RateClock frame_clock_,audio_clock_;
 u32 sample_rate_;
 InputTimeline timeline_;
 public:
 Runtime(u64 cpu_clock_hz,u32 refresh_hz,u32 audio_sample_rate):
  clock_hz_(cpu_clock_hz),frame_clock_(refresh_hz,cpu_clock_hz),audio_clock_(audio_sample_rate,cpu_clock_hz),sample_rate_(audio_sample_rate){}
 Rack& bus(){return bus_;}
 void video(VideoSource& src,std::shared_ptr<FrameSink> sink){if(!sink)throw std::invalid_argument("FRAME_SINK_MISSING");video_=&src;frames_=std::move(sink);}
 void audio(AudioSource& src,std::shared_ptr<AudioSink> sink){if(!sink)throw std::invalid_argument("AUDIO_SINK_MISSING");sound_=&src;audio_=std::move(sink);}
 void input(InputTarget& dst){input_=&dst;}
 void record_input(u64 at_cycle,InputState state){timeline_.append(at_cycle,state);}
 u64 cycles()const{return cpu_cycle_;}
 void deliver_inputs_now(){timeline_.replay_until(cpu_cycle_,[&](InputState s){if(input_)input_->set_input(s);});}
 u64 frames()const{return frames_total_;}
 void advance(u64 cycles){
  if(cycles>1000000000ull||cycles>std::numeric_limits<u64>::max()-cpu_cycle_)
   throw std::invalid_argument("EXCESSIVE_CYCLE_STEP");
  // Count the outputs before mutating any device; failed bounded captures
  // must not leave a half-advanced guest runtime.
  auto preview_audio=audio_clock_,preview_frames=frame_clock_;
  if(preview_audio.consume(cycles)>2000000ull||preview_frames.consume(cycles)>200000ull)
   throw std::length_error("HOST_OUTPUT_BUDGET_EXCEEDED");
  const u64 target=cpu_cycle_+cycles;
  PcmBlock audio_batch;audio_batch.sample_rate=sample_rate_;audio_batch.channels=1;
  bool has_first_sample=false;
  while(cpu_cycle_<target){
   timeline_.replay_until(cpu_cycle_,[&](InputState s){if(input_)input_->set_input(s);});
   u64 tick=std::min({target-cpu_cycle_,frame_clock_.until_next(),audio_clock_.until_next()});
   const u64 next_input=timeline_.next_cycle();
   if(next_input>cpu_cycle_&&next_input!=std::numeric_limits<u64>::max())
    tick=std::min(tick,next_input-cpu_cycle_);
   if(!tick)throw std::logic_error("SCHEDULER_ZERO_TICK");
   bus_.advance(tick);cpu_cycle_+=tick;
   const u64 samples=audio_clock_.consume(tick);
   if(samples&&sound_&&audio_){
    if(!has_first_sample){audio_batch.first_cycle=cpu_cycle_;has_first_sample=true;}
    for(u64 i=0;i<samples;++i)audio_batch.samples.push_back(sound_->sample(cpu_cycle_));
   }
   const u64 produced_frames=frame_clock_.consume(tick);
   for(u64 i=0;i<produced_frames;++i){++frames_total_;
    if(video_&&frames_){Frame f=video_->render();f.ordinal=frames_total_;f.source_cycle=cpu_cycle_;frames_->submit(f);}
   }
  }
  timeline_.replay_until(cpu_cycle_,[&](InputState s){if(input_)input_->set_input(s);});
  if(!audio_batch.samples.empty())audio_->submit(audio_batch);
 }

};
} // namespace recomp::hw
