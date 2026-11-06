// Controller-owned integration of the already verified native P-code runtime.
// Unlike legacy prepare/recover this route never launches Python or a harness
// process; the shared compiled runner loads CPU, SMS, game and sink DLLs.
#include "native_execute.hpp"
#include "rd_harness_runner.hpp"
#include <algorithm>
#include <filesystem>
#include <regex>
#include <stdexcept>
#include <string>
#include <vector>
namespace fs=std::filesystem;
int rd_native_execute(const std::vector<std::string>& args,const fs::path& exe_path){
 fs::path plugin_dir=exe_path.parent_path();
 if(fs::is_directory(plugin_dir/"active"))plugin_dir/="active";
 fs::path rom,out;
 std::string game;
 std::vector<std::string> runner;
 bool native_only=true;
 for(size_t i=0;i<args.size();++i){
  auto next=[&]()->std::string{if(++i>=args.size())throw std::runtime_error("MISSING_ARGUMENT "+args[i-1]);return args[i];};
  const auto&a=args[i];
  if(a=="--stage"){
   if(next()!="native-execute")throw std::runtime_error("UNEXPECTED_NATIVE_EXECUTION_STAGE");
  }else if(a=="--rom"){rom=fs::u8path(next());runner.insert(runner.end(),{"--rom",rom.u8string()});}
  else if(a=="--game"){
   game=next();if(!std::regex_match(game,std::regex("rd_[a-zA-Z0-9_]+")))throw std::runtime_error("INVALID_GAME_PLUGIN_NAME");
   runner.insert(runner.end(),{"--game",game});
  }else if(a=="--plugin-dir")plugin_dir=fs::u8path(next());
  else if(a=="--out"){out=fs::u8path(next());runner.insert(runner.end(),{"--out",out.u8string()});}
  else if(a=="--steps"||a=="--entry"||a=="--buttons"){
   auto value=next();runner.push_back(a);runner.push_back(value);
  }else if(a=="--validate")runner.push_back("--validate");
  else if(a=="--allow-fallback")native_only=false;
  else throw std::runtime_error("UNKNOWN_NATIVE_EXECUTE_OPTION "+a);
 }
 if(rom.empty()||!fs::is_regular_file(rom))throw std::runtime_error("SOURCE_REQUIRED_OR_NOT_FOUND");
 if(game.empty())throw std::runtime_error("AUTHENTICATED_GAME_DLL_REQUIRED (use --game rd_...)");
 if(out.empty())throw std::runtime_error("OUTPUT_REQUIRED_FOR_NATIVE_EXECUTION");
 if(fs::exists(fs::path(out.string()+".report.json")))throw std::runtime_error("EVIDENCE_EXISTS_REFUSING_OVERWRITE");
 // Preserve the harness' full-source identity check before executing any
 // precompiled instruction. The game DLL MUST expose source hash and size.
 runner.insert(runner.begin(),{"--case","rom","--plugin-dir",fs::absolute(plugin_dir).u8string()});
 if(native_only)runner.push_back("--no-fallback");
 std::vector<std::string> argv{"RecompDevNativeRunner"};argv.insert(argv.end(),runner.begin(),runner.end());
 std::vector<char*> raw;raw.reserve(argv.size()+1);
 for(auto &a:argv)raw.push_back(a.data());
 raw.push_back(nullptr);
 return rd_harness_run(int(argv.size()),raw.data());
}
