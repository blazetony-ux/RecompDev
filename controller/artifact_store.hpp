#pragma once
// Universal, CPU/hardware-neutral, content-addressed immutable artifact service.
// Producers own semantics; this component owns content integrity, dependency records
// and relocatable storage. No executable bytes are loaded without plugin attestation.
#include <cstdint>
#include <filesystem>
#include <optional>
#include <string>
#include <vector>
namespace rdartifact {
struct Blob {
    std::string digest, kind, producer, target, abi;
    std::uint64_t bytes=0;
};
struct Capsule {
    std::filesystem::path session;
    std::string digest, architecture, platform;
    int emitted=0, frames=0;
};
// Generic producer entry point: opaque bytes, labels and explicit compatibility ABI.
Blob put(const std::filesystem::path& root, const std::string& kind,
         const std::string& producer, const std::string& target,
         const std::string& abi, const std::string& data);
std::string get(const std::filesystem::path& root, const Blob& blob);
// Transitional source-attested recovery adapter, not part of the generic CAS ABI.
// Returns nullopt when a legacy session lacks the complete portable inputs.
std::optional<std::string> promote(const std::filesystem::path& root,
    const std::filesystem::path& session, const std::string& source_sha256);
// Returns a verified independently materialised capsule, never a historical path.
std::optional<Capsule> best(const std::filesystem::path& root,
    const std::string& source_sha256);
}
