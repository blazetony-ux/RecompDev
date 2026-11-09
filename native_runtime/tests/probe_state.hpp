#pragma once
// Synthetic-only machine fixture. Production modules only see void*.
#include <cstdint>
struct ProbeState {
 std::uint32_t pc=0, bank=1;
 std::uint64_t cycles=0, frames=0, input=0;
 std::uint8_t ram[32]{};
};
