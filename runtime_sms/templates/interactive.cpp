// Source-attested generated Z80 executable with interchangeable CPU-neutral
// presentation backends. Null outputs never replace guest VDP/PSG/controller
// devices: those devices remain in the translated CPU execution path.
#include "live_sms.hpp"
#include "hardware/backends.hpp"
#include "hardware/wav.hpp"
#include "hardware/image_io.hpp"
#include "rd_runtime_host.h"
#if defined(RD_SMS_HOT_TRANSLATION)
#include "rd_sms_dynamic_adapter.hpp"
#include "rd_live_recovery.hpp"
#endif
#include <filesystem>
#include "rd_sha256.hpp"
#include <algorithm>
#include <chrono>
#include <fstream>
#include <iostream>
#include <sstream>
#include <iomanip>
#include <iterator>
#include <memory>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace hw=recomp::hw;
class OutputFrames final:public hw::FrameSink {
 public:hw::Frame last;std::vector<hw::u64> hashes;
 std::chrono::steady_clock::time_point playback_start=std::chrono::steady_clock::now();
 RD_Host* window=nullptr;
 std::string snapshot_prefix;
 std::size_t snapshot_every=0,snapshots_written=0;

 void submit(const hw::Frame& f)override {
  f.validate();if(hashes.size()>=36000)throw std::length_error("FRAME_CAPTURE_LIMIT");
  hashes.push_back(hw::frame_fingerprint(f));last=f;
  if(snapshot_every && hashes.size()%snapshot_every==0 && snapshots_written<128){
   std::ostringstream name;name<<snapshot_prefix<<"-snapshot-"<<std::setw(6)<<std::setfill('0')<<hashes.size()<<".ppm";
   if(!hw::write_rgb_ppm(name.str(),f))throw std::runtime_error("FRAME_SNAPSHOT_WRITE_FAILED");
   ++snapshots_written;
  }
  if(window){
   const auto deadline=playback_start+std::chrono::microseconds((hashes.size()*1000000ull)/60);
   if(deadline>std::chrono::steady_clock::now())std::this_thread::sleep_until(deadline);
   if(rd_host_present(window,f.pixels.data(),f.width,f.height,RD_HOST_PIXELS_BGRA8888)!=0)
    throw std::runtime_error("RUNTIME_HOST_PRESENT_FAILED");
  }
 }
};
class OutputAudio final:public hw::AudioSink {
 public:hw::PcmBlock pcm;RD_Host* speaker=nullptr;
 void submit(const hw::PcmBlock& b)override {
  b.validate();if(!pcm.sample_rate){pcm.sample_rate=b.sample_rate;pcm.channels=b.channels;}
  if(pcm.sample_rate!=b.sample_rate||pcm.channels!=b.channels)throw std::invalid_argument("AUDIO_FORMAT_MISMATCH");
  if(b.samples.size()>6000000||pcm.samples.size()>6000000-b.samples.size())throw std::length_error("PCM_CAPTURE_LIMIT");
  pcm.samples.insert(pcm.samples.end(),b.samples.begin(),b.samples.end());
  if(speaker && rd_host_pcm(speaker,b.samples.data(),b.samples.size(),b.sample_rate,b.channels)!=0)
   throw std::runtime_error("RUNTIME_HOST_PCM_FAILED");
 }
};
static hw::u64 parse(const char* arg,hw::u64 max){
 const std::string text(arg);if(text.empty()||text.find_first_not_of("0123456789")!=std::string::npos)
  throw std::invalid_argument("INVALID_DECIMAL_ARGUMENT");
 const auto n=std::stoull(text);if(!n||n>max)throw std::invalid_argument("LIMIT_OUT_OF_RANGE");return n;
}
struct Options {
 std::string video="capture",audio="capture",input="neutral",input_events,live_control,preload_module;
 bool input_explicit=false,mode_headless=false,diagnose_events=false,hold_window=false;
 std::size_t snapshot_every=0;
 unsigned live_max_recoveries=128,live_wait_seconds=900;
 std::vector<std::uint16_t> ram_watches;
};
static Options options(int argc,char**argv){
 Options out;bool input_file_seen=false,video_explicit=false,audio_explicit=false;
 for(int i=5;i<argc;++i){const std::string a=argv[i];
  if(a=="--hold-window"){out.hold_window=true;
  }else if(a=="--snapshot-every"){
   if(++i>=argc)throw std::invalid_argument("SNAPSHOT_INTERVAL_MISSING");
   const std::string raw=argv[i];
   if(raw.empty()||raw.find_first_not_of("0123456789")!=std::string::npos)
    throw std::invalid_argument("SNAPSHOT_INTERVAL_INVALID");
   const auto value=std::stoull(raw);
   if(value<1||value>600)throw std::invalid_argument("SNAPSHOT_INTERVAL_INVALID");
   out.snapshot_every=std::size_t(value);
  }else if(a=="--live-control"){
   if(++i>=argc)throw std::invalid_argument("LIVE_CONTROL_PATH_MISSING");
   out.live_control=argv[i];
  }else if(a=="--preload-module"){
   if(++i>=argc)throw std::invalid_argument("PRELOAD_MODULE_PATH_MISSING");
   out.preload_module=argv[i];
  }else if(a=="--live-max-recoveries"){
   if(++i>=argc)throw std::invalid_argument("LIVE_RECOVERY_LIMIT_MISSING");
   out.live_max_recoveries=unsigned(parse(argv[i],512));
  }else if(a=="--live-wait-seconds"){
   if(++i>=argc)throw std::invalid_argument("LIVE_WAIT_LIMIT_MISSING");
   out.live_wait_seconds=unsigned(parse(argv[i],7200));
  }else if(a=="--diagnose-events"){out.diagnose_events=true;
  }else if(a=="--watch-ram"){
   if(++i>=argc)throw std::invalid_argument("RAM_WATCH_ADDRESS_MISSING");
   const std::string raw=argv[i];std::size_t end=0;
   const auto n=std::stoul(raw,&end,0);
   if(end!=raw.size() || n<0xc000 || n>0xffff || out.ram_watches.size()>=8)
    throw std::invalid_argument("RAM_WATCH_ADDRESS_INVALID");
   out.ram_watches.push_back(static_cast<std::uint16_t>(n));
  }else if(a=="--mode"){
   if(++i>=argc)throw std::invalid_argument("MODE_VALUE_MISSING");
   const std::string mode=argv[i];
   if(mode!="HEADLESS_AUTONOMOUS"&&mode!="headless-autonomous")throw std::invalid_argument("INVALID_HOST_MODE");
   out.mode_headless=true;
  }else if(a=="--window"){
   out.video="window";out.audio="speaker";out.input="live";out.input_explicit=true;video_explicit=true;audio_explicit=true;
  }else if(a=="--video"||a=="--audio"||a=="--input"||a=="--input-events"){
   if(++i>=argc)throw std::invalid_argument("HOST_BACKEND_VALUE_MISSING");
   if(a=="--video"){out.video=argv[i];video_explicit=true;}
   if(a=="--audio"){out.audio=argv[i];audio_explicit=true;}
   if(a=="--input"){out.input=argv[i];out.input_explicit=true;}
   if(a=="--input-events"){out.input_events=argv[i];input_file_seen=true;}
  }else if(i==5 && !a.empty() && a[0]!='-'){
   out.input_events=a;input_file_seen=true; // legacy positional replay filename
  }else if(i==5&&a=="-"){}  // legacy positional neutral controller
  else throw std::invalid_argument("UNKNOWN_HOST_ARGUMENT");
 }
 // Defaults are resolved only after parsing: flag order must never allow
 // a physical device through an autonomous/headless policy.
 if(!out.ram_watches.empty() && !out.diagnose_events)
  throw std::invalid_argument("RAM_WATCH_REQUIRES_DIAGNOSE_EVENTS");
 if(out.snapshot_every && out.video=="null")throw std::invalid_argument("SNAPSHOT_REQUIRES_VISIBLE_FRAMES");
 if(out.hold_window && out.video!="window")throw std::invalid_argument("HOLD_WINDOW_REQUIRES_WINDOW_BACKEND");
 if(!out.live_control.empty() && out.mode_headless)
  throw std::invalid_argument("LIVE_RECOVERY_CANNOT_BE_HEADLESS");
 if(out.mode_headless){
  if(!video_explicit)out.video="null";
  if(!audio_explicit)out.audio="null";
  if(!out.input_explicit)out.input="neutral";
 }
 // Source replay is an input backend, never a guest-hardware replacement.
 if(input_file_seen&&!out.input_explicit)out.input="replay";
 const auto video=hw::video_backend(out.video);
 const auto audio=hw::audio_backend(out.audio);
 const auto input=hw::input_backend(out.input);
 if(out.mode_headless && (video==hw::VideoBackend::Window ||
                           audio==hw::AudioBackend::Speaker ||
                           input==hw::InputBackend::Live))
  throw std::invalid_argument("AUTONOMOUS_MODE_REQUIRES_NO_PHYSICAL_DEVICES");
 if(input==hw::InputBackend::Replay&&out.input_events.empty())throw std::invalid_argument("INPUT_REPLAY_FILE_REQUIRED");
 if(input!=hw::InputBackend::Replay&&!out.input_events.empty())throw std::invalid_argument("INPUT_REPLAY_BACKEND_REQUIRED");
 if(input==hw::InputBackend::Live&&video!=hw::VideoBackend::Window)throw std::invalid_argument("LIVE_INPUT_REQUIRES_WINDOW");
 if(!out.live_control.empty() && !((input==hw::InputBackend::Live&&video==hw::VideoBackend::Window)||
                               (input==hw::InputBackend::Neutral&&video==hw::VideoBackend::Capture)))
  throw std::invalid_argument("LIVE_RECOVERY_REQUIRES_LIVE_INPUT_WINDOW_NO_HOLD");
#if !defined(RD_SMS_HOT_TRANSLATION)
 if(!out.live_control.empty())throw std::invalid_argument("LIVE_RECOVERY_REQUIRES_DYNAMIC_TRANSLATION");
#endif
 return out;
}
int main(int argc,char**argv){
 if(argc<5){std::cerr<<"Usage: RecompDevNativeApp <local-rom> <output-prefix> <frames> <steps> [legacy replay.csv or -] [--window] [--mode HEADLESS_AUTONOMOUS] [--video null|capture|window] [--audio null|capture|speaker] [--input neutral|replay|live] [--input-events file] [--hold-window] [--live-control DIR] [--live-max-recoveries N] [--diagnose-events] [--watch-ram 0xC001]\n";return 2;}
 try{
  const Options config=options(argc,argv);
  std::ifstream f(argv[1],std::ios::binary|std::ios::ate);
  if(!f||f.tellg()<0||f.tellg()>64*1024*1024)throw std::runtime_error("OWNER_ROM_MISSING_OR_TOO_LARGE");
  f.seekg(0);std::vector<std::uint8_t> rom(std::istreambuf_iterator<char>{f},{});
  if(rd_sms_native_runtime_abi()!=0x00010000u || rd_sms_mode4_abi()!=RD_SMS_MODE4_ABI)
   throw std::runtime_error("NATIVE_MACHINE_VIDEO_ABI_MISMATCH");
#if defined(RD_SMS_HOT_TRANSLATION)
  // Load a source-bound native *shared module* into this persistent app.
  // No CPU or ROM translation happens inside the presentation host.
  const auto module=std::filesystem::absolute(std::filesystem::path(argv[0])).parent_path()/
#if defined(_WIN32)
   "rd_generated_translation_hot.dll";
#else
   "rd_generated_translation_hot.so";
#endif
  recomp::sms::dynamic::activate(module,rdhash::sha256(rom.data(),rom.size()),rom.size());
  if(!config.preload_module.empty()){
   if(config.live_control.empty())throw std::runtime_error("PRELOAD_REQUIRES_LIVE_CONTROLLER");
   const auto preloaded=std::filesystem::canonical(std::filesystem::u8path(config.preload_module));
   if(preloaded.parent_path()!=std::filesystem::canonical(std::filesystem::u8path(config.live_control)/"modules"/"preload"))
    throw std::runtime_error("PRELOAD_MODULE_OUTSIDE_SESSION");
   recomp::sms::dynamic::activate(preloaded,rdhash::sha256(rom.data(),rom.size()),rom.size());
  }
#endif
  recomp::guest::SmsNativeMachine guest;guest.load_rom(rom);
  for(auto a:config.ram_watches)guest.state().add_watch(a);
  if(config.diagnose_events)guest.state().enable_event_stream(std::string(argv[2])+"-events");
  const auto video=hw::video_backend(config.video);
  const auto audio=hw::audio_backend(config.audio);
  const auto input=hw::input_backend(config.input);
  auto captured_frames=std::make_shared<OutputFrames>();
  captured_frames->snapshot_every=config.snapshot_every;
  captured_frames->snapshot_prefix=argv[2];
  auto captured_audio=std::make_shared<OutputAudio>();
  auto null_frames=std::make_shared<hw::NullVideoSink>();
  auto null_audio=std::make_shared<hw::NullAudioSink>();
  hw::Runtime runtime(3579545,60,44100);
  runtime.video(guest,video==hw::VideoBackend::Null?std::static_pointer_cast<hw::FrameSink>(null_frames):std::static_pointer_cast<hw::FrameSink>(captured_frames));
  runtime.audio(guest,audio==hw::AudioBackend::Null?std::static_pointer_cast<hw::AudioSink>(null_audio):std::static_pointer_cast<hw::AudioSink>(captured_audio));
  runtime.input(guest);
  std::unique_ptr<RD_Host,decltype(&rd_host_destroy)> view(nullptr,&rd_host_destroy);
  std::unique_ptr<RD_Host,decltype(&rd_host_destroy)> speaker(nullptr,&rd_host_destroy);
  if(rd_host_abi_version()!=RD_HOST_ABI_VERSION)
   throw std::runtime_error("RUNTIME_HOST_ABI_MISMATCH");
  if(video==hw::VideoBackend::Window){
   RD_Host* handle=nullptr;
   if(rd_host_create(RD_HOST_MODE_WINDOW,"RecompDev - Native game",44100,&handle)!=0)
    throw std::runtime_error("HOST_WINDOW_UNAVAILABLE");
   view.reset(handle);captured_frames->window=view.get();
  }
  if(audio==hw::AudioBackend::Speaker){
   RD_Host* handle=nullptr;
   if(rd_host_create(RD_HOST_MODE_SPEAKER,"RecompDev audio",44100,&handle)!=0)
    throw std::runtime_error("HOST_AUDIO_DEVICE_UNAVAILABLE_USE_NULL_AUDIO");
   speaker.reset(handle);captured_audio->speaker=speaker.get();
  }
  if(input==hw::InputBackend::Replay){
   hw::ReplayInputSource(hw::load_input_replay(config.input_events)).install(runtime);
  }else hw::NeutralInputSource{}.install(runtime);
  hw::ContinuousSession session(guest,runtime);
  hw::RunLimits limits;limits.max_frames=parse(argv[3],36000);
  limits.max_steps=parse(argv[4],20000000);limits.max_guest_cycles=1000000000ull;limits.wall_seconds=60;
  std::ofstream telemetry;
  std::uint64_t last_reported_frame=0,total_native_steps=0;
  unsigned hot_activations=0;
  std::uint64_t pending_resume_buttons=0,pending_resume_until_frame=0;
  const auto source_sha=rdhash::sha256(rom.data(),rom.size());
  std::filesystem::path control;
  if(!config.live_control.empty()){
   control=std::filesystem::canonical(std::filesystem::u8path(config.live_control));
   if(!std::filesystem::is_directory(control)||std::filesystem::is_symlink(control)||
      !std::filesystem::is_directory(control/"modules"))
    throw std::runtime_error("LIVE_RECOVERY_SESSION_DIRECTORY_INVALID");
   telemetry.open(control/"telemetry.jsonl",std::ios::binary|std::ios::app);
   if(!telemetry)throw std::runtime_error("LIVE_MONITOR_EVENT_STREAM_UNAVAILABLE");
  }
  auto notice=[&](const std::string& status){
#if defined(RD_SMS_HOT_TRANSLATION)
   if(telemetry){telemetry<<"{\"type\":\"session\",\"status\":"<<rdjson::escape(status)<<"}\n";
    telemetry.flush();}
#else
   (void)status; // Historical standalone preview has no recovery transport.
#endif
  };
  auto observe=[&](){
   if(!telemetry)return;
   const auto pc=guest.state().pc;
   const auto physical=pc<0xc000?guest.state().rom_offset(pc):0;
   telemetry<<"{\"type\":\"instruction\",\"cpu\":\"Z80\",\"pc\":"<<pc
    <<",\"physical_offset\":"<<physical<<",\"sp\":"<<guest.state().get_register(68,2)
    <<",\"steps\":"<<guest.state().steps<<",\"guest_cycles\":"<<runtime.cycles()
    <<",\"opcode_class\":\"SAMPLED_NEXT_PC\"}\n";
   if(runtime.frames()!=last_reported_frame){
    last_reported_frame=runtime.frames();
    telemetry<<"{\"type\":\"frame\",\"frame\":"<<runtime.frames()
     <<",\"guest_cycles\":"<<runtime.cycles()<<",\"steps\":"<<guest.state().steps<<"}\n";
   }
   telemetry.flush();
  };
  notice("NATIVE_GAME_STARTED");
  hw::RunResult result;
  while(true){
   hw::RunLimits remaining=limits;
   if(total_native_steps>=limits.max_steps){result.status="STEP_BUDGET_REACHED";break;}
   remaining.max_steps-=total_native_steps;
   result=session.run(remaining,[&](hw::u64,hw::u64){
    if(video==hw::VideoBackend::Window){if(!view || rd_host_pump(view.get())<=0)return false;}
    if(input==hw::InputBackend::Live){
     auto buttons=rd_host_buttons(view.get());
     if(pending_resume_buttons && runtime.frames()<pending_resume_until_frame)
      buttons|=pending_resume_buttons;
     else pending_resume_buttons=0;
     runtime.record_input(runtime.cycles(),{0,buttons,0,0});
     // Normal live samples are not replayed after a recovery; only edges
     // pumped while the guest was paused are latched and replayed.
     (void)rd_host_take_pressed(view.get());
    }
    if(audio==hw::AudioBackend::Speaker)if(speaker)rd_host_pump(speaker.get());
    observe();return true;
   });
   total_native_steps+=result.executed;
   observe();
#if defined(RD_SMS_HOT_TRANSLATION)
   if(control.empty() || (result.status!="UNTRANSLATED_INITIAL_CODE" &&
       result.status!="BANKED_CODE_NOT_TRANSLATED"))break;
   if(hot_activations>=config.live_max_recoveries){result.status="LIVE_RECOVERY_LIMIT_REACHED";break;}
   const auto frozen=guest.guest_fingerprint();
   const auto pc=guest.state().pc;
   const auto physical=guest.state().rom_offset(pc);
   std::ostringstream seed;
   seed<<"{\"schema\":\"recompdev.native.app.stop.v1\",\"status\":"<<rdjson::escape(result.status)
       <<",\"source_sha256\":"<<rdjson::escape(source_sha)
       <<",\"rom_bytes\":"<<rom.size()
       <<",\"pc\":"<<pc<<",\"physical_offset\":"<<physical
       <<",\"sp\":"<<guest.state().get_register(68,2)
       <<",\"native_steps\":"<<guest.state().steps
       <<",\"guest_frames\":"<<runtime.frames()
       <<",\"guest_state_fingerprint\":\""<<std::hex<<frozen<<std::dec<<"\""
       <<",\"mapper\":["<<unsigned(guest.state().mapper[0])<<","<<unsigned(guest.state().mapper[1])
       <<","<<unsigned(guest.state().mapper[2])<<","<<unsigned(guest.state().mapper[3])<<"]}";
   notice("RECOVERY_REQUESTED");
   if(view)rd_host_title(view.get(),"RecompDev - translating missing native code (session paused)");
   const auto module=recomp::native::live::await_module(control,hot_activations+1,seed.str(),source_sha,[&]{
    return !view || rd_host_pump(view.get())>0;
   },config.live_wait_seconds);
   if(input==hw::InputBackend::Live && view){
    const auto pressed=rd_host_take_pressed(view.get());
    if(pressed){pending_resume_buttons|=pressed;
     pending_resume_until_frame=runtime.frames()+2;}
   }
   if(frozen!=guest.guest_fingerprint())throw std::runtime_error("LIVE_RECOVERY_GUEST_STATE_CHANGED_DURING_COMPILE");
   recomp::sms::dynamic::activate(module,source_sha,rom.size());
   if(!guest.resume_after_native_activation())throw std::runtime_error("LIVE_RECOVERY_RESUME_REJECTED");
   if(frozen!=guest.guest_fingerprint())throw std::runtime_error("LIVE_RECOVERY_GUEST_STATE_CHANGED_DURING_ACTIVATION");
   ++hot_activations;
   // Durable activation receipt: controller must NOT cache a candidate merely
   // because it sent READY. ABI, checksum and guest-state checks passed above.
   std::ostringstream receipt;
   receipt<<"{\"schema\":\"recompdev.native.live.activation.v1\",\"sequence\":"<<hot_activations
    <<",\"source_sha256\":"<<rdjson::escape(source_sha)
    <<",\"request_sha256\":"<<rdjson::escape(recomp::native::sha256_binary(
       control/("request-"+recomp::native::live::request_id(hot_activations)+".json")))
    <<",\"module_sha256\":"<<rdjson::escape(recomp::native::sha256_binary(module))
    <<",\"guest_state_fingerprint\":\""<<std::hex<<frozen<<std::dec<<"\"}";
   recomp::native::live::atomic_new(control/("activation-"+
    recomp::native::live::request_id(hot_activations)+".json"),receipt.str());
   notice("NATIVE_MODULE_ACTIVATED_RESUMING");
   if(view)rd_host_title(view.get(),"RecompDev - Native game");
#else
   break;
#endif
  }
  result.executed=total_native_steps;
  result.cycles=runtime.cycles();result.frames=runtime.frames();
  notice(result.status);
  if(config.diagnose_events){guest.state().finish_event_stream();
    if(!guest.state().event_stream_complete)throw std::runtime_error("EVENT_STREAM_INCOMPLETE");}
  // Presentation only: guest execution and reported state have already stopped.
  // Hold the last guest-produced frame for inspection, until Esc/close or a
  // bounded 300-second guard. This cannot advance the guest or fake graphics.
  if(config.hold_window){
   rd_host_title(view.get(),"RecompDev - Native capture complete (Esc to close)");
   const auto until=std::chrono::steady_clock::now()+std::chrono::seconds(300);
   while(std::chrono::steady_clock::now()<until && view && rd_host_pump(view.get())>0)
    std::this_thread::sleep_for(std::chrono::milliseconds(30));
  }
  const std::string prefix=argv[2];
  if(video!=hw::VideoBackend::Null&&!captured_frames->last.pixels.empty()&&
     !hw::write_rgb_ppm(prefix+".ppm",captured_frames->last))throw std::runtime_error("FRAME_WRITE_FAILED");
  if(audio!=hw::AudioBackend::Null&&!captured_audio->pcm.samples.empty()&&
     !hw::write_pcm16_wav(prefix+".wav",captured_audio->pcm))throw std::runtime_error("AUDIO_WRITE_FAILED");
  const auto frames_discarded=null_frames->frames();
  const auto samples_discarded=null_audio->samples();
  std::cout<<"NATIVE_APP_RESULT={\"schema\":\"recomp-continuous-native-v2\",\"status\":\""<<result.status
   <<"\",\"native_steps\":"<<result.executed<<",\"guest_cycles\":"<<result.cycles
   <<",\"frames\":"<<result.frames<<",\"guest_frames\":"<<guest.state().frames<<",\"frame_hashes\":[";
  for(std::size_t i=0;i<captured_frames->hashes.size();++i){if(i)std::cout<<",";std::cout<<captured_frames->hashes[i];}
  std::cout<<"],\"snapshot_every\":"<<config.snapshot_every
   <<",\"snapshots_written\":"<<captured_frames->snapshots_written
   <<",\"audio_nonzero_samples\":"<<std::count_if(captured_audio->pcm.samples.begin(),captured_audio->pcm.samples.end(),[](auto x){return x!=0;})
   <<",\"audio_samples\":"<<captured_audio->pcm.samples.size()+samples_discarded
   <<",\"discarded_frames\":"<<frames_discarded
   <<",\"discarded_audio_samples\":"<<samples_discarded
   <<",\"pc\":"<<guest.state().pc
   <<",\"physical_offset\":"<<(guest.state().pc<0xc000?guest.state().rom_offset(guest.state().pc):0)
   <<",\"sp\":"<<guest.state().get_register(68,2)<<",\"rom_bytes\":"<<rom.size()
   <<",\"mapper\":["<<unsigned(guest.state().mapper[0])<<","<<unsigned(guest.state().mapper[1])
   <<","<<unsigned(guest.state().mapper[2])<<","<<unsigned(guest.state().mapper[3])<<"]"
   <<",\"cram_writes\":"<<guest.state().cram_writes
   <<",\"cram_nonzero_bytes\":"<<std::count_if(guest.state().cram.begin(),guest.state().cram.end(),[](auto x){return x!=0;})
   <<",\"vblank_events\":"<<guest.state().vblank_events
   <<",\"maskable_interrupts\":"<<guest.state().maskable_interrupts
   <<",\"nmi_events\":"<<guest.state().nmi_events
   <<",\"bank_switches\":"<<guest.state().bank_switches
   <<",\"hot_activations\":"<<hot_activations
   <<",\"guest_state_fingerprint\":"<<guest.guest_fingerprint()
   <<",\"guest_vdp_writes\":"<<guest.state().vdp_control_writes+guest.state().vdp_data_writes
   <<",\"guest_psg_writes\":"<<guest.state().psg_writes
   <<",\"timing_qualified_steps\":"<<guest.state().qualified_timing_instructions
   <<",\"timing_unqualified_steps\":"<<guest.state().unqualified_timing_instructions
   <<",\"vcounter_reads\":"<<guest.state().vcounter_reads
   <<",\"first_vcounter_read_step\":"<<guest.state().first_vcounter_read_step
   <<",\"frame_hardware\":";guest.write_frame_hardware_json(std::cout);std::cout
   <<",\"trace_tail\":";guest.write_trace_json(std::cout);std::cout
   <<",\"hcounter_reads\":"<<guest.state().hcounter_reads
   <<",\"video_backend\":\""<<config.video<<"\",\"audio_backend\":\""<<config.audio
   <<"\",\"input_backend\":\""<<config.input
   <<"\",\"native_qualified\":false,\"hardware_parity\":\"NOT_TESTED\"}\n";
  return 0;
 }catch(const std::exception& e){std::cerr<<"NATIVE_APP_ERROR="<<e.what()<<"\n";return 3;}
}
