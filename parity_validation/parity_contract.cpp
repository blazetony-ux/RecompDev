#include "capture_compare.hpp"
#include <iostream>
#include <stdexcept>
static void yes(bool x){if(!x)throw std::runtime_error("PARITY_CONTRACT_FAIL");}
static rdparity::Capture c(const std::string&role,const std::string&frames,const std::string&audio=""){
 std::string raw="{\"schema\":\"recompdev.parity.capture.v1\",\"capture_role\":\""+role+"\",\"rom_sha256\":\""+std::string(64,'a')+
 "\",\"clock_domain\":\"host_output_frames\",\"capture_provider\":\""+role+"\",\"video_fingerprint_algorithm\":\"recomp.hw.frame_fingerprint.v1\",\"video_fingerprints\":["+frames+"]";
 if(!audio.empty())raw+=",\"audio_sha256\":\""+audio+"\"";
 raw+='}';return rdparity::load(rdjson::Reader(raw).parse());
}
int main(){
 auto a=c("reference","\"0000000000000001\",\"0000000000000002\"");
 auto b=c("candidate","\"0000000000000001\",\"0000000000000002\"");
 auto r=rdparity::compare(a,b);
 yes(r.status=="MATCHED_UNQUALIFIED"&&r.compared_frames==2&&!r.full_audio);
 b.video[1]="0000000000000003";r=rdparity::compare(a,b);yes(r.status=="MISMATCH"&&r.first_mismatch==2);
 b.video=a.video;b.source=std::string(64,'b');r=rdparity::compare(a,b);yes(r.status=="REJECTED");
 b.source=a.source;b.inputs=std::string(64,'c');b.input_attested=true;
 a.inputs=std::string(64,'d');a.input_attested=true;r=rdparity::compare(a,b);yes(r.reason=="INPUT_REPLAY_IDENTITY_MISMATCH");
 std::cout<<"PASS: native parity data contract requires source/input identity and compares first mismatch without qualification\n";
}
