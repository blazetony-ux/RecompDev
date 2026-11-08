#pragma once
// Hardware/ISA-neutral parity evidence comparison contract. This tests the
// equality of supplied captures, NOT the independence of a reference emulator.
#include "rd_tiny_json.hpp"
#include <algorithm>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>
namespace rdparity {
constexpr const char* kSchema="recompdev.parity.capture.v1";
inline std::string required_string(const rdjson::V&v,const char*field){
 const auto&x=v.get(field);if(x.t!=rdjson::V::String||x.s.empty()||x.s.size()>256)
  throw std::runtime_error(std::string("PARITY_REQUIRED_")+field);return x.s;
}
inline bool lowercase_sha256(const std::string&s){
 if(s.size()!=64)return false;
 return std::all_of(s.begin(),s.end(),[](char c){return (c>='a'&&c<='f')||(c>='0'&&c<='9');});
}
struct Capture{
 std::string source,inputs,clock,role,provider,algorithm;
 std::vector<std::string> video;
 std::string audio,state;
 bool input_attested=false;
};
inline Capture load(const rdjson::V&v){
 if(v.t!=rdjson::V::Object||required_string(v,"schema")!=kSchema)throw std::runtime_error("PARITY_SCHEMA_INVALID");
 Capture c;c.source=required_string(v,"rom_sha256");if(!lowercase_sha256(c.source))throw std::runtime_error("PARITY_ROM_HASH_INVALID");
 c.role=required_string(v,"capture_role");
 if(c.role!="reference"&&c.role!="candidate")throw std::runtime_error("PARITY_ROLE_INVALID");
 c.clock=required_string(v,"clock_domain");if(c.clock!="host_output_frames")throw std::runtime_error("PARITY_CLOCK_DOMAIN_UNSUPPORTED");
 c.provider=required_string(v,"capture_provider");
 c.algorithm=required_string(v,"video_fingerprint_algorithm");
 if(v.get("input_sha256").t==rdjson::V::String){c.inputs=required_string(v,"input_sha256");
   if(!lowercase_sha256(c.inputs))throw std::runtime_error("PARITY_INPUT_HASH_INVALID");c.input_attested=true;}
 const auto&f=v.get("video_fingerprints");if(f.t!=rdjson::V::Array||f.a.empty()||f.a.size()>36000)
  throw std::runtime_error("PARITY_VIDEO_REQUIRED");
 for(const auto&x:f.a){
  if(x.t!=rdjson::V::String||x.s.size()!=16||!std::all_of(x.s.begin(),x.s.end(),[](char ch){return (ch>='0'&&ch<='9')||(ch>='a'&&ch<='f');}))
   throw std::runtime_error("PARITY_FRAME_FINGERPRINT_INVALID");
  c.video.push_back(x.s);
 }
 if(v.get("audio_sha256").t==rdjson::V::String){c.audio=required_string(v,"audio_sha256");if(!lowercase_sha256(c.audio))throw std::runtime_error("PARITY_AUDIO_HASH_INVALID");}
 if(v.get("state_sha256").t==rdjson::V::String){c.state=required_string(v,"state_sha256");if(!lowercase_sha256(c.state))throw std::runtime_error("PARITY_STATE_HASH_INVALID");}
 return c;
}
struct Result{std::string status,reason;std::size_t first_mismatch=0,compared_frames=0;bool full_inputs=false,full_audio=false,full_state=false;};
inline Result compare(const Capture&reference,const Capture&candidate){
 if(reference.role!="reference"||candidate.role!="candidate")throw std::runtime_error("PARITY_ROLES_MISORDERED");
 if(reference.source!=candidate.source)return {"REJECTED","ROM_IDENTITY_MISMATCH"};
 if(reference.clock!=candidate.clock)return {"REJECTED","CLOCK_DOMAIN_MISMATCH"};
 if(reference.algorithm!=candidate.algorithm)return {"REJECTED","FINGERPRINT_ALGORITHM_MISMATCH"};
 if(reference.provider==candidate.provider && reference.provider!="independent_external_reference"){
  // Same provider is not sufficient evidence of an independent hardware reference.
  // Still compare as a diagnostic without ever certifying parity.
 }
 Result r;r.compared_frames=std::min(reference.video.size(),candidate.video.size());
 r.full_inputs=reference.input_attested&&candidate.input_attested;
 if(r.full_inputs && reference.inputs!=candidate.inputs)return {"REJECTED","INPUT_REPLAY_IDENTITY_MISMATCH"};
 for(std::size_t i=0;i<r.compared_frames;++i)if(reference.video[i]!=candidate.video[i]){
  r.status="MISMATCH";r.reason="VIDEO_FRAME_FINGERPRINT_DIFFERENCE";r.first_mismatch=i+1;return r;
 }
 if(reference.video.size()!=candidate.video.size()){
  r.status="MISMATCH";r.reason="VIDEO_FRAME_COUNT_DIFFERENCE";r.first_mismatch=r.compared_frames+1;return r;
 }
 r.full_audio=!reference.audio.empty()&&!candidate.audio.empty();
 r.full_state=!reference.state.empty()&&!candidate.state.empty();
 if(r.full_audio&&reference.audio!=candidate.audio)return {"MISMATCH","AUDIO_SHA256_DIFFERENCE"};
 if(r.full_state&&reference.state!=candidate.state)return {"MISMATCH","STATE_SHA256_DIFFERENCE"};
 r.status="MATCHED_UNQUALIFIED";
 r.reason=(r.full_inputs&&r.full_audio&&r.full_state)?"REFERENCE_INDEPENDENCE_AND_HARDWARE_PARITY_UNATTESTED":"MISSING_INPUT_AUDIO_OR_STATE_EVIDENCE";
 return r;
}
}
