#pragma once
// SMS-specific adapter to the generic opaque machine-state module ABI.
// The machine owns all timing, registers, mapper and hardware state. This file
// is intentionally not included from the controller or generic module loader.
#include <cstdint>
#include <filesystem>
#include <string>
namespace rd { struct State; }
namespace recomp::sms::dynamic {
inline constexpr const char* cpu_id="z80:LE:16:default";
inline constexpr const char* cpu_semantics="z80.native.codegen.v1";
inline constexpr const char* machine_id="sega-master-system";
inline constexpr const char* state_abi="rd.sms.native.state.cpp.v1";
#if defined(_MSC_VER) && defined(_M_X64)
inline constexpr const char* target_abi="msvc-x64-cpp17-v1";
#elif defined(__linux__) && defined(__x86_64__)
inline constexpr const char* target_abi="linux-gnu-x64-cpp17-v1";
#else
inline constexpr const char* target_abi="unsupported-native-target";
#endif
// This adapter does not analyse or compile code. It accepts only a verified
// module produced by the trusted analysis/translation provider.
void activate(const std::filesystem::path& module, const std::string& rom_sha256, std::uint64_t rom_size);
std::size_t active_modules();
}
