#include "GuestBridge.hpp"
// Tiny user-authored stand-in for a generated guest module. No original ROM
// bytes; this verifies the actual host to guest ABI, input and pixel transfer.
extern "C" int recomp_guest_tick(std::uint32_t input_bits,
    std::uint32_t* pixels, std::size_t pixel_count,
    std::int16_t* audio, std::size_t audio_count) {
    if (!pixels || !audio || pixel_count != 256u*192u || audio_count != 735u)
        return -1;
    std::uint32_t tint = (input_bits & 1u) ? 0x00ff0000u : 0x000000ffu;
    for (std::size_t i=0;i<pixel_count;++i)
        pixels[i]=0xff000000u | tint | (((i / 256u) & 0xffu) << 8u);
    for (std::size_t i=0;i<audio_count;++i) audio[i]=0;
    return 0;
}
