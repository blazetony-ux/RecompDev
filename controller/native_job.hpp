#pragma once
#include <filesystem>
#include <functional>
#include <string>
#include <vector>
// Native controller owns job admission, persistence, safety bounds and multi-batch
// scheduling. The provided bridge is the temporary, explicitly versioned Python
// analysis provider for ONE bounded batch, not a Python job-manager wrapper.
int rd_native_job(const std::vector<std::string>& args,
                  const std::filesystem::path& source,
                  const std::filesystem::path& exe,
                  const std::function<int(const std::vector<std::string>&)>& bridge);
