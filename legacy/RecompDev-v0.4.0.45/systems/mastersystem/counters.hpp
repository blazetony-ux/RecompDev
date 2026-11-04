#pragma once
// Master System NTSC 192-line VDP counter decoding. Machine-specific adapter.
// Source: SMSPower Scanline Counter, NTSC 256x192 sequence 00-DA,D5-FF.
// This does NOT establish pixel-accurate H-counter phase or extended video modes.
#include <cstdint>
namespace recomp::sms {
inline constexpr std::uint8_t vcounter_ntsc_192(unsigned line){
 line%=262;
 return static_cast<std::uint8_t>(line<=0xda ? line : line-6);
}
inline constexpr std::uint8_t vcounter_pal_192(unsigned line){
 line%=313;
 return static_cast<std::uint8_t>(line<=0xf2 ? line : line-57);
}
// Experimental H-counter sample only when controller TH changes low-to-high;
// the CPU reads the held latch between TH transitions. No pixel-phase parity.
inline constexpr std::uint8_t approximate_latched_hcounter(std::uint64_t cycles){
 const unsigned dot=static_cast<unsigned>((cycles%228)*3/2); // 342 dots/scanline
 const unsigned h=(dot/2 + 0) & 0xff;
 return static_cast<std::uint8_t>(h);
}
}
