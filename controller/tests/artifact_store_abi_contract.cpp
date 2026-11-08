#include "artifact_store_abi.h"
#include <filesystem>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
namespace fs=std::filesystem;
static void expect(bool x,const char*why){if(!x)throw std::runtime_error(why);}
int main(){
 auto root=fs::temp_directory_path()/"recompdev-artifact-abi-025";fs::remove_all(root);
 try{
  auto api=rd_artifact_store_api_v1();expect(api&&api->abi_version==1&&api->struct_size==sizeof(RD_ArtifactStoreAPIv1),"ABI mismatch");
  std::string content="\x00\x01\x02";content.assign("binary\0\xFFpayload",15);
  char digest[65]{};
  expect(api->put(root.string().c_str(),"native-code","cpu.mips","host.arm64","elf.aarch64.v1",
         reinterpret_cast<const uint8_t*>(content.data()),content.size(),digest,sizeof(digest))==1,"ABI put failed");
  expect(std::strlen(digest)==64,"digest not returned");
  std::uint64_t size=0;
  expect(api->get(root.string().c_str(),"native-code","cpu.mips","host.arm64","elf.aarch64.v1",digest,nullptr,&size)==-1&&size==content.size(),"size discovery failed");
  std::vector<uint8_t> data(size);std::uint64_t cap=size;
  expect(api->get(root.string().c_str(),"native-code","cpu.mips","host.arm64","elf.aarch64.v1",digest,data.data(),&cap)==1,"ABI get failed");
  expect(std::string(reinterpret_cast<const char*>(data.data()),cap)==content,"payload changed");
  expect(api->get(root.string().c_str(),"native-code","cpu.z80","host.arm64","elf.aarch64.v1",digest,data.data(),&cap)==0,"producer identity not verified");
  fs::remove_all(root);std::cout<<"PASS: native artifact-store C ABI, opaque payload and target identity\n";return 0;
 }catch(const std::exception&e){std::cerr<<"FAIL: "<<e.what()<<"\n";fs::remove_all(root);return 1;}
}
