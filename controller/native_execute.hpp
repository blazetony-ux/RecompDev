#pragma once
#include <filesystem>
#include <string>
#include <vector>
int rd_native_execute(const std::vector<std::string>& args,const std::filesystem::path& exe_path);
