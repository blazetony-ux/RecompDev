#pragma once
// Controller-/host-owned lifetime for compatible native modules. Immutable once
// added; newer source-verified modules take priority, older blocks remain live.
#include "rd_native_block_v1.h"
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <memory>
#include <string>
#include <vector>
namespace recomp::native {
struct Identity {
 std::string cpu_id, cpu_semantics_version, machine_id, machine_state_abi;
 std::string target_abi, source_sha256;
 std::uint64_t source_size=0;
};
class ModuleSet {
 struct Entry;
 Identity id_;
 std::vector<std::unique_ptr<Entry>> entries_;
 public:
 explicit ModuleSet(Identity id);
 ~ModuleSet();
 ModuleSet(const ModuleSet&)=delete;
 ModuleSet& operator=(const ModuleSet&)=delete;
 // Require a SHA-256 of the exact binary supplied by the trusted build
 // pipeline. Reject altered/unreadable/unsupported DLLs without activation.
 void activate(const std::filesystem::path& file, const std::string& expected_binary_sha256);
 // 1 = executed, 0 = untranslated, negative = integrity failure. Caller must
 // not retry negative outcomes or permit module unload while a callback runs.
 int step(void *machine_state, std::uint32_t physical_offset) const;
 std::size_t module_count()const noexcept {return entries_.size();}
 const Identity& identity()const noexcept {return id_;}
};
std::string sha256_binary(const std::filesystem::path& path);
} // namespace recomp::native
