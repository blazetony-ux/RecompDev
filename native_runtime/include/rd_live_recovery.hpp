#pragma once
// CPU-neutral, fail-closed native recovery request/response transport.
// The controller is authoritative for analysis and compilation; the game
// process only reports an observed frontier and activates a verified module.
// No guest state is serialized/restored, so the same session remains alive.
#include "rd_tiny_json.hpp"
#include "rd_native_module_set.hpp"
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <functional>
#include <stdexcept>
#include <string>
#include <thread>
namespace recomp::native::live {
namespace fs = std::filesystem;
inline void atomic_new(const fs::path& file,const std::string& bytes){
 if(bytes.empty()||bytes.size()>8192||fs::exists(file))throw std::runtime_error("LIVE_RECOVERY_MESSAGE_INVALID_OR_REUSED");
 auto temp=file;temp+=".pending";
 if(fs::exists(temp))throw std::runtime_error("LIVE_RECOVERY_PENDING_FILE_EXISTS");
 {std::ofstream out(temp,std::ios::binary|std::ios::trunc);
  if(!out||!out.write(bytes.data(),std::streamsize(bytes.size()))||!(out.flush(),bool(out)))
   throw std::runtime_error("LIVE_RECOVERY_MESSAGE_WRITE_FAILED");}
 std::error_code ec;fs::rename(temp,file,ec);
 if(ec){fs::remove(temp);throw std::runtime_error("LIVE_RECOVERY_MESSAGE_COMMIT_FAILED");}
}
inline std::string read_bound(const fs::path& file){
 if(!fs::is_regular_file(file)||fs::is_symlink(file)||fs::file_size(file)>8192)
  throw std::runtime_error("LIVE_RECOVERY_RESPONSE_UNSAFE");
 std::ifstream in(file,std::ios::binary);
 if(!in)throw std::runtime_error("LIVE_RECOVERY_RESPONSE_UNREADABLE");
 return std::string(std::istreambuf_iterator<char>(in),{});
}
inline std::string request_id(unsigned n){
 if(!n||n>512)throw std::runtime_error("LIVE_RECOVERY_SEQUENCE_OUT_OF_RANGE");
 auto s=std::to_string(n);return std::string(4-s.size(),'0')+s;
}
inline fs::path await_module(const fs::path& root,unsigned sequence,
  const std::string& request,const std::string& rom_sha,
  const std::function<bool()>& pump,unsigned timeout_seconds=900){
 if(!fs::is_directory(root)||fs::is_symlink(root)||timeout_seconds<1||timeout_seconds>7200)
  throw std::runtime_error("LIVE_RECOVERY_CONTROL_ROOT_INVALID");
 const auto id=request_id(sequence);
 const auto request_path=root/("request-"+id+".json");
 const auto response_path=root/("response-"+id+".json");
 atomic_new(request_path,request);
 const auto expected=recomp::native::sha256_binary(request_path);
 const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(timeout_seconds);
 while(std::chrono::steady_clock::now()<deadline){
  if(!pump())throw std::runtime_error("LIVE_RECOVERY_USER_CLOSED_WINDOW");
  if(fs::exists(response_path)){
   auto response=rdjson::Reader(read_bound(response_path)).parse();
   if(response.get("schema").string()!="recompdev.native.live.response.v1"||
      response.get("request_sha256").string()!=expected||
      response.get("source_sha256").string()!=rom_sha)
    throw std::runtime_error("LIVE_RECOVERY_RESPONSE_IDENTITY_MISMATCH");
   if(response.get("status").string()!="READY")
    throw std::runtime_error("LIVE_RECOVERY_CONTROLLER_BLOCKED");
   const auto module=fs::u8path(response.get("module").string());
   if(!module.is_absolute()||!fs::is_regular_file(module)||fs::is_symlink(module))
    throw std::runtime_error("LIVE_RECOVERY_MODULE_PATH_INVALID");
   auto allowed=fs::weakly_canonical(root/"modules");
   auto trusted=fs::weakly_canonical(module);
   auto it=trusted.begin(),end=trusted.end(),limit=allowed.begin();
   for(;limit!=allowed.end();++limit,++it)if(it==end||*it!=*limit)
    throw std::runtime_error("LIVE_RECOVERY_MODULE_PATH_OUTSIDE_SESSION");
   if(response.get("module_sha256").string()!=recomp::native::sha256_binary(trusted))
    throw std::runtime_error("LIVE_RECOVERY_MODULE_DIGEST_MISMATCH");
   return trusted;
  }
  std::this_thread::sleep_for(std::chrono::milliseconds(35));
 }
 throw std::runtime_error("LIVE_RECOVERY_CONTROLLER_TIMEOUT");
}
}
