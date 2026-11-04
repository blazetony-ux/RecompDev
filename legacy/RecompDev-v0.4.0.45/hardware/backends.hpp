#pragma once
// CPU-, console- and OS-neutral host backend selection. Null sinks consume
// guest-produced presentation without disabling guest video/PSG/timing devices.
#include "runtime.hpp"
#include "input_replay.hpp"
#include <stdexcept>
#include <string>

namespace recomp::hw {
enum class VideoBackend { Null, Capture, Window };
enum class AudioBackend { Null, Capture, Speaker };
enum class InputBackend { Neutral, Replay, Live };
inline VideoBackend video_backend(const std::string& name) {
 if(name=="null")return VideoBackend::Null;
 if(name=="capture")return VideoBackend::Capture;
 if(name=="window")return VideoBackend::Window;
 throw std::invalid_argument("INVALID_VIDEO_BACKEND");
}
inline AudioBackend audio_backend(const std::string& name) {
 if(name=="null")return AudioBackend::Null;
 if(name=="capture")return AudioBackend::Capture;
 if(name=="speaker")return AudioBackend::Speaker;
 throw std::invalid_argument("INVALID_AUDIO_BACKEND");
}
inline InputBackend input_backend(const std::string& name) {
 if(name=="neutral")return InputBackend::Neutral;
 if(name=="replay")return InputBackend::Replay;
 if(name=="live")return InputBackend::Live;
 throw std::invalid_argument("INVALID_INPUT_BACKEND");
}
class NullVideoSink final : public FrameSink {
 u64 frames_=0;
 public:
 void submit(const Frame& frame)override {
  frame.validate();
  if(frames_>=36000)throw std::length_error("NULL_FRAME_COUNT_LIMIT");
  ++frames_;
 }
 u64 frames()const{return frames_;}
};
class NullAudioSink final : public AudioSink {
 u64 samples_=0;
 public:
 void submit(const PcmBlock& block)override {
  block.validate();
  if(block.samples.size()>6000000||samples_>6000000-block.samples.size())
   throw std::length_error("NULL_AUDIO_SAMPLE_LIMIT");
  samples_+=block.samples.size();
 }
 u64 samples()const{return samples_;}
};
// Input sources contain only portable button/axis states. Machine input
// adapters remain responsible for active-low polarity and port semantics.
class NeutralInputSource {
 InputState state_;
 public:
 explicit NeutralInputSource(u32 port=0):state_{port,0,0,0}{}
 void install(Runtime& runtime)const{runtime.record_input(0,state_);}
};
class ReplayInputSource {
 InputTimeline replay_;
 public:
 explicit ReplayInputSource(InputTimeline timeline):replay_(std::move(timeline)){}
 void install(Runtime& runtime)const{
  NeutralInputSource{}.install(runtime);
  replay_.visit([&](u64 cycle,InputState state){runtime.record_input(cycle,state);});
 }
};
} // namespace recomp::hw
