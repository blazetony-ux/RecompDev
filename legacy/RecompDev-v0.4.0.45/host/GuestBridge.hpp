#pragma once
#include <cstddef>
#include <cstdint>
// Stable host-side API for a guest runtime adapter. Pixels are BGRA32 (host
// little-endian DWORD), 256x192; audio is signed 16-bit mono, 735 samples.
// Return 0 only when the frame and audio arrays have been fully produced.
// This does NOT imply guest CPU, VDP, PSG, or gameplay parity.
extern "C" int recomp_guest_tick(std::uint32_t input_bits,
    std::uint32_t* pixels, std::size_t pixel_count,
    std::int16_t* audio, std::size_t audio_count);
