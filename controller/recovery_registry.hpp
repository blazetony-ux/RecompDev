#pragma once
#include <filesystem>
#include <optional>
#include <string>

// Persistent, CPU- and platform-neutral *history locator*. These are NOT
// executable-code cache entries, checkpoint images or trusted dispatch targets.
// Actual source/tool/provider/bank verification remains with recovery_history
// and the native translator, after the controller selects a candidate.
namespace rdregistry {
struct Hit {
    std::filesystem::path session;
    int emitted=0;
    int frames=0;
};
std::optional<Hit> find(const std::filesystem::path& evidence_root,
                        const std::string& rom_sha256);
void remember(const std::filesystem::path& evidence_root,
              const std::string& rom_sha256,
              const std::filesystem::path& session,
              const std::string& job_id, int cycle);
}
