#pragma once
#include "core.hpp"
#include <fstream>
namespace recomp::hw {
inline bool write_pcm16_wav(const std::string& path,const PcmBlock& audio){
 audio.validate();
 if(audio.samples.size()>15000000||audio.samples.size()>std::numeric_limits<u32>::max()/2-64)
  throw std::length_error("AUDIO_WAV_LIMIT");
 std::ofstream f(path,std::ios::binary|std::ios::trunc);if(!f)return false;
 auto w16=[&](u32 v){f.put(char(v&255));f.put(char((v>>8)&255));};
 auto w32=[&](u32 v){w16(v);w16(v>>16);};
 const u32 bytes=u32(audio.samples.size()*2),byte_rate=audio.sample_rate*audio.channels*2;
 f.write("RIFF",4);w32(36+bytes);f.write("WAVEfmt ",8);w32(16);
 w16(1);w16(audio.channels);w32(audio.sample_rate);w32(byte_rate);w16(audio.channels*2);w16(16);
 f.write("data",4);w32(bytes);
 for(auto value:audio.samples)w16(std::uint16_t(value));
 f.flush();return f.good();
}
} // namespace recomp::hw
